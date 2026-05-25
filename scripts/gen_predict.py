"""予想記事ベースを生成するスクリプト。"""

import argparse
import glob
import os
import re

import pandas as pd
from keiba_data_interface import DataInterface

_REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PUBLIC_DIR = os.path.join(_REPO_DIR, "public")
_TEMPLATES_DIR = os.path.join(_REPO_DIR, "templates")


def generate_predict(race_code: str) -> None:
    """指定レースの予想記事ベースを生成する。

    Args:
        race_code: 16桁 JRA-VAN 形式の race_code。
    """
    di = DataInterface("mykeibadb")
    race_info = di.get_race_basic_info(race_code)
    race_name = str(race_info["競走名本題"].iloc[0])
    year = str(race_info["開催年"].iloc[0])

    entry_df = di.get_entry(race_code)

    points = _load_points(race_name)
    marks_section = _build_marks_section(entry_df)

    content = (
        f"# {race_name}{year}\n\n"
        f"{points}\n\n"
        f"{marks_section}\n\n"
        f"## 見解\n\n"
        f"## 買い目\n"
    )

    nn = _next_serial(year, _PUBLIC_DIR)
    year_dir = os.path.join(_PUBLIC_DIR, year)
    os.makedirs(year_dir, exist_ok=True)
    output_path = os.path.join(year_dir, f"{nn}_{race_name}.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated: {output_path}")


def main() -> None:
    """エントリポイント。"""
    parser = argparse.ArgumentParser(description="予想記事ベースを生成する")
    parser.add_argument("--race-code", required=True, help="16桁 race_code")
    args = parser.parse_args()
    generate_predict(args.race_code)


def _next_serial(year: str, public_dir: str) -> str:
    files = glob.glob(os.path.join(public_dir, year, "*.md"))
    nums = [
        int(m.group(1))
        for f in files
        if (m := re.match(r"(\d+)_", os.path.basename(f)))
    ]
    return f"{max(nums) + 1:02d}" if nums else "01"


def _load_points(race_name: str) -> str:
    path = os.path.join(_TEMPLATES_DIR, "points", f"{race_name}.md")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return "## ポイント\n\n- \n"


def _build_marks_section(entry_df: pd.DataFrame) -> str:
    lines = ["## 印", ""]
    for _, row in entry_df.iterrows():
        umaban = int(row["馬番"])
        horse_name = str(row["馬名"])
        lines.append(f"{umaban}{horse_name}  ")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
