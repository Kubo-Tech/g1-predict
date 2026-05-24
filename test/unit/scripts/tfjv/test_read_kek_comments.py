"""read_kek_comments の単体テスト。"""
import os

import pytest

from scripts.tfjv import read_kek_comments


def _write_kek_com(tmp_path: pytest.TempPathFactory, year: str, filename: str, lines: list[str]) -> str:
    """テスト用 KEK_COM ファイルを作成してパスを返す。"""
    dirpath = tmp_path / "KEK_COM" / year  # type: ignore[operator]
    dirpath.mkdir(parents=True)
    fpath = dirpath / filename  # type: ignore[operator]
    content = "\r\n".join(lines) + "\r\n"
    fpath.write_bytes(content.encode("shift_jis"))
    return str(tmp_path)


# 正常系
def test_read_kek_comments_returns_comments_for_race(tmp_path: pytest.TempPathFactory) -> None:
    """指定レースの馬番とコメントが正しく返される。"""
    base_dir = _write_kek_com(
        tmp_path,
        "2026",
        "KC05262A.DAT",
        [
            '05262A0101,"[NHKマイルC] 先行して伸びた"',
            '05262A0102,"[NHKマイルC] 出遅れた"',
            '05262A0201,"[NHKマイルC] 別レース"',  # race_no=2 は対象外
        ],
    )

    result = read_kek_comments(base_dir, "05", "26", "2A", race_no=1)

    assert result == {
        1: "[NHKマイルC] 先行して伸びた",
        2: "[NHKマイルC] 出遅れた",
    }


def test_read_kek_comments_returns_empty_when_file_not_found(tmp_path: pytest.TempPathFactory) -> None:
    """KEK_COM ファイルが存在しない場合は空辞書を返す。"""
    result = read_kek_comments(str(tmp_path), "05", "26", "2A", race_no=1)

    assert result == {}


def test_read_kek_comments_filters_by_race_no(tmp_path: pytest.TempPathFactory) -> None:
    """異なるレース番号の行は含まれない。"""
    base_dir = _write_kek_com(
        tmp_path,
        "2026",
        "KC05262A.DAT",
        [
            '05262A0101,"[NHKマイルC] race1"',
            '05262A0201,"[NHKマイルC] race2"',
        ],
    )

    result = read_kek_comments(base_dir, "05", "26", "2A", race_no=2)

    assert result == {1: "[NHKマイルC] race2"}
