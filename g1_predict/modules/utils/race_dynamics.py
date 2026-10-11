"""記事に載せる展開評価（相関係数の表・標準化散布図・総合評価の棒グラフ）を生成するユーティリティ。"""

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

import pandas as pd
from evaluation import RaceDynamicsResult, evaluate_race_dynamics, make_time_plot
from evaluation.params import WAKU_TO_COLOR_DICT
from keiba_data_interface import DataInterface
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle
from race_data import RaceData

# 展開評価の相関係数カラム
DYNAMICS_COLUMNS: tuple[str, ...] = ("差し有利度", "外枠有利度", "外有利度")
# 記事に載せる差し有利度・外枠有利度・外有利度の説明
DYNAMICS_DESCRIPTION = (
    "差し有利度・外枠有利度・外有利度は、それぞれ4角通過位置・馬番・コーナーでの"
    "内外の位置と走破タイムの相関係数を100倍したもの。正なら差し・外枠・外を回した馬が有利。"
)
# 記事に載せる展開評価値の説明
TOTAL_EVALUATION_DESCRIPTION = (
    "展開評価値は、展開（4角の位置・馬番・コーナーでの内外）の有利不利で"
    "走破タイムを補正した値。大きいほど展開の不利をはね返して好走した馬。"
)
# MATLABの標準色の1色目（通常の棒）・2色目（強調する馬の棒）・3色目（今回の出走馬の棒）
_BAR_COLOR = "#0072BD"
_HIGHLIGHT_COLOR = "#D95319"
_RUNNER_COLOR = "#EDB120"
# 枠の色のうち、馬番の文字を黒にする明るい色の枠（白・黄・橙・桃）。他の枠は白
_DARK_TEXT_WAKU = (1, 5, 7, 8)
_JAPANESE_FONT = FontProperties(family="Noto Sans CJK JP")
_JAPANESE_BOLD_FONT = FontProperties(family="Noto Sans CJK JP", weight="bold")
# グラフの寸法（インチ）。左側の余白に馬番・評価値などの列を置く
_CHART_WIDTH = 9.0
_CHART_RIGHT = 0.15
_CHART_TOP = 0.4
_CHART_BOTTOM = 0.4
_CHART_ROW_HEIGHT = 0.32
_CHART_BAR_HEIGHT = 0.7
# 左側の列とグラフの間の余白（インチ）
_COLUMN_GAP = 0.2
# 馬番・順位を囲む四角の幅（インチ）
_BOX_WIDTH = 0.26
# 順位の1〜3位を囲む四角の色（netkeibaの人気・上がり順位の色）
TOP_RANK_COLORS = {1: "#FFF080", 2: "#CCDFFF", 3: "#F0C8A0"}
# 横軸の範囲。範囲を超える評価値の棒は端で切れる
_CHART_LIMIT = 1.0
_CHART_TICKS = (-1.0, -0.5, 0.0, 0.5, 1.0)
# 過去走の展開評価値の折れ線グラフの寸法（インチ）
_TREND_FIGSIZE = (6.0, 3.0)
# 有利度の推移の折れ線グラフの縦軸の範囲と目盛り（相関係数を100倍した値）
_HISTORY_LIMIT = 100.0
_HISTORY_TICKS = (-100.0, -50.0, 0.0, 50.0, 100.0)
# 折れ線の点に書く数値を点から離す距離（ポイント）
_TREND_LABEL_OFFSET = 8
# 縦軸の端からこの割合の範囲にある点は、数値を図の内側に書く（外側に書くと図からはみ出すため）
_TREND_LABEL_EDGE_MARGIN = 0.2
# 馬名を0から離す距離（横軸の値）
_NAME_OFFSET = 0.02


def evaluate_race_dynamics_with_plot(
    race_code: str,
    data_interface: DataInterface,
    reference_date: date,
) -> tuple[RaceDynamicsResult | None, Figure | None]:
    """レースの展開評価を計算する。

    RaceDataを1回だけ取得し、相関係数の計算と標準化散布図の生成の両方に使い回す。
    1000m直線コースは展開評価の対象外のため、両方Noneを返す。
    展開評価が使うのはレース結果とコーナー通過順のみのため、払戻情報は取得しない。

    Args:
        race_code (str): 評価対象レースのrace_code。
        data_interface (DataInterface): 展開評価に使うDataInterface。
        reference_date (date): 未来レースの判定基準日。評価対象レースの開催日より後の
            日付を渡すと、確定済みのレースとして評価する。

    Returns:
        RaceDynamicsResult | None: 展開評価の結果（馬ごとの評価と相関係数）。対象外レースはNone。
        Figure | None: 標準化散布図。対象外レースはNone。

    Raises:
        CornerDataError: レース結果情報または4コーナーの通過順データが存在しない場合。
    """
    race_data = RaceData(
        race_code=race_code,
        data_interface=data_interface,
        reference_date=reference_date,
    )
    if race_data.is_straight_race():
        return None, None

    race_data.fetch_race_result()
    race_data.fetch_race_result_info()
    result = evaluate_race_dynamics(race_data)
    figure = make_time_plot(race_data)
    return result, figure


def format_correlation(cor_df: pd.DataFrame | None, column: str) -> str:
    """相関係数を100倍し、符号付きの整数パーセントの文字列に整形する。

    Args:
        cor_df (pd.DataFrame | None): 展開評価の相関係数DataFrame（1行）。
            対象外レースはNone。
        column (str): カラム名（差し有利度 / 外枠有利度 / 外有利度）。

    Returns:
        str: 符号付きの整数パーセントの文字列（例: "+45%"）。NaN、または対象外レースは "-"。
    """
    if cor_df is None:
        return "-"
    value = cor_df[column].iloc[0]
    if pd.isna(value):
        return "-"
    return f"{round(float(value) * 100):+d}%"


def build_dynamics_table_lines(cor_df: pd.DataFrame) -> list[str]:
    """展開評価の相関係数の表（ヘッダー・区切り・値の3行）を生成する。

    Args:
        cor_df (pd.DataFrame): 展開評価の相関係数DataFrame（1行）。

    Returns:
        list[str]: Markdownの表の行リスト。
    """
    values = [format_correlation(cor_df, column) for column in DYNAMICS_COLUMNS]
    return [
        "| " + " | ".join(DYNAMICS_COLUMNS) + " |",
        "| --- | --- | --- |",
        "| " + " | ".join(values) + " |",
    ]


@dataclass(frozen=True)
class _ChartColumn:
    """棒グラフの左側に置く列。

    Attributes:
        header (str): 見出し。
        key (str): 行のDataFrameのカラム名。
        kind (Literal["umaban", "rank", "value"]): 列の種類。umaban は枠の色の四角で囲み、
            rank は1〜3位を順位ごとの色の四角で囲み（値が無ければ「-」）、
            value は符号付き小数2桁で書く。
        width (float): 列の幅（インチ）。
    """

    header: str
    key: str
    kind: Literal["umaban", "rank", "value"]
    width: float


def make_total_evaluation_chart(
    eval_df: pd.DataFrame,
    result_df: pd.DataFrame,
    highlight_horse_nums: Collection[int] = (),
    runner_horse_nums: Collection[int] = (),
) -> Figure:
    """馬ごとの展開の総合評価を、着順の順に並べた横向きの棒グラフにする。

    上から確定着順の順に並べ、確定着順が無い馬（競走中止など）は最後に馬番順で並べる。
    総合評価が無い馬（競走除外など）は載せない。
    グラフの左側に着順・馬番・評価値・評価順位を縦に揃えて書く。

    Args:
        eval_df (pd.DataFrame): 展開評価の馬ごとの評価DataFrame（馬番・総合評価カラムを使う）。
        result_df (pd.DataFrame): レース結果DataFrame（馬番・枠番・確定着順・馬名カラムを使う）。
        highlight_horse_nums (Collection[int]): 棒を2色目にし、左側の列と馬名を
            太字にする馬の馬番。
        runner_horse_nums (Collection[int]): 棒を3色目にし、馬名を太字にする馬の馬番。

    Returns:
        Figure: 棒グラフ。
    """
    horses = result_df.set_index(result_df["馬番"].astype(int))
    evaluated = eval_df[eval_df["総合評価"].notna()]
    umabans = evaluated["馬番"].astype(int).tolist()
    rows = pd.DataFrame(
        {
            "馬番": umabans,
            "枠番": [horses.loc[umaban, "枠番"] for umaban in umabans],
            "馬名": [str(horses.loc[umaban, "馬名"]) for umaban in umabans],
            "value": evaluated["総合評価"].astype(float).to_numpy(),
            "着順": [horses.loc[umaban, "確定着順"] for umaban in umabans],
        }
    )
    rows["評価順位"] = rows["value"].rank(method="min", ascending=False)
    rows["bar_color"] = [
        _HIGHLIGHT_COLOR
        if umaban in highlight_horse_nums
        else _RUNNER_COLOR
        if umaban in runner_horse_nums
        else _BAR_COLOR
        for umaban in umabans
    ]
    rows["bold"] = [umaban in highlight_horse_nums for umaban in umabans]
    rows["name_bold"] = [umaban in runner_horse_nums for umaban in umabans]
    rows = rows.sort_values(["着順", "馬番"], na_position="last").reset_index(drop=True)
    columns = (
        _ChartColumn("着順", "着順", "rank", 0.6),
        _ChartColumn("馬番", "馬番", "umaban", 0.5),
        _ChartColumn("評価値", "value", "value", 0.75),
        _ChartColumn("評価順位", "評価順位", "rank", 0.7),
    )
    return _make_horse_bar_chart(rows, columns)


def make_average_evaluation_chart(average_df: pd.DataFrame) -> Figure:
    """馬ごとの展開評価値の平均値を、大きい順に並べた横向きの棒グラフにする。

    平均値が同じ馬は馬番順に並べて同じ順位にする。平均値が無い馬は載せない。
    グラフの左側に馬番・評価平均値・順位を縦に揃えて書く。

    Args:
        average_df (pd.DataFrame): 馬番・枠番・馬名・評価平均値カラムを持つDataFrame。

    Returns:
        Figure: 棒グラフ。
    """
    averaged = average_df[average_df["評価平均値"].notna()]
    rows = pd.DataFrame(
        {
            "馬番": averaged["馬番"].astype(int).to_numpy(),
            "枠番": averaged["枠番"].astype(int).to_numpy(),
            "馬名": averaged["馬名"].astype(str).to_numpy(),
            "value": averaged["評価平均値"].astype(float).to_numpy(),
        }
    )
    rows["順位"] = rows["value"].rank(method="min", ascending=False)
    rows["bar_color"] = _BAR_COLOR
    rows["bold"] = False
    rows["name_bold"] = False
    rows = rows.sort_values(["value", "馬番"], ascending=[False, True]).reset_index(drop=True)
    columns = (
        _ChartColumn("馬番", "馬番", "umaban", 0.6),
        _ChartColumn("評価平均値", "value", "value", 0.9),
        _ChartColumn("順位", "順位", "rank", 0.6),
    )
    return _make_horse_bar_chart(rows, columns)


def make_past_evaluation_trend_chart(
    evaluations: Sequence[tuple[int, float]], axis_runs_ago: Sequence[int]
) -> Figure:
    """馬の過去走の展開評価値を、横軸に何走前をとった折れ線グラフにする。

    横軸には axis_runs_ago の走を、左から古い順に等間隔で並べる。
    縦軸は-1.0から+1.0に固定する。範囲を超える点は図の外に出るが、数値は図の中の端に書く。
    点の数値は、正の値は点の上、負の値は点の下に書く。縦軸の端に近い点は図の内側に書く。

    Args:
        evaluations (Sequence[tuple[int, float]]): (何走前, 展開評価値) のリスト。
            何走前はすべて axis_runs_ago に含まれること。
        axis_runs_ago (Sequence[int]): 横軸に並べる何走前のリスト。

    Returns:
        Figure: 折れ線グラフ。
    """
    slots = sorted(axis_runs_ago, reverse=True)
    runs = sorted(evaluations, key=lambda evaluation: -evaluation[0])
    points = [_LinePoint(slots.index(runs_ago), value, True) for runs_ago, value in runs]
    return _make_line_chart(
        points,
        _LineAxes(
            x_tick_labels=[f"{runs_ago}走前" for runs_ago in slots],
            y_limit=_CHART_LIMIT,
            y_ticks=_CHART_TICKS,
            y_tick_labels=None,
            y_label="展開評価値",
            format_value=lambda value: f"{round(value, 2) + 0.0:+.2f}",
        ),
    )


@dataclass(frozen=True)
class HistoryPoint:
    """推移の折れ線グラフの点1つ。

    Attributes:
        year (int): 開催年。
        value (float): 相関係数（-1.0〜+1.0）。
        is_good_track (bool): 良馬場か。False の点は白抜きにする。
    """

    year: int
    value: float
    is_good_track: bool


def make_dynamics_history_chart(
    column: str, points: Sequence[HistoryPoint], years: Sequence[int]
) -> Figure:
    """有利度1つの年ごとの推移を折れ線グラフにする。

    横軸には years を等間隔に並べ、目盛りは西暦にする。points に無い年は位置だけ取り、
    点を打たないが、前後の点は線でつなぐ。値が NaN の点も打たず、前後の点をつなぐ。
    縦軸は相関係数を100倍した値で、-100から+100に固定する。

    Args:
        column (str): 有利度の名前（差し有利度 / 外枠有利度 / 外有利度）。縦軸のラベルにする。
        points (Sequence[HistoryPoint]): 点を打つ年の値。year はすべて years に含まれること。
        years (Sequence[int]): 横軸に並べる年（昇順）。

    Returns:
        Figure: 折れ線グラフ。
    """
    line_points = [
        _LinePoint(list(years).index(point.year), point.value * 100, point.is_good_track)
        for point in points
        if not pd.isna(point.value)
    ]
    return _make_line_chart(
        sorted(line_points, key=lambda point: point.x),
        _LineAxes(
            x_tick_labels=[str(year) for year in years],
            y_limit=_HISTORY_LIMIT,
            y_ticks=_HISTORY_TICKS,
            y_tick_labels=[f"{round(tick):+d}" if tick else "0" for tick in _HISTORY_TICKS],
            y_label=column,
            format_value=lambda value: f"{round(value):+d}",
        ),
    )


@dataclass(frozen=True)
class _LinePoint:
    """折れ線グラフの点1つ。

    Attributes:
        x (int): 横軸の位置（左から0始まり）。
        y (float): 縦軸の値。
        filled (bool): 塗りつぶすか。False の点は白抜きにする。
    """

    x: int
    y: float
    filled: bool


@dataclass(frozen=True)
class _LineAxes:
    """折れ線グラフの軸と点の数値の設定。

    Attributes:
        x_tick_labels (Sequence[str]): 横軸の目盛りの文字（左から順）。
        y_limit (float): 縦軸の範囲（-y_limit〜+y_limit）。
        y_ticks (Sequence[float]): 縦軸の目盛り。
        y_tick_labels (Sequence[str] | None): 縦軸の目盛りの文字。None なら既定の表記。
        y_label (str): 縦軸のラベル。
        format_value (Callable[[float], str]): 点の数値の書式。
    """

    x_tick_labels: Sequence[str]
    y_limit: float
    y_ticks: Sequence[float]
    y_tick_labels: Sequence[str] | None
    y_label: str
    format_value: Callable[[float], str]


def _make_line_chart(points: Sequence[_LinePoint], axes: _LineAxes) -> Figure:
    """点を横軸の左から順につないだ折れ線グラフにする。

    横軸の位置は目盛りの文字の数だけ等間隔に取り、points に無い位置には点を打たない。
    縦軸は-y_limitから+y_limitに固定する。範囲を超える点は図の外に出るが、数値は図の中の端に書く。
    点の数値は、正の値は点の上、負の値は点の下に書く。縦軸の端に近い点は図の内側に書く。

    Args:
        points (Sequence[_LinePoint]): 点（x の昇順）。x はすべて目盛りの範囲内であること。
        axes (_LineAxes): 軸と点の数値の設定。

    Returns:
        Figure: 折れ線グラフ。
    """
    figure = Figure(figsize=_TREND_FIGSIZE)
    ax = figure.subplots()
    xs = [point.x for point in points]
    ys = [point.y for point in points]
    ax.plot(xs, ys, color=_BAR_COLOR, marker="o")
    # 塗りつぶさない点は、白い点を重ねて白抜きにする
    for point in points:
        if not point.filled:
            ax.plot(
                [point.x], [point.y], color=_BAR_COLOR, marker="o", markerfacecolor="white",
                linestyle="none",
            )  # fmt: skip
    ax.axhline(0, color="black", linewidth=0.8)
    for x, y in zip(xs, ys, strict=True):
        label_y = min(max(y, -axes.y_limit), axes.y_limit)
        edge_margin = axes.y_limit * _TREND_LABEL_EDGE_MARGIN
        if label_y > axes.y_limit - edge_margin:
            below = True
        elif label_y < -axes.y_limit + edge_margin:
            below = False
        else:
            below = label_y < 0
        ax.annotate(
            axes.format_value(y),
            (x, label_y),
            xytext=(0, -_TREND_LABEL_OFFSET if below else _TREND_LABEL_OFFSET),
            textcoords="offset points",
            ha="center",
            va="top" if below else "bottom",
            # 範囲を超える点では線が数値の下を通るため、背景を白にして読めるようにする
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1},
        )
    ax.set_xticks(range(len(axes.x_tick_labels)))
    ax.set_xticklabels(axes.x_tick_labels, fontproperties=_JAPANESE_FONT)
    ax.set_xlim(-0.5, len(axes.x_tick_labels) - 0.5)
    ax.set_ylim(-axes.y_limit, axes.y_limit)
    ax.set_yticks(axes.y_ticks)
    if axes.y_tick_labels is not None:
        ax.set_yticklabels(axes.y_tick_labels)
    ax.set_ylabel(axes.y_label, fontproperties=_JAPANESE_FONT)
    ax.grid(True, axis="y", linestyle="--", alpha=0.5)
    figure.tight_layout()
    return figure


def _make_horse_bar_chart(rows: pd.DataFrame, columns: Sequence[_ChartColumn]) -> Figure:
    """馬ごとの値を横向きの棒グラフにし、左側に列を縦に揃えて書く。

    上から行の順に並べる。棒は0から値まで伸び、0の位置に縦線を引く。
    横軸は-1.0から+1.0に固定する。
    馬番は枠の色の四角で囲み、順位の1〜3位は順位ごとの色の四角で囲む。
    馬名は棒と重ならないよう、値が正の馬は0の左側、負の馬は0の右側に書く。

    Args:
        rows (pd.DataFrame): 1行1頭のDataFrame（並び順は上からの順）。馬番・枠番・馬名・
            value（棒の値）・bar_color（棒の色）・bold（左側の列と馬名を太字にするか）・
            name_bold（馬名を太字にするか）と、各列のkeyのカラムを持つ。
        columns (Sequence[_ChartColumn]): 左側の列（左から順）。

    Returns:
        Figure: 棒グラフ。
    """
    chart_left = sum(column.width for column in columns) + _COLUMN_GAP
    height = _CHART_ROW_HEIGHT * len(rows) + _CHART_TOP + _CHART_BOTTOM
    figure = Figure(figsize=(_CHART_WIDTH, height))
    figure.subplots_adjust(
        left=chart_left / _CHART_WIDTH,
        right=1 - _CHART_RIGHT / _CHART_WIDTH,
        top=1 - _CHART_TOP / height,
        bottom=_CHART_BOTTOM / height,
    )
    ax = figure.subplots()
    positions = list(range(len(rows)))
    ax.barh(positions, rows["value"], color=rows["bar_color"].tolist(), height=_CHART_BAR_HEIGHT)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlim(-_CHART_LIMIT, _CHART_LIMIT)
    ax.set_xticks(_CHART_TICKS)
    ax.set_ylim(len(rows) - 0.5, -0.5)
    ax.set_yticks([])
    ax.grid(True, axis="x", linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    # xは軸の幅に対する割合、yはデータ座標の位置として左側の列を置く
    column_transform = ax.get_yaxis_transform()
    axes_width = _CHART_WIDTH - chart_left - _CHART_RIGHT
    box_width = _BOX_WIDTH / axes_width
    column_xs: list[float] = []
    left = 0.0
    for column in columns:
        column_xs.append((left + column.width / 2 - chart_left) / axes_width)
        left += column.width

    def add_box(x: float, position: int, facecolor: str, edgecolor: str) -> None:
        figure.add_artist(
            Rectangle(
                (x - box_width / 2, position - _CHART_BAR_HEIGHT / 2),
                box_width,
                _CHART_BAR_HEIGHT,
                transform=column_transform,
                facecolor=facecolor,
                edgecolor=edgecolor,
                linewidth=0.5,
                # 軸より奥に描き、軸に書く文字を隠さない
                zorder=-1,
            )
        )

    for x, column in zip(column_xs, columns, strict=True):
        ax.text(
            x, -1.0, column.header, ha="center", va="center",
            transform=column_transform, fontproperties=_JAPANESE_FONT,
        )  # fmt: skip
    for position, row in zip(positions, rows.to_dict("records"), strict=True):
        weight = "bold" if row["bold"] else "normal"
        for x, column in zip(column_xs, columns, strict=True):
            cell = row[column.key]
            color = "black"
            if column.kind == "umaban":
                waku = int(row["枠番"])
                add_box(x, position, WAKU_TO_COLOR_DICT[waku], "black")
                text = str(int(cell))
                color = "black" if waku in _DARK_TEXT_WAKU else "white"
            elif column.kind == "rank":
                text = str(int(cell)) if pd.notna(cell) else "-"
                if pd.notna(cell) and int(cell) in TOP_RANK_COLORS:
                    add_box(x, position, TOP_RANK_COLORS[int(cell)], "none")
            else:
                # 0に丸まる負の値を "-0.00" と表示しないよう、丸めてから -0.0 を 0.0 に正規化する
                text = f"{round(float(cell), 2) + 0.0:+.2f}"
            ax.text(
                x, position, text, ha="center", va="center", color=color,
                transform=column_transform, fontweight=weight,
            )  # fmt: skip
        name_bold = row["bold"] or row["name_bold"]
        name_font = _JAPANESE_BOLD_FONT if name_bold else _JAPANESE_FONT
        # 棒は0から値の側へ伸びるため、反対側の空きに馬名を書く
        value = float(row["value"])
        x_name, align = (-_NAME_OFFSET, "right") if value >= 0 else (_NAME_OFFSET, "left")
        ax.text(
            x_name, position, str(row["馬名"]), ha=align, va="center",
            fontproperties=name_font,
        )  # fmt: skip
    return figure
