"""傾向分析記事を生成するスクリプト。

コマンド:
cd path/to/g1-predict
python -m scripts.gen_trend --race-code <16桁 race_code> [--with-entries]
python -m scripts.gen_trend --race-code <16桁 race_code> --tokubetsu-kyoso-bango <4桁>
"""

import argparse
import os

import pandas as pd
import yaml
from dotenv import find_dotenv, load_dotenv
from mykeibadb import RaceGetter

from g1_predict.modules.gen_trend.trend_section import (
    EntrySettings,
    TrendSections,
    build_race_info_from_history,
    build_trend_sections,
    check_race_entries,
)
from g1_predict.modules.utils.image_output import save_images
from g1_predict.modules.utils.output_path import build_race_dir, validate_race_code
from g1_predict.modules.utils.race_name import to_race_label

load_dotenv(find_dotenv())

_REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PUBLIC_DIR = os.path.join(_REPO_DIR, "public")
_CONFIGS_DIR = os.path.join(_REPO_DIR, "configs")
_TRENDS_DIR = os.path.join(_CONFIGS_DIR, "trends")


def generate_trend(
    race_code: str,
    with_entries: bool = False,
    tokubetsu_kyoso_bango: str | None = None,
) -> None:
    """指定レースの傾向分析記事を生成する。

    with_entries が True の場合は、出走馬が当たる行を書いた「該当馬」列と、
    出走馬の比較表の画像を載せる。
    tokubetsu_kyoso_bango を指定した場合は、今回のレースを DB から引かず、同じ特別競走番号の
    直近の開催から競走名・距離・トラックを、race_code から開催年・開催月日・競馬場を取る。

    Args:
        race_code (str): 16桁 JRA-VAN 形式の race_code。
        with_entries (bool): 出走馬の確定後の情報を載せるか。
        tokubetsu_kyoso_bango (str | None): 今回のレースが DB に入る前に生成する場合の特別競走番号。

    Raises:
        ValueError: with_entries と tokubetsu_kyoso_bango を両方指定した場合。
            tokubetsu_kyoso_bango を指定せず、今回のレースが DB に無い場合。
    """
    validate_race_code(race_code)
    if tokubetsu_kyoso_bango is not None:
        if with_entries:
            raise ValueError("--with-entries と --tokubetsu-kyoso-bango は同時に指定できません")
        race_shosai = build_race_info_from_history(race_code, tokubetsu_kyoso_bango)
    else:
        race_getter = RaceGetter()
        race_shosai = race_getter.get_race_shosai(race_code=race_code, convert_codes=False)
        if race_shosai.empty:
            raise ValueError(
                f"レースが DB にありません: {race_code}。"
                "DB に入る前は --tokubetsu-kyoso-bango で特別競走番号を指定してください"
            )
    race_name = str(race_shosai["kyosomei_hondai"].iloc[0]).strip()
    race_label = to_race_label(race_name)
    year = str(race_shosai["kaisai_nen"].iloc[0]).strip()

    trend_sections = _build_trend_sections(race_label, race_shosai, race_code, with_entries)
    content = _render_trend_content(race_label, year, trend_sections)

    race_dir = build_race_dir(_PUBLIC_DIR, year, race_code, race_label)
    os.makedirs(race_dir, exist_ok=True)
    output_path = os.path.join(race_dir, "過去の傾向.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    save_images(race_dir, trend_sections.images)
    print(f"Generated: {output_path}")


def main() -> None:
    """エントリポイント。"""
    parser = argparse.ArgumentParser(description="傾向分析記事を生成する")
    parser.add_argument("--race-code", required=True, help="16桁 race_code")
    parser.add_argument(
        "--with-entries",
        action="store_true",
        help="出走馬の確定後に、出走馬が当たる行の列と出走馬の比較表を載せる",
    )
    parser.add_argument(
        "--tokubetsu-kyoso-bango",
        help="今回のレースが DB に入る前に生成する場合の特別競走番号（4桁）",
    )
    args = parser.parse_args()
    generate_trend(args.race_code, args.with_entries, args.tokubetsu_kyoso_bango)


def _build_trend_sections(
    race_label: str,
    race_info: pd.DataFrame,
    race_code: str,
    with_entries: bool,
) -> TrendSections:
    """傾向セクション群を生成する。

    Args:
        race_label (str): configディレクトリ名に使うレース名。
        race_info (pd.DataFrame): レース基本情報DataFrame。
        race_code (str): 16桁 JRA-VAN 形式の race_code。
        with_entries (bool): 出走馬の確定後の情報を載せるか。

    Returns:
        TrendSections: 集計対象の注記と、カテゴリ名 -> Markdownセクション文字列、比較表の画像。
            trends.yml が無い、または空の場合は注記もセクションも空。

    Raises:
        FileNotFoundError: with_entries が True で table.yml が無い場合。
        MykeibaDBError: with_entries が True で出走馬が DB に無い場合。
    """
    # 出走馬の確定後の情報に必要な table.yml と出走馬は、trends.yml の有無によらず先に確かめる
    entries: EntrySettings | None = None
    if with_entries:
        table_path = os.path.join(_CONFIGS_DIR, race_label, "table.yml")
        with open(table_path, encoding="utf-8") as f:
            entries = EntrySettings(race_code=race_code, table_config=yaml.safe_load(f))
        check_race_entries(race_code)
    config_path = os.path.join(_CONFIGS_DIR, race_label, "trends.yml")
    if not os.path.isfile(config_path):
        return TrendSections(scope_note="", sections={})
    with open(config_path, encoding="utf-8") as f:
        trends_config = yaml.safe_load(f)
    if not trends_config:
        return TrendSections(scope_note="", sections={})
    return build_trend_sections(race_info, race_label, trends_config, _TRENDS_DIR, entries)


def _render_trend_content(
    race_label: str,
    year: str,
    trend_sections: TrendSections,
) -> str:
    """傾向分析記事のMarkdown文字列を生成する。

    タイトルの直後に集計対象の注記を置き、カテゴリセクションを連結する。

    Args:
        race_label (str): 記事タイトルに使うレース名。
        year (str): 開催年。
        trend_sections (TrendSections): 集計対象の注記とカテゴリセクション。

    Returns:
        str: 生成済み傾向分析記事Markdown文字列。
    """
    title = f"# 【{race_label}{year}】傾向分析"
    if not trend_sections.sections:
        return title + "\n"
    body = "\n\n".join(trend_sections.sections.values())
    return title + "\n\n" + trend_sections.scope_note + "\n\n" + body + "\n"


if __name__ == "__main__":
    main()
