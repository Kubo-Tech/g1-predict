"""前日の傾向記事を生成するスクリプト。

コマンド:
cd path/to/g1-predict
python -m scripts.gen_prev_day_trend --race-code <16桁 race_code>
"""

import argparse
import os

import matplotlib

matplotlib.use("Agg")

from dotenv import find_dotenv, load_dotenv  # noqa: E402
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from mykeibadb import RaceGetter  # noqa: E402

from g1_predict.modules.gen_prev_day_trend.prev_day_trend import (  # noqa: E402
    PrevDayTrendBody,
    build_prev_day_trend_body,
)
from g1_predict.modules.utils.output_path import build_race_dir, validate_race_code  # noqa: E402
from g1_predict.modules.utils.race_name import to_race_label  # noqa: E402

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
    race_label = to_race_label(race_name)
    year = str(race_shosai["kaisai_nen"].iloc[0]).strip()

    body = build_prev_day_trend_body(race_code, race_shosai)
    content = _render_prev_day_trend_content(race_label, year, body)

    race_dir = build_race_dir(_PUBLIC_DIR, year, race_code, race_label)
    os.makedirs(race_dir, exist_ok=True)
    output_path = os.path.join(race_dir, "前日の傾向.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    _save_images(race_dir, body.images)
    print(f"Generated: {output_path}")


def main() -> None:
    """エントリポイント。"""
    parser = argparse.ArgumentParser(description="前日の傾向記事を生成する")
    parser.add_argument("--race-code", required=True, help="16桁 race_code")
    args = parser.parse_args()
    generate_prev_day_trend(args.race_code)


def _render_prev_day_trend_content(race_label: str, year: str, body: PrevDayTrendBody) -> str:
    """前日の傾向記事のMarkdown文字列を生成する。

    Args:
        race_label (str): 記事タイトルに使うレース名。
        year (str): 開催年。
        body (PrevDayTrendBody): 前日の傾向記事の本文と画像。

    Returns:
        str: 生成済み前日の傾向記事Markdown文字列。
    """
    title = f"# {race_label}{year}前日の傾向"
    if not body.text:
        return title + "\n"
    return title + "\n\n" + body.text


def _save_images(race_dir: str, images: dict[str, Figure]) -> None:
    """展開評価の画像を記事ディレクトリへ保存する。

    保存後にFigureをcloseし、メモリを解放する。

    Args:
        race_dir (str): レース単位の出力ディレクトリのパス。
        images (dict[str, Figure]): 記事ディレクトリからの相対パス → Figure。
    """
    for relative_path, figure in images.items():
        image_path = os.path.join(race_dir, relative_path)
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        # タイトル・軸ラベルが画像の外に切れないよう余白を内容に合わせる
        figure.savefig(image_path, bbox_inches="tight")
        plt.close(figure)


if __name__ == "__main__":
    main()
