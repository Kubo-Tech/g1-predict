"""今回の出走馬を項目ごとに見比べる比較表の画像を生成するモジュール。"""

from dataclasses import dataclass

import pandas as pd
from evaluation.params import WAKU_TO_COLOR_DICT
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle

from ._trend_renderer import ItemTable
from ._trend_table_config import TableColumn

# 色の名前 -> 塗りの色
_FILL_COLORS: dict[str, str] = {
    "green": "#92D050",
    "yellow": "#FFEB9C",
    "blue": "#9DC3E6",
    "red": "#FF9999",
    "orange": "#FFC000",
    "gray": "#BFBFBF",
}
_HEADER_COLOR = "#D9D9D9"
_BODY_COLOR = "#FFFFFF"
_GRID_COLOR = "#000000"
# 枠の色のうち、文字を黒にする明るい色の枠（白・黄・橙・桃）。他の枠は白
_DARK_TEXT_WAKU = (1, 5, 7, 8)
_NO_ROW_TEXT = "-"
_ROW_SEPARATOR = "・"
_FIXED_HEADERS = ("枠", "馬番", "馬名")
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
    tables: list[ItemTable],
    columns: list[TableColumn],
) -> Figure | None:
    """今回の出走馬を項目ごとに見比べる表を、画像にするためのFigureとして生成する。

    行は出走馬を馬番順に並べる。先頭に枠・馬番・馬名の列を置き、続けて columns の順に
    項目の列を置く。各セルには、その馬が当たる行の名前（display_map があれば表示名）を書く。
    複数の行に当たる場合は「・」でつなぎ、当たる行が無い場合は「-」と書く。
    セルは、当たった行のうち先に色付けのルールに当てはまった行の色で塗る。
    記事に表が出ない項目は載せない。

    Args:
        horses (pd.DataFrame): 馬番順の出走馬。
            waku（枠番）・umaban（馬番）・bamei（馬名）の列を持つ。
        tables (list[ItemTable]): カテゴリの各項目の表。
        columns (list[TableColumn]): 比較表に載せる項目と色付けのルール。

    Returns:
        Figure | None: 比較表。載せる項目が1つも無い場合は None。
    """
    table_map = {table.item.name: table for table in tables}
    shown = [
        (column, table_map[column.item_name])
        for column in columns
        if column.item_name in table_map
    ]
    if not shown:
        return None

    header = [_Cell(text, _HEADER_COLOR, bold=True, centered=True) for text in _FIXED_HEADERS]
    for column, _ in shown:
        header.append(_Cell(column.item_name, _HEADER_COLOR, bold=True, centered=True))
    body: list[list[_Cell]] = []
    for horse in horses.to_dict("records"):
        waku = int(horse["waku"])
        umaban = int(horse["umaban"])
        waku_text_color = "black" if waku in _DARK_TEXT_WAKU else "white"
        row = [
            _Cell(str(waku), WAKU_TO_COLOR_DICT[waku], waku_text_color, centered=True),
            _Cell(str(umaban), _BODY_COLOR, centered=True),
            _Cell(str(horse["bamei"]), _BODY_COLOR),
        ]
        for column, table in shown:
            labels = table.entry_rows.get(umaban, [])
            names = _ROW_SEPARATOR.join(table.display_name(label) for label in labels)
            row.append(_Cell(names or _NO_ROW_TEXT, _find_fill_color(column, table, labels)))
        body.append(row)
    return _draw_table(header, body)


def _find_fill_color(column: TableColumn, table: ItemTable, labels: list[str]) -> str:
    """セルを塗る色を返す。

    出走馬が当たる行を表の順に見て、先に色付けのルールに当てはまった行の、
    最初に当てはまったルールの色にする。

    Args:
        column (TableColumn): 比較表の列。
        table (ItemTable): 列の項目の表。
        labels (list[str]): 出走馬が当たる行のラベル。

    Returns:
        str: 塗る色。当てはまるルールが無い場合は背景色。
    """
    for label in labels:
        for rule in column.color_rules:
            if rule.matches(table.display_name(label), table.stats[label]):
                return _FILL_COLORS[rule.color]
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
