"""前日・当日の傾向記事に共通する生成処理。

`gen_prev_day_trend` と `gen_race_day_trend` が、傾向記事の種類を選んで呼び出す。
"""

import argparse
import os

import matplotlib

matplotlib.use("Agg")

from dotenv import find_dotenv, load_dotenv  # noqa: E402
from mykeibadb import RaceGetter  # noqa: E402

from g1_predict.modules.gen_day_trend.day_trend import (  # noqa: E402
    DayTrendBody,
    DayTrendKind,
    build_day_trend_body,
)
from g1_predict.modules.utils.image_output import save_images  # noqa: E402
from g1_predict.modules.utils.output_path import build_race_dir, validate_race_code  # noqa: E402
from g1_predict.modules.utils.race_name import to_race_label  # noqa: E402

load_dotenv(find_dotenv())

_REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PUBLIC_DIR = os.path.join(_REPO_DIR, "public")


def generate_day_trend(race_code: str, kind: DayTrendKind) -> None:
    """指定レースの傾向記事を生成する。

    Args:
        race_code (str): 16桁 JRA-VAN 形式の race_code。
        kind (DayTrendKind): 傾向記事の種類（PREV_DAY / RACE_DAY）。
    """
    validate_race_code(race_code)
    race_getter = RaceGetter()
    race_shosai = race_getter.get_race_shosai(race_code=race_code, convert_codes=False)
    race_name = str(race_shosai["kyosomei_hondai"].iloc[0]).strip()
    race_label = to_race_label(race_name)
    year = str(race_shosai["kaisai_nen"].iloc[0]).strip()

    body = build_day_trend_body(race_code, race_shosai, race_label, kind)
    content = _render_day_trend_content(race_label, year, body, kind)

    race_dir = build_race_dir(_PUBLIC_DIR, year, race_code, race_label)
    os.makedirs(race_dir, exist_ok=True)
    output_path = os.path.join(race_dir, f"{kind.label}の傾向.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    save_images(race_dir, body.images)
    print(f"Generated: {output_path}")


def run_cli(kind: DayTrendKind) -> None:
    """引数をパースして指定した種類の傾向記事を生成する。

    Args:
        kind (DayTrendKind): 傾向記事の種類（PREV_DAY / RACE_DAY）。
    """
    parser = argparse.ArgumentParser(description=f"{kind.label}の傾向記事を生成する")
    parser.add_argument("--race-code", required=True, help="16桁 race_code")
    args = parser.parse_args()
    generate_day_trend(args.race_code, kind)


def _render_day_trend_content(
    race_label: str, year: str, body: DayTrendBody, kind: DayTrendKind
) -> str:
    """傾向記事のMarkdown文字列を生成する。

    Args:
        race_label (str): 記事タイトルに使うレース名。
        year (str): 開催年。
        body (DayTrendBody): 傾向記事の本文と画像。
        kind (DayTrendKind): 傾向記事の種類。

    Returns:
        str: 生成済み傾向記事Markdown文字列。
    """
    title = f"# 【{race_label}{year}】{kind.label}の傾向"
    if not body.text:
        return title + "\n"
    return title + "\n\n" + body.text
