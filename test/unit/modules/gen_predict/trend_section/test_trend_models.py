"""_trend_models の単体テスト。"""

from g1_predict.modules.gen_predict._trend_models import sire_cache_key


def test_sire_cache_key_basic() -> None:
    """`type` を除いたキーがソート順タプルになる。"""
    src = {
        "type": "sire_race_condition_finisher",
        "race_name": "天皇賞春",
        "kyori": 3200,
    }
    key = sire_cache_key(src)
    assert key == ("kyori", 3200, "race_name", "天皇賞春")


def test_sire_cache_key_excludes_type() -> None:
    """`type` キーが除外される。"""
    src = {"type": "sire_race_condition_finisher", "grade_codes": ["A"]}
    key = sire_cache_key(src)
    assert "type" not in str(key)
    assert key == ("grade_codes", ("A",))


def test_sire_cache_key_list_to_tuple() -> None:
    """List 型の値が tuple に変換される。"""
    src = {"type": "x", "grade_codes": ["A", "B"]}
    key = sire_cache_key(src)
    assert ("grade_codes", ("A", "B")) == key


def test_sire_cache_key_sorted_keys() -> None:
    """キーがソート順で並ぶ。"""
    src = {"type": "x", "z_key": 1, "a_key": 2}
    key = sire_cache_key(src)
    assert key == ("a_key", 2, "z_key", 1)


def test_sire_cache_key_empty_source() -> None:
    """`type` のみの場合は空タプルを返す。"""
    src = {"type": "sire_race_condition_finisher"}
    key = sire_cache_key(src)
    assert key == ()


def test_sire_cache_key_hashable() -> None:
    """生成されたキーが set に格納可能。"""
    src = {"type": "x", "grade_codes": ["A"], "kyori": 2000}
    key = sire_cache_key(src)
    s: set = {key}
    assert key in s
