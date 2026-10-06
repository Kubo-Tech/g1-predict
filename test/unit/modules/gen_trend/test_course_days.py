"""_course_days の単体テスト。"""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

from g1_predict.modules.gen_trend._course_days import assign_course_days, fetch_course_days

# --- assign_course_days ---


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


# --- fetch_course_days ---


def _make_manager(gappi_list: list[str], kubun_list: list[str]) -> MagicMock:
    """開催日とコース区分を返す ConnectionManager のモックを生成する。"""
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame(
        {"kaisai_gappi": gappi_list, "course_kubun": kubun_list}
    )
    return manager


def test_fetch_course_days_returns_days_by_kaisai_gappi() -> None:
    """開催月日ごとにコース区分の何日目かを返す。"""
    manager = _make_manager(
        ["0601", "0602", "0608", "0609", "0615", "0616"], ["A", "A", "A", "B", "B", "B"]
    )
    result = fetch_course_days(manager, "09", "2019")
    assert result == {"0601": 1, "0602": 2, "0608": 3, "0609": 1, "0615": 2, "0616": 3}
    assert manager.fetch_dataframe.call_args[1]["params"] == ("09", "2019")


def test_fetch_course_days_resets_after_gap() -> None:
    """14日以上空いた開催日は1日目に戻る。"""
    manager = _make_manager(["0608", "0622"], ["B", "B"])
    assert fetch_course_days(manager, "09", "2019") == {"0608": 1, "0622": 1}


def test_fetch_course_days_multiple_course_kubun_in_a_day_raises() -> None:
    """同じ開催日に複数のコース区分がある場合は ValueError になる。"""
    manager = _make_manager(["0608", "0608"], ["A", "B"])
    with pytest.raises(ValueError, match="複数のコース区分"):
        fetch_course_days(manager, "09", "2019")
