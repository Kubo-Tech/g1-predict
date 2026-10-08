# セットアップ

## 前提

| 項目 | 内容 |
| --- | --- |
| Python | 3.12（CI で使用しているバージョン） |
| データベース | JRA-VAN データを取り込んだ PostgreSQL（mykeibadb） |
| TARGET frontier JV | 印・成績コメントの読み書きに使用（[tfjv-data.md](tfjv-data.md)） |
| 実行場所 | リポジトリルート（`python -m scripts.xxx` 形式で実行する） |

このリポジトリは KeibaAI プロジェクト（`/KeibaAI`）の `repos/g1-predict` に置かれる前提のパスがコードに含まれている（後述の `TFJV_DATA_DIR` の既定値）。単独クローンで使う場合は環境変数で上書きする。

## 依存インストール

依存は `pyproject.toml` で管理している。

```bash
# 実行するだけなら
pip install -e .

# 開発する場合（テスト・静的解析ツールを含む）
pip install -e ".[dev]"
```

`[project] dependencies` の内容:

| パッケージ | 用途 |
| --- | --- |
| `keiba-domain`（GitHub） | 競馬ドメインの定義・判定。`keiba-data-interface` が要求する |
| `keiba-data-interface`（GitHub） | 日本語カラム名でのレース・出走表・過去成績取得 |
| `mykeibadb-python`（GitHub / `develop` ブランチ） | DB 直接アクセスと着度数集計・出走馬のグループの値の取得（`analytics`） |
| `race-data`（GitHub） | レースデータの取得・判定（`RaceData`）。`race-dynamics-evaluation` が要求する |
| `feature-value-utils`（GitHub、private） | 統計量計算。`race-dynamics-evaluation` が要求する |
| `race-dynamics-evaluation`（GitHub、private） | 展開評価（差し有利度・外枠有利度・外有利度）の計算とプロット |
| `matplotlib` | 前日・当日の傾向のグラフ（出目の棒グラフ・展開グラフ・標準化散布図）と、過去の傾向の出走馬の比較表の画像の生成。日本語表示に Noto Sans CJK JP フォントを使う |
| `python-dotenv` | `.env` の読み込み |
| `pyyaml` | `configs/` 配下の YAML の読み込み |
| `requests` | はてなブログ AtomPub / Fotolife API |

`keiba-domain` は `keiba-data-interface` の依存だが、PyPI に存在せず GitHub からしか取得できないため、**このリポジトリの直接依存としても明示している**。書かないと依存解決が `No matching distribution found for keiba-domain` で失敗する。`feature-value-utils` も同様に `race-dynamics-evaluation` の依存として明示している。

`race-dynamics-evaluation` と `feature-value-utils` は `KeibaAI-developer` の private リポジトリのため、ローカルでの `pip install` には GitHub への認証が必要になる（SSH 鍵、または `https://<token>@github.com/...` 形式の URL など）。CI では Secrets の `KEIBAAI_DEVELOPER_TOKEN`（`KeibaAI-developer` の private リポジトリを読める fine-grained PAT。Contents: Read-only）を使って認証する。

`[project.optional-dependencies] dev` には `pytest` / `pytest-cov` / `pytest-mock` と、静的解析用の `mypy` / 型スタブが入る。ruff は CI 側でバージョンを固定して実行するため、ここには含めない。

## 環境変数

`python-dotenv` の `find_dotenv()` で `.env` を探索するため、リポジトリルートかその上位ディレクトリに `.env` を置けばよい。

### データベース接続（必須）

`mykeibadb-python` の `ConfigManager.from_env()` が読む。未設定時は括弧内の既定値が使われる。

| 変数 | 既定値 |
| --- | --- |
| `MYKEIBADB_HOST` | `localhost` |
| `MYKEIBADB_PORT` | `5432` |
| `MYKEIBADB_DATABASE` | `mykeibadb` |
| `MYKEIBADB_USER` | `postgres` |
| `MYKEIBADB_PASSWORD` | `postgres` |

KeibaAI の開発コンテナからクラウド DB を参照する場合は、ポートフォワーディング（`docker-compose.yml` の `15432` / `54321`）を張ったうえでホスト・ポートを指定する。

### TARGET frontier JV データ（`gen_predict` / `gen_result` / `gen_result_comment` で必須）

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `TFJV_DATA_DIR` | `/KeibaAI/repos/g1-predict/MY_DATA` | `UM*.DAT` と `KEK_COM/` を含むディレクトリ |

`MY_DATA/` は `.gitignore` 済み。TARGET frontier JV 側のデータディレクトリをここへマウント（またはコピー）して使う。

### はてなブログ投稿（GitHub Actions でのみ使用）

`scripts/hatena_publish.py` は以下を**必須**の環境変数として読む（未設定なら `KeyError`）。GitHub の Secrets に登録しておく。

| 変数 | 内容 |
| --- | --- |
| `HATENA_ID` | はてな ID |
| `HATENA_BLOG_ID` | ブログ ID（例: `kubotech.hatenadiary.com`） |
| `HATENA_API_KEY` | AtomPub の API キー |

ローカルから手動投稿する場合のみ、`.env` にも同じ値が必要になる。

### CI の依存インストール（GitHub Actions でのみ使用）

| 変数 | 内容 |
| --- | --- |
| `KEIBAAI_DEVELOPER_TOKEN` | `KeibaAI-developer` の private リポジトリ（`race-dynamics-evaluation`、`feature-value-utils`）を読める fine-grained PAT（Contents: Read-only） |

`.github/workflows/ci.yml` が依存インストール前にこのトークンで `https://github.com/KeibaAI-developer/` への git アクセスを認証する。GitHub の Secrets に登録しておく。

## 動作確認

DB や TFJV データがなくても単体テストは通る（外部依存はモックしている）。

```bash
pytest test/unit
```

実データを使った確認は、傾向分析の生成が一番手軽（DB 接続のみで完結し、TFJV データを必要としない）。

```bash
python -m scripts.gen_trend --race-code 2026061409030411
```

生成物は `public/{年}/{race_code}_{レース名}/過去の傾向.md` に出力される。動作確認で作った生成物をコミットしないよう注意する。
