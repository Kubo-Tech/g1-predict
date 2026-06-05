"""get_course_umagoto_df の単体テスト。"""
import pandas as pd

from g1_predict.modules.gen_table.table_data_cache import TableDataCache


def _shosai(race_code: str, keibajo: str, track_code: str, kyori: int) -> dict[str, object]:
    return {
        "race_code": race_code,
        "keibajo_code": keibajo,
        "track_code": track_code,
        "kyori": kyori,
    }


# 正常系
def test_get_course_umagoto_df_filters_by_keibajo_track_kyori(
    cache: TableDataCache,
) -> None:
    """keibajo_code・track_code・kyoriで絞り込む。"""
    shosai_df = pd.DataFrame(
        [
            _shosai("202501010101", "05", "10", 2000),  # 東京芝2000 → 対象
            _shosai("202501010102", "06", "10", 2000),  # 中山 → 除外
            _shosai("202501010103", "05", "23", 2000),  # ダート → 除外
            _shosai("202501010104", "05", "10", 1600),  # 距離違い → 除外
        ]
    )
    cache._race_getter.get_race_shosai.return_value = shosai_df
    cache._race_getter.get_umagoto_race_joho.return_value = pd.DataFrame(
        {"race_code": ["202501010101"]}
    )

    cache.get_course_umagoto_df("05", "shiba", 2000, 3)
    cache._race_getter.get_umagoto_race_joho.assert_called_once()
    call_kwargs = cache._race_getter.get_umagoto_race_joho.call_args
    assert "202501010101" in call_kwargs[1]["race_code"]


def test_get_course_umagoto_df_returns_empty_when_no_shosai(
    cache: TableDataCache,
) -> None:
    """shosaiが空のとき空DataFrameを返す。"""
    cache._race_getter.get_race_shosai.return_value = pd.DataFrame()
    result = cache.get_course_umagoto_df("05", "shiba", 2000, 3)
    assert result.empty


def test_get_course_umagoto_df_returns_empty_when_no_match(
    cache: TableDataCache,
) -> None:
    """条件に一致するレースがないとき空DataFrameを返す。"""
    shosai_df = pd.DataFrame(
        [_shosai("202501010101", "06", "10", 2000)]  # 中山 → 除外
    )
    cache._race_getter.get_race_shosai.return_value = shosai_df
    result = cache.get_course_umagoto_df("05", "shiba", 2000, 3)
    assert result.empty


def test_get_course_umagoto_df_caches_result(cache: TableDataCache) -> None:
    """同じパラメータの2回目以降はgetterを呼ばない。"""
    cache._race_getter.get_race_shosai.return_value = pd.DataFrame()
    cache.get_course_umagoto_df("05", "shiba", 2000, 3)
    cache.get_course_umagoto_df("05", "shiba", 2000, 3)
    assert cache._race_getter.get_race_shosai.call_count == 1


def test_get_course_umagoto_df_different_params_fetch_separately(
    cache: TableDataCache,
) -> None:
    """パラメータが異なれば別々にgetterを呼ぶ。"""
    cache._race_getter.get_race_shosai.return_value = pd.DataFrame()
    cache.get_course_umagoto_df("05", "shiba", 2000, 3)
    cache.get_course_umagoto_df("06", "shiba", 2000, 3)
    assert cache._race_getter.get_race_shosai.call_count == 2
