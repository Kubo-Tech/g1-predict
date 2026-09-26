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


def _shosai_with_day(
    race_code: str,
    keibajo: str,
    track_code: str,
    kyori: int,
    kaisai_nen: str,
    kaisai_kai: str,
    kaisai_nichime: str,
    kaisai_gappi: str,
    course_kubun: str,
) -> dict[str, object]:
    return {
        "race_code": race_code,
        "keibajo_code": keibajo,
        "track_code": track_code,
        "kyori": kyori,
        "kaisai_nen": kaisai_nen,
        "kaisai_kai": kaisai_kai,
        "kaisai_nichime": kaisai_nichime,
        "kaisai_gappi": kaisai_gappi,
        "course_kubun": course_kubun,
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


def test_get_course_umagoto_df_week_not_shifted_by_three_day_meeting(
    cache: TableDataCache,
) -> None:
    """3日間開催があってもコース区分の使用開始日から数えた週がずれない。

    2026年4回中山Cコースは9/19・20・21（5〜7日目、週1）と
    9/26・27（8・9日目、週2）。9/27（9日目）はCコース2週目であるべき。
    """
    shosai_df = pd.DataFrame(
        [
            _shosai_with_day("202609190601", "06", "10", 2000, "2026", "04", "05", "0919", "C"),
            _shosai_with_day("202609200601", "06", "10", 2000, "2026", "04", "06", "0920", "C"),
            _shosai_with_day("202609210601", "06", "10", 2000, "2026", "04", "07", "0921", "C"),
            _shosai_with_day("202609260601", "06", "10", 2000, "2026", "04", "08", "0926", "C"),
            _shosai_with_day("202609270601", "06", "10", 2000, "2026", "04", "09", "0927", "C"),
        ]
    )
    cache._race_getter.get_race_shosai.return_value = shosai_df
    cache._race_getter.get_umagoto_race_joho.return_value = pd.DataFrame(
        {"race_code": ["202609270601"]}
    )

    cache.get_course_umagoto_df("06", "shiba", 2000, 3, course_kubun="C", week=2)

    call_kwargs = cache._race_getter.get_umagoto_race_joho.call_args
    assert set(call_kwargs[1]["race_code"]) == {"202609260601", "202609270601"}


def test_get_course_umagoto_df_week_ignores_blank_course_kubun_rows(
    cache: TableDataCache,
) -> None:
    """同日に空文字course_kubunの行が混在しても週番号の計算がぶれない。

    障害競走等でcourse_kubunが空文字のレコードが平地競走と同日に存在しても、
    空文字の行を無視してその日のコース区分を一意に決定する（非決定的にならない）。
    """
    shosai_df = pd.DataFrame(
        [
            _shosai_with_day("202609190601", "06", "10", 2000, "2026", "04", "05", "0919", "C"),
            # 同日・空文字course_kubunの行（障害競走等を想定）
            _shosai_with_day("202609190602", "06", "51", 2000, "2026", "04", "05", "0919", ""),
            _shosai_with_day("202609200601", "06", "10", 2000, "2026", "04", "06", "0920", "C"),
            _shosai_with_day("202609260601", "06", "10", 2000, "2026", "04", "08", "0926", "C"),
        ]
    )
    cache._race_getter.get_race_shosai.return_value = shosai_df
    cache._race_getter.get_umagoto_race_joho.return_value = pd.DataFrame(
        {"race_code": ["dummy"]}
    )

    for _ in range(5):
        cache._course_umagoto_cache.clear()
        cache.get_course_umagoto_df("06", "shiba", 2000, 3, course_kubun="C", week=2)
        call_kwargs = cache._race_getter.get_umagoto_race_joho.call_args
        assert set(call_kwargs[1]["race_code"]) == {"202609260601"}


def test_get_course_umagoto_df_week_without_course_kubun_filters_per_course(
    cache: TableDataCache,
) -> None:
    """course_kubun未指定でも各レース自身のコース区分基準の週で絞り込める。"""
    shosai_df = pd.DataFrame(
        [
            # Aコース: 9/12・13（週1）
            _shosai_with_day("202609120601", "06", "10", 2000, "2026", "04", "01", "0912", "A"),
            _shosai_with_day("202609130601", "06", "10", 2000, "2026", "04", "02", "0913", "A"),
            # Cコース: 9/19-21（週1）、9/26-27（週2）
            _shosai_with_day("202609190601", "06", "10", 2000, "2026", "04", "05", "0919", "C"),
            _shosai_with_day("202609200601", "06", "10", 2000, "2026", "04", "06", "0920", "C"),
            _shosai_with_day("202609260601", "06", "10", 2000, "2026", "04", "08", "0926", "C"),
        ]
    )
    cache._race_getter.get_race_shosai.return_value = shosai_df
    cache._race_getter.get_umagoto_race_joho.return_value = pd.DataFrame(
        {"race_code": ["dummy"]}
    )

    cache.get_course_umagoto_df("06", "shiba", 2000, 3, week=1)

    call_kwargs = cache._race_getter.get_umagoto_race_joho.call_args
    assert set(call_kwargs[1]["race_code"]) == {
        "202609120601",
        "202609130601",
        "202609190601",
        "202609200601",
    }
