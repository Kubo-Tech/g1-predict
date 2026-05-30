"""_table_stat テスト共通fixture。"""
from unittest.mock import MagicMock

import pandas as pd
import pytest

from scripts._table_data_cache import TableDataCache


@pytest.fixture
def mock_cache() -> MagicMock:
    """TableDataCacheのモック。"""
    cache = MagicMock(spec=TableDataCache)
    cache.get_umagoto_df.return_value = pd.DataFrame()
    cache.get_course_umagoto_df.return_value = pd.DataFrame()
    cache.get_kyosoba_row.return_value = None
    cache.get_past_umagoto_df.return_value = pd.DataFrame()
    cache.get_past_kyosoba_df.return_value = pd.DataFrame()
    cache.get_course_kyosoba_df.return_value = pd.DataFrame()
    cache.get_horse_umagoto_df.return_value = pd.DataFrame()
    return cache


def make_umagoto_row(
    horse_id: str = "0000000001",
    wakuban: int | None = 3,
    kishu_code: str | None = "00666",
) -> pd.DataFrame:
    """出走馬1行のumagoto DataFrameを生成する。"""
    row: dict[str, object] = {"ketto_toroku_bango": horse_id}
    if wakuban is not None:
        row["wakuban"] = wakuban
    if kishu_code is not None:
        row["kishu_code"] = kishu_code
    return pd.DataFrame([row])


def make_kyosoba_row(
    horse_id: str = "0000000001",
    seisansha_code: str = "BREEDER01",
    sire_hanshoku: str = "SIRE001",
    sire_bamei: str = "ディープインパクト",
) -> MagicMock:
    """pd.Seriesのモックを生成する。"""
    row = MagicMock()
    row.index = [
        "ketto_toroku_bango",
        "seisansha_code",
        "ketto1_hanshoku_toroku_bango",
        "ketto1_bamei",
    ]
    row.__contains__ = lambda self, key: key in row.index
    row.get = lambda key, default=None: {
        "ketto_toroku_bango": horse_id,
        "seisansha_code": seisansha_code,
        "ketto1_hanshoku_toroku_bango": sire_hanshoku,
        "ketto1_bamei": sire_bamei,
    }.get(key, default)
    row.__getitem__ = lambda self, key: row.get(key)
    return row
