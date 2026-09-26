"""get_chokyo_match_days の単体テスト。"""
from unittest.mock import patch

from mykeibadb.analytics import ChokyoThreshold

from g1_predict.modules.gen_table.table_data_cache import TableDataCache

_CONDITION = [ChokyoThreshold(course="hanro", metric="gokei", furlong=2, max_value=239)]


# 正常系
def test_get_chokyo_match_days_returns_resolved_mapping(cache: TableDataCache) -> None:
    """mykeibadb.analytics.get_chokyo_match_daysの解決結果を返す。"""
    with patch(
        "g1_predict.modules.gen_table.table_data_cache.get_chokyo_match_days",
        return_value={"2020100001": [(1, True), (8, False)]},
    ) as mock_get:
        result = cache.get_chokyo_match_days(_CONDITION, 1, 13)

    mock_get.assert_called_once_with(
        cache._race_getter.connection_manager, cache.race_code, _CONDITION, 1, 13
    )
    assert result == {"2020100001": [(1, True), (8, False)]}


def test_get_chokyo_match_days_caches_by_condition_and_days(cache: TableDataCache) -> None:
    """同じchokyo_condition/days_from/days_toの2回目以降は再問い合わせしない。"""
    with patch(
        "g1_predict.modules.gen_table.table_data_cache.get_chokyo_match_days",
        return_value={},
    ) as mock_get:
        cache.get_chokyo_match_days(_CONDITION, 1, 13)
        cache.get_chokyo_match_days(_CONDITION, 1, 13)

    assert mock_get.call_count == 1


def test_get_chokyo_match_days_different_days_fetch_separately(cache: TableDataCache) -> None:
    """days_from/days_toが異なれば別々に問い合わせる。"""
    with patch(
        "g1_predict.modules.gen_table.table_data_cache.get_chokyo_match_days",
        return_value={},
    ) as mock_get:
        cache.get_chokyo_match_days(_CONDITION, 1, 13)
        cache.get_chokyo_match_days(_CONDITION, 1, 20)

    assert mock_get.call_count == 2
