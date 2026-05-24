"""TFJVファイル操作の共通モジュール。"""
import glob
import os

VENUE_ABBR: dict[str, str] = {
    "05": "東",
    "06": "中",
    "07": "名",
    "08": "京",
    "09": "阪",
    "10": "小",
}

MARK_BYTES: dict[bytes, str] = {
    bytes([0x81, 0x9D]): "◎",
    bytes([0x81, 0x9B]): "○",
    bytes([0x81, 0xA3]): "▲",
    bytes([0x81, 0xA2]): "△",
    bytes([0x92, 0x8D]): "注",
    bytes([0x81, 0x99]): "☆",
}

RECORD_SIZE = 264
LINE_WIDTH = 44
MARK_LINE = 4


def race_code_to_tfjv(race_code: str) -> tuple[str, str, str]:
    """16桁 race_code を (競馬場コード, YY, 開催コード16進) に変換する。"""
    venue = race_code[8:10]
    year2 = race_code[2:4]
    kai = int(race_code[10:12])
    nichi = int(race_code[12:14])
    tfjv_code = f"{kai:X}{nichi:X}"
    return venue, year2, tfjv_code


def um_dat_path(race_code: str, base_dir: str) -> str:
    """UM*.DAT のフルパスを返す。"""
    year2 = race_code[2:4]
    kai = int(race_code[10:12])
    venue = race_code[8:10]
    abbr = VENUE_ABBR[venue]
    filename = f"UM{year2}{kai}{abbr}.DAT"
    return os.path.join(base_dir, filename)


def read_marks(dat_path: str, race_no: int) -> dict[int, str]:
    """race_no（1始まり）の印を {馬番: 印記号} で返す。"""
    with open(dat_path, "rb") as f:
        data = f.read()
    rec = data[(race_no - 1) * RECORD_SIZE : race_no * RECORD_SIZE]
    mark_line = rec[MARK_LINE * LINE_WIDTH : MARK_LINE * LINE_WIDTH + 42]
    marks = {}
    for i in range(21):
        two_bytes = mark_line[i * 2 : i * 2 + 2]
        mark = MARK_BYTES.get(bytes(two_bytes))
        if mark:
            marks[i + 1] = mark
    return marks


def find_kek_com_file(base_dir: str, venue: str, year2: str, tfjv_code: str) -> str | None:
    """KC*.DAT のパスを返す。存在しない場合は None。"""
    pattern = os.path.join(base_dir, "KEK_COM", f"20{year2}", f"KC{venue}{year2}{tfjv_code}.DAT")
    matches = glob.glob(pattern)
    return matches[0] if matches else None


def read_kek_comments(
    base_dir: str, venue: str, year2: str, tfjv_code: str, race_no: int
) -> dict[int, str]:
    """指定レースの全馬コメントを {馬番: コメント} で返す。"""
    fpath = find_kek_com_file(base_dir, venue, year2, tfjv_code)
    if fpath is None:
        return {}
    with open(fpath, "rb") as f:
        data = f.read()
    text = data.decode("shift_jis", errors="replace")
    rr = f"{race_no:02d}"
    prefix = f"{venue}{year2}{tfjv_code}{rr}"
    result = {}
    for line in text.splitlines():
        if not line.startswith(prefix):
            continue
        comma = line.index(",")
        hh = int(line[len(prefix) : len(prefix) + 2])
        comment = line[comma + 1 :].strip('"')
        result[hh] = comment
    return result


def write_kek_comment(
    base_dir: str,
    venue: str,
    year2: str,
    tfjv_code: str,
    race_no: int,
    umaban: int,
    comment: str,
) -> None:
    """KEK_COM に1行追記する。

    Raises:
        FileNotFoundError: 対象の KEK_COM ファイルが存在しない場合。
    """
    fpath = find_kek_com_file(base_dir, venue, year2, tfjv_code)
    if fpath is None:
        raise FileNotFoundError(f"KEK_COM file not found: {venue}{year2}{tfjv_code}")
    rr = f"{race_no:02d}"
    hh = f"{umaban:02d}"
    key = f"{venue}{year2}{tfjv_code}{rr}{hh}"
    entry = f'{key},"{comment}"\r\n'
    with open(fpath, "ab") as f:
        f.write(entry.encode("shift_jis"))
