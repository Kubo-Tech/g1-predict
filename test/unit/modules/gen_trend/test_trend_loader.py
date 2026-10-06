"""_trend_loader の単体テスト。"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from mykeibadb.analytics import RaceCondition

from g1_predict.modules.gen_trend._trend_loader import (
    build_race_context,
    decide_trend_years,
    fetch_past_races,
)
from g1_predict.modules.gen_trend._trend_models import TREND_YEARS

_LOADER = "g1_predict.modules.gen_trend._trend_loader"


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


def _make_base_condition() -> RaceCondition:
    """decide_trend_years 用の基本 RaceCondition を生成する。"""
    return RaceCondition(
        keibajo_codes=["05"], kyori=2400, shiba_da="芝", tokubetsu_kyoso_bango="0008"
    )


# --- build_race_context ---


def _build_context(race_info: pd.DataFrame, first_year: int = 2016, years: int = 10) -> tuple:
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


# --- decide_trend_years ---


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


# --- fetch_past_races ---


def test_fetch_past_races_passes_condition_params() -> None:
    """競馬場・距離・芝ダ・特別競走番号・年の範囲がSQLパラメータに渡る。"""
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame()
    condition = RaceCondition(
        keibajo_codes=["06"],
        kyori=1200,
        shiba_da="芝",
        tokubetsu_kyoso_bango="0016",
        year_from="2016",
        year_to="2025",
    )
    fetch_past_races(manager, condition)

    sql = manager.fetch_dataframe.call_args[0][0]
    params = manager.fetch_dataframe.call_args[1]["params"]
    assert "r.keibajo_code = ANY(%s)" in sql
    assert params[0] == ["06"]
    assert params[1] == 1200
    assert "10" in params[2] and "59" in params[2] and "23" not in params[2]
    assert params[3:] == ("0016", "2016", "2025")


def test_fetch_past_races_filters_by_nichime_and_baba() -> None:
    """開催日目と、芝ダに応じた馬場状態で絞り込む。"""
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame()
    fetch_past_races(manager, RaceCondition(kaisai_nichime=[4, 8], babajotai_codes=["1"]))

    sql = manager.fetch_dataframe.call_args[0][0]
    params = manager.fetch_dataframe.call_args[1]["params"]
    assert "TRIM(r.kaisai_nichime)::INTEGER = ANY(%s)" in sql
    assert "TRIM(r.dirt_babajotai_code) ELSE TRIM(r.shiba_babajotai_code)" in sql
    assert params == ([4, 8], ["1"])


def test_fetch_past_races_without_condition_has_no_filter() -> None:
    """条件が無い場合は絞り込まない。"""
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame()
    fetch_past_races(manager, RaceCondition())

    assert "WHERE TRUE" in manager.fetch_dataframe.call_args[0][0]
    assert manager.fetch_dataframe.call_args[1]["params"] == ()
