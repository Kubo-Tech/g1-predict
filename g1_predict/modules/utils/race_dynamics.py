"""記事に載せる展開評価（相関係数の表・標準化散布図・総合評価の棒グラフ）を生成するユーティリティ。"""

from collections.abc import Collection
from datetime import date

import pandas as pd
from evaluation import RaceDynamicsResult, evaluate_race_dynamics, make_time_plot
from keiba_data_interface import DataInterface
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
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
# MATLABの標準色の1色目（通常の棒）・2色目（強調する馬の棒）
_BAR_COLOR = "#0072BD"
_HIGHLIGHT_COLOR = "#D95319"
_JAPANESE_FONT = FontProperties(family="Noto Sans CJK JP")
_JAPANESE_BOLD_FONT = FontProperties(family="Noto Sans CJK JP", weight="bold")
_CHART_WIDTH = 8.0
_CHART_ROW_HEIGHT = 0.32
_CHART_BASE_HEIGHT = 1.2
_CHART_BAR_HEIGHT = 0.7
# 横軸の範囲は、評価値の絶対値の最大にこの倍率と余白を足した値（馬名を書く余地を確保する）
_CHART_LIMIT_SCALE = 1.1
_CHART_LIMIT_MARGIN = 0.1
# 左端の列の右端の位置（軸の幅に対する割合。負の値は軸の左外側）
_UMABAN_COLUMN_X = -0.14
_VALUE_COLUMN_X = -0.015
# 馬名を0から離す距離（横軸の範囲に対する割合）
_NAME_OFFSET_RATIO = 0.02


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
    name_bold_horse_nums: Collection[int] = (),
) -> Figure:
    """馬ごとの展開の総合評価を、着順の順に並べた横向きの棒グラフにする。

    上から確定着順の順に並べ、確定着順が無い馬（競走中止など）は最後に馬番順で並べる。
    総合評価が無い馬（競走除外など）は載せない。
    棒は0から評価値まで伸び、0の位置に縦線を引く。グラフの左外側に馬番と評価値を縦に揃えて書き、
    馬名は棒と重ならないよう、評価値が正の馬は0の左側、負の馬は0の右側に書く。
    横軸は0を中心に左右対称にする。

    Args:
        eval_df (pd.DataFrame): 展開評価の馬ごとの評価DataFrame（馬番・総合評価カラムを使う）。
        result_df (pd.DataFrame): レース結果DataFrame（馬番・確定着順・馬名カラムを使う）。
        highlight_horse_nums (Collection[int]): 棒を強調色にし、馬番・評価値・馬名を
            太字にする馬の馬番。
        name_bold_horse_nums (Collection[int]): 馬名だけを太字にする馬の馬番。

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
    rows = rows.sort_values(["rank", "umaban"], na_position="last").reset_index(drop=True)

    limit = float(rows["value"].abs().max()) * _CHART_LIMIT_SCALE + _CHART_LIMIT_MARGIN
    figure = Figure(figsize=(_CHART_WIDTH, _CHART_ROW_HEIGHT * len(rows) + _CHART_BASE_HEIGHT))
    ax = figure.subplots()
    positions = list(range(len(rows)))
    highlighted = [int(umaban) in highlight_horse_nums for umaban in rows["umaban"]]
    ax.barh(
        positions,
        rows["value"],
        color=[_HIGHLIGHT_COLOR if flag else _BAR_COLOR for flag in highlighted],
        height=_CHART_BAR_HEIGHT,
    )
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlim(-limit, limit)
    ax.set_ylim(len(rows) - 0.5, -0.5)
    ax.set_yticks([])
    ax.grid(True, axis="x", linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    # xは軸の幅に対する割合、yはデータ座標の位置として左端の列を置く
    column_transform = ax.get_yaxis_transform()
    header_y = -1.0
    ax.text(
        _UMABAN_COLUMN_X, header_y, "馬番", ha="right", va="center",
        transform=column_transform, fontproperties=_JAPANESE_FONT,
    )  # fmt: skip
    ax.text(
        _VALUE_COLUMN_X, header_y, "評価値", ha="right", va="center",
        transform=column_transform, fontproperties=_JAPANESE_FONT,
    )  # fmt: skip
    for position, umaban, value, flag in zip(
        positions, rows["umaban"], rows["value"], highlighted, strict=True
    ):
        umaban = int(umaban)
        weight = "bold" if flag else "normal"
        # 0に丸まる負の値を "-0.00" と表示しないよう、丸めてから -0.0 を 0.0 に正規化する
        value_text = f"{round(float(value), 2) + 0.0:+.2f}"
        for column_x, text in ((_UMABAN_COLUMN_X, str(umaban)), (_VALUE_COLUMN_X, value_text)):
            ax.text(
                column_x, position, text, ha="right", va="center",
                transform=column_transform, fontweight=weight,
            )  # fmt: skip
        name_bold = flag or umaban in name_bold_horse_nums
        name_font = _JAPANESE_BOLD_FONT if name_bold else _JAPANESE_FONT
        offset = limit * _NAME_OFFSET_RATIO
        # 棒は0から評価値の側へ伸びるため、反対側の空きに馬名を書く
        x, align = (-offset, "right") if value >= 0 else (offset, "left")
        ax.text(
            x, position, str(horses.loc[umaban, "馬名"]), ha=align, va="center",
            fontproperties=name_font,
        )  # fmt: skip
    figure.tight_layout()
    return figure
