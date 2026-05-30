"""waku_stat の単体テスト。"""
from test.unit.scripts._table_stat.conftest import make_umagoto_row
from unittest.mock import MagicMock

import pandas as pd

from scripts._table_stat import waku_stat

_HORSE_ID = "0000000001"
_SOURCE_BASE = {
    "keibajo_code": "05",
    "track": "shiba",
    "kyori": 2000,
    "years": 3,
    "stat": "wins",
}


def _hist_df(wakubans: list[int], chakujuns: list[int]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "race_code": [f"20250101010{i}" for i in range(len(wakubans))],
            "wakuban": wakubans,
            "kakutei_chakujun": chakujuns,
        }
    )


# 正常系
def test_waku_stat_returns_wins_count(mock_cache: MagicMock) -> None:
    """対象枠の勝利数を返す。"""
    mock_cache.get_umagoto_df.return_value = make_umagoto_row(_HORSE_ID, wakuban=3)
    mock_cache.get_course_umagoto_df.return_value = _hist_df([3, 3, 5], [1, 2, 1])
    result = waku_stat(_HORSE_ID, {**_SOURCE_BASE, "stat": "wins"}, mock_cache)
    assert result == 1


def test_waku_stat_returns_top3_count(mock_cache: MagicMock) -> None:
    """対象枠の3着以内数を返す。"""
    mock_cache.get_umagoto_df.return_value = make_umagoto_row(_HORSE_ID, wakuban=3)
    mock_cache.get_course_umagoto_df.return_value = _hist_df([3, 3, 5], [1, 3, 1])
    result = waku_stat(_HORSE_ID, {**_SOURCE_BASE, "stat": "top3"}, mock_cache)
    assert result == 2


def test_waku_stat_returns_none_when_umagoto_empty(mock_cache: MagicMock) -> None:
    """umagoto_dfが空のときNoneを返す。"""
    mock_cache.get_umagoto_df.return_value = pd.DataFrame()
    assert waku_stat(_HORSE_ID, _SOURCE_BASE, mock_cache) is None


def test_waku_stat_returns_none_when_horse_not_in_umagoto(mock_cache: MagicMock) -> None:
    """対象馬がumagoto_dfにないときNoneを返す。"""
    mock_cache.get_umagoto_df.return_value = make_umagoto_row("9999999999", wakuban=3)
    assert waku_stat(_HORSE_ID, _SOURCE_BASE, mock_cache) is None


def test_waku_stat_returns_none_when_hist_empty(mock_cache: MagicMock) -> None:
    """履歴データが空のときNoneを返す。"""
    mock_cache.get_umagoto_df.return_value = make_umagoto_row(_HORSE_ID, wakuban=3)
    mock_cache.get_course_umagoto_df.return_value = pd.DataFrame()
    assert waku_stat(_HORSE_ID, _SOURCE_BASE, mock_cache) is None
