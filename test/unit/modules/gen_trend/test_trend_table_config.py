"""_trend_table_config の単体テスト。"""

import os
from typing import Any

import pytest
import yaml

from g1_predict.modules.gen_trend._trend_catalog import (
    TrendCategory,
    TrendItem,
    build_trend_categories,
    load_trend_catalog,
)
from g1_predict.modules.gen_trend._trend_models import RowStats
from g1_predict.modules.gen_trend._trend_table_config import (
    LabelsRule,
    MetricRule,
    TableColumn,
    parse_table_config,
)

_CONFIGS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "configs")
)
_RACES = {"東京優駿": 2400, "安田記念": 1600, "宝塚記念": 2200, "スプリンターズS": 1200}


def _make_categories() -> list[TrendCategory]:
    """テスト用のカテゴリ（基本項目: 枠順・脚質（今走の結果で決まる）・所属、前走: 前走レース）。"""
    return [
        TrendCategory(
            name="基本項目",
            description="d",
            items=[
                TrendItem(name="枠順", config={}, condition=None),
                TrendItem(name="脚質", config={}, condition=None, uses_race_result=True),
                TrendItem(name="所属", config={}, condition=None),
            ],
        ),
        TrendCategory(
            name="前走",
            description="d",
            items=[TrendItem(name="前走レース", config={}, condition=None)],
        ),
    ]


def _rule(**options: Any) -> dict[str, Any]:
    """色付けのルール1件を生成する。"""
    return {"metric": "複勝率", "op": ">=", "value": 30, "color": "yellow", **options}


# 正常系
def test_parse_table_config_reads_columns_in_order() -> None:
    """カテゴリごとに、項目を table.yml に書かれた順で読み込む。"""
    raw = {"基本項目": ["所属", {"枠順": {"color_rules": [_rule()]}}], "前走": ["前走レース"]}
    columns = parse_table_config(raw, _make_categories())
    assert list(columns) == ["基本項目", "前走"]
    assert [column.item_name for column in columns["基本項目"]] == ["所属", "枠順"]
    assert columns["基本項目"][0] == TableColumn(item_name="所属", color_rules=())
    assert columns["基本項目"][1].color_rules == (
        MetricRule(color="yellow", metric="複勝率", op=">=", value=30),
    )


def test_parse_table_config_reads_metric_and_labels_rules_mixed() -> None:
    """指標のルールと行の名前のルールを混ぜて書ける。"""
    rules = [_rule(), {"labels": ["栗東", "美浦"], "color": "gray"}]
    raw = {"基本項目": [{"所属": {"color_rules": rules}}]}
    columns = parse_table_config(raw, _make_categories())
    assert columns["基本項目"][0].color_rules == (
        MetricRule(color="yellow", metric="複勝率", op=">=", value=30),
        LabelsRule(color="gray", labels=("栗東", "美浦")),
    )


def test_parse_table_config_reads_min_total() -> None:
    """指標のルールには、行の頭数の下限 min_total を任意で書ける。"""
    raw = {"基本項目": [{"枠順": {"color_rules": [_rule(min_total=10)]}}]}
    columns = parse_table_config(raw, _make_categories())
    assert columns["基本項目"][0].color_rules == (
        MetricRule(color="yellow", metric="複勝率", op=">=", value=30, min_total=10),
    )


# 準正常系
@pytest.mark.parametrize(
    "raw",
    [
        None,
        {},
        [],
        {"存在しないカテゴリ": ["枠順"]},
        {"基本項目": []},
        {"基本項目": "枠順"},
        {"基本項目": ["存在しない項目"]},
        {"基本項目": ["前走レース"]},
        {"基本項目": ["脚質"]},
        {"基本項目": ["枠順", "枠順"]},
        {"基本項目": [{"枠順": {"condition": {}}}]},
        {"基本項目": [{"枠順": {"color_rules": []}}]},
        {"基本項目": [{"枠順": "yellow"}]},
        {"基本項目": [{"枠順": {"color_rules": ["yellow"]}, "所属": {"color_rules": []}}]},
        {"基本項目": [3]},
    ],
)
def test_parse_table_config_invalid_structure_raises(raw: Any) -> None:
    """カテゴリ・項目が trends.yml に無い、今走の結果で決まる、書式が不正な場合は ValueError。"""
    with pytest.raises(ValueError):
        parse_table_config(raw, _make_categories())


@pytest.mark.parametrize(
    "rule",
    [
        {"metric": "複勝率", "op": ">=", "color": "yellow"},
        {"op": ">=", "value": 30, "color": "yellow"},
        {"metric": "複勝率", "op": ">=", "value": 30},
        {"labels": ["栗東"]},
        {"color": "yellow"},
        {"metric": "複勝率", "op": ">=", "value": 30, "color": "yellow", "labels": ["栗東"]},
        _rule(metric="人気"),
        _rule(op="!="),
        _rule(color="purple"),
        _rule(color=["yellow"]),
        _rule(color={"name": "yellow"}),
        _rule(metric=["複勝率"]),
        _rule(op=[">="]),
        {"labels": ["栗東"], "color": ["yellow"]},
        _rule(value="30"),
        _rule(value=True),
        _rule(min_total=0),
        _rule(min_total=10.5),
        _rule(min_total="10"),
        _rule(min_total=True),
        {"labels": ["栗東"], "color": "yellow", "min_total": 10},
        {"labels": [], "color": "yellow"},
        {"labels": "栗東", "color": "yellow"},
        {"labels": [1], "color": "yellow"},
        {"labels": ["栗東"], "color": "purple"},
        "yellow",
    ],
)
def test_parse_table_config_invalid_rule_raises(rule: Any) -> None:
    """色付けのルールのキーの不足・過不足、未知の metric・op・color は ValueError。"""
    raw = {"基本項目": [{"枠順": {"color_rules": [rule]}}]}
    with pytest.raises(ValueError):
        parse_table_config(raw, _make_categories())


# --- ColorRule.matches ---


@pytest.mark.parametrize(
    "metric, op, value, expected",
    [
        ("勝率", ">=", 10, True),
        ("勝率", ">", 10, False),
        ("複勝率", ">=", 30, True),
        ("複勝率", "<", 30, False),
        ("単回", "==", 105, True),
        ("単回", "<=", 100, False),
        ("複回", "<", 90, True),
    ],
)
def test_metric_rule_matches_rounded_percent(
    metric: str, op: str, value: float, expected: bool
) -> None:
    """指標のルールは、記事の表と同じ整数の%で比べる。"""
    stats = RowStats(
        first=1, second=1, third=1, fourth_plus=7, tansho_kaishuu=104.6, fukusho_kaishuu=85.2,
        total=10,
    )
    rule = MetricRule(color="yellow", metric=metric, op=op, value=value)
    assert rule.matches("A", stats) is expected


def test_metric_rule_does_not_match_empty_row() -> None:
    """指標のルールは、行の頭数が0の場合は当てはまらない。"""
    rule = MetricRule(color="gray", metric="複勝率", op="==", value=0)
    assert rule.matches("A", RowStats()) is False


def test_metric_rule_matches_zero_percent_row_with_horses() -> None:
    """頭数があって複勝率が0%の行は == 0 に当てはまる。"""
    rule = MetricRule(color="gray", metric="複勝率", op="==", value=0)
    assert rule.matches("A", RowStats(fourth_plus=5, total=5)) is True


@pytest.mark.parametrize("total, expected", [(9, False), (10, True)])
def test_metric_rule_with_min_total_skips_small_rows(total: int, expected: bool) -> None:
    """min_total がある指標のルールは、行の頭数が min_total に満たない場合は当てはまらない。"""
    stats = RowStats(first=total, total=total)
    rule = MetricRule(color="yellow", metric="複勝率", op=">=", value=30, min_total=10)
    assert rule.matches("A", stats) is expected


def test_labels_rule_matches_by_label_regardless_of_stats() -> None:
    """行の名前のルールは、頭数が0の行でも名前が含まれれば当てはまる。"""
    rule = LabelsRule(color="yellow", labels=("逃げ", "先行"))
    assert rule.matches("先行", RowStats()) is True
    assert rule.matches("差し", RowStats(first=1, total=1)) is False


# --- 実際の table.yml ---


@pytest.mark.parametrize("race_name", list(_RACES))
def test_parse_table_config_accepts_race_table_yml(race_name: str) -> None:
    """各レースの table.yml は、そのレースの trends.yml の項目だけで構成されている。"""
    with open(os.path.join(_CONFIGS_DIR, race_name, "trends.yml"), encoding="utf-8") as f:
        trends = yaml.safe_load(f)
    with open(os.path.join(_CONFIGS_DIR, race_name, "table.yml"), encoding="utf-8") as f:
        table = yaml.safe_load(f)
    catalog = load_trend_catalog(os.path.join(_CONFIGS_DIR, "trends"))
    categories = build_trend_categories(trends, catalog, race_name, _RACES[race_name])
    columns = parse_table_config(table, categories)
    assert list(columns) == list(table)
