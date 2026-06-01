"""to_cell_value の単体テスト。"""
import pandas as pd
import pytest

from g1_predict.modules.gen_table.table_utils import to_cell_value


# 正常系
@pytest.mark.parametrize(
    "value",
    [None, float("nan"), pd.NA],
)
def test_to_cell_value_returns_none_for_na(value: object) -> None:
    """NA系の値はNoneを返す。"""
    assert to_cell_value(value) is None


@pytest.mark.parametrize(
    "value",
    [0, 1, 3.14, "text", True, ""],
)
def test_to_cell_value_returns_value_unchanged(value: object) -> None:
    """NA以外の値はそのまま返す。"""
    assert to_cell_value(value) == value
