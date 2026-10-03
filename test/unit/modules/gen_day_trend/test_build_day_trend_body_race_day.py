"""build_day_trend_body の当日の傾向についての単体テスト。"""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from g1_predict.modules.gen_day_trend.day_trend import (
    PREV_DAY,
    RACE_DAY,
    DayTrendBody,
    DayTrendKind,
    build_day_trend_body,
)

_DYNAMICS_MODULE = "g1_predict.modules.utils.race_dynamics"
_MODULE = "g1_predict.modules.gen_day_trend.day_trend"


def _make_race_info() -> pd.DataFrame:
    """対象レースの基本情報DataFrameを生成する。"""
    return pd.DataFrame({"keibajo_code": ["05"], "track_code": ["10"]})


def _make_raw_shosai(rows: list[tuple[str, str, int]]) -> pd.DataFrame:
    """RACE_SHOSAI形式のDataFrameを生成する。

    Args:
        rows (list[tuple[str, str, int]]): (race_code, data_kubun, race_bango) のリスト。
    """
    return pd.DataFrame(
        {
            "race_code": [row[0] for row in rows],
            "keibajo_code": ["05"] * len(rows),
            "track_code": ["10"] * len(rows),
            "race_bango": [row[2] for row in rows],
            "data_kubun": [row[1] for row in rows],
        }
    )


def _make_race_basic_info(race_no: int) -> pd.DataFrame:
    """レース基本情報DataFrameを生成する。"""
    return pd.DataFrame(
        {
            "レース番号": [race_no],
            "グレードコード": ["_"],
            "競走条件名称": [""],
            "競走条件コード": ["703"],
            "距離": [1800],
        }
    )


def _make_result_df() -> pd.DataFrame:
    """レース結果DataFrameを生成する。"""
    return pd.DataFrame(
        [
            {
                "確定着順": i,
                "枠番": i,
                "馬番": i,
                "単勝人気順": i,
                "4コーナー順位": i,
                "後3ハロン": 35.0 + i * 0.1,
                "脚質判定コード": "1",
            }
            for i in range(1, 5)
        ]
    )


def _call(
    raw_shosai: pd.DataFrame,
    kind: DayTrendKind,
) -> tuple[DayTrendBody, MagicMock, MagicMock]:
    """build_day_trend_body をモック環境で実行する。

    Returns:
        DayTrendBody: 生成結果。
        MagicMock: RaceGetter のモック。
        MagicMock: RaceData クラスのモック。
    """
    mock_di = MagicMock()
    mock_di.get_race_basic_info.side_effect = lambda code: _make_race_basic_info(int(code[-2:]))
    mock_di.get_result.return_value = _make_result_df()
    mock_rg = MagicMock()
    mock_rg.get_race_shosai.return_value = raw_shosai
    mock_race_data = MagicMock()
    mock_race_data.is_straight_race.return_value = False
    cor_df = pd.DataFrame({"差し有利度": [0.1], "外枠有利度": [0.2], "外有利度": [0.3]})

    with (
        patch(f"{_MODULE}.DataInterface", return_value=mock_di),
        patch(f"{_MODULE}.RaceGetter", return_value=mock_rg),
        patch(f"{_MODULE}.keibajo_from_code", return_value="東京"),
        patch(f"{_DYNAMICS_MODULE}.RaceData", return_value=mock_race_data) as mock_race_data_cls,
        patch(
            f"{_DYNAMICS_MODULE}.evaluate_race_dynamics",
            return_value=MagicMock(cor_df=cor_df),
        ),
        patch(f"{_DYNAMICS_MODULE}.make_time_plot", return_value=MagicMock(name="Figure")),
    ):
        body = build_day_trend_body("2026050505010111", _make_race_info(), "天皇賞春", kind)
    return body, mock_rg, mock_race_data_cls


# 正常系
def test_build_day_trend_body_race_day_uses_race_day_date() -> None:
    """当日の傾向では、対象レースと同じ開催日でRaceGetterが呼ばれる。"""
    raw = _make_raw_shosai([("2026050505010106", "7", 6)])
    _, mock_rg, _ = _call(raw, RACE_DAY)
    mock_rg.get_race_shosai.assert_called_once_with(
        start_date=date(2026, 5, 5),
        end_date=date(2026, 5, 5),
        convert_codes=False,
    )


def test_build_day_trend_body_race_day_aggregates_only_confirmed_races() -> None:
    """当日の傾向では、data_kubunが6と7のレースだけを集計する。"""
    raw = _make_raw_shosai(
        [
            ("2026050505010101", "2", 1),
            ("2026050505010102", "3", 2),
            ("2026050505010103", "5", 3),
            ("2026050505010104", "6", 4),
            ("2026050505010105", "7", 5),
            ("2026050505010106", "9", 6),
        ]
    )
    body, _, mock_race_data_cls = _call(raw, RACE_DAY)
    assert "### 東京4R" in body.text
    assert "### 東京5R" in body.text
    assert body.text.count("### ") == 2
    codes = [call.kwargs["race_code"] for call in mock_race_data_cls.call_args_list]
    assert codes == ["2026050505010104", "2026050505010105"]


def test_build_day_trend_body_race_day_excludes_target_race_and_later() -> None:
    """当日の傾向では、対象レース（11R）とそれ以降のレースを集計しない。"""
    raw = _make_raw_shosai(
        [
            ("2026050505010110", "7", 10),
            ("2026050505010111", "7", 11),
            ("2026050505010112", "7", 12),
        ]
    )
    body, _, mock_race_data_cls = _call(raw, RACE_DAY)
    assert body.text.count("### ") == 1
    assert "### 東京10R" in body.text
    codes = [call.kwargs["race_code"] for call in mock_race_data_cls.call_args_list]
    assert codes == ["2026050505010110"]


def test_build_day_trend_body_prev_day_does_not_filter_by_race_bango() -> None:
    """前日の傾向では、対象レースの番号以降のレースも集計する。"""
    raw = _make_raw_shosai([("2026050405010111", "7", 11), ("2026050405010112", "7", 12)])
    body, _, _ = _call(raw, PREV_DAY)
    assert body.text.count("### ") == 2


def test_build_day_trend_body_race_day_returns_empty_when_no_confirmed_races() -> None:
    """当日の傾向では、結果が出ているレースが1件も無ければ本文が空で画像も無い。"""
    raw = _make_raw_shosai([("2026050505010101", "2", 1), ("2026050505010102", "5", 2)])
    body, _, mock_race_data_cls = _call(raw, RACE_DAY)
    assert body == DayTrendBody(text="", images={})
    mock_race_data_cls.assert_not_called()


def test_build_day_trend_body_race_day_headings_and_description() -> None:
    """当日の傾向では、見出しと説明文の「前日」が「当日」になる。"""
    raw = _make_raw_shosai([("2026050505010106", "7", 6)])
    body, _, _ = _call(raw, RACE_DAY)
    description = (
        "各要素において、当日のレースのうち天皇賞春と同じ競馬場、芝ダのレースで"
        "3着以内に入った頭数を集計。"
    )
    assert f"## 当日の出目\n\n{description}\n" in body.text
    assert "前日" not in body.text
    assert "## 展開有利度の傾向" in body.text
    assert "## 各レースの結果" in body.text


def test_build_day_trend_body_race_day_images_under_race_day_dir() -> None:
    """当日の傾向では、画像のパスがimg/race_day配下になる。"""
    raw = _make_raw_shosai([("2026050505010106", "7", 6)])
    body, _, _ = _call(raw, RACE_DAY)
    assert set(body.images) == {
        "img/race_day/dememe_ninki.png",
        "img/race_day/dememe_waku.png",
        "img/race_day/dememe_kyakushitsu.png",
        "img/race_day/dememe_agari.png",
        "img/race_day/dynamics.png",
        "img/race_day/2026050505010106.png",
    }
    assert "![展開](img/race_day/dynamics.png)" in body.text
    assert "![東京6R 標準化散布図](img/race_day/2026050505010106.png)" in body.text
    assert "img/prev_day" not in body.text


def test_build_day_trend_body_race_day_reference_date_is_day_after_race_day() -> None:
    """当日の傾向では、RaceDataの基準日が対象レースの開催日の翌日になる。"""
    raw = _make_raw_shosai([("2026050505010106", "7", 6)])
    _, _, mock_race_data_cls = _call(raw, RACE_DAY)
    assert mock_race_data_cls.call_args.kwargs["reference_date"] == date(2026, 5, 6)


def test_build_day_trend_body_prev_day_does_not_filter_by_data_kubun() -> None:
    """前日の傾向では、data_kubunによる絞り込みをしない。"""
    raw = _make_raw_shosai([("2026050405010101", "2", 1), ("2026050405010102", "7", 2)])
    body, _, _ = _call(raw, PREV_DAY)
    assert body.text.count("### ") == 2
