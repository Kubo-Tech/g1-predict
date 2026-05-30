"""kishu_continuity の単体テスト。"""
from test.unit.scripts._table_stat.conftest import make_umagoto_row
from unittest.mock import MagicMock

import pandas as pd

from scripts._table_stat import kishu_continuity

_HORSE_ID = "0000000001"
_KISHU_A = "00666"
_KISHU_B = "00100"


# 正常系
def test_kishu_continuity_returns_keizoku_when_same_kishu(mock_cache: MagicMock) -> None:
    """直前と同じ騎手のとき「継続」を返す。"""
    mock_cache.get_umagoto_df.return_value = make_umagoto_row(_HORSE_ID, kishu_code=_KISHU_A)
    mock_cache.get_horse_umagoto_df.return_value = pd.DataFrame(
        {"kishu_code": [_KISHU_A, _KISHU_B]}
    )
    assert kishu_continuity(_HORSE_ID, mock_cache) == "継続"


def test_kishu_continuity_returns_ten_nori_when_new_kishu(mock_cache: MagicMock) -> None:
    """過去に乗ったことのない騎手のとき「テン乗り」を返す。"""
    mock_cache.get_umagoto_df.return_value = make_umagoto_row(_HORSE_ID, kishu_code=_KISHU_A)
    mock_cache.get_horse_umagoto_df.return_value = pd.DataFrame({"kishu_code": [_KISHU_B]})
    assert kishu_continuity(_HORSE_ID, mock_cache) == "テン乗り"


def test_kishu_continuity_returns_ten_nori_when_no_past_races(mock_cache: MagicMock) -> None:
    """過去レースがないとき「テン乗り」を返す。"""
    mock_cache.get_umagoto_df.return_value = make_umagoto_row(_HORSE_ID, kishu_code=_KISHU_A)
    mock_cache.get_horse_umagoto_df.return_value = pd.DataFrame()
    assert kishu_continuity(_HORSE_ID, mock_cache) == "テン乗り"


def test_kishu_continuity_returns_nori_modori_when_rode_before(mock_cache: MagicMock) -> None:
    """過去に乗ったがすぐ前ではないとき「乗り戻り」を返す。"""
    mock_cache.get_umagoto_df.return_value = make_umagoto_row(_HORSE_ID, kishu_code=_KISHU_A)
    mock_cache.get_horse_umagoto_df.return_value = pd.DataFrame(
        {"kishu_code": [_KISHU_B, _KISHU_A]}
    )
    assert kishu_continuity(_HORSE_ID, mock_cache) == "乗り戻り"


def test_kishu_continuity_returns_none_when_umagoto_empty(mock_cache: MagicMock) -> None:
    """umagoto_dfが空のときNoneを返す。"""
    mock_cache.get_umagoto_df.return_value = pd.DataFrame()
    assert kishu_continuity(_HORSE_ID, mock_cache) is None


def test_kishu_continuity_returns_none_when_horse_not_in_umagoto(
    mock_cache: MagicMock,
) -> None:
    """umagoto_dfに対象馬がいないときNoneを返す。"""
    mock_cache.get_umagoto_df.return_value = make_umagoto_row("9999999999", kishu_code=_KISHU_A)
    assert kishu_continuity(_HORSE_ID, mock_cache) is None
