"""decide_trend_years の単体テスト。"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from mykeibadb.analytics import RaceCondition

from g1_predict.modules.utils.race_history import TREND_YEARS, decide_trend_years

_LOADER = "g1_predict.modules.utils.race_history"


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


def _make_base_condition() -> RaceCondition:
    """decide_trend_years 用の基本 RaceCondition を生成する。"""
    return RaceCondition(
        keibajo_codes=["05"], kyori=2400, shiba_da="芝", tokubetsu_kyoso_bango="0008"
    )


def _decide(years: list[int], grades: list[str]) -> tuple[int, int]:
    """特別競走番号の過去の開催をモックして decide_trend_years を呼ぶ。"""
    with patch(f"{_LOADER}.fetch_past_races", return_value=_make_past_races(years, grades)):
        return decide_trend_years(MagicMock(), 2026, _make_base_condition())


def test_decide_trend_years_all_g1_uses_trend_years() -> None:
    """過去 TREND_YEARS 年より前からG1なら、TREND_YEARS 年前から集計する。"""
    years = list(range(2000, 2026))
    assert _decide(years, ["A"] * len(years)) == (2016, TREND_YEARS)


def test_decide_trend_years_starts_from_first_g1_year() -> None:
    """期間内にG1になった場合は、G1になった最初の年から集計する。"""
    years = list(range(2000, 2026))
    grades = ["B"] * 17 + ["A"] * 9
    assert _decide(years, grades) == (2017, 9)


def test_decide_trend_years_new_g1_without_previous_editions() -> None:
    """G1として新設されたレースは、最初の開催年から集計する。"""
    assert _decide([2020, 2021, 2022, 2023, 2024, 2025], ["A"] * 6) == (2020, 6)


def test_decide_trend_years_skips_years_without_editions() -> None:
    """最後のG1でない開催と最初のG1の開催の間に休止の年があれば、最初のG1の年から集計する。"""
    years = [2010, 2011, 2012, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
    grades = ["B", "B", "B"] + ["A"] * 8
    assert _decide(years, grades) == (2018, 8)


def test_decide_trend_years_ignores_missing_years_after_g1() -> None:
    """G1になった後に行われなかった年があっても、集計期間は縮めない。"""
    years = [2000, 2001, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2025]
    assert _decide(years, ["A"] * len(years)) == (2016, 10)


def test_decide_trend_years_uses_tokubetsu_number_only() -> None:
    """G1になった年は、競馬場・距離・芝ダによらず特別競走番号と前年までで判定する。"""
    with patch(
        f"{_LOADER}.fetch_past_races", return_value=_make_past_races([2025], ["A"])
    ) as mock_fetch:
        decide_trend_years(MagicMock(), 2026, _make_base_condition())
    history = mock_fetch.call_args[0][1]
    assert history.tokubetsu_kyoso_bango == "0008"
    assert history.keibajo_codes is None
    assert history.kyori is None
    assert history.shiba_da is None
    assert history.year_from is None
    assert history.year_to == "2025"


def test_decide_trend_years_no_g1_before_race_year_raises() -> None:
    """前年までにG1として行われていない場合（G1になった初年）は ValueError になる。"""
    with patch(f"{_LOADER}.fetch_past_races", return_value=_make_past_races([2025], ["B"])):
        with pytest.raises(ValueError, match="G1"):
            decide_trend_years(MagicMock(), 2026, _make_base_condition())
