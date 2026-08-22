# 開発フロー

## ブランチ運用

| 対象 | 運用 |
| --- | --- |
| コード・設定の変更 | `develop` から `feature/{内容}` を切る → PR → `develop` へマージ |
| 記事（`public/` 配下） | `main` へ直接コミット・push（push をトリガーにはてなブログへ投稿される） |
| `develop` → `main` | 区切りのよいところで `main` へ反映する。`main` の記事コミットは適宜 `develop` へマージして同期する |

`main` への push がはてなブログ投稿を起こすため、**コードだけの変更を `main` へ直接入れない**（`public/**/*.md` に差分が無ければ投稿は走らないが、履歴が混ざるのを避ける）。

## 静的解析とテスト

設定はすべて `pyproject.toml` に集約している（`[tool.ruff]` / `[tool.mypy]` / `[tool.pytest.ini_options]`）。CI と同じチェックをローカルで走らせる場合:

```bash
ruff check g1_predict/ scripts/ test/
mypy g1_predict/ scripts/
pytest test/unit
```

ruff は isort・flake8・darglint を置き換えたもので、KeibaAI の他ライブラリと同じルールセット（`E,W,F,N,D,I,DOC` / Google スタイル docstring / 100文字）を使う。CI では共通の `library-workflow` と同じバージョン（`RUFF_VERSION`）に固定して実行するため、ローカルの ruff の版が違うと結果がずれることがある。

CI（`.github/workflows/ci.yml`）は `g1_predict/**` / `scripts/**` / `test/**` / `configs/**` / `pyproject.toml` / `ci.yml` の変更で起動し、ruff は `g1_predict/` + `scripts/` + `test/`、mypy は `g1_predict/` + `scripts/` を検査する。

`pytest` は外部依存をモックしているので DB・TFJV データが無くても通る。ただし `openpyxl` などの依存は必要なので、事前に `pip install -e ".[dev]"` を済ませておく。

## テストの置き場所

`test/unit/` 以下を、対象モジュール・対象関数ごとにディレクトリで切る構成にしている。

```
test/unit/
├── modules/
│   ├── gen_predict/trend_section/test_trend_stats.py
│   ├── gen_table/table_utils/test_apply_color_rules.py
│   └── utils/tfjv/test_read_marks.py
└── scripts/
    ├── gen_predict/test_generate_predict.py
    └── hatena_publish/test_extract_title.py
```

方針（`AGENTS.md` にも記載）:

- 正常系 / 準正常系（`pytest.raises` で検証する想定内の異常入力） / 異常系 に分類する。
- テストクラスは使わない。同型のケースは `@pytest.mark.parametrize` でまとめる。
- モックが呼ばれたことだけを見るテストにしない。

## コーディング規約

`AGENTS.md`（Codex のレビュー指示を兼ねる）に定めた観点:

- public な関数・メソッドを上、private を下に配置する。
- `self` を使わないメソッドはモジュールレベル関数に切り出す。
- 引数・戻り値に型アノテーションを付ける。docstring は Google スタイル。
- 未対応の設定値は握りつぶさず `ValueError` を送出する（フォールバックを書かない）。

## 機能追加の進め方

傾向表・分析表に「今の `source.type` では表現できない項目」を足したくなったときの流れ。

1. **YAML で表現できないか先に確認する**。既存の `source.type` の組み合わせで済むことが多い。
2. 済まない場合、追加する `source.type` の仕様（入力・出力・エラー時の挙動・行ラベル）を決める。
3. 実装する。
   - 傾向表（trends）: `g1_predict/modules/gen_predict/_trend_stats.py` の `compute_stats()` に分岐を追加する。行の出し方を変える場合は `_trend_renderer.py`、集計範囲を変える場合は `_trend_loader.py`。
   - 分析表（table）: `g1_predict/modules/gen_table/table_context.py` の `get_value()` に分岐を追加する。統計計算は `table_stat.py`、DB アクセスは `table_data_cache.py`、色ルール・フィルタは `table_utils.py`。
4. 単体テストを追加する。
5. `configs/{レース名}.yml` を更新し、実データで生成して表が欠損なく出ることを確認する。**動作確認で生成した記事や xlsx はコミットしない**。
6. [config-reference.md](config-reference.md) の一覧に追記する。
