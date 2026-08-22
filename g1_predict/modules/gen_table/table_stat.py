"""テーブル生成用の統計計算関数群。"""

from typing import Any

import pandas as pd

from g1_predict.modules.gen_table.table_data_cache import TableDataCache
from g1_predict.modules.gen_table.table_utils import (
    aggregate_stat,
    filter_by_horse,
    is_na,
    stat_result,
    to_cell_value,
)


def waku_stat(horse_id: str, source: dict[str, Any], cache: TableDataCache) -> Any:
    """枠番の統計値を計算する。

    Args:
        horse_id (str): 血統登録番号。
        source (dict[str, Any]): YAMLのsource設定（keibajo_code/track/kyori/years/stat等）。
        cache (TableDataCache): データキャッシュ。

    Returns:
        Any: int（"wins"/"top3"）またはfloat（"win_rate"/"top3_rate"）。データがない場合はNone。
    """
    keibajo_code = str(source["keibajo_code"])
    track = source["track"]
    kyori = int(source["kyori"])
    years = int(source["years"])
    stat = source["stat"]
    course_kubun: str | None = source.get("course_kubun")
    week: int | None = source.get("week")

    umagoto_df = cache.get_umagoto_df()
    if umagoto_df.empty:
        return None
    horse_rows = filter_by_horse(umagoto_df, horse_id)
    if horse_rows.empty or "wakuban" not in horse_rows.columns:
        return None
    wakuban_raw = horse_rows.iloc[0]["wakuban"]
    if is_na(wakuban_raw):
        return None
    wakuban = int(wakuban_raw)

    hist_df = cache.get_course_umagoto_df(keibajo_code, track, kyori, years, course_kubun, week)
    if hist_df.empty or "wakuban" not in hist_df.columns:
        return None

    hist_df = hist_df.copy()
    hist_df["_wakuban"] = pd.to_numeric(hist_df["wakuban"], errors="coerce")
    waku_df = hist_df[hist_df["_wakuban"] == wakuban]
    total = hist_df["race_code"].nunique()
    kakutei = pd.to_numeric(
        waku_df.get("kakutei_chakujun", pd.Series(dtype="float64")), errors="coerce"
    )
    wins = int((kakutei == 1).sum())
    top3 = int(((kakutei >= 1) & (kakutei <= 3)).sum())
    return stat_result(stat, wins, top3, total)


def kishu_course_stat(horse_id: str, source: dict[str, Any], cache: TableDataCache) -> Any:
    """騎手のコース成績統計を計算する。

    Args:
        horse_id (str): 血統登録番号。
        source (dict[str, Any]): YAMLのsource設定（keibajo_code/track/kyori/years/stat等）。
        cache (TableDataCache): データキャッシュ。

    Returns:
        Any: int（"wins"/"top3"）またはfloat（"win_rate"/"top3_rate"）。
            データがない場合は0系統計またはNone。
    """
    keibajo_code = str(source["keibajo_code"])
    track = source["track"]
    kyori = int(source["kyori"])
    years = int(source["years"])
    stat = source["stat"]

    umagoto_df = cache.get_umagoto_df()
    if umagoto_df.empty:
        return None
    horse_rows = filter_by_horse(umagoto_df, horse_id)
    if horse_rows.empty or "kishu_code" not in horse_rows.columns:
        return None
    kishu_code_raw = horse_rows.iloc[0]["kishu_code"]
    if is_na(kishu_code_raw):
        return None
    kishu_code = str(kishu_code_raw).strip()

    hist_df = cache.get_course_umagoto_df(keibajo_code, track, kyori, years)
    if hist_df.empty or "kishu_code" not in hist_df.columns:
        return stat_result(stat, 0, 0, 0)

    kishu_df = hist_df[hist_df["kishu_code"].astype(str).str.strip() == kishu_code]
    return aggregate_stat(kishu_df, stat)


def seisansha_race_stat(
    horse_id: str, source: dict[str, Any], race_name: str, cache: TableDataCache
) -> Any:
    """生産者の特定レース成績統計を計算する。

    Args:
        horse_id (str): 血統登録番号。
        source (dict[str, Any]): YAMLのsource設定（race_name_for_history/years/stat等）。
        race_name (str): デフォルトのレース名（race_name_for_history未指定時に使用）。
        cache (TableDataCache): データキャッシュ。

    Returns:
        Any: int（"wins"/"top3"）またはfloat（"win_rate"/"top3_rate"）。データがない場合は0系統計。
    """
    race_name_for_history = source.get("race_name_for_history", race_name)
    years = int(source["years"])
    stat = source["stat"]

    kyosoba_row = cache.get_kyosoba_row(horse_id)
    if kyosoba_row is None or "seisansha_code" not in kyosoba_row.index:
        return stat_result(stat, 0, 0, 0)
    seisansha_code = str(kyosoba_row["seisansha_code"]).strip()

    past_umagoto = cache.get_past_umagoto_df(race_name_for_history, years)
    if past_umagoto.empty:
        return stat_result(stat, 0, 0, 0)

    past_kyosoba = cache.get_past_kyosoba_df(race_name_for_history, years)
    if past_kyosoba.empty or "seisansha_code" not in past_kyosoba.columns:
        return stat_result(stat, 0, 0, 0)

    matched_ids = past_kyosoba.loc[
        past_kyosoba["seisansha_code"].astype(str).str.strip() == seisansha_code,
        "ketto_toroku_bango",
    ].tolist()

    if not matched_ids:
        return stat_result(stat, 0, 0, 0)

    past_rows = past_umagoto[past_umagoto["ketto_toroku_bango"].isin(matched_ids)]
    return aggregate_stat(past_rows, stat)


def sire_race_stat(
    horse_id: str, source: dict[str, Any], race_name: str, cache: TableDataCache
) -> Any:
    """種牡馬産駒の特定レース成績統計、または種牡馬名を返す。

    Args:
        horse_id (str): 血統登録番号。
        source (dict[str, Any]): YAMLのsource設定
            （stat/"name"の場合はrace_name_for_history/years不要）。
        race_name (str): デフォルトのレース名（race_name_for_history未指定時に使用）。
        cache (TableDataCache): データキャッシュ。

    Returns:
        Any: stat="name"の場合は種牡馬名（str）。それ以外はint/float統計値。
            データがない場合は0系統計またはNone。
    """
    stat = source["stat"]

    kyosoba_row = cache.get_kyosoba_row(horse_id)

    if stat == "name":
        if kyosoba_row is None:
            return None
        return to_cell_value(kyosoba_row.get("ketto1_bamei"))

    race_name_for_history = source.get("race_name_for_history", race_name)
    years = int(source["years"])

    if kyosoba_row is None:
        return stat_result(stat, 0, 0, 0)
    sire_hanshoku = str(kyosoba_row.get("ketto1_hanshoku_toroku_bango", "")).strip()
    if not sire_hanshoku:
        return stat_result(stat, 0, 0, 0)

    past_umagoto = cache.get_past_umagoto_df(race_name_for_history, years)
    if past_umagoto.empty:
        return stat_result(stat, 0, 0, 0)

    past_kyosoba = cache.get_past_kyosoba_df(race_name_for_history, years)
    if past_kyosoba.empty or "ketto1_hanshoku_toroku_bango" not in past_kyosoba.columns:
        return stat_result(stat, 0, 0, 0)

    matched_ids = past_kyosoba.loc[
        past_kyosoba["ketto1_hanshoku_toroku_bango"].astype(str).str.strip() == sire_hanshoku,
        "ketto_toroku_bango",
    ].tolist()

    if not matched_ids:
        return stat_result(stat, 0, 0, 0)

    past_rows = past_umagoto[past_umagoto["ketto_toroku_bango"].isin(matched_ids)]
    return aggregate_stat(past_rows, stat)


def kishu_continuity(horse_id: str, cache: TableDataCache) -> str | None:
    """騎手の継続/テン乗り/乗り戻りを判定する。

    Args:
        horse_id (str): 血統登録番号。
        cache (TableDataCache): データキャッシュ。

    Returns:
        str | None: "継続"/"テン乗り"/"乗り戻り"のいずれか。現レースの騎手が取得できない場合はNone。
    """
    umagoto_df = cache.get_umagoto_df()
    if umagoto_df.empty:
        return None
    horse_rows = filter_by_horse(umagoto_df, horse_id)
    if horse_rows.empty or "kishu_code" not in horse_rows.columns:
        return None
    current_kishu_raw = horse_rows.iloc[0]["kishu_code"]
    if is_na(current_kishu_raw):
        return None
    current_kishu = str(current_kishu_raw).strip()
    past_df = cache.get_horse_umagoto_df(horse_id)
    if past_df.empty or "kishu_code" not in past_df.columns:
        return "テン乗り"
    past_kishus = past_df["kishu_code"].astype(str).str.strip()
    if past_kishus.empty:
        return "テン乗り"
    if current_kishu == past_kishus.iloc[0]:
        return "継続"
    if current_kishu in past_kishus.values:
        return "乗り戻り"
    return "テン乗り"


def sire_race_chakujun(
    horse_id: str, source: dict[str, Any], race_name: str, cache: TableDataCache
) -> int | None:
    """父馬の指定レースでの確定着順を返す。

    Args:
        horse_id (str): 血統登録番号。
        source (dict[str, Any]): YAMLのsource設定（race_name_for_history/years等）。
        race_name (str): デフォルトのレース名（race_name_for_history未指定時に使用）。
        cache (TableDataCache): データキャッシュ。

    Returns:
        int | None: 父馬の確定着順。父馬が対象レースに出走していない場合はNone。
    """
    race_name_for_history = source.get("race_name_for_history", race_name)
    years = int(source["years"])
    kyosoba_row = cache.get_kyosoba_row(horse_id)
    if kyosoba_row is None:
        return None
    sire_name = str(kyosoba_row.get("ketto1_bamei", "")).strip()
    if not sire_name:
        return None
    past_umagoto = cache.get_past_umagoto_df(race_name_for_history, years)
    if past_umagoto.empty or "bamei" not in past_umagoto.columns:
        return None
    sire_rows = past_umagoto[
        past_umagoto["bamei"].astype(str).str.strip() == sire_name
    ]
    if sire_rows.empty:
        return None
    chakujun = pd.to_numeric(sire_rows.iloc[0]["kakutei_chakujun"], errors="coerce")
    if pd.isna(chakujun):
        return None
    return int(chakujun)


def sire_course_stat(horse_id: str, source: dict[str, Any], cache: TableDataCache) -> Any:
    """種牡馬産駒の特定コース成績統計を計算する。

    Args:
        horse_id (str): 血統登録番号。
        source (dict[str, Any]): YAMLのsource設定（keibajo_code/track/kyori/years/stat等）。
        cache (TableDataCache): データキャッシュ。

    Returns:
        Any: int（"wins"/"top3"）またはfloat（"win_rate"/"top3_rate"）。データがない場合は0系統計。
    """
    keibajo_code = str(source["keibajo_code"])
    track = source["track"]
    kyori = int(source["kyori"])
    years = int(source["years"])
    stat = source["stat"]
    track_condition: str | None = source.get("track_condition")

    kyosoba_row = cache.get_kyosoba_row(horse_id)
    if kyosoba_row is None:
        return stat_result(stat, 0, 0, 0)
    sire_hanshoku = str(kyosoba_row.get("ketto1_hanshoku_toroku_bango", "")).strip()
    if not sire_hanshoku:
        return stat_result(stat, 0, 0, 0)

    course_umagoto = cache.get_course_umagoto_df(
        keibajo_code, track, kyori, years, track_condition=track_condition
    )
    if course_umagoto.empty:
        return stat_result(stat, 0, 0, 0)

    course_kyosoba = cache.get_course_kyosoba_df(
        keibajo_code, track, kyori, years, track_condition
    )
    if course_kyosoba.empty or "ketto1_hanshoku_toroku_bango" not in course_kyosoba.columns:
        return stat_result(stat, 0, 0, 0)

    matched_ids = course_kyosoba.loc[
        course_kyosoba["ketto1_hanshoku_toroku_bango"].astype(str).str.strip()
        == sire_hanshoku,
        "ketto_toroku_bango",
    ].tolist()

    if not matched_ids:
        return stat_result(stat, 0, 0, 0)

    past_rows = course_umagoto[course_umagoto["ketto_toroku_bango"].isin(matched_ids)]
    return aggregate_stat(past_rows, stat)


def prev_race_kohan_3f_rank(horse_id: str, cache: TableDataCache) -> int | None:
    """前走（直近の有効レース）における上がり3Fタイムの全頭中順位を返す。

    Args:
        horse_id (str): 血統登録番号。
        cache (TableDataCache): データキャッシュ。

    Returns:
        int | None: 前走の上がり3F順位。算出できない場合はNone。
    """
    past_df = cache.get_horse_umagoto_df(horse_id)
    if past_df.empty or "kohan_3f" not in past_df.columns:
        return None
    valid_past = past_df[_valid_finish_mask(past_df) & _valid_kohan_3f_mask(past_df)]
    if valid_past.empty:
        return None
    prev_race_code = str(valid_past.iloc[0]["race_code"]).strip()

    field_df = cache.get_race_field_df(prev_race_code)
    if field_df.empty or "kohan_3f" not in field_df.columns:
        return None
    valid_field = field_df[_valid_finish_mask(field_df) & _valid_kohan_3f_mask(field_df)].copy()
    if valid_field.empty:
        return None
    valid_field["_kohan_3f"] = pd.to_numeric(valid_field["kohan_3f"], errors="coerce")
    valid_field["_jun"] = valid_field["_kohan_3f"].rank(method="min").astype(int)

    horse_row = valid_field[valid_field["ketto_toroku_bango"].astype(str).str.strip() == horse_id]
    if horse_row.empty:
        return None
    return int(horse_row.iloc[0]["_jun"])


def same_race_prev_year_finish(
    horse_id: str, source: dict[str, Any], race_year: int, cache: TableDataCache
) -> Any:
    """前年の同一特別競走における確定着順を返す。

    Args:
        horse_id (str): 血統登録番号。
        source (dict[str, Any]): YAMLのsource設定（tokubetsu_kyoso_bango/absent_label）。
        race_year (int): 今回のレース開催年。
        cache (TableDataCache): データキャッシュ。

    Returns:
        Any: 確定着順（int）。前年に出走していない場合はsource["absent_label"]の値。
    """
    tokubetsu_kyoso_bango = str(source["tokubetsu_kyoso_bango"]).strip()
    absent_label = source.get("absent_label")
    target_year = race_year - 1

    past_df = cache.build_past_df(horse_id)
    if past_df.empty or "特別競走番号" not in past_df.columns:
        return absent_label

    mask = (past_df["特別競走番号"].astype(str).str.strip() == tokubetsu_kyoso_bango) & (
        pd.to_numeric(past_df["開催年"], errors="coerce") == target_year
    )
    rows = past_df[mask]
    if rows.empty:
        return absent_label

    chakujun = pd.to_numeric(rows.iloc[0]["確定着順"], errors="coerce")
    if pd.isna(chakujun):
        return absent_label
    return int(chakujun)


def _valid_finish_mask(df: pd.DataFrame) -> pd.Series:
    """確定着順が有効値（2桁の数字かつ"00"以外）の行を示すマスクを返す。

    Args:
        df (pd.DataFrame): kakutei_chakujunカラムを持つDataFrame。

    Returns:
        pd.Series: 各行が有効な確定着順を持つかどうかの真偽値Series。
    """
    chakujun = df["kakutei_chakujun"].astype(str).str.strip()
    return chakujun.str.match(r"^[0-9]{2}$") & (chakujun != "00")


def _valid_kohan_3f_mask(df: pd.DataFrame) -> pd.Series:
    """上がり3Fタイムが有効値（数字かつ"000"以外）の行を示すマスクを返す。

    Args:
        df (pd.DataFrame): kohan_3fカラムを持つDataFrame。

    Returns:
        pd.Series: 各行が有効な上がり3Fタイムを持つかどうかの真偽値Series。
    """
    kohan_3f = df["kohan_3f"].astype(str).str.strip()
    return kohan_3f.str.match(r"^[0-9]+$") & (kohan_3f != "000")
