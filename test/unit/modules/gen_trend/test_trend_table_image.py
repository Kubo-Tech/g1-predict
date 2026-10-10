"""_trend_table_image の単体テスト。"""

from typing import Any

import pandas as pd
from matplotlib.colors import to_hex
from matplotlib.figure import Figure

from g1_predict.modules.gen_trend._trend_catalog import TrendItem
from g1_predict.modules.gen_trend._trend_models import OTHER_LABEL, RowStats
from g1_predict.modules.gen_trend._trend_renderer import ItemTable
from g1_predict.modules.gen_trend._trend_table_config import (
    LabelsRule,
    MetricRule,
    TableColumn,
)
from g1_predict.modules.gen_trend._trend_table_image import make_comparison_table

_HORSES = pd.DataFrame(
    {"waku": [1, 2, 8], "umaban": [1, 3, 16], "bamei": ["アルファ", "ベータ", "ガンマ"]}
)


def _make_table(
    name: str,
    stats: dict[str, RowStats],
    entry_rows: dict[int, list[str]],
    display_map: dict[str, str] | None = None,
    rows_type: str | None = None,
    entry_values: dict[int, list[str]] | None = None,
) -> ItemTable:
    """テスト用 ItemTable を生成する。"""
    config: dict[str, Any] = {"display_map": display_map} if display_map else {}
    if rows_type is not None:
        config["rows"] = {"type": rows_type}
    item = TrendItem(name=name, config=config, condition=None)
    return ItemTable(
        item=item,
        rows=list(stats),
        stats=stats,
        entry_rows=entry_rows,
        entry_values=entry_rows if entry_values is None else entry_values,
    )


def _cells(figure: Figure) -> tuple[list[str], list[str]]:
    """描かれたセルの文字と塗りの色を、見出し行から順に返す。"""
    ax = figure.axes[0]
    texts = [text.get_text() for text in ax.texts]
    fills = [to_hex(patch.get_facecolor()).upper() for patch in ax.patches]
    return texts, fills


def _draw(tables: list[ItemTable], columns: list[TableColumn]) -> Figure:
    """列と同じ名前の項目の表を組にして、比較表を描く。"""
    table_map = {table.item.name: table for table in tables}
    return make_comparison_table(
        _HORSES, [(column, [table_map[column.item_name]]) for column in columns]
    )


_GOOD = RowStats(first=2, second=1, third=0, fourth_plus=7, total=10)
_BAD = RowStats(fourth_plus=10, total=10)


# 正常系
def test_make_comparison_table_has_fixed_columns_then_item_columns() -> None:
    """先頭に枠・馬番・馬名の列を置き、続けて項目の列を columns の順に置く。"""
    tables = [
        _make_table("所属", {"栗東": _GOOD}, {}),
        _make_table("性別", {"牡": _GOOD}, {}),
    ]
    columns = [TableColumn("性別", ()), TableColumn("所属", ())]
    figure = _draw(tables, columns)
    texts, _ = _cells(figure)
    assert texts[:6] == ["枠", "馬番", "馬名", "性別", "所属", "好データ"]


def test_make_comparison_table_rows_follow_horse_order_and_waku_color() -> None:
    """行は出走馬の順に並び、枠の列は枠の色で塗る。"""
    tables = [_make_table("所属", {"栗東": _GOOD}, {1: ["栗東"], 3: ["栗東"], 16: ["栗東"]})]
    figure = _draw(tables, [TableColumn("所属", ())])
    texts, fills = _cells(figure)
    # 各行は5セル（枠・馬番・馬名・項目・好データ）で、先頭の1行が見出し
    assert texts[5:9] == ["1", "1", "アルファ", "栗東"]
    assert texts[10:14] == ["2", "3", "ベータ", "栗東"]
    assert texts[15:19] == ["8", "16", "ガンマ", "栗東"]
    assert [fills[5], fills[10], fills[15]] == ["#FFFFFF", "#444444", "#EF8FA0"]
    assert fills[:5] == ["#D9D9D9"] * 5


def test_make_comparison_table_cell_text_uses_display_name_and_joins_rows() -> None:
    """セルには当たる行の表示名を書き、複数の行は「・」でつなぐ。"""
    stats = {"継続": _GOOD, "乗り戻り": _BAD}
    tables = [_make_table("継続騎乗", stats, {1: ["継続", "乗り戻り"]}, {"継続": "同じ騎手"})]
    figure = _draw(tables, [TableColumn("継続騎乗", ())])
    texts, _ = _cells(figure)
    assert texts[8] == "同じ騎手・乗り戻り"


def test_make_comparison_table_fixed_item_shows_first_hit_row_only() -> None:
    """fixed の項目で複数の行に当たる馬は、表の先頭に近い行だけを書き、その行の色で塗る。"""
    stats = {"前年3着以内": _BAD, "前年5着以内": _GOOD}
    rule = MetricRule(color="green", metric="複勝率", op=">=", value=30)
    tables = [
        _make_table(
            "リピーター", stats, {1: ["前年3着以内", "前年5着以内"]}, rows_type="fixed"
        )
    ]
    figure = _draw(tables, [TableColumn("リピーター", (rule,))])
    texts, fills = _cells(figure)
    assert texts[8] == "前年3着以内"
    assert fills[8] == "#FFFFFF"


def test_make_comparison_table_horse_without_row_shows_hyphen() -> None:
    """当たる行が無い馬のセルは「-」と書く。"""
    tables = [_make_table("前走レース", {"安田記念": _GOOD}, {1: ["安田記念"]})]
    figure = _draw(tables, [TableColumn("前走レース", ())])
    texts, _ = _cells(figure)
    assert [texts[8], texts[13], texts[18]] == ["安田記念", "-", "-"]


def test_make_comparison_table_dynamic_writes_value_instead_of_other() -> None:
    """dynamic の項目で記事の表では「その他」にまとめた馬も、セルには値そのものを書く。"""
    stats = {"武豊": _GOOD, OTHER_LABEL: _BAD}
    tables = [
        _make_table(
            "騎手",
            stats,
            {1: ["武豊"], 3: [OTHER_LABEL]},
            rows_type="dynamic",
            entry_values={1: ["武豊"], 3: ["坂井瑠星"]},
        )
    ]
    gray = MetricRule(color="gray", metric="複勝率", op="==", value=0)
    yellow = LabelsRule(color="yellow", labels=("坂井瑠星",))
    figure = _draw(tables, [TableColumn("騎手", (gray, yellow))])
    texts, fills = _cells(figure)
    assert [texts[8], texts[13]] == ["武豊", "坂井瑠星"]
    # 指標のルールは「その他」行の集計値で判定する
    assert fills[13] == "#BFBFBF"

    figure = _draw(tables, [TableColumn("騎手", (yellow,))])
    _, fills = _cells(figure)
    # 行の名前のルールはセルに書く値で判定する
    assert fills[13] == "#FFEB9C"


def test_make_comparison_table_fills_by_metric_rule() -> None:
    """指標のルールは、馬が当たる行の集計値で塗る。"""
    rule = MetricRule(color="yellow", metric="複勝率", op=">=", value=30)
    tables = [
        _make_table("枠順", {"1枠": _GOOD, "2枠": _BAD}, {1: ["1枠"], 3: ["2枠"]}),
    ]
    figure = _draw(tables, [TableColumn("枠順", (rule,))])
    _, fills = _cells(figure)
    assert [fills[8], fills[13], fills[18]] == ["#FFEB9C", "#FFFFFF", "#FFFFFF"]


def test_make_comparison_table_fills_by_labels_rule_using_display_name() -> None:
    """行の名前のルールは、表示名で判定して塗る。"""
    rule = LabelsRule(color="blue", labels=("内枠",))
    tables = [_make_table("枠順", {"1-4枠": _GOOD}, {1: ["1-4枠"]}, {"1-4枠": "内枠"})]
    figure = _draw(tables, [TableColumn("枠順", (rule,))])
    _, fills = _cells(figure)
    assert fills[8] == "#9DC3E6"


def test_make_comparison_table_first_matching_rule_wins() -> None:
    """先頭から評価し、最初に当てはまったルールの色で塗る。"""
    rules = (
        LabelsRule(color="orange", labels=("1枠",)),
        MetricRule(color="yellow", metric="複勝率", op=">=", value=30),
    )
    tables = [_make_table("枠順", {"1枠": _GOOD}, {1: ["1枠"]})]
    figure = _draw(tables, [TableColumn("枠順", rules)])
    _, fills = _cells(figure)
    assert fills[8] == "#FFC000"


def test_make_comparison_table_metric_rule_skips_row_without_horses() -> None:
    """頭数が0の行には指標のルールを当てはめない。"""
    rule = MetricRule(color="gray", metric="複勝率", op="==", value=0)
    tables = [_make_table("枠順", {"1枠": RowStats()}, {1: ["1枠"]})]
    figure = _draw(tables, [TableColumn("枠順", (rule,))])
    _, fills = _cells(figure)
    assert fills[8] == "#FFFFFF"


def test_make_comparison_table_multiple_rows_use_first_row_matching_a_rule() -> None:
    """複数の行に当たる馬は、先にルールに当てはまった行の色で塗る。"""
    rule = MetricRule(color="green", metric="複勝率", op=">=", value=30)
    tables = [_make_table("継続騎乗", {"継続": _BAD, "乗り戻り": _GOOD}, {1: ["継続", "乗り戻り"]})]
    figure = _draw(tables, [TableColumn("継続騎乗", (rule,))])
    _, fills = _cells(figure)
    assert fills[8] == "#92D050"


def test_make_comparison_table_without_rules_leaves_cells_white() -> None:
    """色付けのルールが無い列は塗らない。"""
    tables = [_make_table("所属", {"栗東": _GOOD}, {1: ["栗東"]})]
    figure = _draw(tables, [TableColumn("所属", ())])
    _, fills = _cells(figure)
    assert fills[8] == "#FFFFFF"


def test_make_comparison_table_class_finish_column_prefixes_class_label() -> None:
    """前走クラス着順の列は、まとめた項目の値の前にクラスの略称を付けて書き、その値で塗る。"""

    def finish_table(name: str, class_label: str, entry_rows: dict[int, list[str]]) -> ItemTable:
        item = TrendItem(
            name=name, config={"rows": {"type": "fixed"}}, condition=None, class_label=class_label
        )
        stats = {"1着": _GOOD, "10着以下": _BAD}
        return ItemTable(
            item=item, rows=list(stats), stats=stats, entry_rows=entry_rows, entry_values=entry_rows
        )

    column = TableColumn(
        "前走クラス着順",
        (LabelsRule(color="yellow", labels=("G1 1着",)),),
        parts=("前走G1着順", "前走オープン着順"),
    )
    tables = [
        finish_table("前走G1着順", "G1", {1: ["1着"]}),
        finish_table("前走オープン着順", "OP", {3: ["10着以下"]}),
    ]
    figure = make_comparison_table(_HORSES, [(column, tables)])
    texts, fills = _cells(figure)
    assert texts[3:5] == ["前走クラス着順", "好データ"]
    assert [texts[8], texts[13], texts[18]] == ["G1 1着", "OP 10着以下", "-"]
    assert [fills[8], fills[13]] == ["#FFEB9C", "#FFFFFF"]


def test_make_comparison_table_good_column_counts_yellow_cells() -> None:
    """右端の好データ列には、その馬の項目の列のうち黄色で塗ったセルの数を書く。"""
    yellow = MetricRule(color="yellow", metric="複勝率", op=">=", value=30)
    green = MetricRule(color="green", metric="複勝率", op=">=", value=30)
    tables = [
        _make_table("枠順", {"1枠": _GOOD, "2枠": _BAD}, {1: ["1枠"], 3: ["2枠"]}),
        _make_table("所属", {"栗東": _GOOD}, {1: ["栗東"], 3: ["栗東"]}),
        _make_table("性別", {"牡": _GOOD}, {1: ["牡"]}),
    ]
    columns = [
        TableColumn("枠順", (yellow,)),
        TableColumn("所属", (yellow,)),
        TableColumn("性別", (green,)),
    ]
    figure = _draw(tables, columns)
    texts, fills = _cells(figure)
    # 各行は7セル（枠・馬番・馬名・項目3列・好データ）で、先頭の1行が見出し
    assert [texts[13], texts[20], texts[27]] == ["2", "1", "0"]
    assert fills[13] == "#FFFFFF"
