"""build_prev_day_trend_body の単体テスト。"""
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from matplotlib.colors import to_hex

from g1_predict.modules.gen_prev_day_trend.prev_day_trend import (
    PrevDayTrendBody,
    build_prev_day_trend_body,
)

_DEMEME_IMAGE_PATHS = {
    "img/prev_day/dememe_ninki.png",
    "img/prev_day/dememe_waku.png",
    "img/prev_day/dememe_kyakushitsu.png",
    "img/prev_day/dememe_agari.png",
}


def _make_race_info(keibajo_code: str = "05", track_code: str = "10") -> pd.DataFrame:
    """対象レースの基本情報DataFrameを生成する。"""
    return pd.DataFrame({"keibajo_code": [keibajo_code], "track_code": [track_code]})


def _make_raw_shosai(
    race_code: str = "2026050405010106",
    keibajo_code: str = "05",
    track_code: str = "10",
    race_bango: int = 6,
) -> pd.DataFrame:
    """RACE_SHOSAI形式のDataFrameを生成する。"""
    return pd.DataFrame({
        "race_code": [race_code],
        "keibajo_code": [keibajo_code],
        "track_code": [track_code],
        "race_bango": [race_bango],
    })


def _make_prev_race_info(
    race_no: int = 6,
    grade_code: str = "_",
    condition_name: str = "",
    condition_code: str = "703",
    distance: int = 1800,
) -> pd.DataFrame:
    """前日レース基本情報DataFrameを生成する。"""
    return pd.DataFrame({
        "レース番号": [race_no],
        "グレードコード": [grade_code],
        "競走条件名称": [condition_name],
        "競走条件コード": [condition_code],
        "距離": [distance],
    })


def _make_result_df(rows: list[dict[str, object]] | None = None) -> pd.DataFrame:
    """レース結果DataFrameを生成する。指定がなければデフォルト8頭。"""
    if rows is None:
        rows = [
            {
                "確定着順": i,
                "枠番": ((i - 1) // 2) + 1,
                "馬番": i,
                "単勝人気順": i,
                "4コーナー順位": i,
                "後3ハロン": 35.0 + i * 0.1,
                "脚質判定コード": str(((i - 1) % 4) + 1),
            }
            for i in range(1, 9)
        ]
    return pd.DataFrame(rows)


def _make_mock_di(
    prev_race_info: pd.DataFrame | None = None,
    result_df: pd.DataFrame | None = None,
) -> MagicMock:
    """DataInterface のモックを生成する。"""
    mock = MagicMock()
    mock.get_race_basic_info.return_value = (
        prev_race_info if prev_race_info is not None else _make_prev_race_info()
    )
    mock.get_result.return_value = result_df if result_df is not None else _make_result_df()
    return mock


def _make_cor_df(
    sashi: float = 0.451,
    soto_waku: float = -0.123,
    soto: float = 0.3,
) -> pd.DataFrame:
    """展開評価の相関係数DataFrame（1行）を生成する。"""
    return pd.DataFrame({
        "差し有利度": [sashi],
        "外枠有利度": [soto_waku],
        "外有利度": [soto],
    })


def _make_mock_race_data(is_straight_race: bool = False) -> MagicMock:
    """race_data.RaceData のモックを生成する。"""
    mock = MagicMock()
    mock.is_straight_race.return_value = is_straight_race
    return mock


def _call(
    race_code: str = "2026050505010101",
    race_info: pd.DataFrame | None = None,
    mock_di: MagicMock | None = None,
    raw_shosai: pd.DataFrame | None = None,
    venue_name: str = "東京",
    mock_race_data: MagicMock | None = None,
    cor_df: pd.DataFrame | None = None,
    figure: MagicMock | None = None,
) -> PrevDayTrendBody:
    """build_prev_day_trend_body をモック環境で実行する。"""
    if race_info is None:
        race_info = _make_race_info()
    if mock_di is None:
        mock_di = _make_mock_di()
    if raw_shosai is None:
        raw_shosai = _make_raw_shosai()
    if mock_race_data is None:
        mock_race_data = _make_mock_race_data()
    if cor_df is None:
        cor_df = _make_cor_df()
    if figure is None:
        figure = MagicMock(name="Figure")

    mock_rg = MagicMock()
    mock_rg.get_race_shosai.return_value = raw_shosai

    with (
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.DataInterface",
            return_value=mock_di,
        ),
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.RaceGetter",
            return_value=mock_rg,
        ),
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.keibajo_from_code",
            return_value=venue_name,
        ),
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.RaceData",
            return_value=mock_race_data,
        ),
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.evaluate_race_dynamics",
            return_value=MagicMock(cor_df=cor_df),
        ),
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.make_time_plot",
            return_value=figure,
        ),
    ):
        return build_prev_day_trend_body(race_code, race_info)


@pytest.fixture
def simple_result_df() -> pd.DataFrame:
    """出目カウントテスト用の3頭レース結果。

    1着: 1人気, 1枠, 逃げ, 後3ハロン34.5秒（1位）
    2着: 5人気, 3枠, 先行, 後3ハロン35.0秒（2位）
    3着: 11人気, 8枠, 追込, 後3ハロン35.5秒（3位）
    """
    return _make_result_df([
        {
            "確定着順": 1,
            "枠番": 1,
            "馬番": 1,
            "単勝人気順": 1,
            "4コーナー順位": 1,
            "後3ハロン": 34.5,
            "脚質判定コード": "1",
        },
        {
            "確定着順": 2,
            "枠番": 3,
            "馬番": 5,
            "単勝人気順": 5,
            "4コーナー順位": 3,
            "後3ハロン": 35.0,
            "脚質判定コード": "2",
        },
        {
            "確定着順": 3,
            "枠番": 8,
            "馬番": 15,
            "単勝人気順": 11,
            "4コーナー順位": 8,
            "後3ハロン": 35.5,
            "脚質判定コード": "4",
        },
    ])


# 正常系
@pytest.mark.parametrize(
    "raw_shosai",
    [
        pytest.param(pd.DataFrame(), id="no_races_on_prev_day"),
        pytest.param(_make_raw_shosai(keibajo_code="06"), id="no_keibajo_match"),
        pytest.param(_make_raw_shosai(track_code="23"), id="no_shiba_da_match"),
        pytest.param(_make_raw_shosai(track_code="51"), id="barrier_race_excluded"),
    ],
)
def test_build_prev_day_trend_body_returns_empty_when_no_target_races(
    raw_shosai: pd.DataFrame,
) -> None:
    """対象レースが0件の場合、本文が空文字列で画像も空になる。"""
    result = _call(raw_shosai=raw_shosai)
    assert result.text == ""
    assert result.images == {}


def test_build_prev_day_trend_body_has_dememe_header() -> None:
    """マッチするレースがある場合、## 出目 ヘッダーを含む。"""
    result = _call()
    assert "## 出目" in result.text


@pytest.mark.parametrize(
    "heading, image_link",
    [
        pytest.param("**人気**", "![人気](img/prev_day/dememe_ninki.png)", id="ninki"),
        pytest.param("**枠番**", "![枠番](img/prev_day/dememe_waku.png)", id="waku"),
        pytest.param(
            "**[脚質](http://next5.jra-van.jp/appli/kyakushitsu3.html)**",
            "![脚質](img/prev_day/dememe_kyakushitsu.png)",
            id="kyakushitsu",
        ),
        pytest.param("**上がり順位**", "![上がり順位](img/prev_day/dememe_agari.png)", id="agari"),
    ],
)
def test_build_prev_day_trend_body_dememe_heading_then_chart(heading: str, image_link: str) -> None:
    """出目の各見出しの下に、空行を挟んで棒グラフの画像を載せる。"""
    result = _call()
    assert f"{heading}\n\n{image_link}" in result.text
    assert "頭 |" not in result.text


def test_build_prev_day_trend_body_has_each_race_header() -> None:
    """マッチするレースがある場合、## 各レース ヘッダーを含む。"""
    result = _call()
    assert "## 各レース" in result.text


def test_build_prev_day_trend_body_race_block_starts_with_h3() -> None:
    """レースブロックの見出しが ### {venue}{race_no}R で始まる。"""
    mock_di = _make_mock_di(prev_race_info=_make_prev_race_info(race_no=6))
    result = _call(mock_di=mock_di, venue_name="東京")
    assert "### 東京6R" in result.text


def test_build_prev_day_trend_body_grade_displayed_in_race_header() -> None:
    """グレードコード A は G1 としてレースヘッダーに表示される。"""
    mock_di = _make_mock_di(
        prev_race_info=_make_prev_race_info(grade_code="A", condition_name="天皇賞春")
    )
    result = _call(mock_di=mock_di)
    assert "(G1)" in result.text


def test_build_prev_day_trend_body_no_grade_for_unknown_code() -> None:
    """グレードコードが未定義（_）の場合、グレード表示なし。"""
    mock_di = _make_mock_di(prev_race_info=_make_prev_race_info(grade_code="_"))
    result = _call(mock_di=mock_di)
    assert "(G1)" not in result.text
    assert "(G2)" not in result.text
    assert "(G3)" not in result.text


def test_build_prev_day_trend_body_uses_condition_name_when_present() -> None:
    """競走条件名称がある場合、条件名称をレースヘッダーに使用する。"""
    mock_di = _make_mock_di(
        prev_race_info=_make_prev_race_info(condition_name="カトレア賞")
    )
    result = _call(mock_di=mock_di)
    assert "カトレア賞" in result.text


def test_build_prev_day_trend_body_uses_condition_code_when_name_absent() -> None:
    """競走条件名称が空の場合、条件コードから表示名を使用する。"""
    mock_di = _make_mock_di(
        prev_race_info=_make_prev_race_info(condition_name="", condition_code="703")
    )
    result = _call(mock_di=mock_di)
    assert "未勝利" in result.text


def test_build_prev_day_trend_body_prev_date_passed_to_race_getter() -> None:
    """RaceGetter.get_race_shosai が前日の日付で呼ばれる。"""
    mock_rg = MagicMock()
    mock_rg.get_race_shosai.return_value = pd.DataFrame()

    with (
        patch("g1_predict.modules.gen_prev_day_trend.prev_day_trend.DataInterface"),
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.RaceGetter",
            return_value=mock_rg,
        ),
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.keibajo_from_code",
            return_value="東京",
        ),
    ):
        build_prev_day_trend_body("2026050505010101", _make_race_info())

    mock_rg.get_race_shosai.assert_called_once_with(
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 4),
        convert_codes=False,
    )


def _bar_heights(figure: object) -> list[float]:
    """棒グラフのFigureから棒の高さを取り出す。"""
    ax = figure.axes[0]  # type: ignore[attr-defined]
    return [patch.get_height() for patch in ax.patches]


@pytest.mark.parametrize(
    "image_path, expected",
    [
        pytest.param("img/prev_day/dememe_ninki.png", [1, 0, 0, 1, 0, 1], id="ninki"),
        pytest.param("img/prev_day/dememe_waku.png", [1, 0, 1, 0, 0, 0, 0, 1], id="waku"),
        pytest.param("img/prev_day/dememe_kyakushitsu.png", [1, 1, 0, 1], id="kyakushitsu"),
        pytest.param("img/prev_day/dememe_agari.png", [1, 1, 1, 0, 0, 0], id="agari"),
    ],
)
def test_build_prev_day_trend_body_dememe_counts(
    simple_result_df: pd.DataFrame, image_path: str, expected: list[int]
) -> None:
    """出目の棒グラフの高さが3着以内の頭数と一致する。"""
    mock_di = _make_mock_di(result_df=simple_result_df)
    result = _call(mock_di=mock_di)
    assert _bar_heights(result.images[image_path]) == expected


def test_build_prev_day_trend_body_dememe_chart_labels_and_colors() -> None:
    """出目の棒グラフは項目ごとの目盛りラベルを持ち、枠番は枠色、他はMATLAB標準色で塗る。"""
    result = _call()
    waku_ax = result.images["img/prev_day/dememe_waku.png"].axes[0]
    assert [label.get_text() for label in waku_ax.get_xticklabels()] == [
        f"{waku}枠" for waku in range(1, 9)
    ]
    assert [to_hex(patch.get_facecolor()) for patch in waku_ax.patches] == [
        "#ffffff", "#444444", "#e95556", "#416bba", "#e7c52c", "#45af4c", "#ee9738", "#ef8fa0",
    ]
    kyaku_ax = result.images["img/prev_day/dememe_kyakushitsu.png"].axes[0]
    assert [label.get_text() for label in kyaku_ax.get_xticklabels()] == [
        "逃げ", "先行", "差し", "追込",
    ]
    assert [to_hex(patch.get_facecolor()) for patch in kyaku_ax.patches] == [
        "#0072bd", "#d95319", "#edb120", "#7e2f8e",
    ]


def test_build_prev_day_trend_body_race_table_has_kyakushitsu_column(
    simple_result_df: pd.DataFrame,
) -> None:
    """各レースの表で、4角通過順位の右に脚質を載せる。"""
    mock_di = _make_mock_di(result_df=simple_result_df)
    result = _call(mock_di=mock_di)
    assert "| 4角通過順位 | 脚質 | 後3ハロン |" in result.text
    assert "番手 | 逃げ |" in result.text


def test_build_prev_day_trend_body_multiple_races_sorted_by_race_bango() -> None:
    """複数レースが race_bango 昇順でレースブロックに出力される。"""
    raw = pd.DataFrame({
        "race_code": ["2026050405010108", "2026050405010103"],
        "keibajo_code": ["05", "05"],
        "track_code": ["10", "10"],
        "race_bango": [8, 3],
    })
    race_3_info = _make_prev_race_info(race_no=3, condition_name="3R条件")
    race_8_info = _make_prev_race_info(race_no=8, condition_name="8R条件")
    race_info_map = {
        "2026050405010103": race_3_info,
        "2026050405010108": race_8_info,
    }
    mock_di = MagicMock()
    mock_di.get_race_basic_info.side_effect = lambda rc: race_info_map[rc]
    mock_di.get_result.return_value = _make_result_df()

    result = _call(raw_shosai=raw, mock_di=mock_di)

    assert result.text.index("### 東京3R") < result.text.index("### 東京8R")


def test_build_prev_day_trend_body_has_dynamics_header() -> None:
    """マッチするレースがある場合、## 展開 ヘッダーを## 出目と## 各レースの間に含む。"""
    result = _call()
    dememe_index = result.text.index("## 出目")
    dynamics_index = result.text.index("## 展開")
    each_race_index = result.text.index("## 各レース")
    assert dememe_index < dynamics_index < each_race_index


def test_build_prev_day_trend_body_dynamics_description() -> None:
    """展開セクションに説明文を含む。"""
    result = _call()
    assert (
        "差し有利度・外枠有利度・外有利度は、それぞれ4角通過位置・馬番・コーナーでの"
        "内外の位置と走破タイムの相関係数。正なら差し・外枠・外を回した馬が有利。"
    ) in result.text


def test_build_prev_day_trend_body_dynamics_section_has_chart_link() -> None:
    """展開セクションに展開グラフの画像を載せる。"""
    result = _call()
    section = result.text[result.text.index("## 展開") : result.text.index("## 各レース")]
    assert "![展開](img/prev_day/dynamics.png)" in section
    assert "|" not in section


def test_build_prev_day_trend_body_race_block_table_between_top3_and_image() -> None:
    """レースブロックで、上位3頭の表と標準化散布図の間に有利度の表を空行で挟んで載せる。"""
    mock_di = _make_mock_di(prev_race_info=_make_prev_race_info(race_no=6))
    raw = _make_raw_shosai(race_code="2026050405010106")
    cor_df = _make_cor_df(sashi=0.451, soto_waku=-0.123, soto=0.3)
    result = _call(mock_di=mock_di, raw_shosai=raw, venue_name="東京", cor_df=cor_df)
    assert (
        " |\n\n| 差し有利度 | 外枠有利度 | 外有利度 |\n| --- | --- | --- |\n"
        "| +0.45 | -0.12 | +0.30 |\n\n![東京6R 標準化散布図](img/prev_day/2026050405010106.png)"
    ) in result.text


def test_build_prev_day_trend_body_race_table_negative_zero_is_plus_zero() -> None:
    """0に丸まる負の値は -0.00 ではなく +0.00 と表示される。"""
    cor_df = _make_cor_df(sashi=-0.001, soto_waku=-0.004, soto=0.0)
    result = _call(cor_df=cor_df)
    assert "| +0.00 | +0.00 | +0.00 |" in result.text


def test_build_prev_day_trend_body_race_table_nan_is_dash() -> None:
    """外有利度がNaN（全馬最内）の場合、有利度の表の値が - になる。"""
    cor_df = _make_cor_df(soto=float("nan"))
    result = _call(cor_df=cor_df)
    assert "| +0.45 | -0.12 | - |" in result.text


def test_build_prev_day_trend_body_straight_race_has_no_table_and_image_link() -> None:
    """直線コースの場合、レースブロックに有利度の表と画像リンクを載せない。"""
    mock_race_data = _make_mock_race_data(is_straight_race=True)
    result = _call(mock_race_data=mock_race_data)
    assert "| 差し有利度" not in result.text
    assert "標準化散布図" not in result.text


def test_build_prev_day_trend_body_images_keyed_by_relative_path() -> None:
    """images が記事ディレクトリからの相対パスをキーとして展開グラフと散布図を保持する。"""
    raw = _make_raw_shosai(race_code="2026050405010106")
    figure = MagicMock(name="Figure")
    result = _call(raw_shosai=raw, figure=figure)
    assert set(result.images) == {
        *_DEMEME_IMAGE_PATHS,
        "img/prev_day/dynamics.png",
        "img/prev_day/2026050405010106.png",
    }
    assert result.images["img/prev_day/2026050405010106.png"] is figure


def test_build_prev_day_trend_body_straight_race_has_only_summary_charts() -> None:
    """直線コースの場合、images は出目と展開のグラフだけになる。"""
    mock_race_data = _make_mock_race_data(is_straight_race=True)
    result = _call(mock_race_data=mock_race_data)
    assert set(result.images) == {*_DEMEME_IMAGE_PATHS, "img/prev_day/dynamics.png"}


def test_build_prev_day_trend_body_dynamics_chart_lines() -> None:
    """展開グラフは有利度ごとにMATLAB標準色の折れ線を持ち、縦軸は-1〜1、横軸はレース番号。"""
    mock_di = _make_mock_di(prev_race_info=_make_prev_race_info(race_no=6))
    cor_df = _make_cor_df(sashi=0.451, soto_waku=-0.123, soto=0.3)
    result = _call(mock_di=mock_di, cor_df=cor_df)
    ax = result.images["img/prev_day/dynamics.png"].axes[0]
    labels = ("差し有利度", "外枠有利度", "外有利度")
    lines = [line for line in ax.get_lines() if line.get_label() in labels]
    assert [line.get_label() for line in lines] == ["差し有利度", "外枠有利度", "外有利度"]
    assert [line.get_color() for line in lines] == ["#0072BD", "#D95319", "#EDB120"]
    assert [float(line.get_ydata()[0]) for line in lines] == pytest.approx([0.451, -0.123, 0.3])
    assert ax.get_ylim() == (-1, 1)
    assert [label.get_text() for label in ax.get_xticklabels()] == ["6R"]


def test_build_prev_day_trend_body_dynamics_chart_places_races_evenly() -> None:
    """展開グラフはレース番号に関係なくレースを等間隔に並べる。"""
    raw = pd.concat(
        [
            _make_raw_shosai(race_code="2026050405010103", race_bango=3),
            _make_raw_shosai(race_code="2026050405010111", race_bango=11),
        ],
        ignore_index=True,
    )
    result = _call(raw_shosai=raw)
    ax = result.images["img/prev_day/dynamics.png"].axes[0]
    assert list(ax.get_lines()[0].get_xdata()) == [0, 1]


def test_build_prev_day_trend_body_race_data_uses_target_race_date_as_reference() -> None:
    """前日レースのRaceDataは、対象レースの開催日を未来レース判定の基準日にして作る。"""
    mock_race_data = _make_mock_race_data()
    mock_di = _make_mock_di()
    mock_rg = MagicMock()
    mock_rg.get_race_shosai.return_value = _make_raw_shosai(race_code="2026050405010106")

    with (
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.DataInterface",
            return_value=mock_di,
        ),
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.RaceGetter",
            return_value=mock_rg,
        ),
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.keibajo_from_code",
            return_value="東京",
        ),
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.RaceData",
            return_value=mock_race_data,
        ) as mock_race_data_cls,
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.evaluate_race_dynamics",
            return_value=MagicMock(cor_df=_make_cor_df()),
        ),
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.make_time_plot",
            return_value=MagicMock(name="Figure"),
        ),
    ):
        build_prev_day_trend_body("2026050505010101", _make_race_info())

    mock_race_data_cls.assert_called_once_with(
        race_code="2026050405010106",
        data_interface=mock_di,
        reference_date=date(2026, 5, 5),
    )


def test_build_prev_day_trend_body_race_data_created_once_per_race() -> None:
    """RaceDataの取得が1レースにつき1回になる（evaluateとplotで使い回す）。"""
    mock_race_data = _make_mock_race_data()
    mock_di = _make_mock_di()
    mock_rg = MagicMock()
    mock_rg.get_race_shosai.return_value = _make_raw_shosai()

    with (
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.DataInterface",
            return_value=mock_di,
        ),
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.RaceGetter",
            return_value=mock_rg,
        ),
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.keibajo_from_code",
            return_value="東京",
        ),
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.RaceData",
            return_value=mock_race_data,
        ) as mock_race_data_cls,
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.evaluate_race_dynamics",
            return_value=MagicMock(cor_df=_make_cor_df()),
        ),
        patch(
            "g1_predict.modules.gen_prev_day_trend.prev_day_trend.make_time_plot",
            return_value=MagicMock(name="Figure"),
        ),
    ):
        build_prev_day_trend_body("2026050505010101", _make_race_info())

    assert mock_race_data_cls.call_count == 1
    mock_race_data.fetch_race_result.assert_called_once_with()
    mock_race_data.fetch_race_result_info.assert_called_once_with()
