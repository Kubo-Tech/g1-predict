"""race_dynamics の単体テスト。"""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from g1_predict.modules.utils.race_dynamics import (
    build_dynamics_table_lines,
    build_total_evaluation_table_lines,
    evaluate_race_dynamics_with_plot,
    format_correlation,
)

_MODULE = "g1_predict.modules.utils.race_dynamics"


def _cor_df(sashi: float = 0.456, waku: float = -0.154, soto: float = 0.0) -> pd.DataFrame:
    return pd.DataFrame({"差し有利度": [sashi], "外枠有利度": [waku], "外有利度": [soto]})


# format_correlation
def test_format_correlation_signed_percent() -> None:
    """相関係数を100倍した符号付きの整数パーセントに整形する。"""
    df = _cor_df()
    assert format_correlation(df, "差し有利度") == "+46%"
    assert format_correlation(df, "外枠有利度") == "-15%"
    assert format_correlation(df, "外有利度") == "+0%"


def test_format_correlation_nan_and_none() -> None:
    """NaN・対象外レース（None）は「-」になる。"""
    assert format_correlation(_cor_df(sashi=float("nan")), "差し有利度") == "-"
    assert format_correlation(None, "差し有利度") == "-"


# build_dynamics_table_lines
def test_build_dynamics_table_lines() -> None:
    """ヘッダー・区切り・値の3行を返す。"""
    assert build_dynamics_table_lines(_cor_df()) == [
        "| 差し有利度 | 外枠有利度 | 外有利度 |",
        "| --- | --- | --- |",
        "| +46% | -15% | +0% |",
    ]


# build_total_evaluation_table_lines
def test_build_total_evaluation_table_lines_sorted_by_value() -> None:
    """評価値の高い順に並べ、総合評価が無い馬は載せない。"""
    eval_df = pd.DataFrame(
        {"馬番": [1, 2, 3, 4], "総合評価": [-0.31, 0.524, float("nan"), -0.001]}
    )
    result_df = pd.DataFrame(
        {
            "馬番": [1, 2, 3, 4],
            "確定着順": [1, 3, float("nan"), 2],
            "馬名": ["ホースA", "ホースB", "ホースC", "ホースD"],
        }
    )
    assert build_total_evaluation_table_lines(eval_df, result_df) == [
        "| 着順 | 馬番 | 馬名 | 展開評価値 |",
        "| --- | --- | --- | --- |",
        "| 3着 | 2 | ホースB | +0.52 |",
        "| 2着 | 4 | ホースD | +0.00 |",
        "| 1着 | 1 | ホースA | -0.31 |",
    ]


def _bold_eval_and_result() -> tuple[pd.DataFrame, pd.DataFrame]:
    eval_df = pd.DataFrame({"馬番": [1, 2, 3], "総合評価": [0.3, 0.2, 0.1]})
    result_df = pd.DataFrame(
        {"馬番": [1, 2, 3], "確定着順": [1, 2, 3], "馬名": ["ホースA", "ホースB", "ホースC"]}
    )
    return eval_df, result_df


def test_build_total_evaluation_table_lines_bold_row_and_name() -> None:
    """行全体の太字は全セル、馬名のみの太字は馬名のセルだけを太字にする。"""
    eval_df, result_df = _bold_eval_and_result()
    assert build_total_evaluation_table_lines(
        eval_df, result_df, bold_row_horse_nums=[1], bold_name_horse_nums=[3]
    ) == [
        "| 着順 | 馬番 | 馬名 | 展開評価値 |",
        "| --- | --- | --- | --- |",
        "| **1着** | **1** | **ホースA** | **+0.30** |",
        "| 2着 | 2 | ホースB | +0.20 |",
        "| 3着 | 3 | **ホースC** | +0.10 |",
    ]


def test_build_total_evaluation_table_lines_bold_row_takes_precedence() -> None:
    """行全体と馬名のみの両方に指定された馬は、行全体を太字にする。"""
    eval_df, result_df = _bold_eval_and_result()
    lines = build_total_evaluation_table_lines(
        eval_df, result_df, bold_row_horse_nums=[2], bold_name_horse_nums=[2]
    )
    assert lines[3] == "| **2着** | **2** | **ホースB** | **+0.20** |"


# evaluate_race_dynamics_with_plot
def test_evaluate_race_dynamics_with_plot_returns_cor_df_and_figure() -> None:
    """RaceDataを基準日付きで1回作り、展開評価の結果と散布図を返す。"""
    race_data = MagicMock()
    race_data.is_straight_race.return_value = False
    dynamics = MagicMock(cor_df=_cor_df())
    figure = MagicMock(name="Figure")
    di = MagicMock()
    with (
        patch(f"{_MODULE}.RaceData", return_value=race_data) as mock_cls,
        patch(f"{_MODULE}.evaluate_race_dynamics", return_value=dynamics),
        patch(f"{_MODULE}.make_time_plot", return_value=figure) as mock_plot,
    ):
        result = evaluate_race_dynamics_with_plot("2026092706040911", di, date(2026, 9, 28))
    assert result == (dynamics, figure)
    mock_cls.assert_called_once_with(
        race_code="2026092706040911", data_interface=di, reference_date=date(2026, 9, 28)
    )
    mock_plot.assert_called_once_with(race_data)
    race_data.fetch_race_result.assert_called_once_with()
    race_data.fetch_race_result_info.assert_called_once_with()


def test_evaluate_race_dynamics_with_plot_straight_race_is_skipped() -> None:
    """1000m直線コースは評価せず、両方Noneを返す。"""
    race_data = MagicMock()
    race_data.is_straight_race.return_value = True
    with (
        patch(f"{_MODULE}.RaceData", return_value=race_data),
        patch(f"{_MODULE}.evaluate_race_dynamics") as mock_evaluate,
    ):
        result = evaluate_race_dynamics_with_plot(
            "2026092706040911", MagicMock(), date(2026, 9, 28)
        )
    assert result == (None, None)
    mock_evaluate.assert_not_called()
