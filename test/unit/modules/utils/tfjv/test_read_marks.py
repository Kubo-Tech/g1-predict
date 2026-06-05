"""read_marks の単体テスト。"""
import pytest

from g1_predict.modules.utils.tfjv import MARK_LINE, read_marks


def _build_um_dat(marks: dict[int, bytes]) -> bytes:
    """テスト用 UM*.DAT バイナリデータを1レコード分生成する。"""
    lines = []
    for i in range(6):
        if i == MARK_LINE:
            content = bytearray(b"\x20\x20" * 21)
            for umaban, mark_bytes in marks.items():
                slot = umaban + 2
                content[slot * 2] = mark_bytes[0]
                content[slot * 2 + 1] = mark_bytes[1]
            lines.append(bytes(content) + b"\r\n")
        else:
            lines.append(b" " * 42 + b"\r\n")
    return b"".join(lines)


# 正常系
def test_read_marks_returns_marked_horses(tmp_path: pytest.TempPathFactory) -> None:
    """印のある馬番と記号が正しく返される。"""
    marks_input = {
        1: bytes([0x81, 0x9D]),  # ◎
        3: bytes([0x81, 0x9B]),  # ○
        5: bytes([0x81, 0xA3]),  # ▲
    }
    dat = tmp_path / "UM261東.DAT"  # type: ignore[operator]
    dat.write_bytes(_build_um_dat(marks_input))

    result = read_marks(str(dat), record_no=1)

    assert result == {1: "◎", 3: "○", 5: "▲"}


def test_read_marks_returns_empty_when_no_marks(tmp_path: pytest.TempPathFactory) -> None:
    """印が1つもない場合は空辞書を返す。"""
    dat = tmp_path / "UM261東.DAT"  # type: ignore[operator]
    dat.write_bytes(_build_um_dat({}))

    result = read_marks(str(dat), record_no=1)

    assert result == {}


def test_read_marks_reads_correct_race_record(tmp_path: pytest.TempPathFactory) -> None:
    """指定した record_no のレコードのみを読む。"""
    dat = tmp_path / "UM261東.DAT"  # type: ignore[operator]
    record1 = _build_um_dat({2: bytes([0x81, 0x9D])})  # record_no=1: 2番◎
    record2 = _build_um_dat({7: bytes([0x81, 0x9B])})  # record_no=2: 7番○
    dat.write_bytes(record1 + record2)

    assert read_marks(str(dat), record_no=1) == {2: "◎"}
    assert read_marks(str(dat), record_no=2) == {7: "○"}
