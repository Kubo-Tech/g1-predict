"""今回の出走馬を項目ごとに見比べる比較表の画像を生成するモジュール。"""

from dataclasses import dataclass

import pandas as pd
from evaluation.params import WAKU_TO_COLOR_DICT
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle

from g1_predict.modules.utils.race_dynamics import TOP_RANK_COLORS

from ._trend_models import RowStats
from ._trend_renderer import ItemTable
from ._trend_table_config import FILL_COLORS, TableColumn

_HEADER_COLOR = "#D9D9D9"
_BODY_COLOR = "#FFFFFF"
_GRID_COLOR = "#000000"
# 枠の色のうち、文字を黒にする明るい色の枠（白・黄・橙・桃）。他の枠は白
_DARK_TEXT_WAKU = (1, 5, 7, 8)
_NO_ROW_TEXT = "-"
_ROW_SEPARATOR = "・"
_FIXED_HEADERS = ("枠", "馬番", "馬名")
# 馬名の右に置く、黄色で塗ったセルの数を書く列
_PLUS_HEADER = "＋データ"
_PLUS_COLOR = "yellow"
# 灰色で塗ったセルの数を書く列。灰色のセルがある項目は、黄色と同様に見比べる材料として列を残す
_MINUS_HEADER = "－データ"
_MINUS_COLOR = "gray"
# －データの数の順位の色（＋データの順位の色を HLS 色空間で彩度だけ半分にした色）
_MINUS_RANK_COLORS: dict[int, str] = {1: "#DFD8A0", 2: "#D9E2F2", 3: "#DCC8B4"}
# 馬名の右に置く、＋データ・－データの列の数
_COUNT_COLUMNS = 2
_FONT = FontProperties(family="Noto Sans CJK JP", size=10)
_BOLD_FONT = FontProperties(family="Noto Sans CJK JP", size=10, weight="bold")
# セルの寸法（インチ）
_ROW_HEIGHT = 0.3
_CELL_PADDING = 0.1
_MIN_COLUMN_WIDTH = 0.5
# 外枠の罫線が画像の端で切れないよう、表の周囲に空ける余白（インチ）
_MARGIN = 0.03


@dataclass(frozen=True)
class _Cell:
    """表のセル1つ。

    Attributes:
        text (str): セルに書く文字。
        fill (str): 塗りの色。
        text_color (str): 文字の色。
        bold (bool): 文字を太字にするか。
        centered (bool): 文字を中央に揃えるか（Falseなら左揃え）。
    """

    text: str
    fill: str
    text_color: str = "black"
    bold: bool = False
    centered: bool = False


def make_comparison_table(
    horses: pd.DataFrame,
    shown: list[tuple[TableColumn, list[ItemTable]]],
) -> Figure | None:
    """今回の出走馬を項目ごとに見比べる表を、画像にするためのFigureとして生成する。

    行は出走馬を馬番順に並べる。先頭に枠・馬番・馬名・＋データ・－データの列を置き、続けて
    shown の順に項目の列を置く。各セルには、その馬の値（display_map があれば表示名）を書く。
    dynamic の項目で記事の表では「その他」にまとめた値も、騎手名などの値そのものを書く。
    複数の行に当たる場合は「・」でつなぎ、当たる行が無い場合は「-」と書く。ただし fixed の項目
    （前年3着以内・前年5着以内のように行の範囲が重なる項目）は、当たる行のうち表の先頭に近い行だけを書く。
    「前走クラス着順」の列は、まとめた項目の値の前にクラスの略称を付けて「G1 1着」のように書く。
    セルは、値のうち先に色付けのルールに当てはまった値の色で塗る。行の名前のルールはセルに書く値で、
    指標のルールは値が当たる記事の表の行の集計値で判定する。
    黄色にも灰色にも塗ったセルが無い項目の列は載せない。枠・馬番・馬名・＋データ・－データの列は
    常に載せる。
    「＋データ」の列には、その馬の項目の列のうち黄色で塗ったセルの数を書く。
    ＋データの数が多い順に1位から3位までを、展開評価値のグラフの順位と同じ色
    （netkeiba の人気・上がり順位の色）で塗る。同じ数の馬は同じ順位とし、次の数を次の順位とする
    （7・5・5・4 なら 7 が1位、5 が2位、4 が3位）。0 は塗らない。
    「－データ」の列には、灰色で塗ったセルの数を書き、同じ順位付けで、＋データの順位の色の
    彩度を半分にした色で塗る。

    Args:
        horses (pd.DataFrame): 馬番順の出走馬。
            waku（枠番）・umaban（馬番）・bamei（馬名）の列を持つ。
        shown (list[tuple[TableColumn, list[ItemTable]]]): 比較表に載せる列と、列に載せる項目の
            記事の表。

    Returns:
        Figure | None: 比較表。載せる項目の列が1つも無い場合は None。
    """
    header = [
        _Cell(text, _HEADER_COLOR, bold=True, centered=True)
        for text in (*_FIXED_HEADERS, _PLUS_HEADER, _MINUS_HEADER)
    ]
    marked_fills = {FILL_COLORS[_PLUS_COLOR], FILL_COLORS[_MINUS_COLOR]}
    column_marked = [False] * len(shown)
    body: list[list[_Cell]] = []
    plus_counts: list[int] = []
    minus_counts: list[int] = []
    for horse in horses.to_dict("records"):
        waku = int(horse["waku"])
        umaban = int(horse["umaban"])
        waku_text_color = "black" if waku in _DARK_TEXT_WAKU else "white"
        row = [
            _Cell(str(waku), WAKU_TO_COLOR_DICT[waku], waku_text_color, centered=True),
            _Cell(str(umaban), _BODY_COLOR, centered=True),
            _Cell(str(horse["bamei"]), _BODY_COLOR),
        ]
        plus_count = 0
        minus_count = 0
        for index, (column, tables) in enumerate(shown):
            entries = [
                entry for table in tables for entry in _cell_entries(column, table, umaban)
            ]
            names = _ROW_SEPARATOR.join(text for text, _ in entries)
            fill = _find_fill_color(column, entries)
            if fill == FILL_COLORS[_PLUS_COLOR]:
                plus_count += 1
            if fill == FILL_COLORS[_MINUS_COLOR]:
                minus_count += 1
            if fill in marked_fills:
                column_marked[index] = True
            row.append(_Cell(names or _NO_ROW_TEXT, fill))
        body.append(row)
        plus_counts.append(plus_count)
        minus_counts.append(minus_count)
    if not any(column_marked):
        return None
    fixed_count = len(_FIXED_HEADERS) + _COUNT_COLUMNS
    kept = [True] * fixed_count + column_marked
    header.extend(
        _Cell(column.item_name, _HEADER_COLOR, bold=True, centered=True) for column, _ in shown
    )
    header = [cell for cell, keep in zip(header, kept, strict=True) if keep]
    plus_rank_colors = _rank_colors(plus_counts, TOP_RANK_COLORS)
    minus_rank_colors = _rank_colors(minus_counts, _MINUS_RANK_COLORS)
    for index, row in enumerate(body):
        plus_fill = plus_rank_colors.get(plus_counts[index], _BODY_COLOR)
        minus_fill = minus_rank_colors.get(minus_counts[index], _BODY_COLOR)
        # ＋データ・－データの列は馬名の右に置く
        row.insert(len(_FIXED_HEADERS), _Cell(str(plus_counts[index]), plus_fill, centered=True))
        row.insert(
            len(_FIXED_HEADERS) + 1, _Cell(str(minus_counts[index]), minus_fill, centered=True)
        )
        body[index] = [cell for cell, keep in zip(row, kept, strict=True) if keep]
    return _draw_table(header, body)


def _rank_colors(counts: list[int], rank_colors: dict[int, str]) -> dict[int, str]:
    """データの数ごとの塗りの色を返す。

    数が多い順に、同じ数は同じ順位として1位から3位までに色を割り当てる。0 には割り当てない。

    Args:
        counts (list[int]): 出走馬ごとのデータの数。
        rank_colors (dict[int, str]): 順位 -> 塗りの色。

    Returns:
        dict[int, str]: データの数 -> 塗りの色。3位までに入らない数は含まない。
    """
    ranked = sorted({count for count in counts if count > 0}, reverse=True)
    return {
        count: rank_colors[rank]
        for rank, count in enumerate(ranked, start=1)
        if rank in rank_colors
    }


def _cell_entries(
    column: TableColumn, table: ItemTable, umaban: int
) -> list[tuple[str, RowStats]]:
    """出走馬のセルに書く値と、その値が当たる記事の表の行の集計値を返す。

    fixed の項目は、当たる行のうち表の先頭に近い行だけにする。
    「前走クラス着順」の列では、値の前にクラスの略称を付ける。

    Args:
        column (TableColumn): 比較表の列。
        table (ItemTable): 列に載せる項目の表。
        umaban (int): 出走馬の馬番。

    Returns:
        list[tuple[str, RowStats]]: セルに書く値（表示名）と行の集計値。当たる行が無い場合は空。
    """
    values = table.entry_values.get(umaban, [])
    if table.item.config.get("rows", {}).get("type") == "fixed":
        values = values[:1]
    prefix = f"{table.item.class_label} " if column.parts else ""
    return [
        (prefix + table.display_name(value), table.stats[table.row_of_value(value)])
        for value in values
    ]


def _find_fill_color(column: TableColumn, entries: list[tuple[str, RowStats]]) -> str:
    """セルを塗る色を返す。

    セルの値を順に見て、先に色付けのルールに当てはまった値の、最初に当てはまったルールの色にする。
    行の名前のルールはセルに書く値で、指標のルールは値が当たる記事の表の行の集計値で判定する。

    Args:
        column (TableColumn): 比較表の列。
        entries (list[tuple[str, RowStats]]): セルに書く値と行の集計値。

    Returns:
        str: 塗る色。当てはまるルールが無い場合は背景色。
    """
    for text, stats in entries:
        for rule in column.color_rules:
            if rule.matches(text, stats):
                return FILL_COLORS[rule.color]
    return _BODY_COLOR


def _draw_table(header: list[_Cell], body: list[list[_Cell]]) -> Figure:
    """見出しとセルから表を描く。

    列の幅は、見出しとセルの文字の幅に合わせる。

    Args:
        header (list[_Cell]): 見出しのセル。
        body (list[list[_Cell]]): 本体のセル（行 x 列）。

    Returns:
        Figure: 描いた表。
    """
    figure = Figure()
    renderer = FigureCanvasAgg(figure).get_renderer()

    def cell_width(cell: _Cell) -> float:
        font = _BOLD_FONT if cell.bold else _FONT
        width, _, _ = renderer.get_text_width_height_descent(cell.text, font, ismath=False)
        return float(width) / figure.dpi + 2 * _CELL_PADDING

    widths = [
        max(_MIN_COLUMN_WIDTH, *(cell_width(cell) for cell in column_cells))
        for column_cells in zip(header, *body, strict=True)
    ]
    total_width = sum(widths)
    total_height = _ROW_HEIGHT * (len(body) + 1)
    figure.set_size_inches(total_width + 2 * _MARGIN, total_height + 2 * _MARGIN)
    ax = figure.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_xlim(-_MARGIN, total_width + _MARGIN)
    ax.set_ylim(total_height + _MARGIN, -_MARGIN)
    ax.axis("off")

    for row_index, row in enumerate([header, *body]):
        left = 0.0
        for cell, width in zip(row, widths, strict=True):
            _draw_cell(ax, cell, left, _ROW_HEIGHT * row_index, width)
            left += width
    return figure


def _draw_cell(ax: Axes, cell: _Cell, left: float, top: float, width: float) -> None:
    """セル1つを、塗りの色・罫線・文字つきで描く。

    Args:
        ax (Axes): 描画先。座標の単位はインチで、下向きが正。
        cell (_Cell): 描くセル。
        left (float): セルの左端。
        top (float): セルの上端。
        width (float): セルの幅。
    """
    ax.add_patch(
        Rectangle(
            (left, top),
            width,
            _ROW_HEIGHT,
            facecolor=cell.fill,
            edgecolor=_GRID_COLOR,
            linewidth=0.5,
        )
    )
    x = left + width / 2 if cell.centered else left + _CELL_PADDING
    ax.text(
        x,
        top + _ROW_HEIGHT / 2,
        cell.text,
        ha="center" if cell.centered else "left",
        va="center",
        color=cell.text_color,
        fontproperties=_BOLD_FONT if cell.bold else _FONT,
    )
