"""year_range の単体テスト。"""
from datetime import date

import pytest

from g1_predict.modules.gen_table.table_utils import year_range


# 正常系
@pytest.mark.parametrize(
    "race_year, years, expected_start, expected_end",
    [
        (2026, 1, date(2026, 1, 1), date(2026, 12, 31)),
        (2026, 3, date(2024, 1, 1), date(2026, 12, 31)),
        (2026, 10, date(2017, 1, 1), date(2026, 12, 31)),
    ],
)
def test_year_range_returns_correct_dates(
    race_year: int, years: int, expected_start: date, expected_end: date
) -> None:
    """開始日・終了日が正しく計算される。"""
    start, end = year_range(race_year, years)
    assert start == expected_start
    assert end == expected_end
