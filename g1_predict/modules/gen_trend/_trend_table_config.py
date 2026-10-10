"""比較表の定義（table.yml）を読み込んで検証するモジュール。"""

import operator
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ._trend_catalog import TrendCategory
from ._trend_models import RowStats

COLOR_NAMES = frozenset({"green", "yellow", "blue", "red", "orange", "gray"})
_OPERATORS: dict[str, Callable[[float, float], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
}
_METRICS: dict[str, Callable[[RowStats], float]] = {
    "勝率": lambda s: round(s.first / s.total * 100),
    "複勝率": lambda s: round((s.first + s.second + s.third) / s.total * 100),
    "単回": lambda s: round(s.tansho_kaishuu),
    "複回": lambda s: round(s.fukusho_kaishuu),
}
_METRIC_RULE_KEYS = frozenset({"metric", "op", "value", "color"})
_METRIC_RULE_OPTIONAL_KEYS = frozenset({"min_total"})
_LABELS_RULE_KEYS = frozenset({"labels", "color"})


@dataclass(frozen=True)
class MetricRule:
    """出走馬が当たる行の集計値の指標で塗る色付けのルール。

    Attributes:
        color (str): 塗る色の名前。
        metric (str): 指標（勝率・複勝率・単回・複回）。
        op (str): 指標と基準値の比較演算子。
        value (float): 基準値（%の数値）。
        min_total (int | None): 行の頭数の下限。行の頭数がこれに満たない場合は当てはまらない。
    """

    color: str
    metric: str
    op: str
    value: float
    min_total: int | None = None

    def matches(self, label: str, stats: RowStats) -> bool:
        """出走馬が当たる行がこのルールに当てはまるか判定する。

        行の頭数が0の場合と、min_total に満たない場合は当てはまらない。
        勝率・複勝率・単回・複回は、記事の表に出ている整数の%で比べる。

        Args:
            label (str): 出走馬が当たる行の名前（表示名）。
            stats (RowStats): その行の過去の集計値。

        Returns:
            bool: 当てはまる場合 True。
        """
        if stats.total == 0 or (self.min_total is not None and stats.total < self.min_total):
            return False
        return _OPERATORS[self.op](_METRICS[self.metric](stats), self.value)


@dataclass(frozen=True)
class LabelsRule:
    """出走馬が当たる行の名前で塗る色付けのルール。

    Attributes:
        color (str): 塗る色の名前。
        labels (tuple[str, ...]): 塗る行の名前（display_map があれば表示名）。
    """

    color: str
    labels: tuple[str, ...]

    def matches(self, label: str, stats: RowStats) -> bool:
        """出走馬が当たる行がこのルールに当てはまるか判定する。

        Args:
            label (str): 出走馬が当たる行の名前（表示名）。
            stats (RowStats): その行の過去の集計値。

        Returns:
            bool: 行の名前が labels に含まれる場合 True。
        """
        return label in self.labels


ColorRule = MetricRule | LabelsRule


@dataclass(frozen=True)
class TableColumn:
    """比較表に載せる項目1件。

    Attributes:
        item_name (str): trends.yml の項目名。
        color_rules (tuple[ColorRule, ...]): 色付けのルール。先頭から評価する。
    """

    item_name: str
    color_rules: tuple[ColorRule, ...]


def parse_table_config(
    raw: Any,
    categories: list[TrendCategory],
) -> dict[str, list[TableColumn]]:
    """table.yml の内容を検証して、カテゴリごとの比較表の列に変換する。

    Args:
        raw (Any): table.yml を読み込んだ内容。
        categories (list[TrendCategory]): そのレースの trends.yml から展開したカテゴリ。

    Returns:
        dict[str, list[TableColumn]]: カテゴリ名 -> 比較表の列（table.yml に書かれた順）。

    Raises:
        ValueError: trends.yml に無いカテゴリ・項目がある場合、今走の結果で決まる項目がある場合、
            または書式（項目・色付けのルールのキー、metric・op・color の値）が不正な場合。
    """
    if not isinstance(raw, dict) or not raw:
        raise ValueError("table.yml はカテゴリ名をキーとする空でないマッピングで指定してください。")
    category_map = {category.name: category for category in categories}
    columns: dict[str, list[TableColumn]] = {}
    for category_name, entries in raw.items():
        if category_name not in category_map:
            raise ValueError(f"trends.yml に無いカテゴリです: {category_name}")
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"{category_name}: 項目は空でないリストで指定してください。")
        columns[category_name] = [
            _parse_column(entry, category_map[category_name]) for entry in entries
        ]
        names = [column.item_name for column in columns[category_name]]
        if len(set(names)) != len(names):
            raise ValueError(f"{category_name}: 項目名が重複しています: {names}")
    return columns


def _parse_column(entry: Any, category: TrendCategory) -> TableColumn:
    """table.yml の項目1件を TableColumn に変換する。

    Args:
        entry (Any): 項目名（文字列）、または `{項目名: {color_rules: [...]}}`。
        category (TrendCategory): 項目が属する trends.yml のカテゴリ。

    Returns:
        TableColumn: 変換した列。

    Raises:
        ValueError: 項目がカテゴリに無い場合、今走の結果で決まる項目の場合、または書式が不正な場合。
    """
    raw_rules: Any = []
    if isinstance(entry, str):
        item_name = entry
    elif isinstance(entry, dict) and len(entry) == 1:
        item_name, options = next(iter(entry.items()))
        if not isinstance(options, dict) or set(options) != {"color_rules"}:
            raise ValueError(f"{item_name}: 指定できるのは color_rules だけです: {options!r}")
        raw_rules = options["color_rules"]
        if not isinstance(raw_rules, list) or not raw_rules:
            raise ValueError(f"{item_name}: color_rules は空でないリストで指定してください。")
    else:
        raise ValueError(
            f"項目は項目名か {{項目名: {{color_rules: ...}}}} で指定してください: {entry!r}"
        )

    items = {item.name: item for item in category.items}
    if item_name not in items:
        raise ValueError(f"{category.name} の trends.yml に無い項目です: {item_name}")
    if items[item_name].uses_race_result:
        raise ValueError(f"{item_name}: 今走の結果で決まる項目は比較表に載せられません。")
    rules = tuple(_parse_rule(rule, item_name) for rule in raw_rules)
    return TableColumn(item_name=item_name, color_rules=rules)


def _parse_rule(raw: Any, item_name: str) -> ColorRule:
    """色付けのルール1件を ColorRule に変換する。

    Args:
        raw (Any): `{metric, op, value, color}`（任意で min_total）または `{labels, color}`。
        item_name (str): 項目名（エラーメッセージ用）。

    Returns:
        ColorRule: 変換したルール。

    Raises:
        ValueError: キーの過不足、または metric・op・value・min_total・labels・color の値が
            不正な場合。
    """
    if not isinstance(raw, dict):
        raise ValueError(f"{item_name}: color_rules の要素はマッピングで指定してください: {raw!r}")
    keys = set(raw)
    is_metric_rule = _METRIC_RULE_KEYS <= keys <= _METRIC_RULE_KEYS | _METRIC_RULE_OPTIONAL_KEYS
    if not is_metric_rule and keys != _LABELS_RULE_KEYS:
        raise ValueError(
            f"{item_name}: color_rules のキーは {sorted(_METRIC_RULE_KEYS)}（任意で "
            f"{sorted(_METRIC_RULE_OPTIONAL_KEYS)}）または {sorted(_LABELS_RULE_KEYS)} で"
            f"指定してください: {sorted(keys)}"
        )
    color = raw["color"]
    if not isinstance(color, str) or color not in COLOR_NAMES:
        raise ValueError(f"{item_name}: 未対応の color です: {color!r}")

    if keys == _LABELS_RULE_KEYS:
        labels = raw["labels"]
        if (
            not isinstance(labels, list)
            or not labels
            or not all(isinstance(label, str) for label in labels)
        ):
            raise ValueError(f"{item_name}: labels は文字列の空でないリストで指定してください。")
        return LabelsRule(color=color, labels=tuple(labels))

    if not isinstance(raw["metric"], str) or raw["metric"] not in _METRICS:
        raise ValueError(f"{item_name}: 未対応の metric です: {raw['metric']!r}")
    if not isinstance(raw["op"], str) or raw["op"] not in _OPERATORS:
        raise ValueError(f"{item_name}: 未対応の op です: {raw['op']!r}")
    value = raw["value"]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{item_name}: value は数値で指定してください: {value!r}")
    min_total = raw.get("min_total")
    if min_total is not None and (
        not isinstance(min_total, int) or isinstance(min_total, bool) or min_total < 1
    ):
        raise ValueError(f"{item_name}: min_total は1以上の整数で指定してください: {min_total!r}")
    return MetricRule(
        color=color, metric=raw["metric"], op=raw["op"], value=value, min_total=min_total
    )
