"""kishu_course_stat の単体テスト。"""
from test.unit.modules.gen_table.table_stat.conftest import make_umagoto_row
from unittest.mock import MagicMock

import pandas as pd

from g1_predict.modules.gen_table.table_stat import kishu_course_stat

_HORSE_ID = "0000000001"
_KISHU = "00666"
_SOURCE = {
    "keibajo_code": "05",
    "track": "shiba",
    "kyori": 2000,
    "years": 3,
    "stat": "wins",
}


def _hist_df(kishu_codes: list[str], chakujuns: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"kishu_code": kishu_codes, "kakutei_chakujun": chakujuns})


# 正常系
def test_kishu_course_stat_returns_wins(mock_cache: MagicMock) -> None:
    """騎手の当該コース勝利数を返す。"""
    mock_cache.get_umagoto_df.return_value = make_umagoto_row(_HORSE_ID, kishu_code=_KISHU)
    mock_cache.get_course_umagoto_df.return_value = _hist_df(
        [_KISHU, _KISHU, "OTHER"], [1, 2, 1]
    )
    result = kishu_course_stat(_HORSE_ID, {**_SOURCE, "stat": "wins"}, mock_cache)
    assert result == 1


def test_kishu_course_stat_returns_zero_when_hist_empty(mock_cache: MagicMock) -> None:
    """履歴データが空のとき0系統計を返す。"""
    mock_cache.get_umagoto_df.return_value = make_umagoto_row(_HORSE_ID, kishu_code=_KISHU)
    mock_cache.get_course_umagoto_df.return_value = pd.DataFrame()
    result = kishu_course_stat(_HORSE_ID, _SOURCE, mock_cache)
    assert result == 0


def test_kishu_course_stat_returns_none_when_umagoto_empty(mock_cache: MagicMock) -> None:
    """umagoto_dfが空のときNoneを返す。"""
    mock_cache.get_umagoto_df.return_value = pd.DataFrame()
    assert kishu_course_stat(_HORSE_ID, _SOURCE, mock_cache) is None


def test_kishu_course_stat_returns_none_when_horse_not_in_umagoto(
    mock_cache: MagicMock,
) -> None:
    """対象馬がumagoto_dfにないときNoneを返す。"""
    mock_cache.get_umagoto_df.return_value = make_umagoto_row("9999999999", kishu_code=_KISHU)
    assert kishu_course_stat(_HORSE_ID, _SOURCE, mock_cache) is None
