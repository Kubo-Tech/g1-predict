"""予想記事ベースを生成するスクリプト。

コマンド:
cd path/to/g1-predict
python -m scripts.gen_predict --race-code <16桁 race_code>
"""

import argparse
import os

import pandas as pd
from dotenv import find_dotenv, load_dotenv
from keiba_data_interface import DataInterface
from scripts.md_utils import replace_section
from scripts.prev_day_trend import GRADE_CODE_DISPLAY, build_prev_day_trend_section
from scripts.tfjv import (
    race_code_to_tfjv,
    read_kek_comments,
    read_marks,
    um_dat_path,
    um_dat_record_no,
)

load_dotenv(find_dotenv())

_REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PUBLIC_DIR = os.path.join(_REPO_DIR, "public")
_TEMPLATES_DIR = os.path.join(_REPO_DIR, "templates")
_DEFAULT_DATA_DIR = "/KeibaAI/repos/g1-predict/MY_DATA"

_MARK_ORDER = ["◎", "○", "▲", "△", "◆", "☆", "注"]


def generate_predict(race_code: str) -> None:
    """指定レースの予想記事ベースを生成する。

    Args:
        race_code: 16桁 JRA-VAN 形式の race_code。
    """
    tfjv_data_dir = os.environ.get("TFJV_DATA_DIR", _DEFAULT_DATA_DIR)

    di = DataInterface("mykeibadb")
    race_info = di.get_race_basic_info(race_code)
    race_name = str(race_info["競走名本題"].iloc[0])
    year = str(race_info["開催年"].iloc[0])

    entry_df = di.get_entry(race_code)

    dat_path = um_dat_path(race_code, tfjv_data_dir)
    marks = read_marks(dat_path, um_dat_record_no(race_code))

    points = _load_points(race_name)
    trend_section = build_prev_day_trend_section(race_code, race_info, di)
    marks_section = _build_marks_section(marks, entry_df)
    insight_section = _build_insight_section(marks, entry_df, di, tfjv_data_dir, race_code)
    args = (race_name, year, points, trend_section, marks_section, insight_section)
    content = _render_from_template(*args)

    year_dir = os.path.join(_PUBLIC_DIR, year)
    os.makedirs(year_dir, exist_ok=True)
    output_path = os.path.join(year_dir, f"{race_code}_{race_name}.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated: {output_path}")


def main() -> None:
    """エントリポイント。"""
    parser = argparse.ArgumentParser(description="予想記事ベースを生成する")
    parser.add_argument("--race-code", required=True, help="16桁 race_code")
    args = parser.parse_args()
    generate_predict(args.race_code)


def _load_points(race_name: str) -> str:
    path = os.path.join(_TEMPLATES_DIR, "points", f"{race_name}.md")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return "## ポイント\n\n- \n"


def _sort_marks(marks: dict[int, str]) -> list[tuple[int, str]]:
    return sorted(
        marks.items(),
        key=lambda x: (
            _MARK_ORDER.index(x[1]) if x[1] in _MARK_ORDER else len(_MARK_ORDER),
            x[0],
        ),
    )


def _build_marks_section(marks: dict[int, str], entry_df: pd.DataFrame) -> str:
    horse_map = {int(row["馬番"]): str(row["馬名"]) for _, row in entry_df.iterrows()}
    lines = ["## 印", ""]
    for umaban, mark in _sort_marks(marks):
        lines.append(f"{mark}{umaban}{horse_map[umaban]}  ")
    return "\n".join(lines)


def _build_insight_section(
    marks: dict[int, str],
    entry_df: pd.DataFrame,
    di: DataInterface,
    tfjv_data_dir: str,
    race_code: str,
) -> str:
    horse_map = {
        int(row["馬番"]): (str(row["馬名"]), str(row["血統登録番号"]))
        for _, row in entry_df.iterrows()
    }
    marked = _sort_marks(marks)
    lines: list[str] = ["## 見解"]

    for umaban, mark in marked:
        horse_name, horse_id = horse_map[umaban]
        lines.append("")
        lines.append(f"### {mark}{umaban}{horse_name}")
        lines.append("")

        past_df = di.get_past_performances(horse_id)
        seen_race_codes: set[str] = set()
        count = 0
        for _, past_row in past_df.iterrows():
            past_race_code = str(past_row["レースコード"])
            if past_race_code >= race_code:
                continue
            race_key = past_race_code[:4] + past_race_code[8:]
            if race_key in seen_race_codes:
                continue
            seen_race_codes.add(race_key)
            count += 1
            past_umaban = int(past_row["馬番"])
            past_race_no = int(past_race_code[14:16])

            venue, year2, tfjv_code = race_code_to_tfjv(past_race_code)
            comments = read_kek_comments(tfjv_data_dir, venue, year2, tfjv_code, past_race_no)

            if past_umaban not in comments:
                continue

            past_race_info = di.get_race_basic_info(past_race_code)
            grade_code = str(past_race_info["グレードコード"].iloc[0])
            grade = GRADE_CODE_DISPLAY.get(grade_code, "")

            comment = comments[past_umaban]
            race_name, body = _parse_kek_comment(comment)
            ordinal = _format_ordinal(count)
            lines.append(f"{ordinal}{grade}{race_name}{body}  ")

    return "\n".join(lines)


def _parse_kek_comment(comment: str) -> tuple[str, str]:
    if comment.startswith("["):
        if "]" not in comment:
            raise ValueError(f"Invalid kek comment format (missing ']'): {comment!r}")
        end = comment.index("]")
        race_name = comment[1:end]
        body = comment[end + 1 :].lstrip(" ")
        return race_name, body
    return "", comment


def _format_ordinal(n: int) -> str:
    if n == 1:
        return "前走"
    if n == 2:
        return "前々走"
    return f"{n}走前"


def _render_from_template(
    race_name: str,
    year: str,
    points_section: str,
    trend_section: str,
    marks_section: str,
    insight_section: str,
) -> str:
    template_path = os.path.join(_TEMPLATES_DIR, "TEMPLATE.md")
    with open(template_path, encoding="utf-8") as f:
        content = f.read()
    content = content.replace("{RaceName}", race_name).replace("{Year}", year)
    content = replace_section(content, "## ポイント", points_section)
    content = replace_section(content, "## 前日の傾向", trend_section)
    content = replace_section(content, "## 印", marks_section)
    content = replace_section(content, "## 見解", insight_section)
    return content


if __name__ == "__main__":
    main()
