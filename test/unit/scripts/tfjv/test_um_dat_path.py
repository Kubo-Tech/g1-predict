"""um_dat_path の単体テスト。"""
import os

import pytest

from scripts.tfjv import um_dat_path


# 正常系
@pytest.mark.parametrize(
    "race_code, expected_filename",
    [
        ("2026010105010101", "UM261東.DAT"),
        ("2026010106010101", "UM261中.DAT"),
        ("2026010107010101", "UM261名.DAT"),
        ("2026010108010101", "UM261京.DAT"),
        ("2026010109010101", "UM261阪.DAT"),
        ("2026010110010101", "UM261小.DAT"),
        ("2026050205021011", "UM262東.DAT"),  # kai=2
    ],
)
def test_um_dat_path_constructs_correct_filename(
    race_code: str, expected_filename: str
) -> None:
    """UM*.DAT のファイル名が競馬場・開催回・年から正しく構築される。"""
    base_dir = "/base"
    result = um_dat_path(race_code, base_dir)
    assert result == os.path.join(base_dir, expected_filename)


# 準正常系
def test_um_dat_path_raises_for_unsupported_venue() -> None:
    """未対応の競馬場コードで ValueError が発生する。"""
    with pytest.raises(ValueError, match="Unsupported venue code"):
        um_dat_path("2026010101010101", "/base")  # venue="01" は未対応
