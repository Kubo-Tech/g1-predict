"""build_prev_day_trend_section の単体テスト。"""
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scripts.prev_day_trend import build_prev_day_trend_section


def _make_race_info(keibajo_code: str = "05", shiba_da: str = "芝") -> pd.DataFrame:
    """対象レースの基本情報DataFrameを生成する。"""
    return pd.DataFrame({"競馬場コード": [keibajo_code], "芝ダ": [shiba_da]})


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


def _call(
    race_code: str = "2026050505010101",
    race_info: pd.DataFrame | None = None,
    mock_di: MagicMock | None = None,
    raw_shosai: pd.DataFrame | None = None,
    venue_name: str = "東京",
) -> str:
    """build_prev_day_trend_section をモック環境で実行する。"""
    if race_info is None:
        race_info = _make_race_info()
    if mock_di is None:
        mock_di = _make_mock_di()
    if raw_shosai is None:
        raw_shosai = _make_raw_shosai()

    mock_rg = MagicMock()
    mock_rg.get_race_shosai.return_value = raw_shosai

    with (
        patch("scripts.prev_day_trend.RaceGetter", return_value=mock_rg),
        patch("scripts.prev_day_trend.keibajo_code_to_name", return_value=venue_name),
    ):
        return build_prev_day_trend_section(race_code, race_info, mock_di)


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
def test_build_prev_day_trend_section_returns_empty_when_no_races() -> None:
    """前日のレースが0件の場合、空のセクション文字列を返す。"""
    result = _call(raw_shosai=pd.DataFrame())
    assert result == "## 前日の傾向\n"


def test_build_prev_day_trend_section_returns_empty_when_no_keibajo_match() -> None:
    """前日に同競馬場のレースがない場合、空のセクション文字列を返す。"""
    raw = _make_raw_shosai(keibajo_code="06")
    result = _call(raw_shosai=raw)
    assert result == "## 前日の傾向\n"


def test_build_prev_day_trend_section_returns_empty_when_no_shiba_da_match() -> None:
    """前日に同芝ダのレースがない場合、空のセクション文字列を返す。"""
    raw = _make_raw_shosai(track_code="23")  # ダートコード
    result = _call(raw_shosai=raw)  # target は芝
    assert result == "## 前日の傾向\n"


def test_build_prev_day_trend_section_excludes_barrier_races() -> None:
    """障害コード（51-59）のレースは除外される。"""
    raw = _make_raw_shosai(track_code="51")
    result = _call(raw_shosai=raw)
    assert result == "## 前日の傾向\n"


def test_build_prev_day_trend_section_has_header() -> None:
    """マッチするレースがある場合、## 前日の傾向 ヘッダーを含む。"""
    result = _call()
    assert "## 前日の傾向" in result


def test_build_prev_day_trend_section_has_dememe_section() -> None:
    """出目セクション（### 出目）を含む。"""
    result = _call()
    assert "### 出目" in result


def test_build_prev_day_trend_section_has_race_block_header() -> None:
    """レースブロックの見出し（### {venue}{race_no}R）を含む。"""
    mock_di = _make_mock_di(prev_race_info=_make_prev_race_info(race_no=6))
    result = _call(mock_di=mock_di, venue_name="東京")
    assert "### 東京6R" in result


def test_build_prev_day_trend_section_grade_displayed_in_race_header() -> None:
    """グレードコード A は G1 としてレースヘッダーに表示される。"""
    mock_di = _make_mock_di(
        prev_race_info=_make_prev_race_info(grade_code="A", condition_name="天皇賞春")
    )
    result = _call(mock_di=mock_di)
    assert "(G1)" in result


def test_build_prev_day_trend_section_no_grade_for_unknown_code() -> None:
    """グレードコードが未定義（_）の場合、グレード表示なし。"""
    mock_di = _make_mock_di(prev_race_info=_make_prev_race_info(grade_code="_"))
    result = _call(mock_di=mock_di)
    assert "(G1)" not in result
    assert "(G2)" not in result
    assert "(G3)" not in result


def test_build_prev_day_trend_section_uses_condition_name_when_present() -> None:
    """競走条件名称がある場合、条件名称をレースヘッダーに使用する。"""
    mock_di = _make_mock_di(
        prev_race_info=_make_prev_race_info(condition_name="カトレア賞")
    )
    result = _call(mock_di=mock_di)
    assert "カトレア賞" in result


def test_build_prev_day_trend_section_uses_condition_code_when_name_absent() -> None:
    """競走条件名称が空の場合、条件コードから表示名を使用する。"""
    mock_di = _make_mock_di(
        prev_race_info=_make_prev_race_info(condition_name="", condition_code="703")
    )
    result = _call(mock_di=mock_di)
    assert "未勝利" in result


def test_build_prev_day_trend_section_prev_date_passed_to_race_getter() -> None:
    """RaceGetter.get_race_shosai が前日の日付で呼ばれる。"""
    mock_rg = MagicMock()
    mock_rg.get_race_shosai.return_value = pd.DataFrame()

    with (
        patch("scripts.prev_day_trend.RaceGetter", return_value=mock_rg),
        patch("scripts.prev_day_trend.keibajo_code_to_name", return_value="東京"),
    ):
        build_prev_day_trend_section("2026050505010101", _make_race_info(), MagicMock())

    mock_rg.get_race_shosai.assert_called_once_with(
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 4),
        convert_codes=False,
    )


def test_build_prev_day_trend_section_ninki_count(simple_result_df: pd.DataFrame) -> None:
    """出目の人気カウントが正しい（1人気1頭, 4-6人気1頭, 10人気以下1頭）。"""
    mock_di = _make_mock_di(result_df=simple_result_df)
    result = _call(mock_di=mock_di)
    assert "| 1頭 | 0頭 | 0頭 | 1頭 | 0頭 | 1頭 |" in result


def test_build_prev_day_trend_section_waku_count(simple_result_df: pd.DataFrame) -> None:
    """出目の枠番カウントが正しい（1枠1頭, 3枠1頭, 8枠1頭）。"""
    mock_di = _make_mock_di(result_df=simple_result_df)
    result = _call(mock_di=mock_di)
    assert "| 1頭 | 0頭 | 1頭 | 0頭 | 0頭 | 0頭 | 0頭 | 1頭 |" in result


def test_build_prev_day_trend_section_kyakushitsu_count(simple_result_df: pd.DataFrame) -> None:
    """出目の脚質カウントが正しい（逃1頭, 先1頭, 差0頭, 追1頭）。"""
    mock_di = _make_mock_di(result_df=simple_result_df)
    result = _call(mock_di=mock_di)
    assert "| 1頭 | 1頭 | 0頭 | 1頭 |" in result


def test_build_prev_day_trend_section_agari_rank_count(simple_result_df: pd.DataFrame) -> None:
    """出目の上がり順位カウントが正しい（1位1頭, 2位1頭, 3位1頭）。"""
    mock_di = _make_mock_di(result_df=simple_result_df)
    result = _call(mock_di=mock_di)
    assert "| 1頭 | 1頭 | 1頭 | 0頭 | 0頭 | 0頭 |" in result


def test_build_prev_day_trend_section_multiple_races_sorted_by_race_bango() -> None:
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

    assert result.index("### 東京3R") < result.index("### 東京8R")
