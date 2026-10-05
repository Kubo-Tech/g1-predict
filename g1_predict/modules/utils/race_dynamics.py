"""記事に載せる展開評価（相関係数の表・標準化散布図・総合評価の棒グラフ）を生成するユーティリティ。"""

from collections.abc import Collection
from datetime import date

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
# グラフの寸法（インチ）。左側の余白に着順・馬番・評価値・評価順位の列を置く
_CHART_WIDTH = 9.0
_CHART_LEFT = 2.75
_CHART_RIGHT = 0.15
_CHART_TOP = 0.4
_CHART_BOTTOM = 0.4
_CHART_ROW_HEIGHT = 0.32
_CHART_BAR_HEIGHT = 0.7
# 左側の列の中心の位置（グラフの左端からの距離、インチ）
_RANK_COLUMN = 0.3
_UMABAN_COLUMN = 0.85
_VALUE_COLUMN = 1.5
_EVALUATION_RANK_COLUMN = 2.25
# 馬番・着順・評価順位を囲む四角の幅（インチ）
_BOX_WIDTH = 0.26
# 着順・評価順位の1〜3位を囲む四角の色（netkeibaの人気・上がり順位の色）
_TOP_RANK_COLORS = {1: "#FFF080", 2: "#CCDFFF", 3: "#F0C8A0"}
# 横軸の範囲。範囲を超える評価値の棒は端で切れる
_CHART_LIMIT = 1.0
_CHART_TICKS = (-1.0, -0.5, 0.0, 0.5, 1.0)
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


def make_total_evaluation_chart(
    eval_df: pd.DataFrame,
    result_df: pd.DataFrame,
    highlight_horse_nums: Collection[int] = (),
    runner_horse_nums: Collection[int] = (),
) -> Figure:
    """馬ごとの展開の総合評価を、着順の順に並べた横向きの棒グラフにする。

    上から確定着順の順に並べ、確定着順が無い馬（競走中止など）は最後に馬番順で並べる。
    総合評価が無い馬（競走除外など）は載せない。
    棒は0から評価値まで伸び、0の位置に縦線を引く。横軸は-1.0から+1.0に固定する。
    グラフの左側に着順・馬番・評価値・評価順位を縦に揃えて書き、馬番は枠の色の四角で囲む。
    着順と評価順位の1〜3位は、順位ごとの色の四角で囲む。
    馬名は棒と重ならないよう、評価値が正の馬は0の左側、負の馬は0の右側に書く。

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
    rows = pd.DataFrame(
        {
            "umaban": evaluated["馬番"].astype(int).to_numpy(),
            "value": evaluated["総合評価"].astype(float).to_numpy(),
        }
    )
    rows["rank"] = [horses.loc[umaban, "確定着順"] for umaban in rows["umaban"]]
    rows["evaluation_rank"] = rows["value"].rank(method="min", ascending=False).astype(int)
    rows = rows.sort_values(["rank", "umaban"], na_position="last").reset_index(drop=True)

    height = _CHART_ROW_HEIGHT * len(rows) + _CHART_TOP + _CHART_BOTTOM
    figure = Figure(figsize=(_CHART_WIDTH, height))
    figure.subplots_adjust(
        left=_CHART_LEFT / _CHART_WIDTH,
        right=1 - _CHART_RIGHT / _CHART_WIDTH,
        top=1 - _CHART_TOP / height,
        bottom=_CHART_BOTTOM / height,
    )
    ax = figure.subplots()
    positions = list(range(len(rows)))
    colors = []
    for umaban in rows["umaban"]:
        if umaban in highlight_horse_nums:
            colors.append(_HIGHLIGHT_COLOR)
        elif umaban in runner_horse_nums:
            colors.append(_RUNNER_COLOR)
        else:
            colors.append(_BAR_COLOR)
    ax.barh(positions, rows["value"], color=colors, height=_CHART_BAR_HEIGHT)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlim(-_CHART_LIMIT, _CHART_LIMIT)
    ax.set_xticks(_CHART_TICKS)
    ax.set_ylim(len(rows) - 0.5, -0.5)
    ax.set_yticks([])
    ax.grid(True, axis="x", linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    # xは軸の幅に対する割合、yはデータ座標の位置として左側の列を置く
    column_transform = ax.get_yaxis_transform()
    axes_width = _CHART_WIDTH - _CHART_LEFT - _CHART_RIGHT

    def column_x(column: float) -> float:
        return (column - _CHART_LEFT) / axes_width

    headers = (
        (_RANK_COLUMN, "着順"),
        (_UMABAN_COLUMN, "馬番"),
        (_VALUE_COLUMN, "評価値"),
        (_EVALUATION_RANK_COLUMN, "評価順位"),
    )
    for column, header in headers:
        ax.text(
            column_x(column), -1.0, header, ha="center", va="center",
            transform=column_transform, fontproperties=_JAPANESE_FONT,
        )  # fmt: skip
    box_width = _BOX_WIDTH / axes_width

    def add_box(column: float, position: int, facecolor: str, edgecolor: str) -> None:
        figure.add_artist(
            Rectangle(
                (column_x(column) - box_width / 2, position - _CHART_BAR_HEIGHT / 2),
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

    wakus = horses["枠番"].astype(int).to_dict()
    for position, umaban, value, rank, evaluation_rank in zip(
        positions,
        rows["umaban"].astype(int).tolist(),
        rows["value"].astype(float).tolist(),
        rows["rank"].tolist(),
        rows["evaluation_rank"].astype(int).tolist(),
        strict=True,
    ):
        highlighted = umaban in highlight_horse_nums
        weight = "bold" if highlighted else "normal"
        waku = wakus[umaban]
        add_box(_UMABAN_COLUMN, position, WAKU_TO_COLOR_DICT[waku], "black")
        if pd.notna(rank) and int(rank) in _TOP_RANK_COLORS:
            add_box(_RANK_COLUMN, position, _TOP_RANK_COLORS[int(rank)], "none")
        if evaluation_rank in _TOP_RANK_COLORS:
            add_box(_EVALUATION_RANK_COLUMN, position, _TOP_RANK_COLORS[evaluation_rank], "none")
        rank_text = f"{int(rank)}" if pd.notna(rank) else "-"
        # 0に丸まる負の値を "-0.00" と表示しないよう、丸めてから -0.0 を 0.0 に正規化する
        value_text = f"{round(value, 2) + 0.0:+.2f}"
        cells = (
            (_RANK_COLUMN, rank_text, "black"),
            (_UMABAN_COLUMN, str(umaban), "black" if waku in _DARK_TEXT_WAKU else "white"),
            (_VALUE_COLUMN, value_text, "black"),
            (_EVALUATION_RANK_COLUMN, str(evaluation_rank), "black"),
        )
        for column, text, color in cells:
            ax.text(
                column_x(column), position, text, ha="center", va="center", color=color,
                transform=column_transform, fontweight=weight,
            )  # fmt: skip
        name_bold = highlighted or umaban in runner_horse_nums
        name_font = _JAPANESE_BOLD_FONT if name_bold else _JAPANESE_FONT
        # 棒は0から評価値の側へ伸びるため、反対側の空きに馬名を書く
        x, align = (-_NAME_OFFSET, "right") if value >= 0 else (_NAME_OFFSET, "left")
        ax.text(
            x, position, str(horses.loc[umaban, "馬名"]), ha=align, va="center",
            fontproperties=name_font,
        )  # fmt: skip
    return figure
