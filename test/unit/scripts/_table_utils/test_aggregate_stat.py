"""aggregate_stat の単体テスト。"""
import pandas as pd

from scripts._table_utils import aggregate_stat


# 正常系
def test_aggregate_stat_wins() -> None:
    """1着の件数を正しくカウントする。"""
    df = pd.DataFrame({"kakutei_chakujun": [1, 2, 1, 3, 1]})
    assert aggregate_stat(df, "wins") == 3


def test_aggregate_stat_top3() -> None:
    """3着以内の件数を正しくカウントする。"""
    df = pd.DataFrame({"kakutei_chakujun": [1, 2, 3, 4, 5]})
    assert aggregate_stat(df, "top3") == 3


def test_aggregate_stat_win_rate() -> None:
    """勝率を正しく計算する。"""
    df = pd.DataFrame({"kakutei_chakujun": [1, 2, 1, 4]})
    assert aggregate_stat(df, "win_rate") == 0.5


def test_aggregate_stat_with_nan_chakujun() -> None:
    """kakutei_chakujunにNaNが含まれていても正しく集計する。"""
    df = pd.DataFrame({"kakutei_chakujun": [1, float("nan"), 2]})
    assert aggregate_stat(df, "wins") == 1


def test_aggregate_stat_with_empty_df() -> None:
    """空DataFrameはwins=0, top3=0, total=0で計算する。"""
    df = pd.DataFrame({"kakutei_chakujun": []})
    assert aggregate_stat(df, "win_rate") == 0.0


def test_aggregate_stat_without_chakujun_column() -> None:
    """kakutei_chakujunカラムがなくてもゼロ系統計を返す。"""
    df = pd.DataFrame({"other_col": [1, 2, 3]})
    assert aggregate_stat(df, "wins") == 0
