"""get_horse_umagoto_df の単体テスト。"""
import pandas as pd

from scripts._table_data_cache import TableDataCache


def _umagoto_df(race_codes: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"race_code": race_codes, "value": range(len(race_codes))})


# 正常系
def test_get_horse_umagoto_df_excludes_current_race(cache: TableDataCache) -> None:
    """現在のrace_codeを含む行を除外する。"""
    cache._race_getter.get_umagoto_race_joho.return_value = _umagoto_df(
        ["202601011234", "202512010101", "202511010101"]
    )
    result = cache.get_horse_umagoto_df("0000000001")
    assert "202601011234" not in result["race_code"].values


def test_get_horse_umagoto_df_sorted_descending(cache: TableDataCache) -> None:
    """race_code降順にソートされている。"""
    cache._race_getter.get_umagoto_race_joho.return_value = _umagoto_df(
        ["202501010101", "202503010101", "202502010101"]
    )
    result = cache.get_horse_umagoto_df("0000000001")
    codes = list(result["race_code"])
    assert codes == sorted(codes, reverse=True)


def test_get_horse_umagoto_df_returns_empty_for_no_races(cache: TableDataCache) -> None:
    """レースなしのとき空DataFrameを返す。"""
    cache._race_getter.get_umagoto_race_joho.return_value = pd.DataFrame()
    result = cache.get_horse_umagoto_df("0000000001")
    assert result.empty


def test_get_horse_umagoto_df_caches_result(cache: TableDataCache) -> None:
    """2回目以降はgetterを呼ばない。"""
    cache._race_getter.get_umagoto_race_joho.return_value = _umagoto_df(
        ["202501010101"]
    )
    cache.get_horse_umagoto_df("0000000001")
    cache.get_horse_umagoto_df("0000000001")
    assert cache._race_getter.get_umagoto_race_joho.call_count == 1
