# g1-predict ドキュメント

このリポジトリで「何を・どう作っているか」を思い出すための索引。

## 読む順番（久しぶりに触るとき）

1. [architecture.md](architecture.md) — 何が何を作っているのか、全体像とデータの流れ
2. [workflow.md](workflow.md) — レース1本を記事にするまでの実作業手順
3. [scripts.md](scripts.md) — 各スクリプトの引数・入出力・処理内容
4. [config-reference.md](config-reference.md) — `configs/{レース名}.yml` の全項目リファレンス

## 目的別

| 知りたいこと | ドキュメント |
| --- | --- |
| 動かすための前提・環境変数・依存関係 | [setup.md](setup.md) |
| 新しいレースの設定ファイルを作りたい | [config-reference.md](config-reference.md) |
| 傾向表に新しい項目を追加したい | [config-reference.md](config-reference.md) / [development.md](development.md) |
| 印・コメントがどこから来ているのか | [tfjv-data.md](tfjv-data.md) |
| はてなブログへの投稿が失敗した | [hatena-publish.md](hatena-publish.md) |
| ブランチ・CI・テストの運用 | [development.md](development.md) |

## ドキュメント一覧

- [architecture.md](architecture.md) — リポジトリ構成、データフロー、モジュール構成、`race_code` の仕様
- [setup.md](setup.md) — 依存インストール、環境変数、DB・TFJV データの準備
- [workflow.md](workflow.md) — 傾向 → 分析表 → 前日の傾向 → 予想 → 結果 → 公開までの手順
- [scripts.md](scripts.md) — `scripts/` 配下5+1スクリプトの詳細仕様
- [config-reference.md](config-reference.md) — `trends` / `table` の YAML スキーマと `source.type` 一覧
- [tfjv-data.md](tfjv-data.md) — TARGET frontier JV のファイル構造と読み書き仕様
- [hatena-publish.md](hatena-publish.md) — AtomPub 投稿、Fotolife 画像アップロード、状態ファイル
- [development.md](development.md) — ブランチ戦略、CI、静的解析、テスト、仕様書運用
