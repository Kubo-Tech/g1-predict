# g1-predict 実装計画書

SPECに基づいた実装をPR単位で分割する。  
各PRは独立してマージ可能であり、後続PRは前PRのマージを前提とする。

---

## 全PR共通ルール

Python を実装するすべての PR において、以下を必ず行うこと。

### コーディング規約

- **`python-coding-rule` スキルに従う** — コードスタイル・型付け・モジュール構成などの規約を遵守する
- **`pytest-coding-rule` スキルに従う** — テストコードを書く場合はこの規約に従う

### 静的解析（実装後に必ず実行）

以下を `__init__.py` を含む全対象ファイルに対して実行し、エラーがないことを確認する。  
実行方法は各スキル（`run-isort-check`・`run-flake8`・`run-mypy`）を参照すること。

1. `run-isort-check` — import の並び順チェック
2. `run-flake8` — スタイル・文法チェック
3. `run-mypy` — 型チェック

### セルフレビュー（PR作成前に必ず実行）

`code-review` スキルを使ってセルフレビューを行い、指摘事項があれば修正してからPRを作成する。

---

## PR1: プロジェクト骨格と共通ユーティリティ

### 目的

スクリプト群が依存する共通処理をモジュールとしてまとめ、後続PRの実装基盤を作る。

### 実装ファイル

- `scripts/tfjv.py` — TFJVファイル操作の共通モジュール
- `requirements.txt` — 依存パッケージ（keiba-data-interface）
- `templates/points/` — ディレクトリのみ作成（`.gitkeep` 配置）

### 作業内容

`scripts/tfjv.py` に以下を実装する。

**定数・マッピング:**
- `VENUE_ABBR: dict[str, str]` — 競馬場コード → 略称（`"05": "東"` など）
- `MARK_BYTES: dict[bytes, str]` — ShiftJIS 2バイト列 → 印記号

**関数:**
- `race_code_to_tfjv(race_code: str) -> tuple[str, str, str]` — 16桁 race_code → (venue, year2, tfjv_code)
- `um_dat_path(race_code: str, base_dir: str) -> str` — UM*.DAT のフルパスを返す
- `read_marks(dat_path: str, race_no: int) -> dict[int, str]` — 印を `{馬番: 記号}` で返す
- `find_kek_com_file(base_dir: str, venue: str, year2: str, tfjv_code: str) -> str | None` — KC*.DAT のパスを返す
- `read_kek_comments(base_dir: str, venue: str, year2: str, tfjv_code: str, race_no: int) -> dict[int, str]` — 指定レースの全馬コメントを `{馬番: コメント}` で返す
- `write_kek_comment(base_dir: str, venue: str, year2: str, tfjv_code: str, race_no: int, umaban: int, comment: str) -> None` — KEK_COM に1行追記する

各関数の仕様詳細は SPEC.md「データソース」セクションを参照。

### 完了条件

- `python -c "from scripts.tfjv import race_code_to_tfjv; print(race_code_to_tfjv('2026050205021011'))"` が `('05', '26', '2A')` を返す
- mypy・flake8 エラーなし

---

## PR2: gen_result_comment.py

### 目的

レース終了後に結果定型文を KEK_COM へ書き込む。最も単純な処理フローであり、DataInterface と `tfjv.write_kek_comment` の動作確認を兼ねる。

### 実装ファイル

- `scripts/gen_result_comment.py`

### 作業内容

```
python scripts/gen_result_comment.py --race-code {16桁race_code}
```

**処理フロー（SPEC.md「gen_result_comment.py」セクション参照）:**

1. `--race-code` 引数をパースする
2. `DataInterface("mykeibadb").get_race_basic_info(race_code)` でレース名を取得
3. `DataInterface("mykeibadb").get_result(race_code)` で全馬の着順・タイム差・着差コード・馬番を取得
4. `race_code_to_tfjv(race_code)` で venue / year2 / tfjv_code を取得
5. 各馬について定型文を生成して `write_kek_comment()` で追記する

**定型文フォーマット:**

```
[{レース名}] {着差}{着順}着。
```

着差の決定ルール（SPEC.md「定型文フォーマット」参照）:
- 1着: 2着との差を下記ルールで算出
- タイム差 0.0 秒: 着差コードをそのまま使用（例: `クビ差`）
- タイム差 0.0 秒以外: `{秒数}秒差`（例: `0.2秒差`）

環境変数 `TFJV_DATA_DIR` を `write_kek_comment` のベースパスとして使用する。

### 完了条件

- 任意の過去レースの race_code を指定して実行し、KEK_COM の該当ファイルに正しいフォーマットの行が追記される
- 既存エントリを上書き・破壊しない
- mypy・flake8 エラーなし

---

## PR3: gen_predict.py ミニマム版（印・過去コメントなし）

### 目的

DataInterface から出馬表を取得し、TEMPLATE.md をベースに記事ファイルを生成する最小版。  
TFJVファイル（印・KEK_COM）への依存を持たず、単体で動作確認できる状態にする。

### 実装ファイル

- `scripts/gen_predict.py`

### 作業内容

```
python scripts/gen_predict.py --race-code {16桁race_code}
```

**処理フロー:**

1. `--race-code` 引数をパースする
2. `DataInterface("mykeibadb").get_race_basic_info(race_code)` でレース名・年を取得
3. `DataInterface("mykeibadb").get_entry(race_code)` で出馬表（馬番・馬名）を取得
4. `templates/points/{race_name}.md` を読み込む（なければ `## ポイント\n\n- \n` を使用）
5. `templates/TEMPLATE.md` を読み込み、プレースホルダーを置換する
6. 連番 `{nn}` を決定して `public/{year}/{nn}_{race_name}.md` に出力する

**この段階での出力内容:**

- `## ポイント` — テンプレートファイルの内容（またはプレースホルダー）
- `## 印` — 全馬を馬番順に並べたリスト（印記号なし、後のPRで置き換える）
- `## 見解` — 印のついた馬のセクション見出しのみ（コメントなし、後のPRで置き換える）
- `## 買い目` — 空のまま

**連番の決定ロジック（SPEC.md「{nn}の決定」参照）:**

`public/{year}/` の既存 `*.md` ファイルの最大番号 + 1（ゼロパディング2桁）。

### 完了条件

- 任意の race_code を指定して実行し、`public/{year}/{nn}_{race_name}.md` が生成される
- 連番が正しくインクリメントされる
- mypy・flake8 エラーなし

---

## PR4: gen_predict.py に印・過去コメントを統合

### 目的

PR3のミニマム版に TFJVファイル読み込みを追加し、印と過去コメントを記事に反映させる。

### 実装ファイル

- `scripts/gen_predict.py`（PR3からの差分）

### 作業内容

**印の取得と印セクション生成:**

1. `um_dat_path(race_code, TFJV_DATA_DIR)` で UM*.DAT のパスを特定
2. `read_marks(dat_path, race_no)` で `{馬番: 印記号}` を取得
3. `## 印` セクションを印記号順（◎○▲△注☆）・同記号内は馬番順で出力

**過去コメントの取得と見解セクション生成:**

印のついた馬について以下を実行する。

1. `DataInterface("mykeibadb").get_past_performances(horse_id)` で過去全レースを取得
2. 各過去レースの race_code に対して `race_code_to_tfjv()` → `read_kek_comments()` を呼ぶ
3. コメントがあるレースのみ、新しい順に以下のフォーマットで出力:

```
前走{グレード}{レース名}{コメント本文（先頭の[レース名]を除く）}
前々走{グレード}{レース名}{コメント本文（先頭の[レース名]を除く）}
3走前{グレード}{レース名}{コメント本文（先頭の[レース名]を除く）}
```

走数カウントはコメントの有無にかかわらず、過去レース全体の順番で数える。  
グレードは `get_past_performances()` の返却値から取得する。

### 完了条件

- 印のついた馬の見解セクションに過去コメントが正しいフォーマットで出力される
- 印のない馬は見解セクションに出力されない
- TFJV_DATA_DIR が未設定の場合はデフォルトパスにフォールバックし、対象ファイルが見つからない場合は空辞書を返す
- 単体テスト実装
- mypy・flake8 エラーなし

---

## PR5: Qiita 自動投稿 CI

### 目的

`public/` 配下の markdown が push されたら GitHub Actions で Qiita へ自動 upsert する。

### 実装ファイル

- `.github/workflows/qiita_publish.yml`
- `scripts/qiita_publish.py` — POST/PATCH を行うスクリプト（CI から呼び出す）

### 作業内容

**CI トリガー:**

```yaml
on:
  push:
    paths:
      - 'public/**/*.md'
```

**新規 vs 更新の判定:**

- `public/{year}/.qiita_ids.json` にファイルパス → 記事ID のマッピングを保持する
- キーが存在しない場合: `POST /api/v2/items` → 取得した ID を `.qiita_ids.json` に追記してコミット・プッシュ
- キーが存在する場合: `PATCH /api/v2/items/{item_id}`

**フロントマターの付与:**

記事ファイルにフロントマターがない場合、スクリプト側でファイル名からタイトルを推定して付与する。

```markdown
---
title: "{race_name}{year}"
tags: ["競馬", "G1", "予想"]
private: false
---
```

**認証:**

GitHub Secrets `QIITA_ACCESS_TOKEN` を CI 環境変数から読み込む。

### 完了条件

- `public/` に新しい記事ファイルを push すると Qiita に新規投稿され、`.qiita_ids.json` が更新される
- 既存ファイルを更新して push すると、対応する Qiita 記事が更新される
- トークン未設定時は CI が明示的なエラーで失敗する
