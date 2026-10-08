"""過去の傾向記事のカテゴリセクションを生成するモジュール。"""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from ._trend_catalog import build_trend_categories, load_trend_catalog
from ._trend_loader import build_race_context
from ._trend_renderer import build_category_section, format_scope_note


@dataclass(frozen=True)
class TrendSections:
    """傾向記事のタイトル直後の注記と、カテゴリごとのセクション。

    Attributes:
        scope_note (str): 集計対象の注記。
        sections (dict[str, str]): カテゴリ名 -> Markdownセクション文字列。
    """

    scope_note: str
    sections: dict[str, str]


def build_trend_sections(
    race_info: pd.DataFrame,
    race_label: str,
    trends_config: dict[str, Any],
    trends_dir: str,
) -> TrendSections:
    """傾向セクション群を生成する。

    Args:
        race_info (pd.DataFrame): レース基本情報DataFrame（raw英語カラム名）。
        race_label (str): 記事に出力するレース名。
        trends_config (dict[str, Any]): レースの trends.yml の内容。
        trends_dir (str): 項目の共有定義のディレクトリ（`configs/trends`）。

    Returns:
        TrendSections: 集計対象の注記と、カテゴリ名 -> Markdownセクション文字列。
    """
    catalog = load_trend_catalog(trends_dir)
    context = build_race_context(race_info)
    categories = build_trend_categories(trends_config, catalog, context.race_name, context.kyori)
    return TrendSections(
        scope_note=format_scope_note(context, race_label),
        sections={
            category.name: build_category_section(category, context) for category in categories
        },
    )
