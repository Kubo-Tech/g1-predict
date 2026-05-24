# 実装アイデア

## 全体構成イメージ

```
g1-predict/
├── scripts/
│   ├── gen_predict.py          # 予想記事ベース生成
│   └── gen_result_comment.py   # KEK_COM 定型文生成
├── templates/
│   └── points/
│       ├── 高松宮記念.md        # G1ごとのポイントテンプレート
│       ├── 大阪杯.md
│       └── ...
├── public/
│   └── {year}/
│       ├── .qiita_ids.json     # Qiita記事IDのキャッシュ
│       └── {nn}_{race_name}.md
└── .github/
    └── workflows/
        └── qiita_publish.yml
```

## ライブラリ使い分け

全処理に `keiba-data-interface` の `DataInterface("mykeibadb")` を使用する。  
スクレイピングより高速・安定なため。

### race_code の体系

keiba-data-interface の race_code は **16桁（JRA-VAN形式）**。  
`{YYYY(4)}{月日(4)}{競馬場(2)}{回(2)}{日目(2)}{R(2)}`  
例: `2026050205021011` = 2026年5月2日、東京(05)、2回2日、10R

TFJV変換は16桁から直接行う。MY_DATA.md の `race_id_to_tfjv_code` は12桁前提で書かれているが、実装時は16桁対応版に書き直す。

```python
# 16桁: {YYYY(4)}{月日(4)}{競馬場(2)}{回(2)}{日目(2)}{R(2)}
venue  = race_code[8:10]
year2  = race_code[2:4]
kai    = int(race_code[10:12])
nichi  = int(race_code[12:14])
tfjv_code = f"{kai:X}{nichi:X}"
```

---

## 1. 予想記事ベース生成

### 概要

`python scripts/gen_predict.py --race-code {16桁race_code}` を実行すると
`public/{year}/{nn}_{race_name}.md` が自動生成される。

### 処理フロー

```
race_code (16桁)
  → DataInterface("mykeibadb").get_entry(race_code)       # 出馬表（馬番・馬名・馬ID）
  → UM{YY}{KK}{競}.DAT 読み込み                           # 印（◎◯▲△など）
  → templates/points/{race_name}.md                       # ポイントセクション
  → 印のついた馬ごとに:
      DataInterface("mykeibadb").get_past_performances(horse_id)  # 過去全成績
      → race_code(16桁) → TFJV変換
      → KEK_COM から過去全レース分のコメントを取得
  → TEMPLATE.md 組み合わせ
  → public/{year}/{nn}_{race_name}.md 出力
```

### 印セクション生成

- `UM{YY}{KK}{競}.DAT` の読み込みは MY_DATA.md のサンプルコードを使用
- 印のついた馬を記号順（◎◯▲△注☆）に並べて `## 印` セクションを生成
- 同じ印がいた場合馬番順で並べる

### 見解セクション生成

- 印のついた馬について `### ◎{馬番}{馬名}` 見出しを生成
- `get_past_performances(horse_id)` で全過去レースを取得
- 各過去レースの race_code → TFJV変換 → KEK_COM を参照
- コメントがあるレースを新しい順に全件貼り付け（コメントなしのレースはスキップ）

### ポイントセクション

- G1ごとに固定内容なので `templates/points/{race_name}.md` として管理
- `DataInterface("mykeibadb").get_race_basic_info(race_code)` でレース名（または特別競走番号）を取得して対応ファイルを選択
- テンプレートが存在しない場合は空の `## ポイント` セクションを生成

### ファイル名の連番

- `public/{year}/` に存在するファイルの最大番号+1 を `{nn}` に使用

---

## 2. Qiita自動投稿

### 概要

`public/` 配下のmarkdownがpushされたら GitHub Actions で Qiita API v2 へ upsert する。

### CI設定 (`.github/workflows/qiita_publish.yml`)

```yaml
on:
  push:
    paths:
      - 'public/**/*.md'
```

### 新規投稿 vs 更新の判定

- `public/{year}/.qiita_ids.json` にファイルパス→Qiita記事IDのマッピングを保存
- 初回: POST `/api/v2/items` → 取得したIDを `.qiita_ids.json` に書き込みコミット
- 2回目以降: PATCH `/api/v2/items/{item_id}`

### Qiita記事のメタデータ

ファイル先頭にフロントマターを追加するか、スクリプト側で付与する。

```markdown
---
title: "オークス2026"
tags: ["競馬", "G1", "予想"]
private: false
---
```

### 認証

- Qiita APIトークンを GitHub Secrets (`QIITA_ACCESS_TOKEN`) に保存
- CI環境変数から読み込む

---

## 3. 結果コメント定型文生成

### 概要

レース終了後に `python scripts/gen_result_comment.py --race-code {16桁race_code}` を実行すると
`KEK_COM` の各馬エントリに定型文が追記される。

### 定型文フォーマット

`{レース名} {着差}{着順}着。`

着差ルール
- タイム差が0.0秒の場合: `クビ差`,`ハナ差`,`アタマ差` などの着差を使用（着差コードより取得）
- タイム差が0.0秒以外の場合: `0.2秒差` のように秒数を記入
- 1着の場合は「2着との差」を記入（例: `0.2秒差1着`, `ハナ差1着`）

### 処理フロー

```
race_code (16桁)
  → DataInterface("mykeibadb").get_race_basic_info(race_code)  # レース名
  → DataInterface("mykeibadb").get_result(race_code)           # 着順・タイム差・馬ID
  → 馬IDごとに定型文生成
  → race_code → TFJV変換 → KEK_COM の対応エントリを ShiftJIS で書き込み
```

---

## 技術的課題・調査事項

| # | 課題 | 対応方針 |
|---|------|----------|
| 1 | コンテナからのローカルファイルアクセス | `C:\TFJV\MY_DATA\` をコンテナ起動時にボリュームマウントする（`-v C:\TFJV\MY_DATA:/tfjv_data`）。スクリプト内のパスは環境変数 `TFJV_DATA_DIR` で設定可能にしておく |
| 2 | `.qiita_ids.json` のgit管理 | CI側でコミット・プッシュ（`actions/github-script` 等） |
| 3 | race_code の決定タイミング | 出馬表公開後（レース前日〜当日朝）に手動指定 or `get_schedule()` から自動取得 |

---

## 実装優先度

1. **`gen_result_comment.py`** — keiba-data-interface + KEK_COM書き込み
2. **`gen_predict.py` の骨格** — TFJVファイル読み込みを後回しにして、keiba-data-interface + TEMPLATE.md だけで動くミニマム版を先に作る
3. **TFJVファイル読み込み** — MY_DATA.md のサンプルコードをベースに印・コメント読み込みを実装
4. **Qiita自動投稿CI** — `.qiita_ids.json` 管理含め
