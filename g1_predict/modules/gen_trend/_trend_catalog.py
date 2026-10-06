"""共有定義とレースの trends.yml を読み、項目ごとの定義に展開するモジュール。"""

import os
from dataclasses import dataclass
from typing import Any

import yaml

from ._trend_condition import parse_trend_condition
from ._trend_models import TrendCondition

_CATEGORY_KEYS = frozenset({"name", "description", "items"})
_ITEM_KEYS = frozenset({"conditionable", "note", "source", "rows", "display_map"})


@dataclass(frozen=True)
class CatalogItem:
    """共有定義の1項目。

    Attributes:
        config (dict[str, Any]): source・rows・display_map・note の定義。
        conditionable (bool): 開催条件を注入できる項目か。
    """

    config: dict[str, Any]
    conditionable: bool


@dataclass(frozen=True)
class CatalogCategory:
    """共有定義の1カテゴリ。

    Attributes:
        name (str): カテゴリ名。
        description (str): カテゴリの説明文。`{years}` は集計した年数に置き換える。
        items (dict[str, CatalogItem]): 項目名 -> 項目の定義。
    """

    name: str
    description: str
    items: dict[str, CatalogItem]


@dataclass(frozen=True)
class TrendItem:
    """記事に出力する1項目。

    Attributes:
        name (str): 項目名。
        config (dict[str, Any]): 対象レースの値を埋め込み済みの source・rows・display_map・note。
        condition (TrendCondition | None): 注入された開催条件。
    """

    name: str
    config: dict[str, Any]
    condition: TrendCondition | None


@dataclass(frozen=True)
class TrendCategory:
    """記事に出力する1カテゴリ。

    Attributes:
        name (str): カテゴリ名。
        description (str): カテゴリの説明文。`{years}` は集計した年数に置き換える。
        items (list[TrendItem]): レースの trends.yml に書かれた順の項目。
    """

    name: str
    description: str
    items: list[TrendItem]


def load_trend_catalog(trends_dir: str) -> dict[str, CatalogCategory]:
    """共有定義ディレクトリのカテゴリごとの yml を読み込む。

    Args:
        trends_dir (str): 共有定義のディレクトリ（`configs/trends`）。

    Returns:
        dict[str, CatalogCategory]: カテゴリ名 -> カテゴリの定義。

    Raises:
        ValueError: 定義のキーや型が不正な場合、またはカテゴリ名が重複している場合。
    """
    catalog: dict[str, CatalogCategory] = {}
    for file_name in sorted(os.listdir(trends_dir)):
        if not file_name.endswith(".yml"):
            continue
        path = os.path.join(trends_dir, file_name)
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        category = _parse_category(raw, file_name)
        if category.name in catalog:
            raise ValueError(f"カテゴリ名が重複しています: {category.name}")
        catalog[category.name] = category
    return catalog


def build_trend_categories(
    race_config: dict[str, Any],
    catalog: dict[str, CatalogCategory],
    race_name: str,
    kyori: int,
) -> list[TrendCategory]:
    """レースの trends.yml を項目ごとの定義に展開する。

    共有定義の `{race_name}`・`{kyori}` は対象レースの競走名本題・距離に置き換える。
    カテゴリと項目は trends.yml の並び順で返す。

    Args:
        race_config (dict[str, Any]): レースの trends.yml の内容。
        catalog (dict[str, CatalogCategory]): 共有定義。
        race_name (str): 対象レースの競走名本題。
        kyori (int): 対象レースの距離（m）。

    Returns:
        list[TrendCategory]: 記事に出力するカテゴリ。

    Raises:
        ValueError: 共有定義に無いカテゴリ名・項目名がある場合、
            conditionable でない項目に条件を注入した場合、
            または trends.yml の書式が不正な場合。
    """
    placeholders = {"{race_name}": race_name, "{kyori}": str(kyori)}
    categories: list[TrendCategory] = []
    for category_name, entries in race_config.items():
        if category_name not in catalog:
            raise ValueError(f"共有定義に無いカテゴリです: {category_name}")
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"{category_name}: 項目は空でないリストで指定してください。")
        catalog_category = catalog[category_name]
        items = [_build_item(entry, catalog_category, placeholders) for entry in entries]
        categories.append(
            TrendCategory(
                name=category_name, description=catalog_category.description, items=items
            )
        )
    return categories


def _parse_category(raw: Any, file_name: str) -> CatalogCategory:
    """共有定義の yml 1ファイル分を CatalogCategory に変換する。

    Args:
        raw (Any): yml を読み込んだ内容。
        file_name (str): ファイル名（エラーメッセージ用）。

    Returns:
        CatalogCategory: 変換したカテゴリ。

    Raises:
        ValueError: キーや型が不正な場合。
    """
    if not isinstance(raw, dict) or set(raw) != _CATEGORY_KEYS:
        raise ValueError(f"{file_name}: キーは {sorted(_CATEGORY_KEYS)} で指定してください。")
    raw_items = raw["items"]
    if not isinstance(raw_items, dict) or not raw_items:
        raise ValueError(f"{file_name}: items は空でないマッピングで指定してください。")
    items: dict[str, CatalogItem] = {}
    for item_name, raw_item in raw_items.items():
        if not isinstance(raw_item, dict):
            raise ValueError(f"{file_name}: {item_name} の定義がマッピングではありません。")
        unknown_keys = set(raw_item) - _ITEM_KEYS
        if unknown_keys:
            raise ValueError(
                f"{file_name}: {item_name} に未対応のキーがあります: {sorted(unknown_keys)}"
            )
        if "rows" not in raw_item:
            raise ValueError(f"{file_name}: {item_name} に rows がありません。")
        config = {key: value for key, value in raw_item.items() if key != "conditionable"}
        items[item_name] = CatalogItem(
            config=config, conditionable=bool(raw_item.get("conditionable", False))
        )
    return CatalogCategory(name=raw["name"], description=raw["description"], items=items)


def _build_item(
    entry: Any,
    catalog_category: CatalogCategory,
    placeholders: dict[str, str],
) -> TrendItem:
    """trends.yml の項目1件を TrendItem に展開する。

    Args:
        entry (Any): 項目名（文字列）、または `{項目名: {condition: {...}}}`。
        catalog_category (CatalogCategory): 項目が属するカテゴリの共有定義。
        placeholders (dict[str, str]): 共有定義の文字列に埋め込む対象レースの値。

    Returns:
        TrendItem: 展開した項目。

    Raises:
        ValueError: 項目名が共有定義に無い場合、conditionable でない項目に条件を
            注入した場合、または書式が不正な場合。
    """
    raw_conditions: list[Any] = []
    if isinstance(entry, str):
        item_name = entry
    elif isinstance(entry, dict) and len(entry) == 1:
        item_name, injection = next(iter(entry.items()))
        if not isinstance(injection, dict) or set(injection) != {"condition"}:
            raise ValueError(f"{item_name}: 指定できるのは condition だけです: {injection!r}")
        raw_conditions.append(injection["condition"])
    else:
        raise ValueError(
            f"項目は項目名か {{項目名: {{condition: ...}}}} で指定してください: {entry!r}"
        )

    if item_name not in catalog_category.items:
        raise ValueError(f"{catalog_category.name} に無い項目です: {item_name}")
    catalog_item = catalog_category.items[item_name]
    condition: TrendCondition | None = None
    if raw_conditions:
        if not catalog_item.conditionable:
            raise ValueError(f"{item_name}: conditionable でない項目には条件を注入できません。")
        condition = parse_trend_condition(raw_conditions[0], item_name)
    return TrendItem(
        name=item_name,
        config=_embed_placeholders(catalog_item.config, placeholders),
        condition=condition,
    )


def _embed_placeholders(value: Any, placeholders: dict[str, str]) -> Any:
    """定義内のすべての文字列について、プレースホルダを対象レースの値に置き換える。

    Args:
        value (Any): 定義（dict・list・文字列・その他）。
        placeholders (dict[str, str]): プレースホルダ -> 置き換える値。

    Returns:
        Any: 置き換え後のコピー。
    """
    if isinstance(value, str):
        for placeholder, replacement in placeholders.items():
            value = value.replace(placeholder, replacement)
        return value
    if isinstance(value, dict):
        return {key: _embed_placeholders(val, placeholders) for key, val in value.items()}
    if isinstance(value, list):
        return [_embed_placeholders(val, placeholders) for val in value]
    return value
