"""sire_course_stat の単体テスト。"""
from test.unit.modules.gen_table.table_stat.conftest import make_kyosoba_row
from unittest.mock import MagicMock

import pandas as pd

from g1_predict.modules.gen_table.table_stat import sire_course_stat

_HORSE_ID = "0000000001"
_SIRE_HANSHOKU = "SIRE001"
_SOURCE = {"keibajo_code": "05", "track": "shiba", "kyori": 2000, "years": 3, "stat": "wins"}


def _course_kyosoba(horse_ids: list[str], hanshokus: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {"ketto_toroku_bango": horse_ids, "ketto1_hanshoku_toroku_bango": hanshokus}
    )


def _course_umagoto(horse_ids: list[str], chakujuns: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"ketto_toroku_bango": horse_ids, "kakutei_chakujun": chakujuns})


# 正常系
def test_sire_course_stat_returns_wins(mock_cache: MagicMock) -> None:
    """種牡馬産駒の当該コース勝利数を返す。"""
    mock_cache.get_kyosoba_row.return_value = make_kyosoba_row(sire_hanshoku=_SIRE_HANSHOKU)
    mock_cache.get_course_umagoto_df.return_value = _course_umagoto(
        ["AAA", "BBB"], [1, 2]
    )
    mock_cache.get_course_kyosoba_df.return_value = _course_kyosoba(
        ["AAA", "BBB"], [_SIRE_HANSHOKU, "OTHER"]
    )
    result = sire_course_stat(_HORSE_ID, _SOURCE, mock_cache)
    assert result == 1


def test_sire_course_stat_returns_zero_when_no_kyosoba(mock_cache: MagicMock) -> None:
    """競走馬マスタが取得できないとき0系統計を返す。"""
    mock_cache.get_kyosoba_row.return_value = None
    assert sire_course_stat(_HORSE_ID, _SOURCE, mock_cache) == 0


def test_sire_course_stat_returns_zero_when_course_umagoto_empty(
    mock_cache: MagicMock,
) -> None:
    """コースデータが空のとき0系統計を返す。"""
    mock_cache.get_kyosoba_row.return_value = make_kyosoba_row(sire_hanshoku=_SIRE_HANSHOKU)
    mock_cache.get_course_umagoto_df.return_value = pd.DataFrame()
    assert sire_course_stat(_HORSE_ID, _SOURCE, mock_cache) == 0


def test_sire_course_stat_passes_track_condition_to_cache(mock_cache: MagicMock) -> None:
    """track_conditionがソースにあればキャッシュに渡す。"""
    mock_cache.get_kyosoba_row.return_value = make_kyosoba_row(sire_hanshoku=_SIRE_HANSHOKU)
    mock_cache.get_course_umagoto_df.return_value = pd.DataFrame()
    source = {**_SOURCE, "track_condition": "1"}
    sire_course_stat(_HORSE_ID, source, mock_cache)
    mock_cache.get_course_umagoto_df.assert_called_once_with(
        "05", "shiba", 2000, 3, track_condition="1"
    )
