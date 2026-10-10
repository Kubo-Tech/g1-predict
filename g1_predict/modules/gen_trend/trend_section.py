"""過去の傾向記事のカテゴリセクションを生成するモジュール。"""

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from matplotlib.figure import Figure
from mykeibadb.config import ConfigManager
from mykeibadb.connection import ConnectionManager

from ._trend_catalog import build_trend_categories, load_trend_catalog
from ._trend_entries import fetch_entry_horses
from ._trend_loader import build_race_context
from ._trend_renderer import (
    build_category_section,
    build_item_table,
    format_scope_note,
    has_entry_horses,
)
from ._trend_table_config import TableColumn, parse_table_config
from ._trend_table_image import make_comparison_table

# 比較表の画像の、記事ディレクトリからの相対ディレクトリ
_TABLE_IMAGE_DIR = "img/trend_table"


def check_race_entries(race_code: str) -> None:
    """今回のレースの出走馬が DB にあることを確認する。

    Args:
        race_code (str): 今回のレースの16桁のレースコード。

    Raises:
        MykeibaDBError: 出走馬が DB に無い場合。
    """
    fetch_entry_horses(ConnectionManager(ConfigManager.from_env()), race_code)


@dataclass(frozen=True)
class EntrySettings:
    """出走馬の確定後に載せる情報の設定。

    Attributes:
        race_code (str): 今回のレースの16桁のレースコード。
        table_config (dict[str, Any]): 比較表の定義（table.yml）の内容。
    """

    race_code: str
    table_config: dict[str, Any]


@dataclass(frozen=True)
class TrendSections:
    """傾向記事のタイトル直後の注記と、カテゴリごとのセクション。

    Attributes:
        scope_note (str): 集計対象の注記。
        sections (dict[str, str]): カテゴリ名 -> Markdownセクション文字列。
        images (dict[str, Figure]): 記事ディレクトリからの相対パス -> 比較表のFigure。
    """

    scope_note: str
    sections: dict[str, str]
    images: dict[str, Figure] = field(default_factory=dict)


def build_trend_sections(
    race_info: pd.DataFrame,
    race_label: str,
    trends_config: dict[str, Any],
    trends_dir: str,
    entries: EntrySettings | None = None,
) -> TrendSections:
    """傾向セクション群を生成する。

    entries を指定した場合は、各表に今回の出走馬が当たる行を「該当馬」列として書き、
    table.yml に項目があるカテゴリには出走馬の比較表の画像を載せる。今回の出走馬が1頭も当たらない
    表は、記事にも比較表にも載せない。

    Args:
        race_info (pd.DataFrame): レース基本情報DataFrame（raw英語カラム名）。
        race_label (str): 記事に出力するレース名。
        trends_config (dict[str, Any]): レースの trends.yml の内容。
        trends_dir (str): 項目の共有定義のディレクトリ（`configs/trends`）。
        entries (EntrySettings | None): 出走馬の確定後に載せる情報の設定。
            None の場合は、該当馬列も比較表も載せない。

    Returns:
        TrendSections: 集計対象の注記と、カテゴリ名 -> Markdownセクション文字列、比較表の画像。
    """
    catalog = load_trend_catalog(trends_dir)
    context = build_race_context(race_info)
    categories = build_trend_categories(trends_config, catalog, context.race_name, context.kyori)

    entry_race_code: str | None = None
    horses = pd.DataFrame()
    table_columns: dict[str, list[TableColumn]] = {}
    if entries is not None:
        entry_race_code = entries.race_code
        table_columns = parse_table_config(entries.table_config, categories)
        horses = fetch_entry_horses(context.manager, entries.race_code)

    sections: dict[str, str] = {}
    images: dict[str, Figure] = {}
    for category in categories:
        tables = [
            table
            for item in category.items
            if (table := build_item_table(item, context, entry_race_code)) is not None
            and (entries is None or has_entry_horses(table))
        ]
        image_path: str | None = None
        if category.name in table_columns:
            figure = make_comparison_table(horses, tables, table_columns[category.name])
            if figure is not None:
                image_path = f"{_TABLE_IMAGE_DIR}/{category.name.replace('/', '')}.png"
                images[image_path] = figure
        sections[category.name] = build_category_section(
            category, context, tables, entries is not None, image_path
        )
    return TrendSections(
        scope_note=format_scope_note(context, race_label),
        sections=sections,
        images=images,
    )
