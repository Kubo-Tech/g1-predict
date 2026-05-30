"""get_kyosoba_row の単体テスト。"""
import pandas as pd

from scripts._table_data_cache import TableDataCache


def _horse_df(horse_id: str) -> pd.DataFrame:
    return pd.DataFrame({"ketto_toroku_bango": [horse_id], "bamei": ["テスト馬"]})


# 正常系
def test_get_kyosoba_row_returns_series_when_found(cache: TableDataCache) -> None:
    """馬が存在するときpd.Seriesを返す。"""
    cache._master_getter.get_kyosoba_master2.return_value = _horse_df("0000000001")
    row = cache.get_kyosoba_row("0000000001")
    assert row is not None
    assert row["bamei"] == "テスト馬"


def test_get_kyosoba_row_returns_none_when_not_found(cache: TableDataCache) -> None:
    """馬が存在しないときNoneを返す。"""
    cache._master_getter.get_kyosoba_master2.return_value = pd.DataFrame()
    assert cache.get_kyosoba_row("9999999999") is None


def test_get_kyosoba_row_caches_result(cache: TableDataCache) -> None:
    """同じhorse_idの2回目以降はgetterを呼ばない。"""
    cache._master_getter.get_kyosoba_master2.return_value = _horse_df("0000000001")
    cache.get_kyosoba_row("0000000001")
    cache.get_kyosoba_row("0000000001")
    assert cache._master_getter.get_kyosoba_master2.call_count == 1


def test_get_kyosoba_row_caches_none_result(cache: TableDataCache) -> None:
    """Noneもキャッシュされ、2回目はgetterを呼ばない。"""
    cache._master_getter.get_kyosoba_master2.return_value = pd.DataFrame()
    cache.get_kyosoba_row("0000000001")
    cache.get_kyosoba_row("0000000001")
    assert cache._master_getter.get_kyosoba_master2.call_count == 1


def test_get_kyosoba_row_fetches_each_horse_id_separately(cache: TableDataCache) -> None:
    """horse_idごとに別々にgetterを呼ぶ。"""
    cache._master_getter.get_kyosoba_master2.return_value = pd.DataFrame()
    cache.get_kyosoba_row("0000000001")
    cache.get_kyosoba_row("0000000002")
    assert cache._master_getter.get_kyosoba_master2.call_count == 2
