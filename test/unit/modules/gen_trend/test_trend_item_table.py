"""build_item_table と該当馬列の単体テスト。"""

from typing import Any
from unittest.mock import MagicMock, patch

from mykeibadb.analytics import RaceCondition

from g1_predict.modules.gen_trend._trend_catalog import TrendCategory, TrendItem
from g1_predict.modules.gen_trend._trend_loader import TrendContext
from g1_predict.modules.gen_trend._trend_models import OTHER_LABEL, RowStats
from g1_predict.modules.gen_trend._trend_renderer import (
    ItemTable,
    _format_item_section,
    build_category_section,
    build_item_table,
)

_RENDERER = "g1_predict.modules.gen_trend._trend_renderer"
_RACE_CODE = "2026092706040911"


def _make_context() -> TrendContext:
    """テスト用 TrendContext を生成する。"""
    return TrendContext(
        manager=MagicMock(),
        condition=RaceCondition(keibajo_codes=["06"], kyori=1200, year_to="2025"),
        race_year=2026,
        race_name="スプリンターズステークス",
        kyori=1200,
        keibajo_code="06",
        shiba_da="芝",
        first_year=2016,
        years=10,
        race_count=10,
    )


def _make_fixed_item(**options: Any) -> TrendItem:
    """枠の固定行を持つ項目を生成する。"""
    config: dict[str, Any] = {
        "source": {"type": "gate_number"},
        "rows": {
            "type": "fixed",
            "items": [
                {"label": "1-4枠", "op": "<=", "value": 4},
                {"label": "5-8枠", "op": ">=", "value": 5},
            ],
            **options.pop("rows_options", {}),
        },
        **options,
    }
    return TrendItem(name="枠順", config=config, condition=None)


def _make_dynamic_item(**rows_options: Any) -> TrendItem:
    """騎手の動的な行を持つ項目を生成する。"""
    return TrendItem(
        name="騎手",
        config={
            "source": {"type": "jockey_name"},
            "rows": {"type": "dynamic", "top_n": 2, **rows_options},
        },
        condition=None,
    )


_STATS = {
    "1-4枠": RowStats(first=1, fourth_plus=3, total=4),
    "5-8枠": RowStats(first=2, second=1, fourth_plus=1, total=4),
}


def _build(
    item: TrendItem,
    stats_map: dict[str, RowStats],
    entry_rows: dict[int, list[str]],
) -> ItemTable | None:
    """集計値と出走馬の判定結果を差し替えて build_item_table を実行する。"""
    with (
        patch(f"{_RENDERER}.compute_stats", return_value=stats_map),
        patch(f"{_RENDERER}.find_entry_rows", return_value=entry_rows),
    ):
        return build_item_table(item, _make_context(), _RACE_CODE)


# --- build_item_table: 出走馬の行 ---


def test_build_item_table_maps_entries_to_fixed_rows() -> None:
    """fixed の項目では、出走馬が当たる行がそのまま馬番 -> 行になる。"""
    table = _build(_make_fixed_item(), _STATS, {1: ["1-4枠"], 2: ["1-4枠"], 9: ["5-8枠"]})
    assert table is not None
    assert table.entry_rows == {1: ["1-4枠"], 2: ["1-4枠"], 9: ["5-8枠"]}
    assert table.horse_nums("1-4枠") == [1, 2]
    assert table.horse_nums("5-8枠") == [9]


def test_build_item_table_dynamic_entry_outside_rows_goes_to_other() -> None:
    """dynamic の項目では、表に出ていない行に当たる馬は「その他」に入る。"""
    stats_map = {
        "A": RowStats(first=3, fourth_plus=1, total=4),
        "B": RowStats(first=1, fourth_plus=2, total=3),
        "C": RowStats(fourth_plus=5, total=5),
    }
    table = _build(_make_dynamic_item(), stats_map, {1: ["A"], 2: ["C"], 3: ["未登場の騎手"]})
    assert table is not None
    assert table.rows == ["A", "B", OTHER_LABEL]
    assert table.entry_rows == {1: ["A"], 2: [OTHER_LABEL], 3: [OTHER_LABEL]}
    assert table.horse_nums(OTHER_LABEL) == [2, 3]


def test_build_item_table_dynamic_other_row_aggregates_stats() -> None:
    """dynamic の項目の「その他」行は、表に出ていない行の集計値を合算する。"""
    stats_map = {
        "A": RowStats(first=3, total=3),
        "B": RowStats(first=1, total=1),
        "C": RowStats(fourth_plus=5, total=5),
    }
    table = _build(_make_dynamic_item(), stats_map, {})
    assert table is not None
    assert table.stats[OTHER_LABEL] == RowStats(fourth_plus=5, total=5)


def test_build_item_table_dynamic_without_other_row_ignores_unlisted_value() -> None:
    """「その他」行が無い dynamic の項目では、表に出ていない行に当たる馬は行に入れない。"""
    item = TrendItem(
        name="騎手",
        config={"source": {"type": "jockey_name"}, "rows": {"type": "dynamic"}},
        condition=None,
    )
    table = _build(item, {"A": RowStats(first=1, total=1)}, {1: ["A"], 2: ["未登場の騎手"]})
    assert table is not None
    assert table.entry_rows == {1: ["A"]}


def test_build_item_table_horse_can_hit_multiple_rows_in_table_order() -> None:
    """複数の行に当たる馬は、表の行の順に並ぶ。"""
    table = _build(_make_fixed_item(), _STATS, {1: ["5-8枠", "1-4枠"]})
    assert table is not None
    assert table.entry_rows == {1: ["1-4枠", "5-8枠"]}


def test_build_item_table_ignores_fixed_rows_not_in_table() -> None:
    """fixed の項目で、表に無い行のラベルは出走馬の行に含めない。"""
    table = _build(_make_fixed_item(), _STATS, {1: ["9枠"]})
    assert table is not None
    assert table.entry_rows == {}


def test_build_item_table_without_entry_race_code_skips_entry_lookup() -> None:
    """出走馬のレースコードが無い場合は、出走馬の判定をしない。"""
    with (
        patch(f"{_RENDERER}.compute_stats", return_value=_STATS),
        patch(f"{_RENDERER}.find_entry_rows") as mock_find,
    ):
        table = build_item_table(_make_fixed_item(), _make_context())
    assert table is not None
    assert table.entry_rows == {}
    mock_find.assert_not_called()


# --- build_item_table: 隠す指定 ---


def test_build_item_table_hide_empty_keeps_row_with_entries() -> None:
    """hide_empty でも、出走馬が当たる行は頭数が0でも隠さない。"""
    stats_map = {"1-4枠": RowStats(first=1, fourth_plus=3, total=4)}
    table = _build(_make_fixed_item(rows_options={"hide_empty": True}), stats_map, {7: ["5-8枠"]})
    assert table is not None
    assert table.rows == ["1-4枠", "5-8枠"]


def test_build_item_table_hide_empty_hides_row_without_entries() -> None:
    """hide_empty では、出走馬が当たらず頭数が0の行を隠す。"""
    stats_map = {"1-4枠": RowStats(first=1, fourth_plus=3, total=4)}
    table = _build(_make_fixed_item(rows_options={"hide_empty": True}), stats_map, {1: ["1-4枠"]})
    assert table is not None
    assert table.rows == ["1-4枠"]


def test_build_item_table_hide_if_empty_keeps_table_with_entries() -> None:
    """hide_if_empty でも、出走馬が当たる表は隠さない。"""
    stats_map = {"1-4枠": RowStats(), "5-8枠": RowStats()}
    table = _build(_make_fixed_item(hide_if_empty=True), stats_map, {3: ["1-4枠"]})
    assert table is not None
    assert table.horse_nums("1-4枠") == [3]


def test_build_item_table_hide_if_empty_hides_table_without_entries() -> None:
    """hide_if_empty では、集計にも出走馬にも該当馬がいない表を隠す。"""
    stats_map = {"1-4枠": RowStats(), "5-8枠": RowStats()}
    assert _build(_make_fixed_item(hide_if_empty=True), stats_map, {}) is None


# --- 該当馬列の書式 ---


def _table_with_entries() -> ItemTable:
    """出走馬が当たる行を持つ表を生成する。"""
    table = _build(_make_fixed_item(), _STATS, {10: ["1-4枠"], 2: ["1-4枠"], 5: ["1-4枠"]})
    assert table is not None
    return table


def test_format_item_section_with_entries_adds_horse_column() -> None:
    """該当馬列には、当たる馬の馬番を昇順にカンマ区切りで書き、当たる馬がいない行は空にする。"""
    lines = _format_item_section(_table_with_entries(), with_entries=True).split("\n")
    assert lines[2] == "| 枠順 | 着度数 | 勝率 | 複率 | 単回 | 複回 | 該当馬 |"
    assert lines[3] == "| --- | --- | --- | --- | --- | --- | --- |"
    assert lines[4] == "| 1-4枠 | 1-0-0-3 | 25% | 25% | 0% | 0% | 2, 5, 10 |"
    assert lines[5] == "| 5-8枠 | 2-1-0-1 | 50% | 75% | 0% | 0% |  |"


def test_format_item_section_without_entries_has_no_horse_column() -> None:
    """出走馬の判定をしない場合は、該当馬列を付けない。"""
    lines = _format_item_section(_table_with_entries(), with_entries=False).split("\n")
    assert lines[2] == "| 枠順 | 着度数 | 勝率 | 複率 | 単回 | 複回 |"
    assert lines[3] == "| --- | --- | --- | --- | --- | --- |"
    assert lines[4] == "| 1-4枠 | 1-0-0-3 | 25% | 25% | 0% | 0% |"


def test_format_item_section_uses_display_map_for_row_label() -> None:
    """行の見出しには display_map の表示名を使う。"""
    item = _make_fixed_item(display_map={"1-4枠": "内枠"})
    table = _build(item, _STATS, {1: ["1-4枠"]})
    assert table is not None
    assert table.display_name("1-4枠") == "内枠"
    assert table.display_name("5-8枠") == "5-8枠"
    assert "| 内枠 | 1-0-0-3 |" in _format_item_section(table, with_entries=True)


# --- build_category_section ---


def test_build_category_section_with_entries_has_horse_column_in_every_table() -> None:
    """with_entries が True なら、カテゴリの全ての表に該当馬列が付く。"""
    category = TrendCategory(name="基本項目", description="d", items=[_make_fixed_item()])
    table = _table_with_entries()
    result = build_category_section(category, _make_context(), [table], with_entries=True)
    assert "| 枠順 | 着度数 | 勝率 | 複率 | 単回 | 複回 | 該当馬 |" in result
