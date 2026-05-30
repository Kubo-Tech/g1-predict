"""sire_race_chakujun の単体テスト。"""
from test.unit.scripts._table_stat.conftest import make_kyosoba_row
from unittest.mock import MagicMock

import pandas as pd

from scripts._table_stat import sire_race_chakujun

_HORSE_ID = "0000000001"
_SIRE_BAMEI = "ディープインパクト"
_SOURCE = {"years": 10}
_RACE_NAME = "東京優駿"


# 正常系
def test_sire_race_chakujun_returns_chakujun_when_sire_found(mock_cache: MagicMock) -> None:
    """父馬が過去レースに出走していたとき着順を返す。"""
    mock_cache.get_kyosoba_row.return_value = make_kyosoba_row(sire_bamei=_SIRE_BAMEI)
    mock_cache.get_past_umagoto_df.return_value = pd.DataFrame(
        {"bamei": [_SIRE_BAMEI, "OTHER"], "kakutei_chakujun": [3, 1]}
    )
    result = sire_race_chakujun(_HORSE_ID, _SOURCE, _RACE_NAME, mock_cache)
    assert result == 3


def test_sire_race_chakujun_returns_none_when_sire_not_in_past(mock_cache: MagicMock) -> None:
    """父馬が過去レースに出走していないときNoneを返す。"""
    mock_cache.get_kyosoba_row.return_value = make_kyosoba_row(sire_bamei=_SIRE_BAMEI)
    mock_cache.get_past_umagoto_df.return_value = pd.DataFrame(
        {"bamei": ["OTHER"], "kakutei_chakujun": [1]}
    )
    assert sire_race_chakujun(_HORSE_ID, _SOURCE, _RACE_NAME, mock_cache) is None


def test_sire_race_chakujun_returns_none_when_no_kyosoba_row(mock_cache: MagicMock) -> None:
    """競走馬マスタが取得できないときNoneを返す。"""
    mock_cache.get_kyosoba_row.return_value = None
    assert sire_race_chakujun(_HORSE_ID, _SOURCE, _RACE_NAME, mock_cache) is None


def test_sire_race_chakujun_returns_none_when_past_umagoto_empty(
    mock_cache: MagicMock,
) -> None:
    """過去データが空のときNoneを返す。"""
    mock_cache.get_kyosoba_row.return_value = make_kyosoba_row(sire_bamei=_SIRE_BAMEI)
    mock_cache.get_past_umagoto_df.return_value = pd.DataFrame()
    assert sire_race_chakujun(_HORSE_ID, _SOURCE, _RACE_NAME, mock_cache) is None


def test_sire_race_chakujun_uses_race_name_for_history_from_source(
    mock_cache: MagicMock,
) -> None:
    """sourceにrace_name_for_historyがあればそちらを使う。"""
    mock_cache.get_kyosoba_row.return_value = make_kyosoba_row(sire_bamei=_SIRE_BAMEI)
    mock_cache.get_past_umagoto_df.return_value = pd.DataFrame()
    source = {**_SOURCE, "race_name_for_history": "日本ダービー"}
    sire_race_chakujun(_HORSE_ID, source, _RACE_NAME, mock_cache)
    mock_cache.get_past_umagoto_df.assert_called_once_with("日本ダービー", 10)
