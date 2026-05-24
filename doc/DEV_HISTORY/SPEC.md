# g1-predict 仕様書

## 概要

G1レースの予想記事を自動生成し、Qiitaへ投稿するシステム。  
主要な処理は以下の2本のスクリプトで構成される。

- `gen_predict.py` — 予想記事のベース（印・見解の素材）を自動生成
- `gen_result_comment.py` — レース結果を各馬のコメントファイルに定型文で追記

---

## ディレクトリ構成

```
g1-predict/
├── scripts/
│   ├── gen_predict.py          # 予想記事ベース生成
│   └── gen_result_comment.py   # KEK_COM 定型文生成
├── templates/
│   ├── TEMPLATE.md             # 記事テンプレート
│   └── points/
│       ├── 高松宮記念.md        # G1ごとのポイントテンプレート
│       ├── 大阪杯.md
│       └── ...
├── public/
│   └── {year}/
│       ├── .qiita_ids.json     # Qiita記事IDのキャッシュ
│       └── {nn}_{race_name}.md # 生成された予想記事
└── .github/
    └── workflows/
        └── qiita_publish.yml
```

---

## データソース

### keiba-data-interface

全処理において `keiba-data-interface` の `DataInterface("mykeibadb")` を使用する。

主要メソッド:

| メソッド | 引数 | 戻り値の主要フィールド |
|---|---|---|
| `get_race_basic_info(race_code)` | 16桁 race_code | レース名、特別競走番号 |
| `get_entry(race_code)` | 16桁 race_code | 馬番、馬名、馬ID |
| `get_past_performances(horse_id)` | 馬ID | 過去レース一覧（race_code含む） |
| `get_result(race_code)` | 16桁 race_code | 着順、タイム差、着差コード、馬ID |

### TFJVファイル

ローカルの `C:\TFJV\MY_DATA\` をコンテナ起動時にボリュームマウントする。

```
docker run ... -v C:\TFJV\MY_DATA:/tfjv_data ...
```

スクリプト内のベースパスは環境変数 `TFJV_DATA_DIR` で設定する（デフォルト: `/tfjv_data`）。

#### race_code 体系

keiba-data-interface が扱う race_code は **16桁（JRA-VAN形式）**。

```
{YYYY(4)}{月日(4)}{競馬場(2)}{回(2)}{日目(2)}{R(2)}
例: 2026050205021011
    ↑年   ↑月日 ↑会場↑回 ↑日目↑R番号
    2026  0502  05   02   10   11
```

各フィールドの取り出し:

```python
year4  = race_code[0:4]   # 年（4桁）
year2  = race_code[2:4]   # 年（下2桁）
venue  = race_code[8:10]  # 競馬場コード（2桁）
kai    = int(race_code[10:12])  # 開催回
nichi  = int(race_code[12:14])  # 開催日
race_no = int(race_code[14:16]) # レース番号
```

#### TFJV 開催コード変換

TFJVファイルの開催コードは **16進2桁**（上位ニブル=開催回、下位ニブル=開催日）。

```python
def race_code_to_tfjv(race_code: str) -> tuple[str, str, str]:
    """16桁 race_code → (競馬場コード, YY, 開催コード16進2桁)"""
    venue  = race_code[8:10]
    year2  = race_code[2:4]
    kai    = int(race_code[10:12])
    nichi  = int(race_code[12:14])
    tfjv_code = f"{kai:X}{nichi:X}"
    return venue, year2, tfjv_code
```

例: `2026050205021011` → venue=`05`, year2=`26`, tfjv_code=`2A`（2回10日）

#### UM{YY}{KK}{競}.DAT — 印データ

**ファイル名の構築:**

```python
VENUE_ABBR = {
    "05": "東",
    "06": "中",
    "07": "名",
    "08": "京",
    "09": "阪",
    "10": "小",
}

def um_dat_path(race_code: str, base_dir: str) -> str:
    year2   = race_code[2:4]
    kai     = int(race_code[10:12])
    venue   = race_code[8:10]
    abbr    = VENUE_ABBR[venue]
    filename = f"UM{year2}{kai}{abbr}.DAT"
    return os.path.join(base_dir, filename)
```

**ファイル形式:**

- エンコード: ShiftJIS、CRLF 区切り
- 1レコード = 264バイト（6行 × 44バイト）
- レコード番号（1始まり）= レース番号

| 行番号 | 内容 |
|---|---|
| 行1〜4 | 未使用（全スペース） |
| **行5** | **印データ** |
| 行6 | 未使用（全スペース） |

行5は 42バイトを **2バイト単位** で区切った 21スロット。スロット N（0始まり）= 馬番 N+1 の印。

| ShiftJIS バイト列 | 記号 |
|---|---|
| `81 9D` | ◎ |
| `81 9B` | ○ |
| `81 A3` | ▲ |
| `81 A2` | △ |
| `92 8D` | 注 |
| `81 99` | ☆ |
| `20 20` | （印なし） |

**読み込みコード:**

```python
RECORD_SIZE = 264
LINE_WIDTH  = 44   # 42バイト + CRLF(2バイト)
MARK_LINE   = 4    # 0始まりで行5 は index 4

MARK_BYTES = {
    bytes([0x81, 0x9D]): "◎",
    bytes([0x81, 0x9B]): "○",
    bytes([0x81, 0xA3]): "▲",
    bytes([0x81, 0xA2]): "△",
    bytes([0x92, 0x8D]): "注",
    bytes([0x81, 0x99]): "☆",
}

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
```

#### KEK_COM — 競走別コメント

**ディレクトリ構造:**

```
{TFJV_DATA_DIR}/KEK_COM/
└── {YYYY}/
    └── KC{競馬場コード}{YY}{開催コード}.DAT
```

例: `KC05262A.DAT` = 東京(05)、2026年(26)、2回10日(2A)

開催コードに `A`〜`F` の16進文字が使われる場合あり。

**エントリフォーマット（ShiftJIS・CRLF区切り）:**

```
{競馬場コード}{YY}{開催コード}{RR}{HH},{コメント}
```

| フィールド | 説明 |
|---|---|
| `{競馬場コード}{YY}{開催コード}` | ファイル名後ろ6桁と同一 |
| `{RR}` | レース番号（10進2桁）|
| `{HH}` | 馬番（10進2桁）|
| `{コメント}` | コメント本文（ShiftJIS文字列）|

コメントの形式:
- テキストあり: `"[レース名] テキスト..."`
- レース名のみ: `[レース名]`

**読み込みコード:**

```python
import os, glob

def find_kek_com_file(base_dir: str, venue: str, year2: str, tfjv_code: str) -> str | None:
    pattern = os.path.join(base_dir, "KEK_COM", f"20{year2}", f"KC{venue}{year2}{tfjv_code}.DAT")
    matches = glob.glob(pattern)
    return matches[0] if matches else None

def read_kek_comments(base_dir: str, venue: str, year2: str, tfjv_code: str, race_no: int) -> dict[int, str]:
    """指定レースの全馬コメントを {馬番: コメント} で返す。"""
    fpath = find_kek_com_file(base_dir, venue, year2, tfjv_code)
    if fpath is None:
        return {}
    with open(fpath, "rb") as f:
        data = f.read()
    text = data.decode("shift_jis", errors="replace")
    rr     = f"{race_no:02d}"
    prefix = f"{venue}{year2}{tfjv_code}{rr}"
    result = {}
    for line in text.splitlines():
        if not line.startswith(prefix):
            continue
        comma   = line.index(",")
        hh      = int(line[8:10])
        comment = line[comma + 1:].strip('"')
        result[hh] = comment
    return result
```

**KEK_COM への書き込み（gen_result_comment.py で使用）:**

既存ファイルに行を追記する。追記時はファイルを ShiftJIS でオープンし、エントリ形式に整形してから書き込む。

```python
def write_kek_comment(base_dir: str, venue: str, year2: str, tfjv_code: str,
                      race_no: int, umaban: int, comment: str) -> None:
    fpath = find_kek_com_file(base_dir, venue, year2, tfjv_code)
    if fpath is None:
        raise FileNotFoundError(f"KEK_COM file not found: {venue}{year2}{tfjv_code}")
    rr    = f"{race_no:02d}"
    hh    = f"{umaban:02d}"
    key   = f"{venue}{year2}{tfjv_code}{rr}{hh}"
    entry = f'{key},"{comment}"\r\n'
    with open(fpath, "ab") as f:
        f.write(entry.encode("shift_jis"))
```

---

## スクリプト仕様

### gen_predict.py — 予想記事ベース生成

**実行方法:**

```sh
python scripts/gen_predict.py --race-code {16桁race_code}
```

**出力:** `public/{year}/{nn}_{race_name}.md`

**処理フロー:**

```
race_code (16桁)
  ├─ DataInterface("mykeibadb").get_race_basic_info(race_code)
  │    → レース名・年を取得（タイトル・出力ファイル名・ポイントテンプレート選択に使用）
  ├─ DataInterface("mykeibadb").get_entry(race_code)
  │    → 出馬表（馬番・馬名・馬ID）
  ├─ read_marks(um_dat_path(race_code, TFJV_DATA_DIR), race_no)
  │    → 印データ（馬番→印記号）
  ├─ ポイントセクション: templates/points/{race_name}.md を読み込み（なければ空セクション）
  ├─ 印のついた馬ごとに（記号順: ◎○▲△注☆、同記号内は馬番順）:
  │    DataInterface("mykeibadb").get_past_performances(horse_id)
  │      → 過去全レース（race_code付き）
  │    race_code_to_tfjv(past_race_code)
  │      → KEK_COM の該当エントリを取得
  │    コメントがある過去レースを新しい順に全件列挙（なしはスキップ）
  └─ TEMPLATE.md に従って組み立て → public/{year}/{nn}_{race_name}.md に出力
```

**{nn}（連番）の決定:**

`public/{year}/` に存在するファイルの最大番号 + 1。ファイルが存在しない場合は `01`。

```python
import glob, os, re

def next_serial(year: str, public_dir: str) -> str:
    files = glob.glob(os.path.join(public_dir, year, "*.md"))
    nums  = [int(m.group(1)) for f in files if (m := re.match(r"(\d+)_", os.path.basename(f)))]
    return f"{max(nums) + 1:02d}" if nums else "01"
```

**印セクション（`## 印`）の出力形式:**

```markdown
## 印

◎{馬番}{馬名}  
○{馬番}{馬名}  
▲{馬番}{馬名}  
...
```

**見解セクション（`## 見解`）の出力形式:**

```markdown
## 見解

### ◎{馬番}{馬名}

前走{グレード}{レース名}{コメント本文}
前々走{グレード}{レース名}{コメント本文}
3走前{グレード}{レース名}{コメント本文}
...
```

- コメントは新しいレース順（1走前から順に並べる）
- 走数の表記: 1走前=「前走」、2走前=「前々走」、3走以上=「n走前」
- グレードは `get_past_performances()` が返す情報から取得（例: `G1`, `G2`, `L`）
- コメント本文は KEK_COM エントリの先頭にある `[レース名]` ラベルを除いたテキスト

---

### gen_result_comment.py — 結果コメント定型文生成

**実行方法:**

```sh
python scripts/gen_result_comment.py --race-code {16桁race_code}
```

**処理フロー:**

```
race_code (16桁)
  ├─ DataInterface("mykeibadb").get_race_basic_info(race_code) → レース名
  ├─ DataInterface("mykeibadb").get_result(race_code)
  │    → 全馬の着順・タイム差（秒）・着差コード・馬ID・馬番
  ├─ race_code_to_tfjv(race_code) → venue, year2, tfjv_code
  └─ 馬ごとに定型文を生成して KEK_COM に追記
```

**定型文フォーマット:**

```
[{レース名}] {着差}{着順}着。
```

着差の決定ルール:

| 条件 | 表記 |
|---|---|
| 1着 | 2着との差（下記ルールで判定）|
| タイム差が 0.0 秒 | 着差コードから取得（例: `クビ差`, `ハナ差`, `アタマ差`）|
| タイム差が 0.0 秒以外 | `{秒数}秒差`（例: `0.2秒差`）|

例:
- `[NHKマイルC] ハナ差1着。`
- `[オークス] 0.2秒差3着。`

---

## 記事テンプレート

`templates/TEMPLATE.md` を基に記事を構成する。

```markdown
# {RaceName}{Year}

## ポイント

- （templates/points/{race_name}.md の内容、なければ空）

## 印

◎{Umaban}{HorseName}  
○{Umaban}{HorseName}  
▲{Umaban}{HorseName}  
...

## 見解

### ◎{Umaban}{HorseName}

（KEK_COM の過去コメントを新しい順に列挙）

### ○{Umaban}{HorseName}

...

## 買い目
```

`templates/points/` には G1 ごとに固定内容を保存する。ファイル名はレース名と一致させる（例: `オークス.md`）。

---

## Qiita自動投稿

### GitHub Actions 設定

`.github/workflows/qiita_publish.yml`:

```yaml
on:
  push:
    paths:
      - 'public/**/*.md'
```

### 新規投稿 vs 更新

`public/{year}/.qiita_ids.json` にファイルパス → Qiita記事IDのマッピングを保存する。

- キーに存在しない場合: `POST /api/v2/items` → 取得したIDを `.qiita_ids.json` に追記しコミット
- キーが存在する場合: `PATCH /api/v2/items/{item_id}`

### 記事メタデータ

ファイル先頭にフロントマターを付与する（スクリプト側で付与するか、ファイルに直接記述する）。

```markdown
---
title: "オークス2026"
tags: ["競馬", "G1", "予想"]
private: false
---
```

### 認証

Qiita APIトークンを GitHub Secrets `QIITA_ACCESS_TOKEN` に保存し、CI 環境変数から読み込む。

---

## 実装優先度

1. **`gen_result_comment.py`** — DataInterface + KEK_COM 書き込み
2. **`gen_predict.py` ミニマム版** — TFJVファイル読み込みを後回しにして DataInterface + TEMPLATE.md だけで動く版を先に作る
3. **TFJVファイル読み込み** — 印（UM*.DAT）・コメント（KEK_COM）の読み込みを実装
4. **Qiita自動投稿CI** — `.qiita_ids.json` 管理含め
