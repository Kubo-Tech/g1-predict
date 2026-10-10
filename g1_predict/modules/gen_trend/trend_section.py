"""過去の傾向記事のカテゴリセクションを生成するモジュール。"""

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from matplotlib.figure import Figure
from mykeibadb.config import ConfigManager
from mykeibadb.connection import ConnectionManager

from ._trend_catalog import build_trend_categories, load_trend_catalog
from ._trend_entries import fetch_entry_horses
from ._trend_loader import build_race_context, fetch_race_info_from_history
from ._trend_renderer import (
    COMPARISON_HEADING,
    ItemTable,
    build_category_section,
    build_comparison_section,
    build_item_table,
    format_scope_note,
    is_entry_table_informative,
)
from ._trend_table_config import TableColumn, parse_table_config
from ._trend_table_image import make_comparison_table

# 比較表の画像の、記事ディレクトリからの相対パス
_TABLE_IMAGE_PATH = "img/trend_table/比較表.png"


def check_race_entries(race_code: str) -> None:
    """今回のレースの出走馬が DB にあることを確認する。

    Args:
        race_code (str): 今回のレースの16桁のレースコード。

    Raises:
        MykeibaDBError: 出走馬が DB に無い場合。
    """
    fetch_entry_horses(ConnectionManager(ConfigManager.from_env()), race_code)


def build_race_info_from_history(race_code: str, tokubetsu_kyoso_bango: str) -> pd.DataFrame:
    """今回のレースが DB に入る前に、同じ特別競走番号の直近の開催からレース基本情報を組み立てる。

    競走名本題・距離・トラックは直近の開催の値、開催年・開催月日・競馬場は race_code の値を使う。

    Args:
        race_code (str): 今回のレースの16桁のレースコード。
        tokubetsu_kyoso_bango (str): 今回のレースの特別競走番号（4桁）。

    Returns:
        pd.DataFrame: build_trend_sections に渡せる1行のレース基本情報。

    Raises:
        ValueError: 特別競走番号が4桁の数字でない場合。今回の開催年より前に同じ特別競走番号の
            レースが無い場合。
    """
    manager = ConnectionManager(ConfigManager.from_env())
    return fetch_race_info_from_history(manager, race_code, tokubetsu_kyoso_bango)


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
        sections (dict[str, str]): 見出し -> Markdownセクション文字列。見出しはカテゴリ名と、
            出走馬の確定後の「比較表」。
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
    最後に table.yml の項目を並べた出走馬の比較表の画像を載せるセクションを足す。
    今回の出走馬が1頭も当たらない表と、全頭が同じ1つの行だけに当たる表は、記事にも比較表にも
    載せない。

    Args:
        race_info (pd.DataFrame): レース基本情報DataFrame（raw英語カラム名）。
        race_label (str): 記事に出力するレース名。
        trends_config (dict[str, Any]): レースの trends.yml の内容。
        trends_dir (str): 項目の共有定義のディレクトリ（`configs/trends`）。
        entries (EntrySettings | None): 出走馬の確定後に載せる情報の設定。
            None の場合は、該当馬列も比較表も載せない。

    Returns:
        TrendSections: 集計対象の注記と、見出し -> Markdownセクション文字列、比較表の画像。
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
    category_tables: dict[str, dict[str, ItemTable]] = {}
    for category in categories:
        tables = [
            table
            for item in category.items
            if (table := build_item_table(item, context, entry_race_code)) is not None
            and (entries is None or is_entry_table_informative(table, len(horses)))
        ]
        category_tables[category.name] = {table.item.name: table for table in tables}
        sections[category.name] = build_category_section(
            category, context, tables, entries is not None, horse_count=len(horses)
        )

    images: dict[str, Figure] = {}
    shown: list[tuple[TableColumn, list[ItemTable]]] = []
    for category_name, columns in table_columns.items():
        for column in columns:
            tables = [
                category_tables[category_name][name]
                for name in column.source_names
                if name in category_tables[category_name]
            ]
            if tables:
                shown.append((column, tables))
    if shown:
        images[_TABLE_IMAGE_PATH] = make_comparison_table(horses, shown)
        sections[COMPARISON_HEADING] = build_comparison_section(_TABLE_IMAGE_PATH)
    return TrendSections(
        scope_note=format_scope_note(context, race_label),
        sections=sections,
        images=images,
    )
