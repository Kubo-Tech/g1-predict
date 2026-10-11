"""build_race_context の単体テスト。"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from g1_predict.modules.utils.race_history import (
    TrendContext,
    build_race_context,
    fetch_race_info_from_history,
)

_LOADER = "g1_predict.modules.utils.race_history"


def _make_race_info(
    keibajo_code: str = "05",
    kyori: int = 2400,
    track_code: str = "10",
    kaisai_nen: int = 2026,
    tokubetsu_kyoso_bango: str = "0008",
    kyosomei_hondai: str = "東京優駿",
) -> pd.DataFrame:
    """build_race_context 用の race_info DataFrame を生成する。"""
    return pd.DataFrame({
        "keibajo_code": [keibajo_code],
        "kyori": [kyori],
        "track_code": [track_code],
        "kaisai_nen": [kaisai_nen],
        "tokubetsu_kyoso_bango": [tokubetsu_kyoso_bango],
        "kyosomei_hondai": [kyosomei_hondai],
    })


def _make_past_races(years: list[int], grade_codes: list[str]) -> pd.DataFrame:
    """fetch_past_races の戻り値に相当する DataFrame を生成する。"""
    return pd.DataFrame({
        "race_code": [f"{year}0527050212{i:02d}" for i, year in enumerate(years)],
        "kaisai_nen": [str(year) for year in years],
        "kaisai_gappi": ["0527"] * len(years),
        "keibajo_code": ["05"] * len(years),
        "grade_code": grade_codes,
        "course_kubun": ["A"] * len(years),
    })


def _build_context(
    race_info: pd.DataFrame, first_year: int = 2016, years: int = 10
) -> tuple[TrendContext, MagicMock]:
    """ConnectionManager と集計年数の決定をモックして build_race_context を呼ぶ。"""
    mock_manager = MagicMock()
    past_races = _make_past_races([2016, 2017, 2018], ["A", "A", "A"])
    with (
        patch(f"{_LOADER}.ConfigManager"),
        patch(f"{_LOADER}.ConnectionManager", return_value=mock_manager),
        patch(f"{_LOADER}.decide_trend_years", return_value=(first_year, years)),
        patch(f"{_LOADER}.fetch_past_races", return_value=past_races),
    ):
        return build_race_context(race_info), mock_manager


def test_build_race_context_returns_correct_condition() -> None:
    """RaceCondition に競馬場・距離・芝ダ・特別競走番号・年の範囲が設定される。"""
    context, _ = _build_context(_make_race_info(), first_year=2017, years=9)
    condition = context.condition
    assert condition.keibajo_codes == ["05"]
    assert condition.kyori == 2400
    assert condition.shiba_da == "芝"
    assert condition.tokubetsu_kyoso_bango == "0008"
    assert condition.year_from == "2017"
    assert condition.year_to == "2025"


def test_build_race_context_returns_scope() -> None:
    """集計対象の初年・年数・レース数と対象レースの情報を返す。"""
    context, mock_manager = _build_context(_make_race_info(), first_year=2017, years=9)
    assert context.manager is mock_manager
    assert context.race_year == 2026
    assert context.race_name == "東京優駿"
    assert context.kyori == 2400
    assert context.keibajo_code == "05"
    assert context.shiba_da == "芝"
    assert context.first_year == 2017
    assert context.years == 9
    assert context.race_count == 3


def test_build_race_context_dirt_track_code() -> None:
    """ダートトラックコードで shiba_da が 'ダ' になる。"""
    context, _ = _build_context(_make_race_info(track_code="23"))
    assert context.shiba_da == "ダ"
    assert context.condition.shiba_da == "ダ"


def test_build_race_context_zero_fills_tokubetsu_kyoso_bango() -> None:
    """特別競走番号は4桁にゼロ埋めされる。"""
    context, _ = _build_context(_make_race_info(tokubetsu_kyoso_bango="16"))
    assert context.condition.tokubetsu_kyoso_bango == "0016"


def test_build_race_context_unknown_track_code_raises() -> None:
    """芝ダを判定できない track_code は ValueError になる。"""
    with pytest.raises(ValueError, match="track_code"):
        build_race_context(_make_race_info(track_code="99"))


def test_fetch_race_info_from_history_result_builds_race_context() -> None:
    """組み立てたレース基本情報は build_race_context に渡せる。"""
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame({
        "kyosomei_hondai": ["秋華賞"],
        "kyori": ["2000"],
        "track_code": ["10"],
    })
    race_info = fetch_race_info_from_history(manager, "2026101808040711", "0018")

    context, _ = _build_context(race_info)

    assert (context.race_name, context.kyori, context.keibajo_code) == ("秋華賞", 2000, "08")
    assert context.race_year == 2026
    assert context.condition.tokubetsu_kyoso_bango == "0018"
