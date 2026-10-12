"""fetch_course_days の単体テスト。"""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from g1_predict.modules.utils.course_days import fetch_course_days


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
