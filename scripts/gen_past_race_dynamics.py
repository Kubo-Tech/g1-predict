"""出走馬の過去走の展開評価記事を生成するスクリプト。

コマンド:
cd path/to/g1-predict
python -m scripts.gen_past_race_dynamics --race-code <16桁 race_code>
"""

import argparse
import os

import matplotlib

matplotlib.use("Agg")

from dotenv import find_dotenv, load_dotenv  # noqa: E402
from mykeibadb import RaceGetter  # noqa: E402

from g1_predict.modules.gen_past_race_dynamics.past_race_dynamics import (  # noqa: E402
    build_past_race_dynamics_body,
)
from g1_predict.modules.utils.image_output import save_images  # noqa: E402
from g1_predict.modules.utils.output_path import build_race_dir, validate_race_code  # noqa: E402
from g1_predict.modules.utils.race_name import to_race_label  # noqa: E402

load_dotenv(find_dotenv())

_REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PUBLIC_DIR = os.path.join(_REPO_DIR, "public")


def generate_past_race_dynamics(race_code: str) -> None:
    """指定レースの出走馬の過去走の展開評価記事を生成する。

    Args:
        race_code (str): 16桁 JRA-VAN 形式の race_code。
    """
    validate_race_code(race_code)
    race_shosai = RaceGetter().get_race_shosai(race_code=race_code, convert_codes=False)
    race_label = to_race_label(str(race_shosai["kyosomei_hondai"].iloc[0]).strip())
    year = str(race_shosai["kaisai_nen"].iloc[0]).strip()

    body = build_past_race_dynamics_body(race_code)
    content = f"# 【{race_label}{year}】出走馬の過去走の展開評価\n\n{body.text}"

    race_dir = build_race_dir(_PUBLIC_DIR, year, race_code, race_label)
    os.makedirs(race_dir, exist_ok=True)
    output_path = os.path.join(race_dir, "出走馬の過去走の展開評価.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    save_images(race_dir, body.images)
    print(f"Generated: {output_path}")


def main() -> None:
    """エントリポイント。"""
    parser = argparse.ArgumentParser(description="出走馬の過去走の展開評価記事を生成する")
    parser.add_argument("--race-code", required=True, help="16桁 race_code")
    args = parser.parse_args()
    generate_past_race_dynamics(args.race_code)


if __name__ == "__main__":
    main()
