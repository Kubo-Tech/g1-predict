"""前日の傾向記事を生成するスクリプト。

コマンド:
cd path/to/g1-predict
python -m scripts.gen_prev_day_trend --race-code <16桁 race_code>
"""

import argparse
import os

from dotenv import find_dotenv, load_dotenv
from mykeibadb import RaceGetter

from g1_predict.modules.gen_predict.prev_day_trend import build_prev_day_trend_body
from g1_predict.modules.utils.output_path import build_race_dir, validate_race_code

load_dotenv(find_dotenv())

_REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PUBLIC_DIR = os.path.join(_REPO_DIR, "public")


def generate_prev_day_trend(race_code: str) -> None:
    """指定レースの前日の傾向記事を生成する。

    Args:
        race_code (str): 16桁 JRA-VAN 形式の race_code。
    """
    validate_race_code(race_code)
    race_getter = RaceGetter()
    race_shosai = race_getter.get_race_shosai(race_code=race_code, convert_codes=False)
    race_name = str(race_shosai["kyosomei_hondai"].iloc[0]).strip()
    year = str(race_shosai["kaisai_nen"].iloc[0]).strip()

    body = build_prev_day_trend_body(race_code, race_shosai)
    content = _render_prev_day_trend_content(race_name, year, body)

    race_dir = build_race_dir(_PUBLIC_DIR, year, race_code, race_name)
    os.makedirs(race_dir, exist_ok=True)
    output_path = os.path.join(race_dir, "前日の傾向.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated: {output_path}")


def main() -> None:
    """エントリポイント。"""
    parser = argparse.ArgumentParser(description="前日の傾向記事を生成する")
    parser.add_argument("--race-code", required=True, help="16桁 race_code")
    args = parser.parse_args()
    generate_prev_day_trend(args.race_code)


def _render_prev_day_trend_content(race_name: str, year: str, body: str) -> str:
    """前日の傾向記事のMarkdown文字列を生成する。

    Args:
        race_name (str): レース名。
        year (str): 開催年。
        body (str): 前日の傾向記事本文。

    Returns:
        str: 生成済み前日の傾向記事Markdown文字列。
    """
    title = f"# {race_name}{year}前日の傾向"
    if not body:
        return title + "\n"
    return title + "\n\n" + body


if __name__ == "__main__":
    main()
