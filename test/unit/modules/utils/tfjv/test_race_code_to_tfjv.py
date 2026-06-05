"""race_code_to_tfjv の単体テスト。"""
import pytest

from g1_predict.modules.utils.tfjv import race_code_to_tfjv


# 正常系
@pytest.mark.parametrize(
    "race_code, expected",
    [
        ("2026050205021011", ("05", "26", "2A")),  # SPEC例: kai=2, nichi=10
        ("2026010106010101", ("06", "26", "11")),  # kai=1, nichi=1 (全桁10進)
        ("2025010109060801", ("09", "25", "68")),  # kai=6, nichi=8 (全桁10進)
        ("2024010110100101", ("10", "24", "A1")),  # kai=10 (16進A), nichi=1
    ],
)
def test_race_code_to_tfjv_returns_correct_tuple(
    race_code: str, expected: tuple[str, str, str]
) -> None:
    """race_code から (競馬場コード, YY, 開催コード) を正しく返す。"""
    assert race_code_to_tfjv(race_code) == expected
