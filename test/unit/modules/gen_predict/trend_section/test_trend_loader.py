"""_trend_loader の単体テスト。"""

from unittest.mock import MagicMock, patch

import pandas as pd

from g1_predict.modules.gen_predict._trend_loader import build_race_context
from g1_predict.modules.gen_predict._trend_models import TREND_YEARS


def _make_race_info(
    keibajo_code: str = "05",
    kyori: int = 2400,
    track_code: str = "10",
    kaisai_nen: int = 2026,
    tokubetsu_kyoso_bango: str = "0008",
) -> pd.DataFrame:
    """build_race_context 用の race_info DataFrame を生成する。"""
    return pd.DataFrame({
        "keibajo_code": [keibajo_code],
        "kyori": [kyori],
        "track_code": [track_code],
        "kaisai_nen": [kaisai_nen],
        "tokubetsu_kyoso_bango": [tokubetsu_kyoso_bango],
    })


def test_build_race_context_returns_correct_keibajo_code() -> None:
    """keibajo_code が RaceCondition に正しく設定される。"""
    race_info = _make_race_info(keibajo_code="05")
    with (
        patch("g1_predict.modules.gen_predict._trend_loader.ConfigManager"),
        patch("g1_predict.modules.gen_predict._trend_loader.ConnectionManager"),
    ):
        _, condition = build_race_context("2026050505010101", race_info)
    assert condition.keibajo_code == "05"


def test_build_race_context_returns_correct_kyori() -> None:
    """kyori が RaceCondition に正しく設定される。"""
    race_info = _make_race_info(kyori=2400)
    with (
        patch("g1_predict.modules.gen_predict._trend_loader.ConfigManager"),
        patch("g1_predict.modules.gen_predict._trend_loader.ConnectionManager"),
    ):
        _, condition = build_race_context("2026050505010101", race_info)
    assert condition.kyori == 2400


def test_build_race_context_shiba_track_code() -> None:
    """芝トラックコードで shiba_da が '芝' になる。"""
    race_info = _make_race_info(track_code="10")
    with (
        patch("g1_predict.modules.gen_predict._trend_loader.ConfigManager"),
        patch("g1_predict.modules.gen_predict._trend_loader.ConnectionManager"),
    ):
        _, condition = build_race_context("2026050505010101", race_info)
    assert condition.shiba_da == "芝"


def test_build_race_context_dirt_track_code() -> None:
    """ダートトラックコードで shiba_da が 'ダ' になる。"""
    race_info = _make_race_info(track_code="23")
    with (
        patch("g1_predict.modules.gen_predict._trend_loader.ConfigManager"),
        patch("g1_predict.modules.gen_predict._trend_loader.ConnectionManager"),
    ):
        _, condition = build_race_context("2026050505010101", race_info)
    assert condition.shiba_da == "ダ"


def test_build_race_context_year_range() -> None:
    """year_from / year_to が TREND_YEARS 分遡った範囲になる。"""
    race_info = _make_race_info(kaisai_nen=2026)
    with (
        patch("g1_predict.modules.gen_predict._trend_loader.ConfigManager"),
        patch("g1_predict.modules.gen_predict._trend_loader.ConnectionManager"),
    ):
        _, condition = build_race_context("2026050505010101", race_info)
    assert condition.year_from == str(2026 - TREND_YEARS)
    assert condition.year_to == "2025"


def test_build_race_context_returns_connection_manager() -> None:
    """ConnectionManager インスタンスを返す。"""
    race_info = _make_race_info()
    mock_manager = MagicMock()
    mock_cm_class = MagicMock(return_value=mock_manager)
    with (
        patch("g1_predict.modules.gen_predict._trend_loader.ConfigManager"),
        patch("g1_predict.modules.gen_predict._trend_loader.ConnectionManager", mock_cm_class),
    ):
        manager, _ = build_race_context("2026050505010101", race_info)
    assert manager is mock_manager
