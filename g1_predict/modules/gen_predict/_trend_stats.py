"""過去レースの統計値を計算するモジュール。"""

from collections import defaultdict
from typing import Any

import pandas as pd

from ._trend_models import OTHER_LABEL, Db, RowStats, sire_cache_key


def compute_stats(
    metric_cfg: dict[str, Any],
    db: Db,
) -> dict[str, RowStats]:
    """過去レース全馬を走査し、各行ラベルの集計値を計算する。

    各馬の着順・払戻金をもとに RowStats を積み上げる。
    boolean_multi の場合は複数ラベルへの重複カウントを許容する。

    Args:
        metric_cfg (dict[str, Any]): metric の YAML 設定dict。
        db (Db): 取得済みデータを保持するインスタンス。

    Returns:
        dict[str, RowStats]: 行ラベル -> RowStats。
    """
    rows_cfg = metric_cfg["rows"]
    stats_map: dict[str, RowStats] = defaultdict(RowStats)

    for rc in db.past_race_codes:
        result_df = db.results.get(rc, pd.DataFrame())
        if result_df.empty:
            continue
        payoff_row = db.payoffs.get(rc)
        payout_lookup = _build_payout_lookup(payoff_row)

        for _, horse_row in result_df.iterrows():
            horse_id = str(horse_row.get("血統登録番号", "")).strip()
            chakujun = _safe_int(horse_row.get("確定着順"))
            if chakujun is None:
                continue
            umaban = _safe_int(horse_row.get("馬番"))
            tansho_pay, fukusho_pay = (
                payout_lookup.get(umaban, (None, None)) if umaban else (None, None)
            )

            if rows_cfg["type"] == "boolean_multi":
                row_labels = _compute_boolean_labels(horse_id, rc, horse_row, metric_cfg, db)
            else:
                value = _compute_value(horse_id, rc, horse_row, metric_cfg, db)
                row_label = _classify(value, rows_cfg, metric_cfg.get("display_map", {}))
                row_labels = [row_label] if row_label else []

            for row_label in row_labels:
                s = stats_map[row_label]
                s.total += 1
                if chakujun == 1:
                    s.first += 1
                    if tansho_pay:
                        s.tansho_total += int(tansho_pay)
                elif chakujun == 2:
                    s.second += 1
                elif chakujun == 3:
                    s.third += 1
                else:
                    s.fourth_plus += 1
                if chakujun in (1, 2, 3) and fukusho_pay:
                    s.fukusho_total += int(fukusho_pay)

    return dict(stats_map)


def _compute_value(
    horse_id: str,
    past_race_code: str,
    result_row: pd.Series,
    metric_cfg: dict[str, Any],
    db: Db,
) -> Any:
    """1頭分の metric 値を計算して返す。

    source.type に応じて結果行・履歴・マスタから値を取得する。
    認識できない source.type の場合は None を返す。

    past_finish_count の source で指定可能なフィルタ:
        top_n (int): 何着以内を対象とするか（デフォルト: 1）。
        grade_codes (list[str]): グレードコードでフィルタ（例: ["A", "B", "C"]）。
        keibajo_code (str): 競馬場コードでフィルタ（例: "05"）。

    Args:
        horse_id (str): 血統登録番号。
        past_race_code (str): 対象の過去レースコード（履歴の時間的上限として使用）。
        result_row (pd.Series): 過去レースの結果DataFrame の1行（get_result 出力）。
        metric_cfg (dict[str, Any]): metric の YAML 設定dict。
        db (Db): 取得済みデータを保持するインスタンス。

    Returns:
        Any: metric 値。型は source.type に依存する。取得不可の場合は None。
    """
    src = metric_cfg.get("source", {})
    src_type = src.get("type", "")

    if src_type == "gate_number":
        return _safe_int(result_row.get("枠番"))

    if src_type == "popularity":
        return _safe_int(result_row.get("単勝人気順"))

    if src_type == "running_style":
        return str(result_row.get("脚質判定コード", "")).strip() or None

    if src_type == "jockey_name":
        return str(result_row.get("騎手名略称", "")).strip() or None

    if src_type == "breeder_name":
        ky = db.kyosoba.get(horse_id)
        if ky is None:
            return None
        v = str(ky.get("seisanshamei_hojinkaku_nashi", "")).strip()
        return v or None

    if src_type == "sire_name":
        ky = db.kyosoba.get(horse_id)
        if ky is None:
            return None
        v = str(ky.get("ketto1_bamei", "")).strip()
        return v or None

    hist = _history_before(horse_id, past_race_code, db.history)

    if src_type == "past_finish_count":
        top_n = int(src.get("top_n", 1))
        grade_codes = src.get("grade_codes")
        keibajo_code = str(src.get("keibajo_code", "")).strip() or None
        count = 0
        for _, row in hist.iterrows():
            rc = str(row.get("race_code", "")).strip()
            if grade_codes is not None:
                grade = db.shosai.get(rc, {}).get("grade_code", "")
                if grade not in grade_codes:
                    continue
            if keibajo_code is not None:
                if db.shosai.get(rc, {}).get("keibajo_code", "") != keibajo_code:
                    continue
            raw_val = row.get("kakutei_chakujun")
            chakujun = pd.to_numeric(raw_val, errors="coerce") if raw_val is not None else None
            if chakujun is not None and not pd.isna(chakujun) and 1 <= int(chakujun) <= top_n:
                count += 1
        return count

    if src_type == "career_count":
        count = 0
        for _, row in hist.iterrows():
            ijo = str(row.get("ijo_kubun_code", "0")).strip()
            if ijo not in ("1", "2", "3"):
                count += 1
        return count

    if src_type == "prev_race_name":
        if hist.empty or "race_code" not in hist.columns:
            return None
        sorted_h = hist.sort_values("race_code", ascending=False)
        prev_rc = str(sorted_h.iloc[0].get("race_code", "")).strip()
        return db.shosai.get(prev_rc, {}).get("kyosomei_hondai") or None

    if src_type == "debut_venue":
        if hist.empty or "race_code" not in hist.columns:
            return None
        allowed = src.get("allowed_values")
        sorted_h = hist.sort_values("race_code", ascending=True)
        for _, row in sorted_h.iterrows():
            ijo = str(row.get("ijo_kubun_code", "0")).strip()
            if ijo not in ("1", "2", "3"):
                venue = str(row.get("keibajo_code", "")).strip() or None
                if allowed is not None and venue not in allowed:
                    return OTHER_LABEL
                return venue
        return None

    if src_type == "jockey_continuity":
        current_kishu = str(result_row.get("騎手コード", "")).strip()
        if not current_kishu:
            return None
        if hist.empty or "kishu_code" not in hist.columns:
            return "テン乗り"
        sorted_h = hist.sort_values("race_code", ascending=False)
        prev_kishus = sorted_h["kishu_code"].astype(str).str.strip()
        if prev_kishus.empty:
            return "テン乗り"
        if current_kishu == prev_kishus.iloc[0]:
            return "継続"
        if current_kishu in prev_kishus.values:
            return "乗り戻り"
        return "テン乗り"

    return None


def _compute_boolean_labels(
    horse_id: str,
    past_race_code: str,
    result_row: pd.Series,
    metric_cfg: dict[str, Any],
    db: Db,
) -> list[str]:
    """boolean_multi 型 metric で馬が該当するラベルのリストを返す。

    rows.items の各 item について source 条件を評価し、
    条件を満たす item の label を収集する。1頭が複数ラベルに属しうる。

    Args:
        horse_id (str): 血統登録番号。
        past_race_code (str): 対象の過去レースコード（未使用、シグネチャ統一のため保持）。
        result_row (pd.Series): 過去レースの結果DataFrame の1行（未使用、シグネチャ統一のため保持）。
        metric_cfg (dict[str, Any]): metric の YAML 設定dict。
        db (Db): 取得済みデータを保持するインスタンス。

    Returns:
        list[str]: 条件を満たす行ラベルのリスト。
    """
    rows_cfg = metric_cfg["rows"]
    ky = db.kyosoba.get(horse_id)
    sire_name = ""
    if ky is not None:
        sire_name = str(ky.get("ketto1_bamei", "")).strip()

    labels = []
    for item in rows_cfg.get("items", []):
        src = item.get("source", {})
        if src.get("type") == "sire_race_condition_finisher":
            key = sire_cache_key(src)
            winner_set = db.sire_finisher_sets.get(key, set())
            if sire_name and sire_name in winner_set:
                labels.append(item["label"])
    return labels


def _classify(
    value: Any,
    rows_cfg: dict[str, Any],
    display_map: dict[str, str],
) -> str | None:
    """値を rows 設定に従って行ラベルに分類する。

    fixed 型は items を順に評価し最初に一致したラベルを返す。
    dynamic 型は値をそのまま文字列として返す。

    Args:
        value (Any): 分類対象の値。
        rows_cfg (dict[str, Any]): rows の YAML 設定dict（type / items を含む）。
        display_map (dict[str, str]): raw 値 -> 表示名のdict（dynamic 型では未使用）。

    Returns:
        str | None: 行ラベル文字列。分類不可の場合は None。
    """
    rows_type = rows_cfg["type"]

    if rows_type == "fixed":
        for item in rows_cfg["items"]:
            if _match_op(value, item["op"], item["value"]):
                return item["label"]
        return None

    if rows_type == "dynamic":
        return str(value) if value is not None else None

    return None


def _build_payout_lookup(
    payoff_row: pd.Series | None,
) -> dict[int, tuple[int | None, int | None]]:
    """払戻情報 Series から馬番 -> (単勝払戻金, 複勝払戻金) の辞書を構築する。

    払戻情報が None の場合は空辞書を返す。
    馬番が 0 またはNA のエントリは無視する。

    Args:
        payoff_row (pd.Series | None): get_payoff() 結果の1行 Series。None の場合は空辞書を返す。

    Returns:
        dict[int, tuple[int | None, int | None]]: 馬番 -> (単勝払戻金 or None, 複勝払戻金 or None)。
    """
    if payoff_row is None:
        return {}
    lookup: dict[int, tuple[int | None, int | None]] = {}

    for i in range(1, 4):
        umaban_val = payoff_row.get(f"単勝{i}馬番")
        pay_val = payoff_row.get(f"単勝{i}払戻金")
        if pd.notna(umaban_val) and int(umaban_val) > 0:
            umaban = int(umaban_val)
            tansho = int(pay_val) if pd.notna(pay_val) else None
            fuku = lookup.get(umaban, (None, None))[1]
            lookup[umaban] = (tansho, fuku)

    for i in range(1, 6):
        umaban_val = payoff_row.get(f"複勝{i}馬番")
        pay_val = payoff_row.get(f"複勝{i}払戻金")
        if pd.notna(umaban_val) and int(umaban_val) > 0:
            umaban = int(umaban_val)
            pay = int(pay_val) if pd.notna(pay_val) else None
            tansho = lookup.get(umaban, (None, None))[0]
            lookup[umaban] = (tansho, pay)

    return lookup


def _history_before(
    horse_id: str,
    past_race_code: str,
    history: pd.DataFrame,
) -> pd.DataFrame:
    """全履歴DataFrameから指定馬の指定レース以前の出走記録を返す。

    Args:
        horse_id (str): 血統登録番号。
        past_race_code (str): この race_code より古いレースのみ返す（以前＝文字列比較 <）。
        history (pd.DataFrame): 全出走馬の全履歴DataFrame（UMAGOTO、convert_codes=False）。

    Returns:
        pd.DataFrame: horse_id かつ race_code < past_race_code の行。
    """
    if history.empty:
        return pd.DataFrame()
    mask = (
        (history["ketto_toroku_bango"].astype(str).str.strip() == horse_id)
        & (history["race_code"].astype(str).str.strip() < past_race_code)
    )
    return history[mask]


def _safe_int(value: Any) -> int | None:
    """値を int に変換する。変換不可・NaN・None の場合は None を返す。

    Args:
        value (Any): 変換対象の値。

    Returns:
        int | None: int 値。変換不可の場合は None。
    """
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _match_op(value: Any, op: str, threshold: Any) -> bool:
    """演算子を使って value と threshold を比較する。

    value が None・NaN の場合、または比較で例外が発生した場合は False を返す。

    Args:
        value (Any): 比較対象の値。
        op (str): 演算子文字列（"==" / "!=" / ">=" / "<=" / ">" / "<" / "in" / "not_in"）。
        threshold (Any): 比較の基準値。

    Returns:
        bool: 比較結果。
    """
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    try:
        if op == "==":
            return bool(value == threshold)
        if op == "!=":
            return bool(value != threshold)
        if op == ">=":
            return bool(value >= threshold)
        if op == "<=":
            return bool(value <= threshold)
        if op == ">":
            return bool(value > threshold)
        if op == "<":
            return bool(value < threshold)
        if op == "in":
            return value in threshold
        if op == "not_in":
            return value not in threshold
    except (TypeError, ValueError):
        return False
    return False
