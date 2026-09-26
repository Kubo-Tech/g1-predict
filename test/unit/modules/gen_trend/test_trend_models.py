"""_trend_models の単体テスト。"""

from g1_predict.modules.gen_trend._trend_models import RowStats


def test_rowstats_default_values() -> None:
    """RowStats のデフォルト値が全て 0 / 0.0 になる。"""
    s = RowStats()
    assert s.first == 0
    assert s.second == 0
    assert s.third == 0
    assert s.fourth_plus == 0
    assert s.tansho_kaishuu == 0.0
    assert s.fukusho_kaishuu == 0.0
    assert s.total == 0


def test_rowstats_fields_assignable() -> None:
    """RowStats のフィールドに値を設定できる。"""
    s = RowStats(
        first=3,
        second=2,
        third=1,
        fourth_plus=4,
        tansho_kaishuu=85.5,
        fukusho_kaishuu=72.3,
        total=10,
    )
    assert s.first == 3
    assert s.tansho_kaishuu == 85.5
    assert s.fukusho_kaishuu == 72.3
    assert s.total == 10
