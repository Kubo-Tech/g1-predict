"""傾向分析記事を生成するスクリプト。

コマンド:
cd path/to/g1-predict
python -m scripts.gen_trend --race-code <16桁 race_code> [--with-entries [--tojitsu-bataiju]]
python -m scripts.gen_trend --race-code <16桁 race_code> --tokubetsu-kyoso-bango <4桁>
"""

import argparse
import datetime
import os

import pandas as pd
import yaml
from dotenv import find_dotenv, load_dotenv
from scraping import JraChokyoBataijuScraper

from g1_predict.modules.gen_trend.trend_section import (
    EntrySettings,
    TrendSections,
    build_trend_sections,
    check_race_entries,
)
from g1_predict.modules.utils.image_output import save_images
from g1_predict.modules.utils.output_path import build_race_dir, validate_race_code
from g1_predict.modules.utils.race_info import load_race_info
from g1_predict.modules.utils.race_name import to_config_dir_name, to_race_label

load_dotenv(find_dotenv())

_REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PUBLIC_DIR = os.path.join(_REPO_DIR, "public")
_CONFIGS_DIR = os.path.join(_REPO_DIR, "configs")
_TRENDS_DIR = os.path.join(_CONFIGS_DIR, "trends")
# 調教後馬体重はレース週に計量する。計量日がレース日の何日前までなら今回の開催の値とみなすか
_CHOKYO_BATAIJU_MAX_DAYS_BEFORE = 7


def generate_trend(
    race_code: str,
    with_entries: bool = False,
    tokubetsu_kyoso_bango: str | None = None,
    tojitsu_bataiju: bool = False,
) -> None:
    """指定レースの傾向分析記事を生成する。

    with_entries が True の場合は、出走馬が当たる行を書いた「該当馬」列と、
    出走馬の比較表の画像を載せる。
    with_entries の馬体重の項目の出走馬は、JRA が発表する調教後馬体重で判定する。
    tojitsu_bataiju が True の場合は、DB にある当日の馬体重で判定する。
    tokubetsu_kyoso_bango を指定した場合は、今回のレースを DB から引かず、同じ特別競走番号の
    直近の開催から競走名・距離・トラックを、race_code から開催年・開催月日・競馬場を取る。

    Args:
        race_code (str): 16桁 JRA-VAN 形式の race_code。
        with_entries (bool): 出走馬の確定後の情報を載せるか。
        tokubetsu_kyoso_bango (str | None): 今回のレースが DB に入る前に生成する場合の特別競走番号。
        tojitsu_bataiju (bool): 馬体重の項目の出走馬を当日の馬体重で判定するか。

    Raises:
        ValueError: with_entries と tokubetsu_kyoso_bango を両方指定した場合。
            tojitsu_bataiju を with_entries なしで指定した場合。
            tokubetsu_kyoso_bango を指定せず、今回のレースが DB に無い場合。
    """
    validate_race_code(race_code)
    if tokubetsu_kyoso_bango is not None and with_entries:
        raise ValueError("--with-entries と --tokubetsu-kyoso-bango は同時に指定できません")
    if tojitsu_bataiju and not with_entries:
        raise ValueError("--tojitsu-bataiju は --with-entries と一緒に指定してください")
    race_shosai = load_race_info(race_code, tokubetsu_kyoso_bango)
    race_name = str(race_shosai["kyosomei_hondai"].iloc[0]).strip()
    race_label = to_race_label(race_name)
    year = str(race_shosai["kaisai_nen"].iloc[0]).strip()
    tokubetsu = str(race_shosai["tokubetsu_kyoso_bango"].iloc[0]).strip()
    config_dir = os.path.join(_CONFIGS_DIR, to_config_dir_name(tokubetsu, race_label))

    trend_sections = _build_trend_sections(
        race_label, config_dir, race_shosai, race_code, with_entries, tojitsu_bataiju
    )
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
    parser.add_argument(
        "--tojitsu-bataiju",
        action="store_true",
        help="馬体重の項目の出走馬を、調教後馬体重ではなく DB にある当日の馬体重で判定する",
    )
    args = parser.parse_args()
    generate_trend(
        args.race_code, args.with_entries, args.tokubetsu_kyoso_bango, args.tojitsu_bataiju
    )


def _build_trend_sections(
    race_label: str,
    config_dir: str,
    race_info: pd.DataFrame,
    race_code: str,
    with_entries: bool,
    tojitsu_bataiju: bool = False,
) -> TrendSections:
    """傾向セクション群を生成する。

    Args:
        race_label (str): 記事に出力するレース名。
        config_dir (str): レースの trends.yml・table.yml・race.yml を置くディレクトリのパス。
        race_info (pd.DataFrame): レース基本情報DataFrame。
        race_code (str): 16桁 JRA-VAN 形式の race_code。
        with_entries (bool): 出走馬の確定後の情報を載せるか。
        tojitsu_bataiju (bool): 馬体重の項目の出走馬を、調教後馬体重ではなく当日の馬体重で
            判定するか。

    Returns:
        TrendSections: 集計対象の注記と、カテゴリ名 -> Markdownセクション文字列、比較表の画像。
            trends.yml が無い、または空の場合は注記もセクションも空。

    Raises:
        FileNotFoundError: with_entries が True で table.yml が無い場合。
            with_entries が True で tojitsu_bataiju が False のときに race.yml が無い場合。
        MykeibaDBError: with_entries が True で出走馬が DB に無い場合。
        ScrapingError: with_entries が True で tojitsu_bataiju が False のときに、
            調教後馬体重を取得できない場合。
    """
    # 出走馬の確定後の情報に必要な table.yml と出走馬は、trends.yml の有無によらず先に確かめる
    entries: EntrySettings | None = None
    if with_entries:
        table_path = os.path.join(config_dir, "table.yml")
        with open(table_path, encoding="utf-8") as f:
            table_config = yaml.safe_load(f)
        check_race_entries(race_code)
        weights = None if tojitsu_bataiju else _fetch_chokyo_bataiju(config_dir, race_code)
        entries = EntrySettings(
            race_code=race_code, table_config=table_config, chokyo_bataiju=weights
        )
    config_path = os.path.join(config_dir, "trends.yml")
    if not os.path.isfile(config_path):
        return TrendSections(scope_note="", sections={})
    with open(config_path, encoding="utf-8") as f:
        trends_config = yaml.safe_load(f)
    if not trends_config:
        return TrendSections(scope_note="", sections={})
    return build_trend_sections(race_info, race_label, trends_config, _TRENDS_DIR, entries)


def _fetch_chokyo_bataiju(config_dir: str, race_code: str) -> dict[str, int]:
    """race.yml の G1 特設ページ名から、出走馬の調教後馬体重を取得する。

    特設ページは同じ G1 で毎年使われるため、計量日がすべてレース日の前の1週間に入っているかを
    確かめ、今回の開催の値であることを保証する。

    Args:
        config_dir (str): レースの race.yml を置くディレクトリのパス。
        race_code (str): 16桁 JRA-VAN 形式の race_code。先頭8桁がレース日。

    Returns:
        dict[str, int]: 馬名 -> 調教後馬体重（kg）。

    Raises:
        FileNotFoundError: race.yml が無い場合。
        ScrapingError: 調教後馬体重を取得できない場合。
        ValueError: 計量日がレース日の前の1週間に入らない馬がいる場合。
    """
    with open(os.path.join(config_dir, "race.yml"), encoding="utf-8") as f:
        race_config = yaml.safe_load(f)
    weights = JraChokyoBataijuScraper(race_config["jra_g1_page"]).get_chokyo_bataiju()
    race_date = datetime.datetime.strptime(race_code[:8], "%Y%m%d").date()
    earliest = race_date - datetime.timedelta(days=_CHOKYO_BATAIJU_MAX_DAYS_BEFORE)
    stale = weights[~weights["計量日"].map(lambda day: earliest <= day < race_date)]
    if not stale.empty:
        raise ValueError(
            f"計量日が {race_date} の前の1週間に入らない調教後馬体重があります: "
            f"{dict(zip(stale['馬名'], stale['計量日'], strict=True))}"
        )
    return dict(zip(weights["馬名"], weights["馬体重"].astype(int), strict=True))


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
