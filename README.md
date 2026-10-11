# g1-predict

JRA-VAN のデータと TARGET frontier JV の自作メモをもとに、**JRA G1 レースの傾向分析・予想・回顧記事を半自動生成し、はてなブログへ自動投稿する**個人用リポジトリ。

生成物（Markdown・画像）は `public/` 配下にレース単位で保存され、`main` へ push すると GitHub Actions がはてなブログへ投稿・更新する。

## できること

| スクリプト | 生成物 | 概要 |
| --- | --- | --- |
| `scripts/gen_trend.py` | `public/{年}/{race_code}_{レース名}/過去の傾向.md` | 過去10年（G1になってから10年に満たないレースはG1になった年から）の着度数・回収率から傾向分析記事を生成する。`--with-entries` で、今回の出走馬が当たる行の列と出走馬の比較表の画像も載せる |
| `scripts/gen_past_race_dynamics.py` | `.../出走馬の過去走の展開評価.md` | 出走馬の過去5走の展開評価を馬ごとの折りたたみで並べた記事を生成する |
| `scripts/gen_prev_day_trend.py` | `.../前日の傾向.md` | 前日の同競馬場・同芝ダの結果から前日の傾向記事を生成する |
| `scripts/gen_race_day_trend.py` | `.../当日の傾向.md` | 当日の同競馬場・同芝ダのうち結果が出ているレースから当日の傾向記事を生成する |
| `scripts/gen_predict.py` | `.../予想.md` | 印・見解を埋めた予想記事のベースを生成する |
| `scripts/gen_result_comment.py` | TFJV の `KEK_COM` ファイル | レース結果から着差・着順の定型コメントを TARGET へ書き戻す |
| `scripts/gen_result.py` | `.../回顧.md` | 着順と回顧コメントを埋めた回顧記事のベースを生成する |
| `scripts/hatena_publish.py` | はてなブログの記事 | 変更された `public/**/*.md` を投稿・更新する（GitHub Actions から実行） |

どのスクリプトも「記事のベース」を作るところまでを担当し、見解・総評・画像などは生成後に手で書き足す。

## クイックスタート

```bash
# 1. 依存インストール（開発する場合は docs/setup.md を参照）
pip install -e .

# 2. 環境変数（.env）を用意する
#    MYKEIBADB_HOST / MYKEIBADB_PORT / MYKEIBADB_DATABASE / MYKEIBADB_USER / MYKEIBADB_PASSWORD
#    TFJV_DATA_DIR（TARGET frontier JV のデータディレクトリ。既定は ./MY_DATA）

# 3. レースごとの設定ファイルを用意する（configs/{レース名}/trends.yml, table.yml）

# 4. 実行（race_code は16桁の JRA-VAN レースコード）
python -m scripts.gen_trend          --race-code 2026061409030411
python -m scripts.gen_trend          --race-code 2026061409030411 --with-entries  # 出走馬の確定後
python -m scripts.gen_prev_day_trend --race-code 2026061409030411
python -m scripts.gen_race_day_trend --race-code 2026061409030411
python -m scripts.gen_past_race_dynamics --race-code 2026061409030411
python -m scripts.gen_predict        --race-code 2026061409030411
```

詳しい手順は [docs/setup.md](docs/setup.md) と [docs/workflow.md](docs/workflow.md) を参照。

## ディレクトリ構成

```
g1-predict/
├── configs/            # 傾向表の共有項目定義（trends/）とレースごとの傾向・比較表定義（YAML）
├── docs/               # 本ドキュメント
├── g1_predict/modules/ # 記事生成のコアロジック
├── public/             # 生成した記事・画像（はてなブログ投稿対象）
├── scripts/            # エントリポイント（python -m scripts.xxx）
├── templates/          # 記事テンプレートとレース別「ポイント」原稿
├── test/unit/          # pytest 単体テスト
└── MY_DATA/            # TARGET frontier JV のデータ置き場（git 管理外）
```

## ドキュメント

- [docs/README.md](docs/README.md) — ドキュメント索引
- [docs/architecture.md](docs/architecture.md) — 全体構成とデータフロー
- [docs/setup.md](docs/setup.md) — セットアップと環境変数
- [docs/workflow.md](docs/workflow.md) — レース1本分の作業手順
- [docs/scripts.md](docs/scripts.md) — 各スクリプトの仕様
- [docs/config-reference.md](docs/config-reference.md) — `configs/{レース名}/*.yml` の全リファレンス
- [docs/tfjv-data.md](docs/tfjv-data.md) — TARGET frontier JV 連携
- [docs/hatena-publish.md](docs/hatena-publish.md) — はてなブログ自動投稿
- [docs/development.md](docs/development.md) — 開発フロー・CI・テスト

## ライセンス

[MIT License](LICENSE)
