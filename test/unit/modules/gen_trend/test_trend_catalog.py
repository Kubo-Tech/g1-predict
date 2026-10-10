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
    TrendCategory,
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


def _item_names(categories: list[TrendCategory], category_name: str) -> list[str]:
    """カテゴリの項目名を並び順で返す。"""
    category = next(c for c in categories if c.name == category_name)
    return [item.name for item in category.items]


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


# --- configs/trends と各レースの trends.yml ---


def test_shared_catalog_has_seven_categories() -> None:
    """共有定義はカテゴリごとに7ファイルあり、説明文を持つ。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    assert list(catalog) == [
        "世代戦",
        "前走",
        "同年/前年レース実績",
        "基本項目",
        "実績",
        "調教",
        "馬以外の属性",
    ]
    assert catalog["基本項目"].description == "同じG1レースの過去{years}年における傾向"
    assert catalog["前走"].description == "出走馬の前走に関する傾向"
    assert catalog["実績"].description == "出走馬の過去の実績に関する傾向"
    assert catalog["世代戦"].description == "世代戦で有効となる傾向"
    assert catalog["調教"].description == "調教の内容"
    assert catalog["同年/前年レース実績"].description == "同年/前年の指定したレースでの実績"
    other_description = catalog["馬以外の属性"].description
    assert other_description == "過去{years}年の出走馬の騎手・生産者・血統に関する傾向"


def test_shared_catalog_conditionable_items() -> None:
    """開催条件を注入できる項目は7つ。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    conditionable = [
        name
        for category in catalog.values()
        for name, item in category.items.items()
        if item.conditionable
    ]
    assert conditionable == [
        "枠順",
        "脚質",
        "前走脚質",
        "4角通過順位",
        "前走4角通過順位",
        "上がり3F順位",
        "前走上がり3F順位",
    ]


def test_build_trend_categories_carries_uses_race_result(trends_dir: Path) -> None:
    """今走の結果で決まる項目は TrendItem にその旨が引き継がれる。"""
    catalog = load_trend_catalog(str(trends_dir))
    items = build_trend_categories({"基本項目": ["人気", "脚質"]}, catalog, "宝塚記念", 2200)[
        0
    ].items
    assert [item.uses_race_result for item in items] == [False, True]


def test_shared_catalog_uses_race_result_items() -> None:
    """今走の結果で決まる項目は脚質・4角通過順位・上がり3F順位。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    names = [
        name
        for category in catalog.values()
        for name, item in category.items.items()
        if item.uses_race_result
    ]
    assert names == ["脚質", "4角通過順位", "上がり3F順位"]


def test_shared_catalog_hide_entry_column_items() -> None:
    """記事の表に該当馬列を付けない項目は人気・枠順。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    names = [
        name
        for category in catalog.values()
        for name, item in category.items.items()
        if item.hide_entry_column
    ]
    assert names == ["人気", "枠順"]


def test_build_trend_categories_carries_hide_entry_column() -> None:
    """hide_entry_column は TrendItem に引き継がれ、該当馬列を付けない扱いになる。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    items = build_trend_categories(
        {"基本項目": ["人気", "脚質", "所属"]}, catalog, "宝塚記念", 2200
    )[0].items
    assert [item.hide_entry_column for item in items] == [True, False, False]
    assert [item.shows_entry_column for item in items] == [False, False, True]


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


def test_tokyo_yuushun_trends_yml_categories_and_items() -> None:
    """東京優駿は世代戦と、継続騎乗・父実績を含む馬以外の属性を持つ。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    categories = build_trend_categories(_load_race_config("東京優駿"), catalog, "東京優駿", 2400)
    assert [category.name for category in categories] == [
        "基本項目",
        "前走",
        "実績",
        "世代戦",
        "馬以外の属性",
    ]
    assert _item_names(categories, "世代戦") == [
        "デビュー競馬場",
        "デビュー月",
        "キャリア",
        "誕生月",
    ]
    assert _item_names(categories, "馬以外の属性") == [
        "騎手",
        "生産者",
        "種牡馬",
        "継続騎乗",
        "父実績",
    ]
    assert _item_names(categories, "実績") == [
        "勝利数",
        "重賞勝利数",
        "東京勝利数",
        "東京重賞好走実績",
        "良馬場好走実績",
        "稍重以上好走実績",
    ]
    sire_item = categories[-1].items[-1]
    labels = [row["label"] for row in sire_item.config["rows"]["items"]]
    assert labels == ["父東京優駿勝ち", "父2400mG1勝ち"]


def test_sprinters_trends_yml_has_training_and_same_year_categories() -> None:
    """スプリンターズSは調教と同年/前年レース実績を持つ。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    categories = build_trend_categories(
        _load_race_config("スプリンターズS"), catalog, "スプリンターズステークス", 1200
    )
    assert _item_names(categories, "調教") == ["当週/1週前坂路ラスト2F24.0秒未満"]
    assert _item_names(categories, "同年/前年レース実績") == ["同年高松宮記念着順"]
    assert _item_names(categories, "実績") == [
        "勝利数",
        "重賞勝利数",
        "中山勝利数",
        "中山重賞好走実績",
        "リピーター",
    ]


def test_sprinters_trends_yml_drops_transport_and_previous_finish() -> None:
    """スプリンターズSは、基本項目の輸送と前走の前走着順を使わない。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    categories = build_trend_categories(
        _load_race_config("スプリンターズS"), catalog, "スプリンターズステークス", 1200
    )
    assert _item_names(categories, "基本項目") == [
        name for name in catalog["基本項目"].items if name != "輸送"
    ]
    assert _item_names(categories, "前走") == [
        name
        for name in catalog["前走"].items
        if name not in [*_LOWER_CLASS_FINISH_ITEMS, "前走着順"]
    ]


def test_takarazuka_trends_yml_injects_condition_into_conditionable_items_only() -> None:
    """宝塚記念は★の項目にだけ阪神4日目良馬場の条件を注入する。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    categories = build_trend_categories(_load_race_config("宝塚記念"), catalog, "宝塚記念", 2200)
    expected = TrendCondition(
        keibajo_codes=("09",), kaisai_nichime=(4,), babajotai_codes=("1",)
    )
    with_condition = [
        item.name for category in categories for item in category.items if item.condition
    ]
    assert with_condition == [
        "枠順",
        "脚質",
        "前走脚質",
        "4角通過順位",
        "前走4角通過順位",
        "上がり3F順位",
        "前走上がり3F順位",
    ]
    for category in categories:
        for item in category.items:
            if item.condition:
                assert item.condition == expected


_LOWER_CLASSES = ("リステッド", "オープン", "3勝クラス", "2勝クラス", "1勝クラス", "未勝利", "新馬")
_LOWER_CLASS_FINISH_ITEMS = [f"前走{race_class}着順" for race_class in _LOWER_CLASSES]


@pytest.mark.parametrize("race_name", ["安田記念", "宝塚記念"])
def test_trends_yml_older_g1_has_all_basic_items(race_name: str) -> None:
    """古馬G1は基本項目の全項目を持つ。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    categories = build_trend_categories(_load_race_config(race_name), catalog, race_name, 2000)
    assert _item_names(categories, "基本項目") == list(catalog["基本項目"].items)


def test_trends_yml_derby_has_basic_items_except_age() -> None:
    """東京優駿は全馬3歳なので、基本項目のうち馬齢を除く全項目を持つ。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    categories = build_trend_categories(_load_race_config("東京優駿"), catalog, "東京優駿", 2400)
    expected = [name for name in catalog["基本項目"].items if name != "馬齢"]
    assert _item_names(categories, "基本項目") == expected


@pytest.mark.parametrize("race_name", ["安田記念", "宝塚記念"])
def test_trends_yml_older_g1_uses_non_graded_finish(race_name: str) -> None:
    """古馬G1は、重賞以外の前走をクラス別に分けず前走非重賞着順だけで見る。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    categories = build_trend_categories(_load_race_config(race_name), catalog, race_name, 2000)
    expected = [
        name for name in catalog["前走"].items if name not in _LOWER_CLASS_FINISH_ITEMS
    ]
    assert _item_names(categories, "前走") == expected


def test_trends_yml_derby_uses_finish_by_class() -> None:
    """東京優駿は、重賞以外の前走をクラス別の着順で見て、前走非重賞着順は使わない。"""
    catalog = load_trend_catalog(_TRENDS_DIR)
    categories = build_trend_categories(_load_race_config("東京優駿"), catalog, "東京優駿", 2400)
    expected = [name for name in catalog["前走"].items if name != "前走非重賞着順"]
    assert _item_names(categories, "前走") == expected
