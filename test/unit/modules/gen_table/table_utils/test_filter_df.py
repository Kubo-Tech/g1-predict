"""filter_df の単体テスト。"""
import pandas as pd

from g1_predict.modules.gen_table.table_utils import filter_df


def _make_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "chakujun": [1, 2, 3, 4, 5],
            "kyori": [1600, 2000, 1600, 2400, 2000],
            "label": ["a", "b", "a", "c", "b"],
        }
    )


# 正常系
def test_filter_df_equal_operator() -> None:
    """== フィルタで一致する行を返す。"""
    df = _make_df()
    filters = [{"field": "chakujun", "op": "==", "value": 1}]
    result = filter_df(df, filters)
    assert list(result["chakujun"]) == [1]


def test_filter_df_lte_operator() -> None:
    """<= フィルタで条件を満たす行を返す。"""
    df = _make_df()
    filters = [{"field": "chakujun", "op": "<=", "value": 3}]
    result = filter_df(df, filters)
    assert list(result["chakujun"]) == [1, 2, 3]


def test_filter_df_in_operator() -> None:
    """in フィルタで一致する行を返す。"""
    df = _make_df()
    filters = [{"field": "label", "op": "in", "value": ["a", "c"]}]
    result = filter_df(df, filters)
    assert set(result["label"]) == {"a", "c"}


def test_filter_df_multiple_filters_applied_sequentially() -> None:
    """複数フィルタは順次 AND 適用される。"""
    df = _make_df()
    filters = [
        {"field": "chakujun", "op": "<=", "value": 3},
        {"field": "kyori", "op": "==", "value": 1600},
    ]
    result = filter_df(df, filters)
    assert list(result["chakujun"]) == [1, 3]


def test_filter_df_missing_field_returns_empty() -> None:
    """存在しないfieldは空DataFrameを返す。"""
    df = _make_df()
    filters = [{"field": "nonexistent", "op": "==", "value": 1}]
    result = filter_df(df, filters)
    assert result.empty


def test_filter_df_with_empty_filters_returns_original() -> None:
    """フィルタ空リストは元のDataFrameをそのまま返す。"""
    df = _make_df()
    result = filter_df(df, [])
    assert len(result) == len(df)


# 準正常系
def test_filter_df_unknown_op_raises_value_error() -> None:
    """不明なopはValueErrorを発生させる。"""
    import pytest

    df = _make_df()
    filters = [{"field": "chakujun", "op": "UNKNOWN", "value": 1}]
    with pytest.raises(ValueError):
        filter_df(df, filters)
