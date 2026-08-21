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

```bash
pip install -r requirements.txt
```

`requirements.txt` の内容:

| パッケージ | 用途 |
| --- | --- |
| `keiba-data-interface`（GitHub） | 日本語カラム名でのレース・出走表・過去成績取得 |
| `mykeibadb-python`（GitHub / `develop` ブランチ） | DB 直接アクセスと着度数集計（`analytics`） |
| `openpyxl` | 分析表（xlsx）の書き出し |
| `python-dotenv` | `.env` の読み込み |
| `pyyaml` | `configs/*.yml` の読み込み |
| `requests` | はてなブログ AtomPub / Fotolife API |

GitHub 上のプライベート／組織リポジトリを参照するため、インストール時に GitHub の認証が必要になる場合がある。

テスト・静的解析用の依存は `requirements.txt` に含まれていない。ローカルで CI と同じチェックを走らせる場合は別途入れる。

```bash
pip install pytest isort flake8 flake8-docstrings flake8-annotations pep8-naming darglint mypy
```

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

## 動作確認

DB や TFJV データがなくても単体テストは通る（外部依存はモックしている）。

```bash
pytest test/unit
```

実データを使った確認は、傾向分析の生成が一番手軽（DB 接続のみで完結し、TFJV データを必要としない）。

```bash
python -m scripts.gen_trend --race-code 2026061409030411
```

生成物は `public/{年}/{race_code}_{レース名}/傾向.md` に出力される。動作確認で作った生成物をコミットしないよう注意する。
