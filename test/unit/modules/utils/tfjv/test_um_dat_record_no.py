"""um_dat_record_no の単体テスト。"""
import pytest

from g1_predict.modules.utils.tfjv import um_dat_record_no


# 正常系
@pytest.mark.parametrize(
    "race_code, expected",
    [
        ("2026051005020611", 12),   # nichi=6,  race_no=11 → 2*6+11-11=12  (NHKマイルC)
        ("2026051705020811", 16),   # nichi=8,  race_no=11 → 2*8+11-11=16  (ヴィクトリアマイル)
        ("2026052405021011", 20),   # nichi=10, race_no=11 → 2*10+11-11=20 (優駿牝馬)
        ("2026051705020809", 14),   # nichi=8,  race_no=9  → 2*8+9-11=14
    ],
)
def test_um_dat_record_no_returns_correct_record_no(race_code: str, expected: int) -> None:
    """レコード番号 = 2*nichi + race_no - 11 を返す。"""
    assert um_dat_record_no(race_code) == expected
