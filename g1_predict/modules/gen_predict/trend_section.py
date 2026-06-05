"""出走馬・騎手・生産者・血統傾向セクションを生成するモジュール。"""

from typing import Any

import pandas as pd
from keiba_data_interface import DataInterface

from ._trend_loader import extract_sire_condition_sources, load_db
from ._trend_renderer import build_category_section


def build_trend_sections(
    race_code: str,
    race_info: pd.DataFrame,
    trends_config: dict[str, list[dict[str, Any]]],
    di: DataInterface,
) -> dict[str, str]:
    """傾向セクション群を生成する。

    Args:
        race_code (str): 16桁レースコード。
        race_info (pd.DataFrame): レース基本情報DataFrame。
        trends_config (dict[str, list[dict[str, Any]]]): YAMLのtrends設定。
        di (DataInterface): DataInterfaceインスタンス。

    Returns:
        dict[str, str]: カテゴリ名 -> Markdownセクション文字列。
    """
    race_year = int(str(race_info["開催年"].iloc[0]))
    sire_sources = extract_sire_condition_sources(trends_config)
    db = load_db(race_code, race_info, race_year, di, sire_sources)

    return {
        category_name: build_category_section(category_name, metrics, db)
        for category_name, metrics in trends_config.items()
    }
