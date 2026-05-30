"""get_kishu_df の単体テスト。"""
import pandas as pd

from scripts._table_data_cache import TableDataCache


# 正常系
def test_get_kishu_df_calls_getter_on_first_call(cache: TableDataCache) -> None:
    """初回呼び出しでget_shussobetsu_kishuを呼ぶ。"""
    cache._shussobetsu_getter.get_shussobetsu_kishu.return_value = pd.DataFrame({"col": [1]})
    cache.get_kishu_df()
    cache._shussobetsu_getter.get_shussobetsu_kishu.assert_called_once_with(
        race_code="202601011234", convert_codes=False
    )


def test_get_kishu_df_caches_result(cache: TableDataCache) -> None:
    """2回目以降はgetterを呼ばずキャッシュ値を返す。"""
    cache._shussobetsu_getter.get_shussobetsu_kishu.return_value = pd.DataFrame({"col": [1]})
    cache.get_kishu_df()
    cache.get_kishu_df()
    assert cache._shussobetsu_getter.get_shussobetsu_kishu.call_count == 1


def test_get_kishu_df_returns_dataframe(cache: TableDataCache) -> None:
    """DataFrameを返す。"""
    expected = pd.DataFrame({"ketto_toroku_bango": ["0001"], "stat": [0.3]})
    cache._shussobetsu_getter.get_shussobetsu_kishu.return_value = expected
    result = cache.get_kishu_df()
    assert list(result.columns) == ["ketto_toroku_bango", "stat"]
