"""sire_race_stat の単体テスト。"""
from test.unit.scripts._table_stat.conftest import make_kyosoba_row
from unittest.mock import MagicMock

import pandas as pd

from scripts._table_stat import sire_race_stat

_HORSE_ID = "0000000001"
_SIRE_HANSHOKU = "SIRE001"
_SIRE_BAMEI = "ディープインパクト"
_SOURCE_WINS = {"years": 10, "stat": "wins"}
_SOURCE_NAME = {"stat": "name"}
_RACE_NAME = "東京優駿"


def _past_kyosoba(horse_ids: list[str], hanshokus: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {"ketto_toroku_bango": horse_ids, "ketto1_hanshoku_toroku_bango": hanshokus}
    )


def _past_umagoto(horse_ids: list[str], chakujuns: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"ketto_toroku_bango": horse_ids, "kakutei_chakujun": chakujuns})


# 正常系
def test_sire_race_stat_returns_name(mock_cache: MagicMock) -> None:
    """stat='name'のとき種牡馬名を返す。"""
    mock_cache.get_kyosoba_row.return_value = make_kyosoba_row(sire_bamei=_SIRE_BAMEI)
    result = sire_race_stat(_HORSE_ID, _SOURCE_NAME, _RACE_NAME, mock_cache)
    assert result == _SIRE_BAMEI


def test_sire_race_stat_returns_none_name_when_no_kyosoba(mock_cache: MagicMock) -> None:
    """stat='name'でkyosoba_rowがNoneのときNoneを返す。"""
    mock_cache.get_kyosoba_row.return_value = None
    assert sire_race_stat(_HORSE_ID, _SOURCE_NAME, _RACE_NAME, mock_cache) is None


def test_sire_race_stat_returns_wins(mock_cache: MagicMock) -> None:
    """種牡馬産駒の勝利数を返す。"""
    mock_cache.get_kyosoba_row.return_value = make_kyosoba_row(sire_hanshoku=_SIRE_HANSHOKU)
    mock_cache.get_past_kyosoba_df.return_value = _past_kyosoba(
        ["AAA", "BBB"], [_SIRE_HANSHOKU, "OTHER"]
    )
    mock_cache.get_past_umagoto_df.return_value = _past_umagoto(["AAA", "BBB"], [1, 2])
    result = sire_race_stat(_HORSE_ID, _SOURCE_WINS, _RACE_NAME, mock_cache)
    assert result == 1


def test_sire_race_stat_returns_zero_when_no_kyosoba(mock_cache: MagicMock) -> None:
    """競走馬マスタが取得できないとき0系統計を返す。"""
    mock_cache.get_kyosoba_row.return_value = None
    assert sire_race_stat(_HORSE_ID, _SOURCE_WINS, _RACE_NAME, mock_cache) == 0


def test_sire_race_stat_returns_zero_when_past_empty(mock_cache: MagicMock) -> None:
    """過去データが空のとき0系統計を返す。"""
    mock_cache.get_kyosoba_row.return_value = make_kyosoba_row(sire_hanshoku=_SIRE_HANSHOKU)
    mock_cache.get_past_umagoto_df.return_value = pd.DataFrame()
    assert sire_race_stat(_HORSE_ID, _SOURCE_WINS, _RACE_NAME, mock_cache) == 0
