"""race_dynamics の単体テスト。"""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from evaluation.params import WAKU_TO_COLOR_DICT
from matplotlib.colors import to_hex
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
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
_RUNNER_COLOR = "#EDB120"
_COLUMNS = ("着順", "馬番", "評価値", "評価順位")


def _chart_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    eval_df = pd.DataFrame(
        {"馬番": [1, 2, 3, 4, 5], "総合評価": [-0.31, 0.524, float("nan"), -0.001, 0.2]}
    )
    result_df = pd.DataFrame(
        {
            "馬番": [1, 2, 3, 4, 5],
            "枠番": [1, 2, 3, 5, 8],
            "確定着順": [1, 3, 4, 2, float("nan")],
            "馬名": ["ホースA", "ホースB", "ホースC", "ホースD", "ホースE"],
        }
    )
    return eval_df, result_df


def _texts_by_column(figure: Figure) -> dict[str, list[Text]]:
    """左側の列（着順・馬番・評価値・評価順位）と馬名のテキストを、上から順に返す。

    左側の列は見出しのx位置で見分け、見出しの行（y<0）は含めない。
    """
    ax = figure.axes[0]
    header_x = {
        text.get_position()[0]: text.get_text() for text in ax.texts if text.get_position()[1] < 0
    }
    columns: dict[str, list[Text]] = {name: [] for name in (*_COLUMNS, "馬名")}
    for text in sorted(ax.texts, key=lambda text: text.get_position()[1]):
        x, y = text.get_position()
        if y < 0:
            continue
        columns[header_x.get(x, "馬名")].append(text)
    return columns


def _texts(texts: list[Text]) -> list[str]:
    return [text.get_text() for text in texts]


def _box_colors(figure: Figure, header: str) -> list[str]:
    """見出しの列にある四角の色を、上から順に返す。"""
    header_x = next(
        text.get_position()[0] for text in figure.axes[0].texts if text.get_text() == header
    )
    boxes = sorted(
        (
            artist
            for artist in figure.artists
            if isinstance(artist, Rectangle)
            and artist.get_x() + artist.get_width() / 2 == pytest.approx(header_x)
        ),
        key=lambda box: box.get_y(),
    )
    return [to_hex(box.get_facecolor()).upper() for box in boxes]


def test_make_total_evaluation_chart_sorted_by_rank_with_unranked_last() -> None:
    """上から着順の順に並べ、確定着順が無い馬は最後に置き、総合評価が無い馬は載せない。"""
    figure = make_total_evaluation_chart(*_chart_inputs())
    columns = _texts_by_column(figure)
    assert _texts(columns["馬番"]) == ["1", "4", "2", "5"]
    assert _texts(columns["馬名"]) == ["ホースA", "ホースD", "ホースB", "ホースE"]
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
            "枠番": [3, 1, 2],
            "確定着順": [float("nan"), float("nan"), 1],
            "馬名": ["C", "A", "B"],
        }
    )
    columns = _texts_by_column(make_total_evaluation_chart(eval_df, result_df))
    assert _texts(columns["馬番"]) == ["2", "1", "3"]


def test_make_total_evaluation_chart_left_columns_text() -> None:
    """左側に着順・馬番・評価値・評価順位を見出し付きで書く。0に丸まる負の値は「-0.00」にしない。"""
    figure = make_total_evaluation_chart(*_chart_inputs())
    columns = _texts_by_column(figure)
    assert _texts(columns["着順"]) == ["1", "2", "3", "-"]
    assert _texts(columns["評価値"]) == ["-0.31", "+0.00", "+0.52", "+0.20"]
    assert _texts(columns["評価順位"]) == ["4", "3", "1", "2"]
    headers = [text for text in figure.axes[0].texts if text.get_position()[1] < 0]
    assert sorted(headers, key=lambda text: text.get_position()[0]) == headers
    assert _texts(headers) == list(_COLUMNS)


def test_make_total_evaluation_chart_evaluation_rank_ties() -> None:
    """評価値が同じ馬は、同じ評価順位にする。"""
    eval_df = pd.DataFrame({"馬番": [1, 2, 3], "総合評価": [0.1, 0.3, 0.1]})
    result_df = pd.DataFrame(
        {"馬番": [1, 2, 3], "枠番": [1, 2, 3], "確定着順": [1, 2, 3], "馬名": ["A", "B", "C"]}
    )
    columns = _texts_by_column(make_total_evaluation_chart(eval_df, result_df))
    assert _texts(columns["評価順位"]) == ["2", "1", "2"]


def test_make_total_evaluation_chart_umaban_box_has_waku_color() -> None:
    """馬番を枠の色の四角で囲み、明るい色の枠は文字を黒、他の枠は白にする。"""
    figure = make_total_evaluation_chart(*_chart_inputs())
    # 上から馬番1(1枠)・4(5枠)・2(2枠)・5(8枠)
    assert _box_colors(figure, "馬番") == [
        WAKU_TO_COLOR_DICT[1].upper(),
        WAKU_TO_COLOR_DICT[5].upper(),
        WAKU_TO_COLOR_DICT[2].upper(),
        WAKU_TO_COLOR_DICT[8].upper(),
    ]
    text_colors = [to_hex(text.get_color()) for text in _texts_by_column(figure)["馬番"]]
    assert text_colors == ["#000000", "#000000", "#ffffff", "#000000"]


def test_make_total_evaluation_chart_top_ranks_have_colored_box() -> None:
    """着順と評価順位の1〜3位を、黄・水色・薄い茶色の四角で囲み、4位以下は囲まない。"""
    figure = make_total_evaluation_chart(*_chart_inputs())
    # 上から着順1・2・3・なし、評価順位4・3・1・2
    assert _box_colors(figure, "着順") == ["#FFF080", "#CCDFFF", "#F0C8A0"]
    assert _box_colors(figure, "評価順位") == ["#F0C8A0", "#FFF080", "#CCDFFF"]


def test_make_total_evaluation_chart_name_placed_opposite_to_bar() -> None:
    """馬名は、評価値が正なら0の左で右揃え、負なら0の右で左揃えにする。"""
    columns = _texts_by_column(make_total_evaluation_chart(*_chart_inputs()))
    names = {text.get_text(): text for text in columns["馬名"]}
    for name in ("ホースB", "ホースE"):
        assert names[name].get_position()[0] < 0
        assert names[name].get_ha() == "right"
    for name in ("ホースA", "ホースD"):
        assert names[name].get_position()[0] > 0
        assert names[name].get_ha() == "left"


def test_make_total_evaluation_chart_zero_value_is_treated_as_positive() -> None:
    """評価値が0の馬は、正と同じく0の左に馬名を書く。"""
    eval_df = pd.DataFrame({"馬番": [1], "総合評価": [0.0]})
    result_df = pd.DataFrame({"馬番": [1], "枠番": [1], "確定着順": [1], "馬名": ["ホースA"]})
    name = _texts_by_column(make_total_evaluation_chart(eval_df, result_df))["馬名"][0]
    assert name.get_position()[0] < 0
    assert name.get_ha() == "right"


def test_make_total_evaluation_chart_xlim_is_fixed() -> None:
    """横軸は評価値によらず-1.0から+1.0に固定する。"""
    ax = make_total_evaluation_chart(*_chart_inputs()).axes[0]
    assert ax.get_xlim() == pytest.approx((-1.0, 1.0))
    assert list(ax.get_xticks()) == pytest.approx([-1.0, -0.5, 0.0, 0.5, 1.0])


def test_make_total_evaluation_chart_has_zero_line() -> None:
    """0の位置に縦線を引く。"""
    ax = make_total_evaluation_chart(*_chart_inputs()).axes[0]
    assert any(list(line.get_xdata()) == [0, 0] for line in ax.lines)


def test_make_total_evaluation_chart_default_colors_and_weights() -> None:
    """強調しないときは、すべての棒を1色目にし、太字にしない。"""
    ax = make_total_evaluation_chart(*_chart_inputs()).axes[0]
    assert {to_hex(patch.get_facecolor()).upper() for patch in ax.patches} == {_BAR_COLOR}
    assert all(text.get_fontweight() == "normal" for text in ax.texts)


def test_make_total_evaluation_chart_highlight_horse() -> None:
    """強調する馬は、棒を2色目にし、左側の列と馬名を太字にする。他の馬は変えない。"""
    figure = make_total_evaluation_chart(*_chart_inputs(), highlight_horse_nums=[2])
    ax = figure.axes[0]
    colors = [to_hex(patch.get_facecolor()).upper() for patch in ax.patches]
    assert colors == [_BAR_COLOR, _BAR_COLOR, _HIGHLIGHT_COLOR, _BAR_COLOR]
    for column in _texts_by_column(figure).values():
        assert [text.get_fontweight() for text in column] == ["normal", "normal", "bold", "normal"]


def test_make_total_evaluation_chart_runner_horse() -> None:
    """今回の出走馬は、棒を3色目にして馬名だけを太字にし、左側の列は太字にしない。"""
    figure = make_total_evaluation_chart(*_chart_inputs(), runner_horse_nums=[4])
    ax = figure.axes[0]
    colors = [to_hex(patch.get_facecolor()).upper() for patch in ax.patches]
    assert colors == [_BAR_COLOR, _RUNNER_COLOR, _BAR_COLOR, _BAR_COLOR]
    columns = _texts_by_column(figure)
    assert [text.get_fontweight() for text in columns["馬名"]] == [
        "normal",
        "bold",
        "normal",
        "normal",
    ]
    for key in _COLUMNS:
        assert all(text.get_fontweight() == "normal" for text in columns[key])


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
