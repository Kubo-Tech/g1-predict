"""過去レースの統計値を analytics 経由で計算するモジュール。"""

from typing import Any

from mykeibadb.analytics import (
    AttrSource,
    ChakudoResult,
    ChakudoRow,
    GroupBy,
    RaceCondition,
    Subject,
    analyze_chakudo,
)
from mykeibadb.connection import ConnectionManager

from ._trend_models import SIRE_YEARS, RowStats

_SUBJECT_MAP: dict[str, Subject] = {
    "jockey_name": Subject.KISHU,
    "sire_name": Subject.SIRE,
    "breeder_name": Subject.SEISANSHA,
}


def compute_stats(
    metric_cfg: dict[str, Any],
    manager: ConnectionManager,
    condition: RaceCondition,
) -> dict[str, RowStats]:
    """metric 設定に従って analytics からデータを取得し RowStats を返す。

    source.type に応じて適切な analytics 関数を呼び出す。
    boolean_multi 型の場合は sire_race_condition_finisher の集計を行う。

    Args:
        metric_cfg (dict[str, Any]): metric の YAML 設定dict。
        manager (ConnectionManager): DB接続マネージャ。
        condition (RaceCondition): レース絞り込み条件。

    Returns:
        dict[str, RowStats]: 行ラベル -> RowStats。
    """
    rows_cfg = metric_cfg["rows"]

    if rows_cfg.get("type") == "boolean_multi":
        return _compute_sire_condition_stats(rows_cfg, manager, condition)

    src = metric_cfg["source"]
    src_type = src.get("type", "")

    if src_type == "gate_number":
        result = analyze_chakudo(
            manager, [], condition, GroupBy(kind="race_col", column="u.wakuban")
        )
        return _group_by_rows_cfg(result, rows_cfg)

    if src_type == "popularity":
        result = analyze_chakudo(
            manager, [], condition, GroupBy(kind="race_col", column="u.tansho_ninkijun")
        )
        return _group_by_rows_cfg(result, rows_cfg)

    if src_type == "running_style":
        result = analyze_chakudo(
            manager, [], condition, GroupBy(kind="race_col", column="u.kyakushitsu_hantei")
        )
        return _group_by_rows_cfg(result, rows_cfg)

    if src_type in _SUBJECT_MAP:
        subject = _SUBJECT_MAP[src_type]
        result = analyze_chakudo(
            manager, [], condition, GroupBy(kind="subject", subject=subject)
        )
        return _chakudo_to_stats_map(result)

    if src_type in (
        "past_finish_count",
        "career_count",
        "prev_race_name",
        "debut_venue",
        "jockey_continuity",
    ):
        group_by = _build_group_by(src, rows_cfg)
        result = analyze_chakudo(manager, [], condition, group_by)
        return _chakudo_to_stats_map(result)

    return {}


def _src_cache_key(src: dict[str, Any]) -> tuple[Any, ...]:
    """source 設定dict からキャッシュキーを生成する。

    Args:
        src (dict[str, Any]): source の YAML 設定dict。

    Returns:
        tuple[Any, ...]: ソート済みキー・値ペアのタプル（type キーを除く）。
    """
    parts: list[Any] = []
    for k in sorted(k for k in src if k != "type"):
        v = src[k]
        parts.append(k)
        parts.append(tuple(v) if isinstance(v, list) else v)
    return tuple(parts)


def _build_group_by(
    src: dict[str, Any],
    rows_cfg: dict[str, Any],
) -> GroupBy:
    """YAML の source / rows 設定から GroupBy を生成する。

    rows_cfg の type が "dynamic" の場合は kind="history"、それ以外は kind="fixed"。

    Args:
        src (dict[str, Any]): source の YAML 設定dict。
        rows_cfg (dict[str, Any]): rows の YAML 設定dict。

    Returns:
        GroupBy: 生成した GroupBy インスタンス。
    """
    attr_source = AttrSource.from_dict(src)
    if rows_cfg.get("type") == "dynamic":
        return GroupBy(kind="history", source=attr_source)
    rows_def = _yaml_rows_to_rowsdef(rows_cfg)
    return GroupBy(kind="fixed", source=attr_source, rows=rows_def)


def _compute_sire_condition_stats(
    rows_cfg: dict[str, Any],
    manager: ConnectionManager,
    condition: RaceCondition,
) -> dict[str, RowStats]:
    """boolean_multi (sire_race_condition_finisher) の RowStats を返す。

    過去レースの全種牡馬別着度数を取得し、条件を満たす父馬を持つ出走馬を集約する。
    同一 source 条件の SQL は1回のみ実行してキャッシュする。

    Args:
        rows_cfg (dict[str, Any]): rows の YAML 設定dict。
        manager (ConnectionManager): DB接続マネージャ。
        condition (RaceCondition): レース絞り込み条件。

    Returns:
        dict[str, RowStats]: 行ラベル -> RowStats。
    """
    race_year = int(condition.year_to) + 1  # type: ignore[arg-type]
    sire_result = analyze_chakudo(
        manager, [], condition, GroupBy(kind="subject", subject=Subject.SIRE)
    )
    sire_stats: dict[str, ChakudoRow] = {
        row.group: row for row in (sire_result.rows if sire_result.success else [])
    }

    winner_set_cache: dict[tuple[Any, ...], set[str]] = {}
    stats_map: dict[str, RowStats] = {}
    for item in rows_cfg.get("items", []):
        src = item.get("source", {})
        if src.get("type") != "sire_race_condition_finisher":
            continue
        label = item["label"]
        cache_key = _src_cache_key(src)
        if cache_key not in winner_set_cache:
            winner_set_cache[cache_key] = _get_sire_winner_set(src, manager, race_year)
        winner_set = winner_set_cache[cache_key]
        matching = [
            _chakudo_row_to_stats(row)
            for name, row in sire_stats.items()
            if name in winner_set
        ]
        stats_map[label] = _merge_stats(matching) if matching else RowStats()
    return stats_map


def _get_sire_winner_set(
    src: dict[str, Any],
    manager: ConnectionManager,
    race_year: int,
) -> set[str]:
    """指定条件のレースで top_n 着内になった馬の父馬名セットを返す。

    Args:
        src (dict[str, Any]): sire_race_condition_finisher の source 設定dict。
        manager (ConnectionManager): DB接続マネージャ。
        race_year (int): 対象レースの開催年（検索範囲の基点）。

    Returns:
        set[str]: 条件に一致するレースで top_n 着内になった馬の父馬名セット。
    """
    years = int(src.get("years", SIRE_YEARS))
    top_n = int(src.get("top_n", 1))
    year_from = str(race_year - years)
    year_to = str(race_year - 1)

    params: list[Any] = [year_from, year_to, top_n]
    where_parts = [
        "r.kaisai_nen >= %s",
        "r.kaisai_nen <= %s",
        "u.kakutei_chakujun ~ '^[0-9]{2}$'",
        "u.kakutei_chakujun != '00'",
        "CAST(u.kakutei_chakujun AS INTEGER) BETWEEN 1 AND %s",
    ]
    if "race_name" in src:
        where_parts.append("r.kyosomei_hondai = %s")
        params.append(src["race_name"])
    if "grade_codes" in src:
        where_parts.append("r.grade_code = ANY(%s)")
        params.append(src["grade_codes"])
    if "kyori" in src:
        where_parts.append("TRIM(r.kyori)::INTEGER = %s")
        params.append(int(src["kyori"]))

    where_clause = " AND ".join(where_parts)
    sql = f"""
        SELECT DISTINCT km2.ketto1_bamei AS sire_name
        FROM umagoto_race_joho u
        JOIN race_shosai r ON u.race_code = r.race_code
        JOIN kyosoba_master2 km2 ON u.ketto_toroku_bango = km2.ketto_toroku_bango
        WHERE {where_clause}
    """
    df = manager.fetch_dataframe(sql, params=tuple(params))
    if df.empty:
        return set()
    return set(df["sire_name"].astype(str).str.strip().tolist())


def _yaml_rows_to_rowsdef(
    rows_cfg: dict[str, Any],
) -> dict[str, tuple[int, int] | int | str]:
    """YAML rows 設定を RowsDef 形式に変換する。

    op: "==" は int/str、op: ">=" は (value, 9999)、op: "<=" は (0, value) に変換する。

    Args:
        rows_cfg (dict[str, Any]): rows の YAML 設定dict。

    Returns:
        dict[str, tuple[int, int] | int | str]: RowsDef 形式の辞書。

    Raises:
        ValueError: op が "in" の場合（GroupBy(kind="fixed") では非対応）。
    """
    if rows_cfg.get("type") == "dynamic":
        return {}
    result: dict[str, tuple[int, int] | int | str] = {}
    for item in rows_cfg.get("items", []):
        label = item["label"]
        op = item["op"]
        value = item["value"]
        if op == "==":
            result[label] = value if isinstance(value, str) else int(value)
        elif op == ">=":
            result[label] = (int(value), 9999)
        elif op == "<=":
            result[label] = (0, int(value))
        elif op == "in":
            raise ValueError(f"op 'in' は fixed rows では使用できません。label={label!r}")
    return result


def _chakudo_to_stats_map(result: ChakudoResult) -> dict[str, RowStats]:
    """ChakudoResult を group -> RowStats の辞書に変換する。

    Args:
        result (ChakudoResult): analytics 集計結果。

    Returns:
        dict[str, RowStats]: 行ラベル -> RowStats。
    """
    if not result.success:
        return {}
    return {row.group: _chakudo_row_to_stats(row) for row in result.rows}


def _chakudo_row_to_stats(row: ChakudoRow) -> RowStats:
    """ChakudoRow を RowStats に変換する。

    Args:
        row (ChakudoRow): 1グループ分の着度数・回収率集計結果。

    Returns:
        RowStats: 変換した RowStats インスタンス。
    """
    return RowStats(
        first=row.wins,
        second=row.second,
        third=row.third,
        fourth_plus=row.chakugai,
        tansho_kaishuu=row.tansho_kaishuu,
        fukusho_kaishuu=row.fukusho_kaishuu,
        total=row.total,
    )


def _group_by_rows_cfg(
    result: ChakudoResult,
    rows_cfg: dict[str, Any],
) -> dict[str, RowStats]:
    """ChakudoResult を YAML rows.items に従ってグループ化する。

    dynamic 型はそのまま変換する。fixed 型は rows_cfg の items を評価して
    条件に合致するグループを集約する。op: "in" も対応する。

    Args:
        result (ChakudoResult): analytics 集計結果。
        rows_cfg (dict[str, Any]): rows の YAML 設定dict。

    Returns:
        dict[str, RowStats]: 行ラベル -> RowStats。
    """
    if not result.success:
        return {}

    rows_type = rows_cfg.get("type", "dynamic")
    if rows_type == "dynamic":
        return _chakudo_to_stats_map(result)

    raw_stats: dict[str, ChakudoRow] = {row.group: row for row in result.rows}
    stats_map: dict[str, RowStats] = {}
    for item in rows_cfg.get("items", []):
        label = item["label"]
        op = item["op"]
        value = item["value"]
        matching = [
            _chakudo_row_to_stats(row)
            for group_str, row in raw_stats.items()
            if _group_matches(group_str, op, value)
        ]
        stats_map[label] = _merge_stats(matching) if matching else RowStats()
    return stats_map


def _group_matches(group_str: str, op: str, threshold: Any) -> bool:
    """ChakudoRow.group 文字列が YAML item の条件に一致するか判定する。

    数値比較は group_str を int に変換して試みる。変換不可の場合は文字列比較する。

    Args:
        group_str (str): ChakudoRow.group の値。
        op (str): 演算子文字列（"==" / ">=" / "<=" / ">" / "<" / "!=" / "in" / "not_in"）。
        threshold (Any): 比較の基準値。

    Returns:
        bool: 比較結果。
    """
    if op in ("in", "not_in"):
        threshold_list = list(threshold) if not isinstance(threshold, list) else threshold
        int_set: set[int] = set()
        str_set: set[str] = set()
        for v in threshold_list:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                int_set.add(int(v))
            str_set.add(str(v))
        try:
            matched = int(group_str) in int_set or group_str in str_set
        except (ValueError, TypeError):
            matched = group_str in str_set
        return matched if op == "in" else not matched

    if isinstance(threshold, (int, float)) and not isinstance(threshold, bool):
        try:
            group_num = int(group_str)
            if op == "==":
                return group_num == int(threshold)
            if op == "!=":
                return group_num != int(threshold)
            if op == ">=":
                return group_num >= int(threshold)
            if op == "<=":
                return group_num <= int(threshold)
            if op == ">":
                return group_num > int(threshold)
            if op == "<":
                return group_num < int(threshold)
        except (ValueError, TypeError):
            pass

    if op == "==":
        return group_str == str(threshold)
    if op == "!=":
        return group_str != str(threshold)
    return False


def _merge_stats(stats_list: list[RowStats]) -> RowStats:
    """複数の RowStats を加重平均で合算する。

    回収率は出走頭数による加重平均で計算する。

    Args:
        stats_list (list[RowStats]): 合算する RowStats のリスト。

    Returns:
        RowStats: 合算した RowStats インスタンス。
    """
    merged = RowStats()
    tansho_sum = 0.0
    fukusho_sum = 0.0
    for s in stats_list:
        merged.first += s.first
        merged.second += s.second
        merged.third += s.third
        merged.fourth_plus += s.fourth_plus
        tansho_sum += s.tansho_kaishuu * s.total
        fukusho_sum += s.fukusho_kaishuu * s.total
        merged.total += s.total
    if merged.total > 0:
        merged.tansho_kaishuu = tansho_sum / merged.total
        merged.fukusho_kaishuu = fukusho_sum / merged.total
    return merged
