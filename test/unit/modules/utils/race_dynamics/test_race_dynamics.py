"""race_dynamics の単体テスト。"""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from g1_predict.modules.utils.race_dynamics import (
    build_dynamics_table_lines,
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


# evaluate_race_dynamics_with_plot
def test_evaluate_race_dynamics_with_plot_returns_cor_df_and_figure() -> None:
    """RaceDataを基準日付きで1回作り、相関係数と散布図を返す。"""
    race_data = MagicMock()
    race_data.is_straight_race.return_value = False
    cor_df = _cor_df()
    figure = MagicMock(name="Figure")
    di = MagicMock()
    with (
        patch(f"{_MODULE}.RaceData", return_value=race_data) as mock_cls,
        patch(f"{_MODULE}.evaluate_race_dynamics", return_value=MagicMock(cor_df=cor_df)),
        patch(f"{_MODULE}.make_time_plot", return_value=figure) as mock_plot,
    ):
        result = evaluate_race_dynamics_with_plot("2026092706040911", di, date(2026, 9, 28))
    assert result == (cor_df, figure)
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
