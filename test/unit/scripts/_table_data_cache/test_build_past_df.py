"""build_past_df の単体テスト。"""
from unittest.mock import patch

import pandas as pd

from scripts._table_data_cache import TableDataCache


def _past_df(race_codes: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"レースコード": race_codes, "着順": [1] * len(race_codes)})


def _race_shosai(race_codes: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "race_code": race_codes,
            "レースコード": race_codes,
            "kyori": [2000] * len(race_codes),
        }
    )


# 正常系
def test_build_past_df_excludes_current_race(cache: TableDataCache) -> None:
    """現在のrace_codeの行を除外する。"""
    past = _past_df(["202601011234", "202512010101"])
    cache._di.get_past_performances.return_value = past
    cache._race_getter.get_race_shosai.return_value = pd.DataFrame()

    result = cache.build_past_df("0000000001")
    assert "202601011234" not in result["レースコード"].values


def test_build_past_df_returns_empty_when_no_past_perfs(cache: TableDataCache) -> None:
    """過去成績なしのとき空DataFrameを返す。"""
    cache._di.get_past_performances.return_value = pd.DataFrame()
    result = cache.build_past_df("0000000001")
    assert result.empty


def test_build_past_df_caches_result(cache: TableDataCache) -> None:
    """同じhorse_idの2回目はDIを呼ばない。"""
    cache._di.get_past_performances.return_value = pd.DataFrame()
    cache.build_past_df("0000000001")
    cache.build_past_df("0000000001")
    assert cache._di.get_past_performances.call_count == 1


def test_build_past_df_merges_race_basic_info(cache: TableDataCache) -> None:
    """RACE_BASIC_INFOのカラムがマージされる。"""
    past = _past_df(["202512010101"])
    cache._di.get_past_performances.return_value = past

    shosai_raw = pd.DataFrame(
        {
            "race_code": ["202512010101"],
            "keibajo_code": ["05"],
        }
    )
    cache._race_getter.get_race_shosai.return_value = shosai_raw

    rename_map = {"race_code": "レースコード"}
    basic_info_cols = ["レースコード", "keibajo_code"]

    with (
        patch("scripts._table_data_cache.RACE_INFO_RENAME", rename_map),
        patch("scripts._table_data_cache.RACE_BASIC_INFO_COLUMNS", basic_info_cols),
    ):
        result = cache.build_past_df("0000000001")

    assert "keibajo_code" in result.columns
