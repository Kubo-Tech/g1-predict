"""_trend_table_image の単体テスト。"""

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
) -> ItemTable:
    """テスト用 ItemTable を生成する。"""
    config = {"display_map": display_map} if display_map else {}
    item = TrendItem(name=name, config=config, condition=None)
    return ItemTable(item=item, rows=list(stats), stats=stats, entry_rows=entry_rows)


def _cells(figure: Figure) -> tuple[list[str], list[str]]:
    """描かれたセルの文字と塗りの色を、見出し行から順に返す。"""
    ax = figure.axes[0]
    texts = [text.get_text() for text in ax.texts]
    fills = [to_hex(patch.get_facecolor()).upper() for patch in ax.patches]
    return texts, fills


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
    figure = make_comparison_table(_HORSES, tables, columns)
    assert figure is not None
    texts, _ = _cells(figure)
    assert texts[:5] == ["枠", "馬番", "馬名", "性別", "所属"]


def test_make_comparison_table_rows_follow_horse_order_and_waku_color() -> None:
    """行は出走馬の順に並び、枠の列は枠の色で塗る。"""
    tables = [_make_table("所属", {"栗東": _GOOD}, {1: ["栗東"], 3: ["栗東"], 16: ["栗東"]})]
    figure = make_comparison_table(_HORSES, tables, [TableColumn("所属", ())])
    assert figure is not None
    texts, fills = _cells(figure)
    # 各行は4セル（枠・馬番・馬名・項目）で、先頭の1行が見出し
    assert texts[4:8] == ["1", "1", "アルファ", "栗東"]
    assert texts[8:12] == ["2", "3", "ベータ", "栗東"]
    assert texts[12:16] == ["8", "16", "ガンマ", "栗東"]
    assert [fills[4], fills[8], fills[12]] == ["#FFFFFF", "#444444", "#EF8FA0"]
    assert fills[:4] == ["#D9D9D9"] * 4


def test_make_comparison_table_cell_text_uses_display_name_and_joins_rows() -> None:
    """セルには当たる行の表示名を書き、複数の行は「・」でつなぐ。"""
    stats = {"継続": _GOOD, "乗り戻り": _BAD}
    tables = [_make_table("継続騎乗", stats, {1: ["継続", "乗り戻り"]}, {"継続": "同じ騎手"})]
    figure = make_comparison_table(_HORSES, tables, [TableColumn("継続騎乗", ())])
    assert figure is not None
    texts, _ = _cells(figure)
    assert texts[7] == "同じ騎手・乗り戻り"


def test_make_comparison_table_horse_without_row_shows_hyphen() -> None:
    """当たる行が無い馬のセルは「-」と書く。"""
    tables = [_make_table("前走レース", {"安田記念": _GOOD}, {1: ["安田記念"]})]
    figure = make_comparison_table(_HORSES, tables, [TableColumn("前走レース", ())])
    assert figure is not None
    texts, _ = _cells(figure)
    assert [texts[7], texts[11], texts[15]] == ["安田記念", "-", "-"]


def test_make_comparison_table_other_row_is_written_as_other() -> None:
    """dynamic の項目で表に出ていない行に当たる馬のセルは「その他」と書く。"""
    tables = [_make_table("騎手", {"武豊": _GOOD, OTHER_LABEL: _BAD}, {3: [OTHER_LABEL]})]
    figure = make_comparison_table(_HORSES, tables, [TableColumn("騎手", ())])
    assert figure is not None
    texts, _ = _cells(figure)
    assert texts[11] == "その他"


# 色付け
def test_make_comparison_table_fills_by_metric_rule() -> None:
    """指標のルールは、馬が当たる行の集計値で塗る。"""
    rule = MetricRule(color="yellow", metric="複勝率", op=">=", value=30)
    tables = [
        _make_table("枠順", {"1枠": _GOOD, "2枠": _BAD}, {1: ["1枠"], 3: ["2枠"]}),
    ]
    figure = make_comparison_table(_HORSES, tables, [TableColumn("枠順", (rule,))])
    assert figure is not None
    _, fills = _cells(figure)
    assert [fills[7], fills[11], fills[15]] == ["#FFEB9C", "#FFFFFF", "#FFFFFF"]


def test_make_comparison_table_fills_by_labels_rule_using_display_name() -> None:
    """行の名前のルールは、表示名で判定して塗る。"""
    rule = LabelsRule(color="blue", labels=("内枠",))
    tables = [_make_table("枠順", {"1-4枠": _GOOD}, {1: ["1-4枠"]}, {"1-4枠": "内枠"})]
    figure = make_comparison_table(_HORSES, tables, [TableColumn("枠順", (rule,))])
    assert figure is not None
    _, fills = _cells(figure)
    assert fills[7] == "#9DC3E6"


def test_make_comparison_table_first_matching_rule_wins() -> None:
    """先頭から評価し、最初に当てはまったルールの色で塗る。"""
    rules = (
        LabelsRule(color="orange", labels=("1枠",)),
        MetricRule(color="yellow", metric="複勝率", op=">=", value=30),
    )
    tables = [_make_table("枠順", {"1枠": _GOOD}, {1: ["1枠"]})]
    figure = make_comparison_table(_HORSES, tables, [TableColumn("枠順", rules)])
    assert figure is not None
    _, fills = _cells(figure)
    assert fills[7] == "#FFC000"


def test_make_comparison_table_metric_rule_skips_row_without_horses() -> None:
    """頭数が0の行には指標のルールを当てはめない。"""
    rule = MetricRule(color="gray", metric="複勝率", op="==", value=0)
    tables = [_make_table("枠順", {"1枠": RowStats()}, {1: ["1枠"]})]
    figure = make_comparison_table(_HORSES, tables, [TableColumn("枠順", (rule,))])
    assert figure is not None
    _, fills = _cells(figure)
    assert fills[7] == "#FFFFFF"


def test_make_comparison_table_multiple_rows_use_first_row_matching_a_rule() -> None:
    """複数の行に当たる馬は、先にルールに当てはまった行の色で塗る。"""
    rule = MetricRule(color="green", metric="複勝率", op=">=", value=30)
    tables = [_make_table("継続騎乗", {"継続": _BAD, "乗り戻り": _GOOD}, {1: ["継続", "乗り戻り"]})]
    figure = make_comparison_table(_HORSES, tables, [TableColumn("継続騎乗", (rule,))])
    assert figure is not None
    _, fills = _cells(figure)
    assert fills[7] == "#92D050"


def test_make_comparison_table_without_rules_leaves_cells_white() -> None:
    """色付けのルールが無い列は塗らない。"""
    tables = [_make_table("所属", {"栗東": _GOOD}, {1: ["栗東"]})]
    figure = make_comparison_table(_HORSES, tables, [TableColumn("所属", ())])
    assert figure is not None
    _, fills = _cells(figure)
    assert fills[7] == "#FFFFFF"


# 記事に表が出ない項目
def test_make_comparison_table_skips_items_without_table() -> None:
    """記事に表が出ない項目は載せない。"""
    tables = [_make_table("所属", {"栗東": _GOOD}, {})]
    columns = [TableColumn("前走G1着順", ()), TableColumn("所属", ())]
    figure = make_comparison_table(_HORSES, tables, columns)
    assert figure is not None
    texts, _ = _cells(figure)
    assert texts[:4] == ["枠", "馬番", "馬名", "所属"]


def test_make_comparison_table_returns_none_without_any_item() -> None:
    """載せる項目が1つも無い場合は None を返す。"""
    assert make_comparison_table(_HORSES, [], [TableColumn("前走G1着順", ())]) is None
