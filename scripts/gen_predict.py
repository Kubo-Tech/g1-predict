"""予想記事ベースを生成するスクリプト。

コマンド:
cd path/to/g1-predict
python -m scripts.gen_predict --race-code <16桁 race_code>
"""

import argparse
import os

import pandas as pd
from dotenv import find_dotenv, load_dotenv
from mykeibadb import RaceGetter

from g1_predict.modules.gen_predict._constants import GRADE_CODE_DISPLAY
from g1_predict.modules.utils.md_utils import replace_section
from g1_predict.modules.utils.output_path import build_race_dir, validate_race_code
from g1_predict.modules.utils.tfjv import (
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
        race_code (str): 16桁 JRA-VAN 形式の race_code。
    """
    validate_race_code(race_code)
    tfjv_data_dir = os.environ.get("TFJV_DATA_DIR", _DEFAULT_DATA_DIR)

    race_getter = RaceGetter()
    race_shosai = race_getter.get_race_shosai(race_code=race_code, convert_codes=False)
    race_name = str(race_shosai["kyosomei_hondai"].iloc[0]).strip()
    year = str(race_shosai["kaisai_nen"].iloc[0]).strip()

    entry_raw = race_getter.get_umagoto_race_joho(race_code=race_code, convert_codes=False)
    entry_raw = entry_raw.sort_values("umaban").reset_index(drop=True)

    dat_path = um_dat_path(race_code, tfjv_data_dir)
    marks = read_marks(dat_path, um_dat_record_no(race_code))

    points = _load_points(race_name)
    marks_section = _build_marks_section(marks, entry_raw)
    insight_section = _build_insight_section(marks, entry_raw, race_getter, tfjv_data_dir)
    content = _render_from_template(race_name, year, points, marks_section, insight_section)

    race_dir = build_race_dir(_PUBLIC_DIR, year, race_code, race_name)
    os.makedirs(race_dir, exist_ok=True)
    output_path = os.path.join(race_dir, "予想.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated: {output_path}")


def main() -> None:
    """エントリポイント。

    Args:
        なし。
    """
    parser = argparse.ArgumentParser(description="予想記事ベースを生成する")
    parser.add_argument("--race-code", required=True, help="16桁 race_code")
    args = parser.parse_args()
    generate_predict(args.race_code)


def _load_points(race_name: str) -> str:
    """ポイントセクションを読み込む。

    Args:
        race_name (str): レース名。

    Returns:
        str: ポイントセクションのMarkdown文字列。
    """
    path = os.path.join(_TEMPLATES_DIR, "points", f"{race_name}.md")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return "## ポイント\n\n- \n"


def _sort_marks(marks: dict[int, str]) -> list[tuple[int, str]]:
    """印を優先度順に並べる。

    Args:
        marks (dict[int, str]): 馬番 -> 印記号のdict。

    Returns:
        list[tuple[int, str]]: 優先度順に並べた馬番と印記号のリスト。
    """
    return sorted(
        marks.items(),
        key=lambda x: (
            _MARK_ORDER.index(x[1]) if x[1] in _MARK_ORDER else len(_MARK_ORDER),
            x[0],
        ),
    )


def _build_marks_section(marks: dict[int, str], entry_raw: pd.DataFrame) -> str:
    """印セクションを生成する。

    Args:
        marks (dict[int, str]): 馬番 -> 印記号のdict。
        entry_raw (pd.DataFrame): 出走馬情報DataFrame。

    Returns:
        str: 印セクションのMarkdown文字列。
    """
    horse_map = {int(row["umaban"]): str(row["bamei"]).strip() for _, row in entry_raw.iterrows()}
    lines = ["## 印", ""]
    for umaban, mark in _sort_marks(marks):
        lines.append(f"{mark}{umaban}{horse_map[umaban]}  ")
    return "\n".join(lines)


def _build_insight_section(
    marks: dict[int, str],
    entry_raw: pd.DataFrame,
    race_getter: RaceGetter,
    tfjv_data_dir: str,
) -> str:
    """見解セクションを生成する。

    Args:
        marks (dict[int, str]): 馬番 -> 印記号のdict。
        entry_raw (pd.DataFrame): 出走馬情報DataFrame。
        race_getter (RaceGetter): レース情報取得オブジェクト。
        tfjv_data_dir (str): JRA-VANデータディレクトリ。

    Returns:
        str: 見解セクションのMarkdown文字列。
    """
    horse_map = {
        int(row["umaban"]): (str(row["bamei"]).strip(), str(row["ketto_toroku_bango"]))
        for _, row in entry_raw.iterrows()
    }
    marked = _sort_marks(marks)
    lines: list[str] = ["## 見解"]

    for umaban, mark in marked:
        horse_name, horse_id = horse_map[umaban]
        lines.append("")
        lines.append(f"### {mark}{umaban}{horse_name}")
        lines.append("")

        past_raw = race_getter.get_umagoto_race_joho(
            ketto_toroku_bango=horse_id, convert_codes=False
        )
        past_raw = past_raw.sort_values("race_code", ascending=False).reset_index(drop=True)
        seen_race_codes: set[str] = set()
        count = 0
        for _, past_row in past_raw.iterrows():
            past_race_code = str(past_row["race_code"])
            race_key = past_race_code[:4] + past_race_code[8:]
            if race_key in seen_race_codes:
                continue
            seen_race_codes.add(race_key)
            count += 1
            past_umaban = int(past_row["umaban"])
            past_race_no = int(past_race_code[14:16])

            venue, year2, tfjv_code = race_code_to_tfjv(past_race_code)
            comments = read_kek_comments(tfjv_data_dir, venue, year2, tfjv_code, past_race_no)

            if past_umaban not in comments:
                continue

            past_shosai = race_getter.get_race_shosai(
                race_code=past_race_code, convert_codes=False
            )
            grade_code = str(past_shosai["grade_code"].iloc[0]).strip()
            grade = GRADE_CODE_DISPLAY.get(grade_code, "")

            comment = comments[past_umaban]
            race_name_str, body = _parse_kek_comment(comment)
            ordinal = _format_ordinal(count)
            lines.append(f"{ordinal}{grade}{race_name_str}{body}  ")

    return "\n".join(lines)


def _parse_kek_comment(comment: str) -> tuple[str, str]:
    """成績コメントからレース名と本文を分離する。

    Args:
        comment (str): 成績コメント文字列。

    Returns:
        str: レース名。
        str: コメント本文。

    Raises:
        ValueError: コメントのレース名閉じ括弧が存在しない場合。
    """
    if comment.startswith("["):
        if "]" not in comment:
            raise ValueError(f"Invalid kek comment format (missing ']'): {comment!r}")
        end = comment.index("]")
        race_name = comment[1:end]
        body = comment[end + 1 :].lstrip(" ")
        return race_name, body
    return "", comment


def _format_ordinal(n: int) -> str:
    """走数を前走表記へ変換する。

    Args:
        n (int): 走数。

    Returns:
        str: 前走、前々走、または n走前 の文字列。
    """
    if n == 1:
        return "前走"
    if n == 2:
        return "前々走"
    return f"{n}走前"


def _render_from_template(
    race_name: str,
    year: str,
    points_section: str,
    marks_section: str,
    insight_section: str,
) -> str:
    """予想テンプレートに各セクションを埋め込む。

    Args:
        race_name (str): レース名。
        year (str): 開催年。
        points_section (str): ポイントセクション。
        marks_section (str): 印セクション。
        insight_section (str): 見解セクション。

    Returns:
        str: 生成済み予想記事Markdown文字列。
    """
    template_path = os.path.join(_TEMPLATES_DIR, "TEMPLATE_PREDICT.md")
    with open(template_path, encoding="utf-8") as f:
        content = f.read()
    content = content.replace("{RaceName}", race_name).replace("{Year}", year)
    content = replace_section(content, "## ポイント", points_section)
    content = replace_section(content, "## 印", marks_section)
    content = replace_section(content, "## 見解", insight_section)
    return content


if __name__ == "__main__":
    main()
