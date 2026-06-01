"""write_kek_comment の単体テスト。"""
import pytest

from g1_predict.modules.utils.tfjv import write_kek_comment


def _make_kek_com(tmp_path: pytest.TempPathFactory, year: str, filename: str) -> tuple[str, str]:
    """空の KEK_COM ファイルを作成し (base_dir, fpath) を返す。"""
    dirpath = tmp_path / "KEK_COM" / year  # type: ignore[operator]
    dirpath.mkdir(parents=True)
    fpath = dirpath / filename  # type: ignore[operator]
    fpath.write_bytes(b"")
    return str(tmp_path), str(fpath)


# 正常系
def test_write_kek_comment_appends_entry(tmp_path: pytest.TempPathFactory) -> None:
    """コメントが ShiftJIS エントリ形式で追記される。"""
    base_dir, fpath = _make_kek_com(tmp_path, "2026", "KC05262A.DAT")

    write_kek_comment(base_dir, "05", "26", "2A", race_no=1, umaban=3, comment="[NHKマイルC] 好走")

    content = open(fpath, "rb").read().decode("shift_jis")
    assert content == '05262A0103,"[NHKマイルC] 好走"\r\n'


def test_write_kek_comment_appends_multiple_entries(tmp_path: pytest.TempPathFactory) -> None:
    """複数回呼んだ場合、既存エントリを壊さず追記される。"""
    base_dir, fpath = _make_kek_com(tmp_path, "2026", "KC05262A.DAT")

    write_kek_comment(base_dir, "05", "26", "2A", race_no=1, umaban=1, comment="first")
    write_kek_comment(base_dir, "05", "26", "2A", race_no=1, umaban=2, comment="second")

    lines = open(fpath, "rb").read().decode("shift_jis").splitlines()
    assert len(lines) == 2
    assert lines[0] == '05262A0101,"first"'
    assert lines[1] == '05262A0102,"second"'


# 準正常系
def test_write_kek_comment_raises_when_file_not_found(tmp_path: pytest.TempPathFactory) -> None:
    """KEK_COM ファイルが存在しない場合は FileNotFoundError が発生する。"""
    with pytest.raises(FileNotFoundError):
        write_kek_comment(str(tmp_path), "05", "26", "2A", race_no=1, umaban=1, comment="test")


def test_write_kek_comment_raises_for_double_quote_in_comment(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """コメントに二重引用符が含まれる場合は ValueError が発生する。"""
    base_dir, _ = _make_kek_com(tmp_path, "2026", "KC05262A.DAT")
    with pytest.raises(ValueError, match="double quotes"):
        write_kek_comment(base_dir, "05", "26", "2A", race_no=1, umaban=1, comment='bad"comment')
