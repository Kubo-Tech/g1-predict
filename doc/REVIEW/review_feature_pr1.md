# レビュー: feature/pr1

## 概要

- **対象**: main → feature/pr1（新規ファイル）
- **レビュー日**: 2026-05-24
- **レビュー対象ファイル数**: 3ファイル（scripts/tfjv.py, requirements.txt, templates/points/.gitkeep）

## 指摘事項

### 1. `read_kek_comments` の前提条件が暗黙的

| 項目 | 内容 |
|------|------|
| 重要度 | Suggestion |
| 場所 | `scripts/tfjv.py` L87 |

**指摘内容**

`hh = int(line[8:10])` は prefix が常に8文字であることを前提とする。
`prefix = f"{venue(2)}{year2(2)}{tfjv_code(2)}{rr(2)}"` で合計8文字になるが、
`tfjv_code` が2文字でない場合（kai または nichi が 16 以上の場合）に切り出し位置がずれる。
実際の JRA 開催では kai・nichi とも16以上になることはなく、実害はない。

**修正案**

prefix の長さに依存した固定スライスより `len(prefix)` を使う方が意図が明確。

```python
hh = int(line[len(prefix) : len(prefix) + 2])
```

---

## まとめ

| 重要度 | 件数 |
|--------|------|
| Critical | 0 |
| Warning | 0 |
| Suggestion | 1 |

指摘はすべて Suggestion のみ。コミット可能な品質。
