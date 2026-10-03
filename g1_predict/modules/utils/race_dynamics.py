"""記事に載せる展開評価（相関係数の表・標準化散布図・総合評価の表）を生成するユーティリティ。"""

from datetime import date

import pandas as pd
from evaluation import RaceDynamicsResult, evaluate_race_dynamics, make_time_plot
from keiba_data_interface import DataInterface
from matplotlib.figure import Figure
from race_data import RaceData

# 展開評価の相関係数カラム
DYNAMICS_COLUMNS: tuple[str, ...] = ("差し有利度", "外枠有利度", "外有利度")


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


def build_total_evaluation_table_lines(
    eval_df: pd.DataFrame,
    result_df: pd.DataFrame,
) -> list[str]:
    """馬ごとの展開の総合評価を、評価値の高い順に並べた表を生成する。

    総合評価が無い馬（競走除外など）は載せない。

    Args:
        eval_df (pd.DataFrame): 展開評価の馬ごとの評価DataFrame（馬番・総合評価カラムを使う）。
        result_df (pd.DataFrame): レース結果DataFrame（馬番・確定着順・馬名カラムを使う）。

    Returns:
        list[str]: Markdownの表の行リスト（ヘッダー・区切り・各馬の行）。
    """
    horses = result_df.set_index(result_df["馬番"].astype(int))
    evaluated = eval_df[eval_df["総合評価"].notna()].sort_values("総合評価", ascending=False)
    lines = ["| 着順 | 馬番 | 馬名 | 評価値 |", "| --- | --- | --- | --- |"]
    for _, row in evaluated.iterrows():
        umaban = int(row["馬番"])
        horse = horses.loc[umaban]
        chakujun = horse["確定着順"]
        chakujun_str = f"{int(chakujun)}着" if pd.notna(chakujun) else "-"
        # 0に丸まる負の値を "-0.00" と表示しないよう、丸めてから -0.0 を 0.0 に正規化する
        value = round(float(row["総合評価"]), 2) + 0.0
        lines.append(f"| {chakujun_str} | {umaban} | {horse['馬名']} | {value:+.2f}秒 |")
    return lines
