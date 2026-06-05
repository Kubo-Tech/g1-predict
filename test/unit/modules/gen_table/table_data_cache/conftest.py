"""_table_data_cache テスト共通fixture。"""
from unittest.mock import MagicMock, patch

import pytest

from g1_predict.modules.gen_table.table_data_cache import TableDataCache


@pytest.fixture
def mock_di() -> MagicMock:
    """DataInterfaceのモック。"""
    return MagicMock()


@pytest.fixture
def cache(mock_di: MagicMock) -> TableDataCache:
    """外部依存をモック化したTableDataCache。"""
    with (
        patch("g1_predict.modules.gen_table.table_data_cache.RaceGetter"),
        patch("g1_predict.modules.gen_table.table_data_cache.MasterGetter"),
        patch("g1_predict.modules.gen_table.table_data_cache.ShussobetsuGetter"),
    ):
        c = TableDataCache("202601011234", 2026, mock_di)
    c._race_getter = MagicMock()
    c._master_getter = MagicMock()
    c._shussobetsu_getter = MagicMock()
    return c
