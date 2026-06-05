# レビュー: feature/g1predict-trend-loader

## 概要

- **対象**: main → feature/g1predict-trend-loader
- **レビュー日**: 2026-06-05
- **レビュー対象ファイル数**: 9ファイル（実装5 + テスト4）

変更内容: `_trend_models`, `_trend_loader`, `_trend_stats`, `_trend_renderer`, `trend_section` を全面再実装。
`DataInterface` / `RaceGetter` / `MasterGetter` / pandas集計を廃止し、`analyze_chakudo` / `analyze_subject_chakudo` /
`analyze_entry_attr_chakudo` 経由で `RaceCondition` を渡す形に統一。

## 指摘事項

### 1. compute_stats でフォールバック処理を実装している

| 項目 | 内容 |
|------|------|
| 重要度 | Warning |
| 場所 | `g1_predict/modules/gen_predict/_trend_stats.py` L45–46 |

**指摘内容**

`rows_cfg = metric_cfg.get("rows", {})` と `src = metric_cfg.get("source", {})` は YAML設定キーが存在しない場合に空 dict を返すフォールバック。
`_build_metric_section` 側では同じキーを `metric_cfg["rows"]` で直接参照しており、一貫性がない。
CLAUDE.md「フォールバック処理を実装してはいけません。意図した処理が失敗する場合は、例外を発生させてください。」に違反。

**修正案**

```python
# 修正前
rows_cfg = metric_cfg.get("rows", {})
src = metric_cfg.get("source", {})

# 修正後
rows_cfg = metric_cfg["rows"]
src = metric_cfg["source"]
```

---

### 2. _yaml_rows_to_rowsdef で op: "in" がサイレントスキップされる

| 項目 | 内容 |
|------|------|
| 重要度 | Suggestion |
| 場所 | `g1_predict/modules/gen_predict/_trend_stats.py` L217–222 |

**指摘内容**

`op: "in"` の item は変換対象外として result に追加されない（サイレント）。
`entry_attr` 系 source で `in` を使った YAML 設定を書いても該当ラベルが出力から消えるだけで、
設定ミスに気づけない。

**修正案**

ドキュメント上の仕様として `"in"` をサポート外と明示しているなら、明示的にエラーを出すべき。

```python
# 修正前
if op == "==":
    result[label] = value if isinstance(value, str) else int(value)
elif op == ">=":
    result[label] = (int(value), 9999)
elif op == "<=":
    result[label] = (0, int(value))

# 修正後
if op == "==":
    result[label] = value if isinstance(value, str) else int(value)
elif op == ">=":
    result[label] = (int(value), 9999)
elif op == "<=":
    result[label] = (0, int(value))
elif op == "in":
    raise ValueError(f"op 'in' は entry_attr 系 source では使用できません。label={label!r}")
```

---

### 3. TRACK_CODE_TO_SHIBA_DA.get() に冗長な or None

| 項目 | 内容 |
|------|------|
| 重要度 | Suggestion |
| 場所 | `g1_predict/modules/gen_predict/_trend_loader.py` L68 |

**指摘内容**

`TRACK_CODE_TO_SHIBA_DA.get(track_code) or None` の `or None` が冗長。
`dict.get()` は既に未知のキーに対して `None` を返す。

**修正案**

```python
# 修正前
shiba_da = TRACK_CODE_TO_SHIBA_DA.get(track_code) or None

# 修正後
shiba_da = TRACK_CODE_TO_SHIBA_DA.get(track_code)
```

---

### 4. test_format_percent_* を parametrize で集約できる

| 項目 | 内容 |
|------|------|
| 重要度 | Suggestion |
| 場所 | `test/unit/modules/gen_predict/trend_section/test_trend_renderer.py` L30–53 |

**指摘内容**

`_format_percent` に対する5テストは「入力値だけが異なる」ケース群。
pytest-coding-rule「入力値だけが異なるテストは `@pytest.mark.parametrize` でまとめる」に従い集約すべき。

**修正案**

```python
@pytest.mark.parametrize(
    "count, total, expected",
    [
        (0, 0, "-"),
        (0, 10, "0%"),
        (5, 10, "50%"),
        (1, 3, "33%"),
        (3, 3, "100%"),
    ],
)
def test_format_percent(count: int, total: int, expected: str) -> None:
    """_format_percent が正しく変換する。"""
    assert _format_percent(count, total) == expected
```

---

### 5. test_group_matches_* を parametrize で集約できる

| 項目 | 内容 |
|------|------|
| 重要度 | Suggestion |
| 場所 | `test/unit/modules/gen_predict/trend_section/test_trend_stats.py` L120–158 |

**指摘内容**

`_group_matches` の7テストも入力パターンの違いだけで、同じく parametrize 化が適切。

**修正案**

```python
@pytest.mark.parametrize(
    "group_str, op, threshold, expected",
    [
        ("3", "==", 3, True),
        ("3", "==", 4, False),
        ("継続", "==", "継続", True),
        ("継続", "==", "テン乗り", False),
        ("10", ">=", 10, True),
        ("9", ">=", 10, False),
        ("2", "<=", 2, True),
        ("3", "<=", 2, False),
        ("4", "in", [4, 5, 6], True),
        ("7", "in", [4, 5, 6], False),
        ("1", "in", ["1", "2"], True),
        ("3", "in", ["1", "2"], False),
        ("01", "==", 1, True),
    ],
)
def test_group_matches(group_str: str, op: str, threshold: object, expected: bool) -> None:
    """_group_matches が各演算子を正しく評価する。"""
    assert _group_matches(group_str, op, threshold) is expected
```

---

## まとめ

| 重要度 | 件数 |
|--------|------|
| Critical | 0 |
| Warning | 1 |
| Suggestion | 4 |
