# レビュー: feature/g1predict-remove-di-remaining

## 概要

- **対象**: develop → feature/g1predict-remove-di-remaining
- **レビュー日**: 2026-06-05
- **レビュー対象ファイル数**: 4ファイル

変更内容: trend系モジュール（`_trend_loader.py`, `trend_section.py`, `prev_day_trend.py`）および
`scripts/gen_predict.py` に残存する `DataInterface` 依存を削除し、`RaceGetter` ベースの実装に置換する。

## 指摘事項

### 1. `_trend_loader.py` の import が絶対パス → 解消済み

| 項目 | 内容 |
|------|------|
| 重要度 | Suggestion |
| 場所 | `g1_predict/modules/gen_predict/_trend_loader.py` L8 |

**指摘内容**

同一パッケージ内の `prev_day_trend` モジュールを絶対インポートしていた。

**対応**

相対インポートに修正済み。さらに Copilot レビューにより `TRACK_CODE_TO_SHIBA_DA` を
`_constants.py` へ分離し、`_trend_loader.py` から `prev_day_trend` への依存を解消した。

### 2. `build_prev_day_trend_section()` 内で `DataInterface("mykeibadb")` をハードコード → 解消済み

| 項目 | 内容 |
|------|------|
| 重要度 | Suggestion |
| 場所 | `g1_predict/modules/gen_predict/prev_day_trend.py` L53 |

**指摘内容**

`di = DataInterface("mykeibadb")` が関数内にハードコードされており、テスト時に DI を差し替えられない。

**対応**

`test/unit/modules/gen_predict/prev_day_trend/test_build_prev_day_trend_section.py` を追加し、
`patch("...DataInterface")` でモック注入する形でテストを実装した。

## まとめ

| 重要度 | 件数 |
|--------|------|
| Critical | 0 |
| Warning | 0 |
| Suggestion | 2 |

すべて対応済み。
