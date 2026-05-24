"""gen_result_comment 統合テスト。

実際の MY_DATA ディレクトリに書き込むテスト。
DB 接続不可の場合はスキップする。
"""
import os
from collections.abc import Generator

import pytest

from scripts.gen_result_comment import generate_result_comments

_BASE_DIR = os.environ.get("TFJV_DATA_DIR", "/KeibaAI/repos/g1-predict/MY_DATA")
_RACE_CODE = "2026013105010110"
_KEK_COM_PATH = os.path.join(_BASE_DIR, "KEK_COM", "2026", "KC052611.DAT")


@pytest.fixture
def restore_kek_com() -> Generator[None, None, None]:
    """テスト前後で KEK_COM ファイルを元に戻す。"""
    original = open(_KEK_COM_PATH, "rb").read()
    yield
    with open(_KEK_COM_PATH, "wb") as f:
        f.write(original)


@pytest.fixture
def skip_if_no_db() -> None:
    """DB 接続不可の場合はテストをスキップする。"""
    try:
        from keiba_data_interface import DataInterface

        di = DataInterface("mykeibadb")
        di.get_race_basic_info(_RACE_CODE)
    except Exception as e:
        pytest.skip(f"DB 接続不可: {e}")


def test_generate_result_comments_appends_to_real_file(
    skip_if_no_db: None,
    restore_kek_com: None,
) -> None:
    """実際の KEK_COM ファイルに結果定型文が正しいフォーマットで追記される。"""
    original_lines = open(_KEK_COM_PATH, "rb").read().decode("shift_jis").splitlines()

    generate_result_comments(_RACE_CODE, _BASE_DIR)

    new_content = open(_KEK_COM_PATH, "rb").read().decode("shift_jis")
    new_lines = new_content.splitlines()
    appended = new_lines[len(original_lines) :]

    assert len(appended) > 0, "結果定型文が追記されていない"
    for line in appended:
        assert "[クロッカスステークス]" in line
        assert "着。" in line
        assert line.startswith("052611")


def test_generate_result_comments_preserves_existing_entries(
    skip_if_no_db: None,
    restore_kek_com: None,
) -> None:
    """既存エントリが破壊されない。"""
    original = open(_KEK_COM_PATH, "rb").read()
    original_lines = original.decode("shift_jis").splitlines()

    generate_result_comments(_RACE_CODE, _BASE_DIR)

    new_content = open(_KEK_COM_PATH, "rb").read().decode("shift_jis")
    new_lines = new_content.splitlines()
    for line in original_lines:
        assert line in new_lines, f"既存エントリが消えた: {line!r}"
