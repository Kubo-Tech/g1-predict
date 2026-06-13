"""_trend_loader の単体テスト。"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from mykeibadb.analytics import RaceCondition

from g1_predict.modules.gen_predict._trend_loader import (
    build_metric_condition, build_race_context)
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


def test_build_race_context_returns_correct_keibajo_codes() -> None:
    """keibajo_codes が RaceCondition に正しく設定される。"""
    race_info = _make_race_info(keibajo_code="05")
    with (
        patch("g1_predict.modules.gen_predict._trend_loader.ConfigManager"),
        patch("g1_predict.modules.gen_predict._trend_loader.ConnectionManager"),
    ):
        _, condition = build_race_context("2026050505010101", race_info)
    assert condition.keibajo_codes == ["05"]


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


# --- build_metric_condition ---


def _make_base_condition() -> RaceCondition:
    """build_metric_condition テスト用の基本 RaceCondition を生成する。"""
    return RaceCondition(
        keibajo_codes=["05"],
        kyori=2400,
        shiba_da="芝",
        year_from="2016",
        year_to="2025",
        tokubetsu_kyoso_bango="0008",
    )


def test_build_metric_condition_none_returns_base_condition() -> None:
    """condition_cfg が None の場合は base_condition をそのまま返す。"""
    base_condition = _make_base_condition()
    result = build_metric_condition(base_condition, 2026, None)
    assert result == base_condition


def test_build_metric_condition_overrides_years() -> None:
    """years 指定時に year_from / year_to が再計算される。"""
    base_condition = _make_base_condition()
    result = build_metric_condition(base_condition, 2026, {"years": 5})
    assert result.year_from == "2021"
    assert result.year_to == "2025"


def test_build_metric_condition_default_years_is_trend_years() -> None:
    """years 未指定時は TREND_YEARS 分遡る。"""
    base_condition = _make_base_condition()
    result = build_metric_condition(base_condition, 2026, {"keibajo_codes": ["09"]})
    assert result.year_from == str(2026 - TREND_YEARS)
    assert result.year_to == "2025"


def test_build_metric_condition_overrides_keibajo_codes_kaisai_nichime_babajotai_codes() -> None:
    """keibajo_codes / kaisai_nichime / babajotai_codes が condition に反映される。"""
    base_condition = _make_base_condition()
    result = build_metric_condition(
        base_condition,
        2026,
        {"keibajo_codes": ["09"], "kaisai_nichime": [4], "babajotai_codes": ["1"]},
    )
    assert result.keibajo_codes == ["09"]
    assert result.kaisai_nichime == [4]
    assert result.babajotai_codes == ["1"]


def test_build_metric_condition_keeps_base_fields() -> None:
    """condition_cfg に無いフィールドは base_condition の値を維持する。"""
    base_condition = _make_base_condition()
    result = build_metric_condition(base_condition, 2026, {"years": 5})
    assert result.keibajo_codes == ["05"]
    assert result.kyori == 2400
    assert result.shiba_da == "芝"
    assert result.tokubetsu_kyoso_bango == "0008"


def test_build_metric_condition_years_less_than_one_raises() -> None:
    """years が1未満の場合は ValueError が発生する。"""
    base_condition = _make_base_condition()
    with pytest.raises(ValueError, match="years"):
        build_metric_condition(base_condition, 2026, {"years": 0})
