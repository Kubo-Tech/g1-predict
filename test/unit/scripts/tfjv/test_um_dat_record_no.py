"""um_dat_record_no の単体テスト。"""
import pytest

from scripts.tfjv import um_dat_record_no


# 正常系
@pytest.mark.parametrize(
    "race_code, expected",
    [
        ("2026052305021011", 11),   # 5/23(土) race_no=11 → 0*9+11=11
        ("2026052405021011", 20),   # 5/24(日) race_no=11 → 1*9+11=20
        ("2026052305021001", 1),    # 5/23(土) race_no=1  → 1
        ("2026052405021012", 21),   # 5/24(日) race_no=12 → 9+12=21
    ],
)
def test_um_dat_record_no_returns_correct_record_no(race_code: str, expected: int) -> None:
    """土曜は race_no そのまま、日曜は 12+race_no のレコード番号を返す。"""
    assert um_dat_record_no(race_code) == expected
