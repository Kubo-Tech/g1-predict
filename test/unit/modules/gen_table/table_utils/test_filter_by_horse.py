"""filter_by_horse の単体テスト。"""
import pandas as pd

from g1_predict.modules.gen_table.table_utils import filter_by_horse


def _make_df() -> pd.DataFrame:
    """テスト用DataFrameを返す。"""
    return pd.DataFrame(
        {
            "ketto_toroku_bango": ["0000000001", "0000000002", "0000000001"],
            "value": [10, 20, 30],
        }
    )


# 正常系
def test_filter_by_horse_returns_matching_rows() -> None:
    """指定horse_idの行のみ返す。"""
    df = _make_df()
    result = filter_by_horse(df, "0000000001")
    assert len(result) == 2
    assert set(result["value"]) == {10, 30}


def test_filter_by_horse_returns_empty_when_not_found() -> None:
    """存在しないhorse_idは空DataFrameを返す。"""
    df = _make_df()
    result = filter_by_horse(df, "9999999999")
    assert result.empty


def test_filter_by_horse_strips_whitespace() -> None:
    """ketto_toroku_bangoの前後空白を無視してマッチする。"""
    df = pd.DataFrame({"ketto_toroku_bango": [" 0000000001 "], "value": [1]})
    result = filter_by_horse(df, "0000000001")
    assert len(result) == 1
