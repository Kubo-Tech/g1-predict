"""既存の予想記事 md に結果・回顧セクションを書き込むスクリプト。

コマンド:
cd path/to/g1-predict
python -m scripts.add_result --race-code <16桁 race_code>
"""

import argparse
import glob
import os

import pandas as pd
from dotenv import find_dotenv, load_dotenv
from keiba_data_interface import DataInterface
from mykeibadb.code_converter import convert_ijo_kubun_code

from scripts.md_utils import replace_section
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
_DEFAULT_DATA_DIR = "/KeibaAI/repos/g1-predict/MY_DATA"

_ABNORMAL_CODES = {"1", "2", "3", "4"}


def add_result(race_code: str) -> None:
    """指定レースの結果・回顧セクションを予想記事 md に書き込む。

    Args:
        race_code: 16桁 JRA-VAN 形式の race_code。

    Raises:
        FileNotFoundError: 対応する md ファイルが存在しない場合。
    """
    tfjv_data_dir = os.environ.get("TFJV_DATA_DIR", _DEFAULT_DATA_DIR)

    di = DataInterface("mykeibadb")
    result_df = di.get_result(race_code)

    dat_path = um_dat_path(race_code, tfjv_data_dir)
    marks = read_marks(dat_path, um_dat_record_no(race_code))

    venue, year2, tfjv_code = race_code_to_tfjv(race_code)
    race_no = int(race_code[14:16])
    comments = read_kek_comments(tfjv_data_dir, venue, year2, tfjv_code, race_no)

    result_section = _build_result_section(result_df, marks)
    review_section = _build_review_section(result_df, marks, comments)

    year = race_code[:4]
    pattern = os.path.join(_PUBLIC_DIR, year, f"{race_code}_*.md")
    matches = glob.glob(pattern)
    if not matches:
        raise FileNotFoundError(f"No md file found for race_code: {race_code}")
    md_path = matches[0]

    with open(md_path, encoding="utf-8") as f:
        content = f.read()

    content = replace_section(content, "## 結果", result_section)
    content = replace_section(content, "## 回顧", review_section)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Updated: {md_path}")


def main() -> None:
    """エントリポイント。"""
    parser = argparse.ArgumentParser(description="結果・回顧セクションを予想記事 md に書き込む")
    parser.add_argument("--race-code", required=True, help="16桁 race_code")
    args = parser.parse_args()
    add_result(args.race_code)


def _build_result_section(result_df: pd.DataFrame, marks: dict[int, str]) -> str:
    lines = ["## 結果", ""]
    normal_df = _get_normal_rows(result_df).sort_values("確定着順")
    for _, row in normal_df.iterrows():
        chakusa = int(row["確定着順"])
        if chakusa > 3:
            break
        umaban = int(row["馬番"])
        mark = marks.get(umaban, "")
        suffix = "  " if chakusa < 3 else ""
        lines.append(f"{chakusa}着 {mark}{umaban}{row['馬名']}{suffix}")
    return "\n".join(lines)


def _build_review_section(
    result_df: pd.DataFrame,
    marks: dict[int, str],
    comments: dict[int, str],
) -> str:
    lines: list[str] = ["## 回顧"]

    normal_df = _get_normal_rows(result_df).sort_values("確定着順")
    for _, row in normal_df.iterrows():
        umaban = int(row["馬番"])
        mark = marks.get(umaban, "")
        comment = _extract_comment_body(comments.get(umaban, ""))
        if not comment:
            continue
        lines.append("")
        lines.append(f"### {int(row['確定着順'])}着 {mark}{umaban}{row['馬名']}")
        lines.append("")
        lines.append(_format_comment_body(comment))

    abnormal_df = _get_abnormal_rows(result_df)
    for _, row in abnormal_df.iterrows():
        umaban = int(row["馬番"])
        mark = marks.get(umaban, "")
        comment = _extract_comment_body(comments.get(umaban, ""))
        if not comment:
            continue
        raw = row.get("異常区分コード")
        ijo_code = str(int(float(str(raw))))
        label = convert_ijo_kubun_code(ijo_code)
        lines.append("")
        lines.append(f"### {label} {mark}{umaban}{row['馬名']}")
        lines.append("")
        lines.append(_format_comment_body(comment))

    return "\n".join(lines)


def _get_normal_rows(result_df: pd.DataFrame) -> pd.DataFrame:
    mask = result_df.apply(_is_normal_row, axis=1)
    return result_df[mask]


def _get_abnormal_rows(result_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in result_df.iterrows():
        raw = row.get("異常区分コード")
        ijo_code = str(int(float(raw))) if pd.notna(raw) else "0"
        if ijo_code in _ABNORMAL_CODES:
            rows.append({**row.to_dict(), "_ijo_int": int(ijo_code)})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.sort_values(["_ijo_int", "馬番"], ascending=[False, True])


def _is_normal_row(row: pd.Series) -> bool:
    raw = row.get("異常区分コード")
    ijo_code = str(int(float(raw))) if pd.notna(raw) else "0"
    return ijo_code not in _ABNORMAL_CODES


def _extract_comment_body(raw_comment: str) -> str:
    if not raw_comment:
        return ""
    if raw_comment.startswith("["):
        end = raw_comment.find("]")
        if end == -1:
            return raw_comment
        return raw_comment[end + 1 :].strip()
    return raw_comment


def _format_comment_body(comment: str) -> str:
    return comment.replace("。", "。  \n").rstrip("\n")


if __name__ == "__main__":
    main()
