# C:\TFJV\MY_DATA 調査結果

## ディレクトリ構成

```
C:\TFJV\MY_DATA\
├── UM{YY}{KK}{競}.DAT   # 印データ（複数ファイル）
├── KEK_COM\             # 競走別コメント（ディレクトリ）
│   ├── 2025\
│   │   └── KC{競馬場コード}{YY}{開催コード}.DAT
│   └── 2026\
│       └── KC{競馬場コード}{YY}{開催コード}.DAT
├── UMA_COM\             # 馬個別コメント（ディレクトリ）
│   └── {YYYY}\
│       └── UC{YYYY}{??}.DAT
├── YOS_COM\             # 予想コメント（KEK_COMと同フォーマット）
│   └── {YYYY}\
│       └── YC{競馬場コード}{YY}{開催コード}.DAT
├── KOL1_COM\            # （空、未使用）
├── KOL2_COM\            # （空、未使用）
├── RACE_COM\            # （空、未使用）
└── ComTemp.LST / ComTempS.LST  # （空）
```

---

## UM{YY}{KK}{競}.DAT — 印データ

### ファイル名

`UM{YY}{KK}{競}.DAT`

| フィールド | 説明 | 例 |
|---|---|---|
| `{YY}` | 西暦下2桁 | `26` (2026年) |
| `{KK}` | 開催回（その競馬場の年内何回目か） | `2` |
| `{競}` | 競馬場略称1文字 | `東`、`中`、`阪`、`京`、`名`、`小` |

例: `UM262東.DAT` = 2026年第2回東京

### エンコード

ShiftJIS テキスト (CRLF 区切り)

### レコード構造

- **1レコード = 264バイト** = 6行 × (42バイト + CRLF(2バイト))
- **レコード番号（1始まり）= レース番号（R1〜）**
- ファイル内のレコード数 = そのファイルのレース数（16〜20）

| 行番号 | 内容 |
|---|---|
| 行1〜4 | 現時点では未使用（全スペース） |
| **行5** | **印データ** |
| 行6 | 現時点では未使用（全スペース） |

### 印データ（行5）のフォーマット

行5の42バイトを**2バイト単位**で区切った21スロット。

- **スロット N（0始まり）= 馬番 N+1 の印**
- スロット N のバイトオフセット = N × 2

| ShiftJIS バイト列 | 印記号 | 意味 |
|---|---|---|
| `81 9D` | ◎ | 本命 |
| `81 9B` | ○ | 対抗 |
| `81 A3` | ▲ | 単穴 |
| `81 A2` | △ | 連下 |
| `92 8D` | 注 | 抑え |
| `81 99` | ☆ | 穴 |
| `20 20` | (空白) | 印なし |

### 読み込みサンプルコード

```python
RECORD_SIZE = 264
LINE_WIDTH = 44  # 42バイト + CRLF(2バイト)
MARK_LINE_INDEX = 4  # 0始まりで行5は index 4

MARK_BYTES = {
    bytes([0x81, 0x9D]): "◎",
    bytes([0x81, 0x9B]): "○",
    bytes([0x81, 0xA3]): "▲",
    bytes([0x81, 0xA2]): "△",
    bytes([0x92, 0x8D]): "注",
    bytes([0x81, 0x99]): "☆",
}

def read_marks(dat_path: str, race_no: int) -> dict[int, str]:
    """race_no (1始まり) のレースの印を {馬番: 印記号} で返す。"""
    with open(dat_path, "rb") as f:
        data = f.read()
    rec = data[(race_no - 1) * RECORD_SIZE : race_no * RECORD_SIZE]
    mark_line = rec[MARK_LINE_INDEX * LINE_WIDTH : MARK_LINE_INDEX * LINE_WIDTH + 42]
    marks = {}
    for i in range(21):
        two_bytes = mark_line[i * 2 : i * 2 + 2]
        mark = MARK_BYTES.get(bytes(two_bytes))
        if mark:
            marks[i + 1] = mark  # 馬番は1始まり
    return marks
```

---

## KEK_COM — 競走別コメント

### ディレクトリ構造

```
C:\TFJV\MY_DATA\KEK_COM\
└── {YYYY}\
    └── KC{競馬場コード}{YY}{開催コード}.DAT
```

### ファイル名

`KC{競馬場コード}{YY}{開催コード}.DAT`

| フィールド | 説明 | 値 |
|---|---|---|
| `{競馬場コード}` | JRA競馬場コード2桁（netkeibaと同一） | `05`=東京, `06`=中山, `07`=中京, `08`=京都, `09`=阪神, `10`=小倉 |
| `{YY}` | 西暦下2桁 | `26` |
| `{開催コード}` | 16進2桁（上位ニブル=開催回、下位ニブル=開催日） | `26` = 2回6日 |

例: `KC052626.DAT` = 東京(05)、2026年(26)、第2回6日(26) → NHKマイルカップ

**開催コードに `A`〜`F` の16進文字が使われる場合あり。**
例: `KC05262A.DAT` = 開催コード `2A` = 2回10日

### エントリフォーマット

各行が1頭分のコメントで、ShiftJIS・CRLF区切り。

```
{競馬場コード}{YY}{開催コード}{RR}{HH},{コメント}
```

| フィールド | 説明 | 型 |
|---|---|---|
| `{競馬場コード}{YY}{開催コード}` | ファイル名の後ろ6桁と同一 | 6文字 |
| `{RR}` | レース番号 | 10進2桁 (`11` = 11R) |
| `{HH}` | 馬番 | 10進2桁 (`17` = 17番) |
| `{コメント}` | コメント本文 | ShiftJIS文字列 |

**コメントの形式:**
- テキストあり: `"[レース名] テキスト..."`
- レース名のみ: `[レース名]`

### netkeibaのrace_idとの対応

netkeibaのrace_idフォーマット: `{YYYY}{競馬場コード2桁}{開催回2桁}{開催日2桁}{R番号2桁}` (12桁)

TFJV開催コード（16進2桁）との変換（検証済み: race_id `202605021011` → `KC05262A.DAT`）:
- 上位ニブル → 開催回（10進）
- 下位ニブル → 開催日（10進）

```python
def race_id_to_tfjv_code(race_id: str) -> tuple[str, str, str]:
    """netkeibaのrace_id(12桁) → (競馬場コード, YY, 開催コード(16進2桁))

    race_id フォーマット: {YYYY(4)}{競馬場(2)}{開催回(2)}{開催日(2)}{R番号(2)} = 12桁
    例: "202605021011" → venue="05", year2="26", tfjv_code="2A"
    """
    venue     = race_id[4:6]           # "05" (東京)
    year2     = race_id[2:4]           # "26" (2026年)
    kai       = int(race_id[6:8])      # 開催回 (2桁10進) = 2
    nichi     = int(race_id[8:10])     # 開催日 (2桁10進) = 10
    tfjv_code = f"{kai:X}{nichi:X}"    # 例: 2回10日 → "2A"
    return venue, year2, tfjv_code
```

### 読み込みサンプルコード

```python
import os
import glob

KEK_COM_DIR = r"C:\TFJV\MY_DATA\KEK_COM"

def find_kek_com_file(venue_code: str, year2: str, tfjv_code: str) -> str | None:
    """KC*.DATファイルのパスを返す。"""
    pattern = os.path.join(
        KEK_COM_DIR, f"20{year2}", f"KC{venue_code}{year2}{tfjv_code}.DAT"
    )
    matches = glob.glob(pattern)
    return matches[0] if matches else None

def read_kek_comments(
    venue_code: str, year2: str, tfjv_code: str, race_no: int
) -> dict[int, str]:
    """指定レースの全馬コメントを {馬番: コメント} で返す。"""
    fpath = find_kek_com_file(venue_code, year2, tfjv_code)
    if fpath is None:
        return {}
    with open(fpath, "rb") as f:
        data = f.read()
    text = data.decode("shift_jis", errors="replace")
    rr = f"{race_no:02d}"
    prefix = f"{venue_code}{year2}{tfjv_code}{rr}"
    result = {}
    for line in text.splitlines():
        if not line.startswith(prefix):
            continue
        comma = line.index(",")
        hh = int(line[8:10])
        comment = line[comma + 1:].strip('"')
        result[hh] = comment
    return result
```

---

## 未解決事項

| # | 課題 | 現状 |
|---|---|---|
| 1 | TFJV開催コードとnetkeibaのrace_idの変換精度 | **検証済み。** race_id `202605021011`（2回東京10日11R）→ 開催コード `2A`（上位`2`=開催回、下位`A`=10進10=開催日10）→ `KC05262A.DAT` にオークスのエントリが存在することを確認。 |
| 2 | UM*.DATの行1〜4・行6の用途 | 現時点では全スペース。将来的に使われる可能性あり |
| 3 | UMA_COMのキー体系 | ファイル名・エントリキーともに体系が不明。使用頻度が低いため低優先度 |
