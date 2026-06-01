"""is_na の単体テスト。"""
import pandas as pd
import pytest

from g1_predict.modules.gen_table.table_utils import is_na


# 正常系
@pytest.mark.parametrize(
    "value",
    [None, float("nan"), pd.NA, pd.NaT],
)
def test_is_na_returns_true_for_na_values(value: object) -> None:
    """None/NaN/pd.NA/pd.NaTはTrueを返す。"""
    assert is_na(value) is True


@pytest.mark.parametrize(
    "value",
    [0, 1, -1, 0.0, 1.5, "", "abc", False, True],
)
def test_is_na_returns_false_for_non_na_values(value: object) -> None:
    """NA以外の値はFalseを返す。"""
    assert is_na(value) is False


def test_is_na_returns_false_for_list() -> None:
    """TypeErrorが発生する型はFalseを返す。"""
    assert is_na([1, 2, 3]) is False
