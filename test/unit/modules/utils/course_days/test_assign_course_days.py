"""assign_course_days の単体テスト。"""

from datetime import date

import pytest

from g1_predict.modules.utils.course_days import assign_course_days


def test_assign_course_days_counts_days_in_same_course_kubun() -> None:
    """同じコース区分が続く開催日は1日目から数える。"""
    dates = [date(2025, 6, 7), date(2025, 6, 8), date(2025, 6, 14), date(2025, 6, 15)]
    assert assign_course_days(dates, ["A", "A", "A", "A"]) == [1, 2, 3, 4]


def test_assign_course_days_resets_when_course_kubun_changes() -> None:
    """コース区分が前の開催日から変わった日は1日目に戻る。"""
    dates = [date(2019, 6, 1), date(2019, 6, 2), date(2019, 6, 8), date(2019, 6, 9)]
    assert assign_course_days(dates, ["A", "A", "B", "B"]) == [1, 2, 1, 2]


def test_assign_course_days_resets_after_gap_of_14_days() -> None:
    """前の開催日から14日以上空いた日は、同じコース区分でも1日目に戻る。"""
    dates = [date(2025, 6, 7), date(2025, 6, 21)]
    assert assign_course_days(dates, ["A", "A"]) == [1, 1]


def test_assign_course_days_keeps_counting_after_13_days() -> None:
    """前の開催日から13日しか空いていなければ数え続ける。"""
    dates = [date(2025, 6, 7), date(2025, 6, 20)]
    assert assign_course_days(dates, ["A", "A"]) == [1, 2]


def test_assign_course_days_empty() -> None:
    """開催日が無ければ空リストを返す。"""
    assert assign_course_days([], []) == []


def test_assign_course_days_length_mismatch_raises() -> None:
    """開催日とコース区分の長さが異なる場合は ValueError になる。"""
    with pytest.raises(ValueError, match="長さ"):
        assign_course_days([date(2025, 6, 7)], [])
