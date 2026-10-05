"""race_dynamics の単体テスト。"""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from matplotlib.colors import to_hex
from matplotlib.figure import Figure
from matplotlib.text import Text

from g1_predict.modules.utils.race_dynamics import (
    build_dynamics_table_lines,
    evaluate_race_dynamics_with_plot,
    format_correlation,
    make_total_evaluation_chart,
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


# make_total_evaluation_chart
_BAR_COLOR = "#0072BD"
_HIGHLIGHT_COLOR = "#D95319"


def _chart_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    eval_df = pd.DataFrame(
        {"馬番": [1, 2, 3, 4, 5], "総合評価": [-0.31, 0.524, float("nan"), -0.001, 0.2]}
    )
    result_df = pd.DataFrame(
        {
            "馬番": [1, 2, 3, 4, 5],
            "確定着順": [1, 3, 4, 2, float("nan")],
            "馬名": ["ホースA", "ホースB", "ホースC", "ホースD", "ホースE"],
        }
    )
    return eval_df, result_df


def _texts_by_column(figure: Figure) -> dict[str, dict[float, Text]]:
    """左端の列（馬番・評価値）と馬名のテキストを、y位置をキーにして返す。"""
    ax = figure.axes[0]
    columns: dict[str, dict[float, Text]] = {"umaban": {}, "value": {}, "name": {}}
    for text in ax.texts:
        x = text.get_position()[0]
        y = text.get_position()[1]
        if y < 0:
            continue
        if x == pytest.approx(-0.14):
            columns["umaban"][y] = text
        elif x == pytest.approx(-0.015):
            columns["value"][y] = text
        else:
            columns["name"][y] = text
    return columns


def test_make_total_evaluation_chart_sorted_by_rank_with_unranked_last() -> None:
    """上から着順の順に並べ、確定着順が無い馬は最後に置き、総合評価が無い馬は載せない。"""
    figure = make_total_evaluation_chart(*_chart_inputs())
    columns = _texts_by_column(figure)
    assert [columns["umaban"][y].get_text() for y in sorted(columns["umaban"])] == [
        "1",
        "4",
        "2",
        "5",
    ]
    assert [columns["name"][y].get_text() for y in sorted(columns["name"])] == [
        "ホースA",
        "ホースD",
        "ホースB",
        "ホースE",
    ]
    ax = figure.axes[0]
    assert [patch.get_width() for patch in ax.patches] == pytest.approx(
        [-0.31, -0.001, 0.524, 0.2]
    )
    assert ax.get_ylim()[0] > ax.get_ylim()[1]


def test_make_total_evaluation_chart_unranked_horses_sorted_by_umaban() -> None:
    """確定着順が無い馬が複数いるときは、馬番順に並べる。"""
    eval_df = pd.DataFrame({"馬番": [3, 1, 2], "総合評価": [0.1, 0.2, 0.3]})
    result_df = pd.DataFrame(
        {
            "馬番": [3, 1, 2],
            "確定着順": [float("nan"), float("nan"), 1],
            "馬名": ["C", "A", "B"],
        }
    )
    columns = _texts_by_column(make_total_evaluation_chart(eval_df, result_df))
    assert [columns["umaban"][y].get_text() for y in sorted(columns["umaban"])] == ["2", "1", "3"]


def test_make_total_evaluation_chart_left_columns_text() -> None:
    """左端に馬番と、符号付き小数2桁の評価値を書く。0に丸まる負の値は「-0.00」にしない。"""
    figure = make_total_evaluation_chart(*_chart_inputs())
    columns = _texts_by_column(figure)
    ys = sorted(columns["value"])
    assert [columns["value"][y].get_text() for y in ys] == ["-0.31", "+0.00", "+0.52", "+0.20"]
    assert all(columns["umaban"][y].get_ha() == "right" for y in ys)
    assert all(columns["value"][y].get_ha() == "right" for y in ys)
    assert all(text.get_fontweight() == "normal" for text in columns["umaban"].values())
    headers = [text.get_text() for text in figure.axes[0].texts if text.get_position()[1] < 0]
    assert headers == ["馬番", "評価値"]


def test_make_total_evaluation_chart_name_placed_opposite_to_bar() -> None:
    """馬名は、評価値が正なら0の左で右揃え、負なら0の右で左揃えにする。"""
    columns = _texts_by_column(make_total_evaluation_chart(*_chart_inputs()))
    names = {text.get_text(): text for text in columns["name"].values()}
    for name in ("ホースB", "ホースE"):
        assert names[name].get_position()[0] < 0
        assert names[name].get_ha() == "right"
    for name in ("ホースA", "ホースD"):
        assert names[name].get_position()[0] > 0
        assert names[name].get_ha() == "left"


def test_make_total_evaluation_chart_zero_value_is_treated_as_positive() -> None:
    """評価値が0の馬は、正と同じく0の左に馬名を書く。"""
    eval_df = pd.DataFrame({"馬番": [1], "総合評価": [0.0]})
    result_df = pd.DataFrame({"馬番": [1], "確定着順": [1], "馬名": ["ホースA"]})
    columns = _texts_by_column(make_total_evaluation_chart(eval_df, result_df))
    name = columns["name"][0]
    assert name.get_position()[0] < 0
    assert name.get_ha() == "right"


def test_make_total_evaluation_chart_xlim_is_symmetric_with_margin() -> None:
    """横軸は0を中心に左右対称で、評価値の絶対値の最大より広い。"""
    ax = make_total_evaluation_chart(*_chart_inputs()).axes[0]
    left, right = ax.get_xlim()
    assert left == pytest.approx(-right)
    assert right > 0.524


def test_make_total_evaluation_chart_has_zero_line() -> None:
    """0の位置に縦線を引く。"""
    ax = make_total_evaluation_chart(*_chart_inputs()).axes[0]
    assert any(list(line.get_xdata()) == [0, 0] for line in ax.lines)


def test_make_total_evaluation_chart_default_colors_and_weights() -> None:
    """強調しないときは、すべての棒を1色目にし、馬名も太字にしない。"""
    ax = make_total_evaluation_chart(*_chart_inputs()).axes[0]
    assert {to_hex(patch.get_facecolor()).upper() for patch in ax.patches} == {_BAR_COLOR}
    assert all(text.get_fontweight() == "normal" for text in ax.texts)


def test_make_total_evaluation_chart_highlight_horse() -> None:
    """強調する馬は、棒を2色目にし、馬番・評価値・馬名を太字にする。他の馬は変えない。"""
    figure = make_total_evaluation_chart(*_chart_inputs(), highlight_horse_nums=[2])
    ax = figure.axes[0]
    colors = [to_hex(patch.get_facecolor()).upper() for patch in ax.patches]
    assert colors == [_BAR_COLOR, _BAR_COLOR, _HIGHLIGHT_COLOR, _BAR_COLOR]
    columns = _texts_by_column(figure)
    for column in columns.values():
        weights = [column[y].get_fontweight() for y in sorted(column)]
        assert weights == ["normal", "normal", "bold", "normal"]


def test_make_total_evaluation_chart_name_bold_horse() -> None:
    """馬名だけ太字にする馬は、棒の色と左端の馬番・評価値を変えない。"""
    figure = make_total_evaluation_chart(*_chart_inputs(), name_bold_horse_nums=[4])
    ax = figure.axes[0]
    assert {to_hex(patch.get_facecolor()).upper() for patch in ax.patches} == {_BAR_COLOR}
    columns = _texts_by_column(figure)
    assert [columns["name"][y].get_fontweight() for y in sorted(columns["name"])] == [
        "normal",
        "bold",
        "normal",
        "normal",
    ]
    for key in ("umaban", "value"):
        assert all(text.get_fontweight() == "normal" for text in columns[key].values())


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
