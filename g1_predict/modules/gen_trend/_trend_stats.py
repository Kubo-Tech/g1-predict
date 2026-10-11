"""過去レースの統計値を analytics 経由で計算するモジュール。"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from mykeibadb.analytics import (
    AttrSource,
    ChakudoResult,
    ChakudoRow,
    EntryFilter,
    GroupBy,
    RaceCondition,
    Subject,
    analyze_chakudo,
    get_race_display_names,
)
from mykeibadb.connection import ConnectionManager

from ._trend_loader import fetch_past_races
from ._trend_models import SIRE_YEARS, RowStats
from ._trend_sql_exprs import (
    BIRTH_MONTH_EXPR,
    CORNER4_JUNI_EXPR,
    HORSE_WEIGHT_EXPR,
    build_debut_month_expr,
    build_good_baba_top3_count_expr,
    build_prev_corner4_juni_expr,
    build_prev_distance_diff_expr,
    build_prev_race_class_expr,
    build_prev_race_finish_by_class_expr,
    build_soft_baba_top3_count_expr,
    build_transport_expr,
)

SUBJECT_MAP: dict[str, Subject] = {
    "jockey_name": Subject.KISHU,
    "sire_name": Subject.SIRE,
    "breeder_name": Subject.SEISANSHA,
}

# 上がり3F順位: 同一レース内で上がり3Fタイム昇順に順位付けする
_AGARI_3F_RANK_EXPR = (
    "RANK() OVER ("
    "PARTITION BY u.race_code "
    "ORDER BY CASE WHEN TRIM(u.kohan_3f) ~ '^[0-9]+$' AND TRIM(u.kohan_3f) != '000' "
    "THEN TRIM(u.kohan_3f)::NUMERIC ELSE NULL END)"
)

_RACE_COL_MAP: dict[str, str] = {
    "gate_number": "u.wakuban",
    "popularity": "u.tansho_ninkijun",
    "running_style": "u.kyakushitsu_hantei",
    "affiliation": "u.tozai_shozoku_code",
    "horse_age": "u.barei",
    "sex": "u.seibetsu_code",
    "agari_3f_rank": _AGARI_3F_RANK_EXPR,
    "corner4_juni": CORNER4_JUNI_EXPR,
    "horse_weight": HORSE_WEIGHT_EXPR,
    "birth_month": BIRTH_MONTH_EXPR,
}

# 集計対象レースの出走馬の過去走から値を求める source.type -> SQL 式の組み立て関数
_HISTORY_EXPR_BUILDERS: dict[str, Callable[[list[str]], str]] = {
    "prev_corner4_juni": build_prev_corner4_juni_expr,
    "prev_distance_diff": build_prev_distance_diff_expr,
    "prev_race_class": build_prev_race_class_expr,
    "transport": build_transport_expr,
    "good_baba_top3_count": build_good_baba_top3_count_expr,
    "soft_baba_top3_count": build_soft_baba_top3_count_expr,
    "debut_month": build_debut_month_expr,
}

# prev_race_grade / prev_race_finish / prev_race_finish_by_grade -> prev_race_col の column名
_PREV_RACE_COL_TYPES: dict[str, str] = {
    "prev_race_grade": "grade_code",
    "prev_race_finish": "kakutei_chakujun",
    "prev_race_finish_by_grade": "kakutei_chakujun",
}

# chokyo_match_days の rows.items で使える op
_CHOKYO_MATCH_DAYS_OPS = frozenset({"any_match", "none_match", "empty"})

# past_race_top_n_count の filters で指定する field名 -> mykeibadb horse_hist の column名
_HIST_FILTER_FIELD_MAP: dict[str, str] = {
    "確定着順": "kakutei_chakujun",
    "グレードコード": "grade_code",
    "競馬場コード": "keibajo_code",
    "距離": "kyori_int",
    "脚質判定コード": "kyakushitsu_hantei",
    "特別競走番号": "tokubetsu_kyoso_bango",
}


@dataclass(frozen=True)
class ItemGrouping:
    """項目の集計と出走馬の判定で共有するグループ分けの定義。

    Attributes:
        group_by (GroupBy): グループ分け軸。
        assign_rows (Callable[[str], list[str]]): グループの値 -> その値が当たる表の行のラベル。
            fixed の op・chokyo_match_days の op・boolean_multi の父の判定により、
            複数の行に当たることがある。
        row_labels (list[str] | None): 集計値が空でも表に必ず載せる行のラベル。
            dynamic の項目は None。
    """

    group_by: GroupBy
    assign_rows: Callable[[str], list[str]]
    row_labels: list[str] | None = None


def compute_stats(
    metric_cfg: dict[str, Any],
    manager: ConnectionManager,
    condition: RaceCondition,
    filters: list[EntryFilter],
) -> dict[str, RowStats]:
    """metric 設定に従って analytics からデータを取得し RowStats を返す。

    build_item_grouping で組み立てたグループ分けで analyze_chakudo を実行し、
    グループごとの集計値を表の行に割り当てて合算する。

    Args:
        metric_cfg (dict[str, Any]): metric の YAML 設定dict。
        manager (ConnectionManager): DB接続マネージャ。
        condition (RaceCondition): レース絞り込み条件。
        filters (list[EntryFilter]): 追加のエントリフィルタ。

    Returns:
        dict[str, RowStats]: 行ラベル -> RowStats。
    """
    grouping = build_item_grouping(
        metric_cfg, manager, condition, lambda: _past_race_codes(manager, condition)
    )
    result = _analyze(manager, filters, condition, grouping.group_by)
    grouped: dict[str, list[RowStats]] = {label: [] for label in grouping.row_labels or []}
    for row in result.rows:
        stats = _chakudo_row_to_stats(row)
        for label in grouping.assign_rows(row.group):
            grouped.setdefault(label, []).append(stats)
    return {label: _combine_stats(stats_list) for label, stats_list in grouped.items()}


def build_item_grouping(
    metric_cfg: dict[str, Any],
    manager: ConnectionManager,
    condition: RaceCondition,
    race_codes: Callable[[], list[str]],
) -> ItemGrouping:
    """metric 設定から、集計と出走馬の判定で共有するグループ分けを組み立てる。

    過去走を参照する SQL 式は、race_codes のレースの出走馬について値を求める式になる。
    集計では過去の開催のレースコード、出走馬の判定では対象レースのレースコードを渡す。

    Args:
        metric_cfg (dict[str, Any]): metric の YAML 設定dict。
        manager (ConnectionManager): DB接続マネージャ。
        condition (RaceCondition): レース絞り込み条件。特別競走番号と、
            boolean_multi の判定の基準年（year_to の翌年）に使う。
        race_codes (Callable[[], list[str]]): 過去走を参照する式を組み立てるときだけ呼ばれ、
            値を求める出走馬のレースコードを返す。

    Returns:
        ItemGrouping: グループ分け軸と、グループの値から行への割り当て。

    Raises:
        ValueError: source.type が未対応の場合、tokubetsu_race_finish の特別競走番号が
            condition にも source にも無い場合、または boolean_multi で condition.year_to が
            None の場合。
    """
    rows_cfg = metric_cfg["rows"]

    if rows_cfg.get("type") == "boolean_multi":
        return _build_sire_condition_grouping(rows_cfg, manager, condition)

    src = metric_cfg["source"]
    src_type = src.get("type", "")

    race_col_expr = _build_race_col_expr(src, race_codes)
    if race_col_expr is not None:
        return _rows_cfg_grouping(GroupBy(kind="race_col", column=race_col_expr), rows_cfg)

    if src_type in SUBJECT_MAP:
        group_by = GroupBy(kind="subject", subject=SUBJECT_MAP[src_type])
        return ItemGrouping(group_by, _same_group_row)

    if src_type in (
        "past_race_top_n_count",
        "career_count",
        "prev_race_name",
        "debut_venue",
        "jockey_continuity",
        "prev_race_col",
    ):
        return ItemGrouping(_build_group_by(src, rows_cfg), _same_group_row)

    if src_type == "tokubetsu_race_finish":
        if "tokubetsu_kyoso_bango" not in src:
            if condition.tokubetsu_kyoso_bango is None:
                raise ValueError(
                    "tokubetsu_race_finish の特別競走番号が source にも condition にもありません。"
                )
            src = {**src, "tokubetsu_kyoso_bango": condition.tokubetsu_kyoso_bango}
        group_by = GroupBy(kind="history", source=AttrSource.from_dict(src))
        return _rows_cfg_grouping(group_by, rows_cfg)

    if src_type == "chokyo_match_days":
        group_by = GroupBy(kind="history", source=AttrSource.from_dict(src))
        return _build_chokyo_match_days_grouping(group_by, rows_cfg)

    if src_type in _PREV_RACE_COL_TYPES:
        attr_source = AttrSource.from_dict(_convert_prev_race_source(src))
        return _rows_cfg_grouping(GroupBy(kind="history", source=attr_source), rows_cfg)

    raise ValueError(f"未対応の source.type です: {src_type!r}")


def get_juusho_race_names(
    manager: ConnectionManager,
    grades: list[str],
) -> set[str]:
    """grade_code が grades に含まれるレースの表示用レース名セットを返す。

    表示用レース名は get_race_display_names と同じ統一ロジックで解決するため、
    prev_race_name の集計結果（stats_map のキー）と整合する。

    Args:
        manager (ConnectionManager): DB接続マネージャ。
        grades (list[str]): 対象グレードコードのリスト（例: ["A", "B", "C"]）。

    Returns:
        set[str]: 表示用レース名の文字列セット。
    """
    sql = """
        SELECT DISTINCT r.race_code
        FROM race_shosai r
        WHERE r.grade_code = ANY(%s)
    """
    df = manager.fetch_dataframe(sql, params=(grades,))
    if df.empty:
        return set()
    race_codes = df["race_code"].astype(str).str.strip().tolist()
    return set(get_race_display_names(manager, race_codes).values())


def _analyze(
    manager: ConnectionManager,
    filters: list[EntryFilter],
    condition: RaceCondition,
    group_by: GroupBy,
) -> ChakudoResult:
    """analyze_chakudo を実行し、集計に失敗した場合は例外を送出する。

    Args:
        manager (ConnectionManager): DB接続マネージャ。
        filters (list[EntryFilter]): エントリフィルタ。
        condition (RaceCondition): レース絞り込み条件。
        group_by (GroupBy): グループ分け軸。

    Returns:
        ChakudoResult: 集計結果（success=True）。

    Raises:
        RuntimeError: 集計に失敗した場合。
    """
    result = analyze_chakudo(manager, filters, condition, group_by)
    if not result.success:
        raise RuntimeError(f"着度数の集計に失敗しました: {result.error}")
    return result


def _past_race_codes(manager: ConnectionManager, condition: RaceCondition) -> list[str]:
    """条件に合う過去のレースのレースコードを返す。

    Args:
        manager (ConnectionManager): DB接続マネージャ。
        condition (RaceCondition): レース絞り込み条件。

    Returns:
        list[str]: 集計対象レースのレースコード。
    """
    return list(fetch_past_races(manager, condition)["race_code"].tolist())


def _build_race_col_expr(
    src: dict[str, Any],
    race_codes_loader: Callable[[], list[str]],
) -> str | None:
    """source から GroupBy(kind="race_col") に渡す SQL 式を組み立てる。

    Args:
        src (dict[str, Any]): source の YAML 設定dict。
        race_codes_loader (Callable[[], list[str]]): 過去走を参照する式に埋め込む
            レースコードを返す関数。

    Returns:
        str | None: SQL 式。race_col で集計しない source.type の場合は None。

    Raises:
        ValueError: prev_race_finish_by_class に race_class が無い場合。
    """
    src_type = src.get("type", "")
    if src_type in _RACE_COL_MAP:
        return _RACE_COL_MAP[src_type]
    if src_type not in _HISTORY_EXPR_BUILDERS and src_type != "prev_race_finish_by_class":
        return None

    race_codes = race_codes_loader()
    if src_type == "prev_race_finish_by_class":
        if "race_class" not in src:
            raise ValueError("prev_race_finish_by_class には race_class が必要です。")
        return build_prev_race_finish_by_class_expr(race_codes, src["race_class"])
    return _HISTORY_EXPR_BUILDERS[src_type](race_codes)


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

    Raises:
        ValueError: past_race_top_n_count の top_n が 1 未満、
            または filters に未対応fieldがある場合。
    """
    if src.get("type") == "past_race_top_n_count":
        top_n = src.get("top_n")
        if top_n is not None and int(top_n) < 1:
            raise ValueError("past_race_top_n_count の top_n は 1 以上で指定してください。")
    if src.get("type") == "past_race_top_n_count" and src.get("filters"):
        src = {**src, "filters": [_convert_hist_filter(f) for f in src["filters"]]}
    attr_source = AttrSource.from_dict(src)
    if rows_cfg.get("type") == "dynamic":
        return GroupBy(kind="history", source=attr_source)
    rows_def = _yaml_rows_to_rowsdef(rows_cfg)
    return GroupBy(kind="fixed", source=attr_source, rows=rows_def)


def _convert_hist_filter(filt: dict[str, Any]) -> dict[str, Any]:
    """past_race_top_n_count の filters 1要素をAttrSource.filters形式へ変換する。

    Args:
        filt (dict[str, Any]): {"field": str, "op": str, "value": Any} 形式のYAML設定。

    Returns:
        dict[str, Any]: {"column": str, "op": str, "value": Any} 形式の辞書。

    Raises:
        ValueError: field が _HIST_FILTER_FIELD_MAP に存在しない場合。
    """
    field = filt["field"]
    if field not in _HIST_FILTER_FIELD_MAP:
        raise ValueError(f"past_race_top_n_count の filters で未対応の field です: {field!r}")
    return {"column": _HIST_FILTER_FIELD_MAP[field], "op": filt["op"], "value": filt["value"]}


def _convert_prev_race_source(src: dict[str, Any]) -> dict[str, Any]:
    """prev_race_grade/prev_race_finish/prev_race_finish_by_grade を prev_race_col 形式へ変換する。

    Args:
        src (dict[str, Any]): source の YAML 設定dict。

    Returns:
        dict[str, Any]: type="prev_race_col" の source 設定dict。

    Raises:
        ValueError: prev_race_finish_by_grade で grade_codes と exclude_grade_codes を
            同時に指定した場合。
    """
    src_type = src["type"]
    converted = {**src, "type": "prev_race_col", "column": _PREV_RACE_COL_TYPES[src_type]}
    if src_type == "prev_race_finish_by_grade":
        grade_codes = converted.pop("grade_codes", None)
        exclude_grade_codes = converted.pop("exclude_grade_codes", None)
        if grade_codes is not None and exclude_grade_codes is not None:
            raise ValueError(
                "prev_race_finish_by_grade では grade_codes と exclude_grade_codes を"
                "同時に指定できません。"
            )
        if grade_codes is not None:
            converted["filters"] = [{"column": "grade_code", "op": "in", "value": grade_codes}]
        elif exclude_grade_codes is not None:
            converted["filters"] = [
                {"column": "grade_code", "op": "not_in", "value": exclude_grade_codes}
            ]
    return converted


def _build_sire_condition_grouping(
    rows_cfg: dict[str, Any],
    manager: ConnectionManager,
    condition: RaceCondition,
) -> ItemGrouping:
    """boolean_multi (sire_race_condition_finisher) のグループ分けを組み立てる。

    種牡馬名でグループ分けし、条件を満たす種牡馬の産駒を各行に割り当てる。
    同一 source 条件の SQL は1回のみ実行してキャッシュする。

    Args:
        rows_cfg (dict[str, Any]): rows の YAML 設定dict。
        manager (ConnectionManager): DB接続マネージャ。
        condition (RaceCondition): レース絞り込み条件。

    Returns:
        ItemGrouping: 種牡馬名でグループ分けし、父が行の条件を満たす行に割り当てる定義。

    Raises:
        ValueError: condition.year_to が None の場合。
    """
    if condition.year_to is None:
        raise ValueError("condition.year_to は必須です。")
    race_year = int(condition.year_to) + 1

    winner_set_cache: dict[tuple[Any, ...], set[str]] = {}
    winner_sets: dict[str, set[str]] = {}
    for item in rows_cfg.get("items", []):
        src = item.get("source", {})
        if src.get("type") != "sire_race_condition_finisher":
            continue
        cache_key = _src_cache_key(src)
        if cache_key not in winner_set_cache:
            winner_set_cache[cache_key] = _get_sire_winner_set(src, manager, race_year)
        winner_sets[item["label"]] = winner_set_cache[cache_key]

    def assign_rows(sire_name: str) -> list[str]:
        return [label for label, winners in winner_sets.items() if sire_name in winners]

    return ItemGrouping(
        GroupBy(kind="subject", subject=Subject.SIRE), assign_rows, list(winner_sets)
    )


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
        where_parts.append("TRIM(r.kyosomei_hondai) = %s")
        params.append(src["race_name"])
    if "grade_codes" in src:
        where_parts.append("r.grade_code = ANY(%s)")
        params.append(src["grade_codes"])
    if "kyori" in src:
        where_parts.append("TRIM(r.kyori)::INTEGER = %s")
        params.append(int(src["kyori"]))

    where_clause = " AND ".join(where_parts)
    sql = f"""
        SELECT DISTINCT u.bamei AS sire_name
        FROM umagoto_race_joho u
        JOIN race_shosai r ON u.race_code = r.race_code
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

    op: "==" は int/str、op: ">=" は (value, 9999)、op: "<=" は (0, value)、
    op: ">" は (value+1, 9999)、op: "<" は (0, value-1)、
    op: "between" は (value[0], value[1]) に変換する。

    Args:
        rows_cfg (dict[str, Any]): rows の YAML 設定dict。

    Returns:
        dict[str, tuple[int, int] | int | str]: RowsDef 形式の辞書。

    Raises:
        ValueError: op が "in" の場合（GroupBy(kind="fixed") では非対応）、
            または op が "between" で value が [下限, 上限] でない場合。
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
        elif op == "<":
            result[label] = (0, int(value) - 1)
        elif op == ">":
            result[label] = (int(value) + 1, 9999)
        elif op == "between":
            lower, upper = _between_bounds(value)
            result[label] = (lower, upper)
        elif op == "in":
            raise ValueError(f"op 'in' は fixed rows では使用できません。label={label!r}")
    return result


def _between_bounds(value: Any) -> tuple[int, int]:
    """op: between の value を (下限, 上限) に変換する。

    Args:
        value (Any): [下限, 上限] 形式の値。

    Returns:
        tuple[int, int]: (下限, 上限)。

    Raises:
        ValueError: value が整数2要素のリストでない場合。
    """
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"op 'between' の value は [下限, 上限] で指定してください: {value!r}")
    return int(value[0]), int(value[1])


def _same_group_row(group: str) -> list[str]:
    """グループの値をそのまま行のラベルとして返す。

    Args:
        group (str): グループの値。

    Returns:
        list[str]: グループの値だけを持つリスト。
    """
    return [group]


def _combine_stats(stats_list: list[RowStats]) -> RowStats:
    """行に割り当てられたグループの集計値を1つにまとめる。

    Args:
        stats_list (list[RowStats]): 行に割り当てられたグループの集計値。

    Returns:
        RowStats: 1つだけならそのまま、複数なら合算した集計値。空なら全て0の集計値。
    """
    if len(stats_list) == 1:
        return stats_list[0]
    return _merge_stats(stats_list)


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


def _rows_cfg_grouping(group_by: GroupBy, rows_cfg: dict[str, Any]) -> ItemGrouping:
    """グループの値を YAML rows.items に従って行に割り当てる定義を返す。

    dynamic 型はグループの値をそのまま行のラベルにする。fixed 型は rows_cfg の items を
    評価して条件に合致する行すべてに割り当てる。op: "in" も対応する。

    Args:
        group_by (GroupBy): グループ分け軸。
        rows_cfg (dict[str, Any]): rows の YAML 設定dict。

    Returns:
        ItemGrouping: グループ分け軸と、グループの値から行への割り当て。
    """
    if rows_cfg.get("type", "dynamic") == "dynamic":
        return ItemGrouping(group_by, _same_group_row)

    items = rows_cfg.get("items", [])

    def assign_rows(group: str) -> list[str]:
        return [
            item["label"] for item in items if _group_matches(group, item["op"], item["value"])
        ]

    return ItemGrouping(group_by, assign_rows, [item["label"] for item in items])


def _group_matches(group_str: str, op: str, threshold: Any) -> bool:
    """ChakudoRow.group 文字列が YAML item の条件に一致するか判定する。

    数値比較は group_str を int に変換して試みる。変換不可の場合は文字列比較する。

    Args:
        group_str (str): ChakudoRow.group の値。
        op (str): 演算子文字列
            （"==" / ">=" / "<=" / ">" / "<" / "!=" / "in" / "not_in" / "between"）。
        threshold (Any): 比較の基準値。between は [下限, 上限]（両端を含む）。

    Returns:
        bool: 比較結果。
    """
    if op == "between":
        lower, upper = _between_bounds(threshold)
        try:
            return lower <= int(group_str) <= upper
        except (ValueError, TypeError):
            return False

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


def _build_chokyo_match_days_grouping(group_by: GroupBy, rows_cfg: dict[str, Any]) -> ItemGrouping:
    """chokyo_match_days のグループの値を YAML rows.items に従って行に割り当てる定義を返す。

    グループの値（`[[何日前, 該当bool], ...]` 形式のJSON配列テキスト）を
    any_match / none_match / empty のいずれかで判定し、条件に合致する行すべてに割り当てる。

    Args:
        group_by (GroupBy): グループ分け軸。
        rows_cfg (dict[str, Any]): rows の YAML 設定dict。

    Returns:
        ItemGrouping: グループ分け軸と、グループの値から行への割り当て。

    Raises:
        ValueError: item の op が any_match / none_match / empty 以外の場合。
    """
    items = rows_cfg.get("items", [])
    for item in items:
        if item["op"] not in _CHOKYO_MATCH_DAYS_OPS:
            raise ValueError(f"chokyo_match_days の rows.items で未対応の op です: {item['op']!r}")

    def assign_rows(group: str) -> list[str]:
        return [item["label"] for item in items if _chokyo_match_days_matches(group, item["op"])]

    return ItemGrouping(group_by, assign_rows, [item["label"] for item in items])


def _chokyo_match_days_matches(group_text: str, op: str) -> bool:
    """chokyo_match_days の group テキストが op の条件に一致するか判定する。

    Args:
        group_text (str): `[[何日前, 該当bool], ...]` 形式のJSON配列テキスト。
        op (str): "any_match" / "none_match" / "empty" のいずれか。

    Returns:
        bool: 条件に一致する場合 True。
    """
    records: list[list[Any]] = json.loads(group_text)
    if op == "empty":
        return len(records) == 0
    if op == "any_match":
        return any(rec[1] for rec in records)
    return len(records) > 0 and not any(rec[1] for rec in records)


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
