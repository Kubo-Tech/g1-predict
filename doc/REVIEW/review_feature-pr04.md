# レビュー: feature/pr04

## 概要

- **対象**: develop → feature/pr04（未コミット差分）
- **レビュー日**: 2026-05-25
- **レビュー対象ファイル数**: 3ファイル（scripts/gen_predict.py, test_generate_predict.py, __init__.py）

## 指摘事項

### 1. マーク並び替えロジックの重複

| 項目 | 内容 |
|------|------|
| 重要度 | Warning |
| 場所 | `scripts/gen_predict.py` L97-103, L119-125 |

**指摘内容**

`_build_marks_section` と `_build_insight_section` が同一の `sorted(marks.items(), ...)` ロジックを重複実装している。DRY原則違反。

**修正案**

モジュールレベルのヘルパー関数として抽出する。

```python
def _sort_marks(marks: dict[int, str]) -> list[tuple[int, str]]:
    return sorted(
        marks.items(),
        key=lambda x: (
            _MARK_ORDER.index(x[1]) if x[1] in _MARK_ORDER else len(_MARK_ORDER),
            x[0],
        ),
    )
```

両関数で `_sort_marks(marks)` を呼ぶ。

---

### 2. グレードコード "E"（特別競走）が未定義

| 項目 | 内容 |
|------|------|
| 重要度 | Suggestion |
| 場所 | `scripts/gen_predict.py` L25-34 |

**指摘内容**

`_GRADE_CODE_DISPLAY` に `"E"` (特別競走) が定義されていない。grade_code.yml では `"E" → "特別競走"` が定義されているが、この辞書では `get(grade_code, "")` のフォールバックで空文字になる。特別競走の過去コメントが一般競走と同じ表示になり、区別できない。

**修正案**

```python
_GRADE_CODE_DISPLAY: dict[str, str] = {
    "A": "G1",
    "B": "G2",
    "C": "G3",
    "D": "重賞",
    "E": "特別",
    "F": "J・G1",
    "G": "J・G2",
    "H": "J・G3",
    "L": "L",
}
```

## まとめ

| 重要度 | 件数 |
|--------|------|
| Critical | 0 |
| Warning | 1 |
| Suggestion | 1 |

Warning（DRY違反）はリファクタリング必須ではないが、今後 `_build_marks_section` や `_build_insight_section` にロジック追加が発生した場合に片方だけ更新する危険がある。対応を推奨する。
