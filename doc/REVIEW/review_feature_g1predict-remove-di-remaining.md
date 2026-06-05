# レビュー: feature/g1predict-remove-di-remaining

## 概要

- **対象**: develop → feature/g1predict-remove-di-remaining
- **レビュー日**: 2026-06-05
- **レビュー対象ファイル数**: 4ファイル

変更内容: trend系モジュール（`_trend_loader.py`, `trend_section.py`, `prev_day_trend.py`）および
`scripts/gen_predict.py` に残存する `DataInterface` 依存を削除し、`RaceGetter` ベースの実装に置換する。

## 指摘事項

### 1. `_trend_loader.py` の import が絶対パス

| 項目 | 内容 |
|------|------|
| 重要度 | Suggestion |
| 場所 | `g1_predict/modules/gen_predict/_trend_loader.py` L8 |

**指摘内容**

同一パッケージ内の `prev_day_trend` モジュールを絶対インポートしている。同一パッケージ内のモジュールは相対インポートで参照するのが Python の慣習。

**修正案**

```python
# 修正前
from g1_predict.modules.gen_predict.prev_day_trend import TRACK_CODE_TO_SHIBA_DA

# 修正後
from .prev_day_trend import TRACK_CODE_TO_SHIBA_DA
```

### 2. `build_prev_day_trend_section()` 内で `DataInterface("mykeibadb")` をハードコード

| 項目 | 内容 |
|------|------|
| 重要度 | Suggestion |
| 場所 | `g1_predict/modules/gen_predict/prev_day_trend.py` L53 |

**指摘内容**

`di = DataInterface("mykeibadb")` が関数内にハードコードされており、テスト時に DI を差し替えられない。
今後テストを追加する際の障壁になりうる。

**修正案**

現時点ではこのリポジトリに `prev_day_trend` のテストが存在しないため、差し迫った問題はない。
将来テストが必要になった際に引数として受け取る形に変更することを検討する。

## まとめ

| 重要度 | 件数 |
|--------|------|
| Critical | 0 |
| Warning | 0 |
| Suggestion | 2 |

Critical・Warning なし。Suggestion 2件はいずれも修正しなくても支障なし。PRを進める。
