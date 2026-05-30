"""stat_result の単体テスト。"""
import pytest

from scripts._table_utils import stat_result


# 正常系
@pytest.mark.parametrize(
    "stat, wins, top3, total, expected",
    [
        ("wins", 3, 5, 10, 3),
        ("top3", 3, 5, 10, 5),
        ("win_rate", 1, 5, 4, 0.25),
        ("top3_rate", 2, 4, 8, 0.5),
    ],
)
def test_stat_result_returns_correct_value(
    stat: str, wins: int, top3: int, total: int, expected: object
) -> None:
    """stat種別に応じた正しい値を返す。"""
    assert stat_result(stat, wins, top3, total) == expected


@pytest.mark.parametrize("stat", ["win_rate", "top3_rate"])
def test_stat_result_returns_zero_when_total_is_zero(stat: str) -> None:
    """total=0のときrateは0.0を返す。"""
    assert stat_result(stat, 0, 0, 0) == 0.0


def test_stat_result_returns_none_for_unknown_stat() -> None:
    """不明なstatはNoneを返す。"""
    assert stat_result("unknown", 1, 2, 3) is None
