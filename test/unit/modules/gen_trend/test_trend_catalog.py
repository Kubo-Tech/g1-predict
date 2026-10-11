"""_trend_catalog の単体テスト。"""

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import yaml
from mykeibadb.analytics import ChakudoResult, RaceCondition

from g1_predict.modules.gen_trend._trend_catalog import (
    build_trend_categories,
    load_trend_catalog,
)
from g1_predict.modules.gen_trend._trend_models import TrendCondition
from g1_predict.modules.gen_trend._trend_stats import compute_stats

_CONFIGS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "configs")
)
_TRENDS_DIR = os.path.join(_CONFIGS_DIR, "trends")
_RACE_NAMES = ["東京優駿", "安田記念", "宝塚記念", "スプリンターズS"]
_ROW_KEYS = frozenset(
    {"type", "items", "top_n", "always_include_grades", "hide_empty", "exclude_no_top3"}
)


def _write_category(trends_dir: Path, file_name: str, content: str) -> None:
    """共有定義のカテゴリファイルを書き出す。"""
    (trends_dir / file_name).write_text(content, encoding="utf-8")


_CATEGORY_YAML = """
name: 基本項目
description: 同じG1レースの過去{years}年における傾向
items:
  人気:
    hide_entry_column: true
    source: {type: popularity}
    rows: {type: fixed, items: [{label: "1人気", op: "==", value: 1}]}
  枠順:
    conditionable: true
    note: ※注記
    hide_if_empty: true
    source: {type: gate_number}
    rows: {type: fixed, items: [{label: "1枠", op: "==", value: 1}]}
  脚質:
    uses_race_result: true
    source: {type: running_style}
    rows: {type: fixed, items: [{label: "逃げ", op: "==", value: "1"}]}
  父実績:
    rows:
      type: boolean_multi
      items:
        - label: "父{race_name}勝ち"
          source: {type: sire_race_condition_finisher, race_name: "{race_name}", kyori: "{kyori}"}
"""


@pytest.fixture
def trends_dir(tmp_path: Path) -> Path:
    """共有定義を1カテゴリだけ持つディレクトリ。"""
    _write_category(tmp_path, "基本項目.yml", _CATEGORY_YAML)
    return tmp_path


def _load_race_config(race_name: str) -> dict[str, Any]:
    """レースの trends.yml を読み込む。"""
    with open(os.path.join(_CONFIGS_DIR, race_name, "trends.yml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


# --- load_trend_catalog ---


# 正常系
def test_load_trend_catalog_reads_category(trends_dir: Path) -> None:
    """カテゴリ名・説明文・項目を読み込む。"""
    catalog = load_trend_catalog(str(trends_dir))
    category = catalog["基本項目"]
    assert category.description == "同じG1レースの過去{years}年における傾向"
    assert list(category.items) == ["人気", "枠順", "脚質", "父実績"]
    assert category.items["人気"].conditionable is False
    assert category.items["枠順"].conditionable is True
    assert category.items["人気"].uses_race_result is False
    assert category.items["脚質"].uses_race_result is True


def test_load_trend_catalog_ignores_non_yml_files(trends_dir: Path) -> None:
    """yml 以外のファイルは読み込まない。"""
    (trends_dir / "メモ.txt").write_text("not yaml: [", encoding="utf-8")
    assert list(load_trend_catalog(str(trends_dir))) == ["基本項目"]


# 準正常系
def test_load_trend_catalog_duplicate_category_raises(trends_dir: Path) -> None:
    """カテゴリ名が重複している場合は ValueError になる。"""
    _write_category(trends_dir, "別名.yml", _CATEGORY_YAML)
    with pytest.raises(ValueError, match="重複"):
        load_trend_catalog(str(trends_dir))


@pytest.mark.parametrize(
    "content, message",
    [
        ("name: x\nitems: {}\n", "キー"),
        ("name: x\ndescription: y\nitems: {}\n", "items"),
        ("name: x\ndescription: y\nitems: {a: {source: {}}}\n", "rows"),
        ("name: x\ndescription: y\nitems: {a: {rows: {}, condition: {}}}\n", "未対応のキー"),
        ("name: x\ndescription: y\nitems: {a: 1}\n", "マッピング"),
    ],
)
def test_load_trend_catalog_invalid_definition_raises(
    tmp_path: Path, content: str, message: str
) -> None:
    """共有定義の書式が不正な場合は ValueError になる。"""
    _write_category(tmp_path, "不正.yml", content)
    with pytest.raises(ValueError, match=message):
        load_trend_catalog(str(tmp_path))


# --- build_trend_categories ---


# 正常系
def test_build_trend_categories_keeps_race_config_order(trends_dir: Path) -> None:
    """項目は trends.yml の並び順で展開される。"""
    catalog = load_trend_catalog(str(trends_dir))
    categories = build_trend_categories({"基本項目": ["枠順", "人気"]}, catalog, "宝塚記念", 2200)
    assert [category.name for category in categories] == ["基本項目"]
    assert [item.name for item in categories[0].items] == ["枠順", "人気"]
    assert categories[0].description == "同じG1レースの過去{years}年における傾向"


def test_build_trend_categories_injects_condition(trends_dir: Path) -> None:
    """条件を注入した項目は TrendCondition を持つ。"""
    catalog = load_trend_catalog(str(trends_dir))
    race_config = {
        "基本項目": [
            "人気",
            {"枠順": {"condition": {"keibajo_codes": ["09"], "kaisai_nichime": [4]}}},
        ]
    }
    items = build_trend_categories(race_config, catalog, "宝塚記念", 2200)[0].items
    assert items[0].condition is None
    assert items[1].condition == TrendCondition(keibajo_codes=("09",), kaisai_nichime=(4,))


def test_build_trend_categories_embeds_race_name_and_kyori(trends_dir: Path) -> None:
    """共有定義の {race_name}・{kyori} は対象レースの値になる。"""
    catalog = load_trend_catalog(str(trends_dir))
    item = build_trend_categories({"基本項目": ["父実績"]}, catalog, "東京優駿", 2400)[0].items[0]
    row = item.config["rows"]["items"][0]
    assert row["label"] == "父東京優駿勝ち"
    assert row["source"]["race_name"] == "東京優駿"
    assert row["source"]["kyori"] == "2400"


def test_build_trend_categories_does_not_modify_catalog(trends_dir: Path) -> None:
    """展開しても共有定義のプレースホルダは書き換わらない。"""
    catalog = load_trend_catalog(str(trends_dir))
    build_trend_categories({"基本項目": ["父実績"]}, catalog, "東京優駿", 2400)
    label = catalog["基本項目"].items["父実績"].config["rows"]["items"][0]["label"]
    assert label == "父{race_name}勝ち"


def test_build_trend_categories_item_config_excludes_conditionable(trends_dir: Path) -> None:
    """項目の定義には conditionable・uses_race_result を含めず、note と hide_if_empty を含める。"""
    catalog = load_trend_catalog(str(trends_dir))
    item = build_trend_categories({"基本項目": ["枠順"]}, catalog, "宝塚記念", 2200)[0].items[0]
    assert "conditionable" not in item.config
    assert "uses_race_result" not in item.config
    assert item.config["note"] == "※注記"
    assert item.config["hide_if_empty"] is True


# 準正常系
@pytest.mark.parametrize(
    "race_config, message",
    [
        ({"存在しないカテゴリ": ["人気"]}, "存在しないカテゴリ"),
        ({"基本項目": ["存在しない項目"]}, "存在しない項目"),
        ({"基本項目": []}, "空でないリスト"),
        ({"基本項目": "人気"}, "空でないリスト"),
        ({"基本項目": [{"人気": {"condition": {"kaisai_nichime": [4]}}}]}, "conditionable"),
        ({"基本項目": [{"枠順": {"condition": {"years": 10}}}]}, "未対応のキー"),
        ({"基本項目": [{"枠順": {"years": 10}}]}, "condition"),
        ({"基本項目": [{"枠順": {"condition": {}}, "人気": {}}]}, "項目は"),
        ({"基本項目": [1]}, "項目は"),
    ],
)
def test_build_trend_categories_invalid_race_config_raises(
    trends_dir: Path, race_config: dict[str, Any], message: str
) -> None:
    """共有定義に無い名前や不正な書式は ValueError になる。"""
    catalog = load_trend_catalog(str(trends_dir))
    with pytest.raises(ValueError, match=message):
        build_trend_categories(race_config, catalog, "宝塚記念", 2200)


def test_build_trend_categories_carries_uses_race_result(trends_dir: Path) -> None:
    """今走の結果で決まる項目は TrendItem にその旨が引き継がれる。"""
    catalog = load_trend_catalog(str(trends_dir))
    items = build_trend_categories({"基本項目": ["人気", "脚質"]}, catalog, "宝塚記念", 2200)[
        0
    ].items
    assert [item.uses_race_result for item in items] == [False, True]


def test_build_trend_categories_carries_hide_entry_column(trends_dir: Path) -> None:
    """hide_entry_column は TrendItem に引き継がれ、該当馬列を付けない扱いになる。"""
    catalog = load_trend_catalog(str(trends_dir))
    items = build_trend_categories(
        {"基本項目": ["人気", "脚質", "枠順"]}, catalog, "宝塚記念", 2200
    )[0].items
    assert [item.hide_entry_column for item in items] == [True, False, False]
    assert [item.shows_entry_column for item in items] == [False, False, True]


# --- configs/trends と各レースの trends.yml ---


def test_shared_catalog_rows_use_known_keys() -> None:
    """共有定義の rows は既知のキーだけを使う。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    for category in catalog.values():
        for item in category.items.values():
            assert set(item.config["rows"]) <= _ROW_KEYS


@pytest.mark.parametrize("race_name", _RACE_NAMES)
def test_race_trends_yml_expands_with_shared_catalog(race_name: str) -> None:
    """4レースの trends.yml が共有定義に対して欠損なく展開できる。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    categories = build_trend_categories(_load_race_config(race_name), catalog, race_name, 2000)
    assert [category.name for category in categories] == list(_load_race_config(race_name))


@pytest.mark.parametrize("race_name", _RACE_NAMES)
def test_race_trends_yml_items_have_supported_source_types(race_name: str) -> None:
    """4レースの全項目が、compute_stats の対応する source.type だけを使う。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    categories = build_trend_categories(_load_race_config(race_name), catalog, race_name, 2000)
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame(
        {"race_code": ["2025092806040911"], "sire_name": ["ディープインパクト"]}
    )
    condition = RaceCondition(keibajo_codes=["06"], tokubetsu_kyoso_bango="0016", year_to="2025")
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=ChakudoResult(success=True, rows=[]),
    ):
        for category in categories:
            for item in category.items:
                compute_stats(item.config, manager, condition, [])
