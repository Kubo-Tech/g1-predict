"""出走馬・騎手・生産者・血統傾向セクションを生成するモジュール。"""

from typing import Any

import pandas as pd

from ._trend_loader import build_race_context
from ._trend_renderer import build_category_section


def build_trend_sections(
    race_code: str,
    race_info: pd.DataFrame,
    trends_config: dict[str, list[dict[str, Any]]],
) -> dict[str, str]:
    """傾向セクション群を生成する。

    Args:
        race_code (str): 16桁レースコード。
        race_info (pd.DataFrame): レース基本情報DataFrame（raw英語カラム名）。
        trends_config (dict[str, list[dict[str, Any]]]): YAMLのtrends設定。

    Returns:
        dict[str, str]: カテゴリ名 -> Markdownセクション文字列。
    """
    manager, condition = build_race_context(race_code, race_info)
    return {
        category_name: build_category_section(
            category_name, metrics, manager, condition, race_code
        )
        for category_name, metrics in trends_config.items()
    }
