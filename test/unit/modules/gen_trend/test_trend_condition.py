"""_trend_condition の単体テスト。"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from mykeibadb.analytics import RaceColFilter, RaceCondition

from g1_predict.modules.gen_trend._trend_condition import (
    apply_trend_condition,
    parse_trend_condition,
)
from g1_predict.modules.gen_trend._trend_loader import TrendContext
from g1_predict.modules.gen_trend._trend_models import TrendCondition

_CONDITION = "g1_predict.modules.gen_trend._trend_condition"


def _make_context() -> TrendContext:
    """阪神芝2200mの集計対象を持つ TrendContext を生成する。"""
    return TrendContext(
        manager=MagicMock(),
        condition=RaceCondition(
            keibajo_codes=["09"],
            kyori=2200,
            shiba_da="芝",
            tokubetsu_kyoso_bango="0021",
            year_from="2016",
            year_to="2025",
        ),
        race_year=2026,
        race_name="宝塚記念",
        kyori=2200,
        keibajo_code="09",
        shiba_da="芝",
        first_year=2016,
        years=10,
        race_count=9,
    )


def _make_past_races() -> pd.DataFrame:
    """阪神の過去の開催（Bコース・Aコース）を表す DataFrame を生成する。"""
    return pd.DataFrame({
        "race_code": ["2018062409030811", "2019062309030811", "2025061509030411"],
        "kaisai_nen": ["2018", "2019", "2025"],
        "kaisai_gappi": ["0624", "0623", "0615"],
        "keibajo_code": ["09", "09", "09"],
        "grade_code": ["A", "A", "A"],
        "course_kubun": ["B", "B", "A"],
    })


# --- parse_trend_condition ---


# 正常系
def test_parse_trend_condition_all_keys() -> None:
    """5つのキーをすべて TrendCondition に変換する。"""
    condition = parse_trend_condition(
        {
            "keibajo_codes": ["09"],
            "course_kubun": "B",
            "course_days": [7, 8],
            "kaisai_nichime": [4],
            "babajotai_codes": ["1"],
        },
        "枠順",
    )
    assert condition == TrendCondition(
        keibajo_codes=("09",),
        course_kubun="B",
        course_days=(7, 8),
        kaisai_nichime=(4,),
        babajotai_codes=("1",),
    )


def test_parse_trend_condition_partial_keys_leave_others_none() -> None:
    """指定しなかったキーは None になる。"""
    condition = parse_trend_condition({"kaisai_nichime": [4]}, "枠順")
    assert condition == TrendCondition(kaisai_nichime=(4,))


# 準正常系
@pytest.mark.parametrize(
    "raw, message",
    [
        ({}, "1つ以上"),
        ({"years": 10}, "未対応のキー"),
        ({"keibajo_codes": "09"}, "keibajo_codes"),
        ({"keibajo_codes": []}, "keibajo_codes"),
        ({"keibajo_codes": [9]}, "keibajo_codes"),
        ({"course_kubun": "F"}, "course_kubun"),
        ({"course_days": [0]}, "course_days"),
        ({"course_days": ["4"]}, "course_days"),
        ({"kaisai_nichime": [True]}, "kaisai_nichime"),
        ({"babajotai_codes": ["5"]}, "babajotai_codes"),
    ],
)
def test_parse_trend_condition_invalid_raises(raw: dict, message: str) -> None:
    """不正な condition は ValueError になる。"""
    with pytest.raises(ValueError, match=message):
        parse_trend_condition(raw, "枠順")


# --- apply_trend_condition ---


# 正常系
def test_apply_trend_condition_reflects_race_condition_fields() -> None:
    """keibajo_codes・kaisai_nichime・babajotai_codes が RaceCondition に反映される。"""
    race_condition, filters = apply_trend_condition(
        _make_context(),
        TrendCondition(keibajo_codes=("09",), kaisai_nichime=(4,), babajotai_codes=("1",)),
    )
    assert race_condition.keibajo_codes == ["09"]
    assert race_condition.kaisai_nichime == [4]
    assert race_condition.babajotai_codes == ["1"]
    assert filters == []


def test_apply_trend_condition_keeps_base_fields() -> None:
    """指定しなかった条件は既定の集計対象の値を維持する。"""
    race_condition, _ = apply_trend_condition(
        _make_context(), TrendCondition(kaisai_nichime=(4,))
    )
    assert race_condition.keibajo_codes == ["09"]
    assert race_condition.kyori == 2200
    assert race_condition.shiba_da == "芝"
    assert race_condition.tokubetsu_kyoso_bango == "0021"
    assert race_condition.year_from == "2016"
    assert race_condition.year_to == "2025"


def test_apply_trend_condition_course_kubun_filters_by_race_code() -> None:
    """course_kubun は条件に合う開催の race_code で絞り込む。"""
    with patch(f"{_CONDITION}.fetch_past_races", return_value=_make_past_races()):
        _, filters = apply_trend_condition(_make_context(), TrendCondition(course_kubun="B"))
    assert filters == [
        RaceColFilter(column="u.race_code", values=["2018062409030811", "2019062309030811"])
    ]


def test_apply_trend_condition_course_days_filters_by_race_code() -> None:
    """course_days はコース区分の何日目が合う開催の race_code で絞り込む。"""
    with (
        patch(f"{_CONDITION}.fetch_past_races", return_value=_make_past_races()),
        patch(
            f"{_CONDITION}.fetch_course_days",
            side_effect=lambda _manager, _keibajo, year: {
                "2018": {"0624": 4},
                "2019": {"0623": 5},
                "2025": {"0615": 4},
            }[year],
        ),
    ):
        _, filters = apply_trend_condition(
            _make_context(), TrendCondition(course_kubun="B", course_days=(4,))
        )
    assert filters == [RaceColFilter(column="u.race_code", values=["2018062409030811"])]


def test_apply_trend_condition_course_days_without_kubun_checks_all_races() -> None:
    """course_kubun を指定しない場合は、コース区分に関わらず何日目で絞り込む。"""
    with (
        patch(f"{_CONDITION}.fetch_past_races", return_value=_make_past_races()),
        patch(
            f"{_CONDITION}.fetch_course_days",
            side_effect=lambda _manager, _keibajo, year: {
                "2018": {"0624": 4},
                "2019": {"0623": 5},
                "2025": {"0615": 4},
            }[year],
        ),
    ):
        _, filters = apply_trend_condition(_make_context(), TrendCondition(course_days=(4,)))
    assert filters == [
        RaceColFilter(column="u.race_code", values=["2018062409030811", "2025061509030411"])
    ]


def test_apply_trend_condition_course_days_fetches_each_year_once() -> None:
    """コース区分の何日目は、競馬場・年ごとに1回だけ取得する。"""
    past_races = pd.concat([_make_past_races(), _make_past_races().iloc[[0]]])
    with (
        patch(f"{_CONDITION}.fetch_past_races", return_value=past_races),
        patch(f"{_CONDITION}.fetch_course_days", return_value={"0624": 4}) as mock_fetch,
    ):
        apply_trend_condition(_make_context(), TrendCondition(course_days=(4,)))
    assert mock_fetch.call_count == 3


def test_apply_trend_condition_skips_race_without_course_day() -> None:
    """コース区分が登録されていない開催日のレースは対象外にする。"""
    with (
        patch(f"{_CONDITION}.fetch_past_races", return_value=_make_past_races()),
        patch(
            f"{_CONDITION}.fetch_course_days",
            side_effect=lambda _manager, _keibajo, year: {
                "2018": {"0624": 4},
                "2019": {},
                "2025": {},
            }[year],
        ),
    ):
        _, filters = apply_trend_condition(_make_context(), TrendCondition(course_days=(4,)))
    assert filters == [RaceColFilter(column="u.race_code", values=["2018062409030811"])]


# 準正常系
def test_apply_trend_condition_keibajo_not_in_scope_raises() -> None:
    """集計対象の競馬場を含まない keibajo_codes は ValueError になる。"""
    with pytest.raises(ValueError, match="keibajo_codes"):
        apply_trend_condition(_make_context(), TrendCondition(keibajo_codes=("06",)))


def test_apply_trend_condition_no_matching_race_raises() -> None:
    """条件に合う開催が無い場合は ValueError になる。"""
    with patch(f"{_CONDITION}.fetch_past_races", return_value=_make_past_races()):
        with pytest.raises(ValueError, match="条件に合う開催がありません"):
            apply_trend_condition(_make_context(), TrendCondition(course_kubun="E"))
