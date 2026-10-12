"""過去の展開記事を生成するスクリプト。

コマンド:
cd path/to/g1-predict
python -m scripts.gen_dynamics_history --race-code <16桁 race_code>
python -m scripts.gen_dynamics_history --race-code <16桁 race_code> --tokubetsu-kyoso-bango <4桁>
"""

import argparse
import os

import matplotlib

matplotlib.use("Agg")

from dotenv import find_dotenv, load_dotenv  # noqa: E402

from g1_predict.modules.gen_dynamics_history.dynamics_history import (  # noqa: E402
    build_dynamics_history,
)
from g1_predict.modules.utils.image_output import save_images  # noqa: E402
from g1_predict.modules.utils.output_path import build_race_dir, validate_race_code  # noqa: E402
from g1_predict.modules.utils.race_info import load_race_info  # noqa: E402
from g1_predict.modules.utils.race_name import to_race_label  # noqa: E402

load_dotenv(find_dotenv())

_REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PUBLIC_DIR = os.path.join(_REPO_DIR, "public")


def generate_dynamics_history(race_code: str, tokubetsu_kyoso_bango: str | None = None) -> None:
    """指定レースの過去の展開記事を生成する。

    tokubetsu_kyoso_bango を指定した場合は、今回のレースを DB から引かず、同じ特別競走番号の
    直近の開催から競走名・距離・トラックを、race_code から開催年・開催月日・競馬場を取る。

    Args:
        race_code (str): 16桁 JRA-VAN 形式の race_code。
        tokubetsu_kyoso_bango (str | None): 今回のレースが DB に入る前に生成する場合の特別競走番号。

    Raises:
        ValueError: tokubetsu_kyoso_bango を指定せず、今回のレースが DB に無い場合。
    """
    validate_race_code(race_code)
    race_info = load_race_info(race_code, tokubetsu_kyoso_bango)
    race_label = to_race_label(str(race_info["kyosomei_hondai"].iloc[0]).strip())
    year = str(race_info["kaisai_nen"].iloc[0]).strip()

    body = build_dynamics_history(race_info, race_label)

    race_dir = build_race_dir(_PUBLIC_DIR, year, race_code, race_label)
    os.makedirs(race_dir, exist_ok=True)
    output_path = os.path.join(race_dir, "過去の展開.md")
    # 画像の保存に失敗したときに、画像の無い記事を残さないよう先に保存する
    save_images(race_dir, body.images)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(body.content)
    print(f"Generated: {output_path}")


def main() -> None:
    """エントリポイント。"""
    parser = argparse.ArgumentParser(description="過去の展開記事を生成する")
    parser.add_argument("--race-code", required=True, help="16桁 race_code")
    parser.add_argument(
        "--tokubetsu-kyoso-bango",
        help="今回のレースが DB に入る前に生成する場合の特別競走番号（4桁）",
    )
    args = parser.parse_args()
    generate_dynamics_history(args.race_code, args.tokubetsu_kyoso_bango)


if __name__ == "__main__":
    main()
