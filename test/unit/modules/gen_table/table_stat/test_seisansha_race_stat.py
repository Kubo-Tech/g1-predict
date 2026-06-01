"""seisansha_race_stat の単体テスト。"""
from test.unit.modules.gen_table.table_stat.conftest import make_kyosoba_row
from unittest.mock import MagicMock

import pandas as pd

from g1_predict.modules.gen_table.table_stat import seisansha_race_stat

_HORSE_ID = "0000000001"
_SEISANSHA = "BREEDER01"
_SOURCE = {"years": 10, "stat": "wins"}
_RACE_NAME = "東京優駿"


def _past_umagoto(horse_ids: list[str], chakujuns: list[int]) -> pd.DataFrame:
    return pd.DataFrame(
        {"ketto_toroku_bango": horse_ids, "kakutei_chakujun": chakujuns}
    )


def _past_kyosoba(horse_ids: list[str], seisansha_codes: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {"ketto_toroku_bango": horse_ids, "seisansha_code": seisansha_codes}
    )


# 正常系
def test_seisansha_race_stat_returns_wins(mock_cache: MagicMock) -> None:
    """生産者の該当レース勝利数を返す。"""
    kyosoba = make_kyosoba_row(seisansha_code=_SEISANSHA)
    kyosoba.index = ["seisansha_code"]
    kyosoba.__contains__ = lambda self, key: key == "seisansha_code"
    kyosoba.__getitem__ = lambda self, key: _SEISANSHA if key == "seisansha_code" else None
    mock_cache.get_kyosoba_row.return_value = kyosoba
    mock_cache.get_past_kyosoba_df.return_value = _past_kyosoba(["AAA", "BBB"], [_SEISANSHA, "X"])
    mock_cache.get_past_umagoto_df.return_value = _past_umagoto(["AAA", "BBB"], [1, 2])
    result = seisansha_race_stat(_HORSE_ID, _SOURCE, _RACE_NAME, mock_cache)
    assert result == 1


def test_seisansha_race_stat_returns_zero_when_no_kyosoba(mock_cache: MagicMock) -> None:
    """競走馬マスタが取得できないとき0系統計を返す。"""
    mock_cache.get_kyosoba_row.return_value = None
    assert seisansha_race_stat(_HORSE_ID, _SOURCE, _RACE_NAME, mock_cache) == 0


def test_seisansha_race_stat_returns_zero_when_past_empty(mock_cache: MagicMock) -> None:
    """過去データが空のとき0系統計を返す。"""
    kyosoba = make_kyosoba_row(seisansha_code=_SEISANSHA)
    kyosoba.index = ["seisansha_code"]
    kyosoba.__contains__ = lambda self, key: key == "seisansha_code"
    mock_cache.get_kyosoba_row.return_value = kyosoba
    mock_cache.get_past_umagoto_df.return_value = pd.DataFrame()
    assert seisansha_race_stat(_HORSE_ID, _SOURCE, _RACE_NAME, mock_cache) == 0
