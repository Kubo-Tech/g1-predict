"""get_race_display_name の単体テスト。"""
from unittest.mock import patch

from g1_predict.modules.gen_table.table_data_cache import TableDataCache


# 正常系
def test_get_race_display_name_returns_resolved_name(cache: TableDataCache) -> None:
    """mykeibadb.analytics.get_race_display_namesの解決結果を返す。"""
    with patch(
        "g1_predict.modules.gen_table.table_data_cache.get_race_display_names",
        return_value={"2017091009040211": "産経賞セントウルステークス"},
    ) as mock_get_names:
        result = cache.get_race_display_name("2017091009040211")

    mock_get_names.assert_called_once_with(
        cache._race_getter.connection_manager, ["2017091009040211"]
    )
    assert result == "産経賞セントウルステークス"


def test_get_race_display_name_caches_result(cache: TableDataCache) -> None:
    """同じrace_codeの2回目以降は再問い合わせしない。"""
    with patch(
        "g1_predict.modules.gen_table.table_data_cache.get_race_display_names",
        return_value={"2017091009040211": "産経賞セントウルステークス"},
    ) as mock_get_names:
        cache.get_race_display_name("2017091009040211")
        cache.get_race_display_name("2017091009040211")

    assert mock_get_names.call_count == 1


def test_get_race_display_name_returns_none_when_not_found(cache: TableDataCache) -> None:
    """race_shosaiに存在しないrace_codeはNoneを返す。"""
    with patch(
        "g1_predict.modules.gen_table.table_data_cache.get_race_display_names",
        return_value={},
    ):
        result = cache.get_race_display_name("9999999999999999")

    assert result is None
