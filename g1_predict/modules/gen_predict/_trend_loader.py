"""傾向計算に必要なデータをDBから一括取得するモジュール。"""

from typing import Any

import pandas as pd
from mykeibadb import MasterGetter, RaceGetter

from g1_predict.modules.gen_table.table_utils import DIRT_TRACK_CODES, SHIBA_TRACK_CODES, year_range

from ._constants import TRACK_CODE_TO_SHIBA_DA
from ._trend_models import SIRE_YEARS, TREND_YEARS, Db, sire_cache_key


def load_db(
    race_code: str,
    race_info: pd.DataFrame,
    race_year: int,
    sire_sources: list[dict[str, Any]],
) -> Db:
    """傾向計算に必要なデータを一括取得して Db を返す。

    過去レースの結果・払戻・出走馬履歴・競走馬マスタ・父馬勝利セットを
    バッチ取得しキャッシュにまとめる。

    Args:
        race_code (str): 対象レースの16桁レースコード。
        race_info (pd.DataFrame): 対象レースの基本情報DataFrame（raw英語カラム名）。
        race_year (int): 開催年。
        sire_sources (list[dict[str, Any]]): sire_race_condition_finisher の source 設定リスト。

    Returns:
        Db: 取得データをまとめたインスタンス。
    """
    keibajo_code = str(race_info["keibajo_code"].iloc[0]).strip()
    kyori = int(race_info["kyori"].iloc[0])
    track_code = str(race_info["track_code"].iloc[0]).strip()
    shiba_da = TRACK_CODE_TO_SHIBA_DA.get(track_code, "")
    tokubetsu_kyoso_bango = str(race_info["tokubetsu_kyoso_bango"].iloc[0]).strip().zfill(4)
    track_codes = SHIBA_TRACK_CODES if shiba_da == "芝" else DIRT_TRACK_CODES

    rg = RaceGetter()
    mg = MasterGetter()

    past_race_codes, matched_years = _find_past_races(
        race_code, tokubetsu_kyoso_bango, race_year, keibajo_code, kyori, track_codes, rg
    )

    results: dict[str, pd.DataFrame] = {}
    payoffs: dict[str, pd.Series | None] = {}
    for rc in past_race_codes:
        result_df = rg.get_umagoto_race_joho(race_code=rc, convert_codes=False)
        results[rc] = result_df
        payoff_df = rg.get_haraimodoshi(race_code=rc, convert_codes=False)
        payoffs[rc] = payoff_df.iloc[0] if not payoff_df.empty else None

    all_horse_ids: list[str] = []
    seen: set[str] = set()
    for result_df in results.values():
        if result_df.empty or "ketto_toroku_bango" not in result_df.columns:
            continue
        for v in result_df["ketto_toroku_bango"].dropna():
            hid = str(v).strip()
            if hid and hid not in seen:
                seen.add(hid)
                all_horse_ids.append(hid)

    history = pd.DataFrame()
    shosai: dict[str, dict[str, str]] = {}
    if all_horse_ids:
        history = rg.get_umagoto_race_joho(
            ketto_toroku_bango=all_horse_ids, convert_codes=False
        )
        if not history.empty and "race_code" in history.columns:
            h_race_codes = (
                history["race_code"].dropna().astype(str).str.strip().unique().tolist()
            )
            if h_race_codes:
                shosai_df = rg.get_race_shosai(race_code=h_race_codes, convert_codes=False)
                for _, row in shosai_df.iterrows():
                    rc = str(row.get("race_code", "")).strip()
                    if rc:
                        shosai[rc] = {
                            "grade_code": str(row.get("grade_code", "")).strip(),
                            "kyosomei_hondai": str(row.get("kyosomei_hondai", "")).strip(),
                            "keibajo_code": str(row.get("keibajo_code", "")).strip(),
                        }

    kyosoba: dict[str, pd.Series] = {}
    if all_horse_ids:
        kyosoba_df = mg.get_kyosoba_master2(
            ketto_toroku_bango=all_horse_ids, convert_codes=False
        )
        if not kyosoba_df.empty and "ketto_toroku_bango" in kyosoba_df.columns:
            for _, row in kyosoba_df.iterrows():
                hid = str(row.get("ketto_toroku_bango", "")).strip()
                if hid:
                    kyosoba[hid] = row

    sire_finisher_sets: dict[tuple[Any, ...], set[str]] = {}
    for src in sire_sources:
        key = sire_cache_key(src)
        if key not in sire_finisher_sets:
            sire_finisher_sets[key] = _get_condition_winners(race_year, src, rg)

    return Db(
        past_race_codes=past_race_codes,
        results=results,
        payoffs=payoffs,
        history=history,
        shosai=shosai,
        kyosoba=kyosoba,
        sire_finisher_sets=sire_finisher_sets,
        matched_years=matched_years,
    )


def extract_sire_condition_sources(
    trends_config: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """trends_config 内の sire_race_condition_finisher source を重複なく収集する。

    boolean_multi 型の rows を持つ metric から type が
    sire_race_condition_finisher の source を抽出する。
    同一条件の source は重複して返さない。

    Args:
        trends_config (dict[str, list[dict[str, Any]]]): YAMLのtrends設定。

    Returns:
        list[dict[str, Any]]: sire_race_condition_finisher の source dict のリスト（重複なし）。
    """
    seen: set[tuple[Any, ...]] = set()
    sources: list[dict[str, Any]] = []
    for metrics in trends_config.values():
        for metric_cfg in metrics:
            rows_cfg = metric_cfg.get("rows", {})
            if rows_cfg.get("type") != "boolean_multi":
                continue
            for item in rows_cfg.get("items", []):
                src = item.get("source", {})
                if src.get("type") == "sire_race_condition_finisher":
                    key = sire_cache_key(src)
                    if key not in seen:
                        seen.add(key)
                        sources.append(src)
    return sources


def _is_valid_race_code(code: str) -> bool:
    """レースコードが get_umagoto_race_joho に渡せる形式か判定する。

    RACE_SHOSAI には無効なプレースホルダーコードが含まれる場合があるため、
    呼び出し前に事前フィルタするために使用する。

    Args:
        code (str): 判定するレースコード文字列。

    Returns:
        bool: 形式が正常な場合 True。
    """
    if len(code) != 16:
        return False
    month_str = code[4:6]
    if not month_str.isdigit() or not (1 <= int(month_str) <= 12):
        return False
    day_str = code[6:8]
    if not day_str.isdigit() or not (1 <= int(day_str) <= 31):
        return False
    if not code[10:12].isdigit() or not code[12:14].isdigit():
        return False
    race_str = code[14:16]
    if not race_str.isdigit() or not (1 <= int(race_str) <= 12):
        return False
    return True


def _find_past_races(
    current_race_code: str,
    tokubetsu_kyoso_bango: str,
    race_year: int,
    keibajo_code: str,
    kyori: int,
    track_codes: frozenset[str],
    rg: RaceGetter,
) -> tuple[list[str], int]:
    """同一特別競走・同コースの過去レースコード一覧と一致年数を返す。

    過去 TREND_YEARS 年の RACE_SHOSAI から特別競走番号・競馬場・馬場・距離が
    一致するレースを抽出する。現在のレースは除外する。

    Args:
        current_race_code (str): 除外する対象レースのレースコード。
        tokubetsu_kyoso_bango (str): 特別競走番号（例: "0008"）。
        race_year (int): 対象レースの開催年。
        keibajo_code (str): 競馬場コード（例: "05"）。
        kyori (int): 距離（メートル）。
        track_codes (frozenset[str]): 馬場種別コードのセット（芝またはダート）。
        rg (RaceGetter): RaceGetter インスタンス。

    Returns:
        list[str]: 過去レースコードのリスト（昇順）。
        int: 一致年数。
    """
    start_dt, end_dt = year_range(race_year - 1, TREND_YEARS)
    raw = rg.get_race_shosai(start_date=start_dt, end_date=end_dt, convert_codes=False)
    if raw.empty:
        return [], 0

    tokubetsu_mask = (
        raw["tokubetsu_kyoso_bango"].astype(str).str.strip() == tokubetsu_kyoso_bango
    ) & (
        raw["race_code"].astype(str).str.strip() != current_race_code
    )
    same_race = raw[tokubetsu_mask]
    if same_race.empty:
        return [], 0

    venue_mask = same_race["keibajo_code"].astype(str).str.strip() == keibajo_code
    track_mask = same_race["track_code"].astype(str).str.strip().isin(track_codes)
    kyori_mask = pd.to_numeric(same_race["kyori"], errors="coerce") == kyori

    filtered = same_race[venue_mask & track_mask & kyori_mask]
    past_codes = filtered["race_code"].astype(str).str.strip().tolist()
    return sorted(past_codes), len(past_codes)


def _get_condition_winners(
    race_year: int,
    source: dict[str, Any],
    rg: RaceGetter,
) -> set[str]:
    """指定条件のレースで1着になった馬名セットを返す。

    source で指定可能なフィルタ:
        race_name (str): 競走名本題でフィルタ。
        grade_codes (list[str]): グレードコードでフィルタ（例: ["A", "B"]）。
        kyori (int): 距離でフィルタ（メートル）。
        years (int): 遡る年数（デフォルト: SIRE_YEARS）。
        top_n (int): 何着以内を対象とするか（デフォルト: 1）。

    Args:
        race_year (int): 対象レースの開催年（検索範囲の基点）。
        source (dict[str, Any]): フィルタ条件を定義した source 設定dict。
        rg (RaceGetter): RaceGetter インスタンス。

    Returns:
        set[str]: 条件に一致するレースで1着になった馬の馬名セット。
    """
    years = int(source.get("years", SIRE_YEARS))
    start_dt, end_dt = year_range(race_year - 1, years)
    raw = rg.get_race_shosai(start_date=start_dt, end_date=end_dt, convert_codes=False)
    if raw.empty:
        return set()

    mask = pd.Series(True, index=raw.index)
    if "race_name" in source:
        mask &= raw["kyosomei_hondai"].astype(str).str.strip() == str(source["race_name"])
    if "grade_codes" in source:
        mask &= raw["grade_code"].astype(str).str.strip().isin(source["grade_codes"])
    if "kyori" in source:
        mask &= pd.to_numeric(raw["kyori"], errors="coerce") == int(source["kyori"])

    codes = [c for c in raw[mask]["race_code"].tolist() if _is_valid_race_code(str(c))]
    if not codes:
        return set()

    umagoto = rg.get_umagoto_race_joho(race_code=codes, convert_codes=False)
    if umagoto.empty or "kakutei_chakujun" not in umagoto.columns:
        return set()

    top_n = int(source.get("top_n", 1))
    chakujun = pd.to_numeric(umagoto["kakutei_chakujun"], errors="coerce")
    winner_mask = (chakujun >= 1) & (chakujun <= top_n)
    return set(umagoto[winner_mask]["bamei"].dropna().astype(str).str.strip().tolist())
