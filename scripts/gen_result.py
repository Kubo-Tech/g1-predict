"""結果記事を生成するスクリプト。

コマンド:
cd path/to/g1-predict
python -m scripts.gen_result --race-code <16桁 race_code>
"""

import argparse
import os
from datetime import datetime, timedelta

import matplotlib

matplotlib.use("Agg")

import pandas as pd  # noqa: E402
from dotenv import find_dotenv, load_dotenv  # noqa: E402
from evaluation import RaceDynamicsResult  # noqa: E402
from keiba_data_interface import DataInterface  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from mykeibadb.code_converter import convert_ijo_kubun_code  # noqa: E402

from g1_predict.modules.utils.hatena_links import build_related_articles_section  # noqa: E402
from g1_predict.modules.utils.image_output import save_images  # noqa: E402
from g1_predict.modules.utils.md_utils import replace_section  # noqa: E402
from g1_predict.modules.utils.output_path import build_race_dir, validate_race_code  # noqa: E402
from g1_predict.modules.utils.race_dynamics import (  # noqa: E402
    build_dynamics_table_lines,
    build_total_evaluation_table_lines,
    evaluate_race_dynamics_with_plot,
)
from g1_predict.modules.utils.race_name import to_race_label  # noqa: E402
from g1_predict.modules.utils.race_result import format_corner4, format_halon  # noqa: E402
from g1_predict.modules.utils.tfjv import (  # noqa: E402
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
_HATENA_CONFIG_PATH = os.path.join(_REPO_DIR, "configs", "hatena.yml")
_DEFAULT_DATA_DIR = "/KeibaAI/repos/g1-predict/MY_DATA"

# 関連記事に載せる記事ファイル名（拡張子を除く）
_RELATED_ARTICLE_NAMES = ["予想"]
_ABNORMAL_CODES = {"1", "2", "3", "4"}
# 標準化散布図を保存する、記事ディレクトリからの相対ディレクトリ
_RESULT_IMAGE_DIR = "img/race_result"


def generate_result(race_code: str) -> None:
    """指定レースの結果記事を生成する。

    Args:
        race_code: 16桁 JRA-VAN 形式の race_code。
    """
    validate_race_code(race_code)
    tfjv_data_dir = os.environ.get("TFJV_DATA_DIR", _DEFAULT_DATA_DIR)

    di = DataInterface("mykeibadb")
    race_info = di.get_race_basic_info(race_code)
    race_name = str(race_info["競走名本題"].iloc[0])
    race_label = to_race_label(race_name)
    year = str(race_info["開催年"].iloc[0])

    result_df = di.get_result(race_code)

    dat_path = um_dat_path(race_code, tfjv_data_dir)
    marks = read_marks(dat_path, um_dat_record_no(race_code))

    venue, year2, tfjv_code = race_code_to_tfjv(race_code)
    race_no = int(race_code[14:16])
    comments = read_kek_comments(tfjv_data_dir, venue, year2, tfjv_code, race_no)

    # 開催日の翌日を基準日にして、開催日当日でも確定済みのレースとして評価する
    race_date = datetime.strptime(race_code[0:8], "%Y%m%d").date()
    dynamics, figure = evaluate_race_dynamics_with_plot(
        race_code, di, race_date + timedelta(days=1)
    )
    image_path = f"{_RESULT_IMAGE_DIR}/{race_code}.png"
    result_section = _build_result_section(result_df, marks, dynamics, figure, image_path)
    review_section = _build_review_section(result_df, marks, comments)

    race_dir = build_race_dir(_PUBLIC_DIR, year, race_code, race_label)
    related_section = build_related_articles_section(
        _PUBLIC_DIR, race_dir, _RELATED_ARTICLE_NAMES, "自作AIの結果", _HATENA_CONFIG_PATH
    )
    sections = (result_section, related_section, review_section)
    content = _render_from_template(race_label, year, *sections)

    os.makedirs(race_dir, exist_ok=True)
    output_path = os.path.join(race_dir, "回顧.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    images = {image_path: figure} if figure is not None else {}
    save_images(race_dir, images)
    print(f"Generated: {output_path}")


def main() -> None:
    """エントリポイント。"""
    parser = argparse.ArgumentParser(description="結果記事を生成する")
    parser.add_argument("--race-code", required=True, help="16桁 race_code")
    args = parser.parse_args()
    generate_result(args.race_code)


def _build_result_section(
    result_df: pd.DataFrame,
    marks: dict[int, str],
    dynamics: RaceDynamicsResult | None,
    figure: Figure | None,
    image_path: str,
) -> str:
    lines = [
        "## 結果",
        "",
        "| 着順 | 印 | 馬番 | 馬名 | 人気 | 4角通過 | 後3F |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    normal_df = _get_normal_rows(result_df).sort_values("確定着順")
    for _, row in normal_df.iterrows():
        chakusa = int(row["確定着順"])
        if chakusa > 3:
            break
        umaban = int(row["馬番"])
        ninki = int(row["単勝人気順"]) if pd.notna(row["単勝人気順"]) else "-"
        cols = [
            f"{chakusa}着",
            marks.get(umaban, ""),
            str(umaban),
            str(row["馬名"]),
            str(ninki),
            format_corner4(row),
            format_halon(row, result_df),
        ]
        lines.append("| " + " | ".join(cols) + " |")
    if dynamics is not None:
        lines.extend(["", *build_dynamics_table_lines(dynamics.cor_df)])
    if figure is not None:
        lines.extend(["", f"![標準化散布図]({image_path})"])
    if dynamics is not None:
        lines.extend(
            [
                "",
                *build_total_evaluation_table_lines(dynamics.eval_df, result_df),
                "",
                "※ 評価値は、展開（4角の位置・馬番・コーナーでの内外）の有利不利で"
                "走破タイムを補正した値。大きいほど展開の不利をはね返して好走した馬。",
            ]
        )
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


def _render_from_template(
    race_label: str,
    year: str,
    result_section: str,
    related_section: str,
    review_section: str,
) -> str:
    template_path = os.path.join(_TEMPLATES_DIR, "TEMPLATE_RESULT.md")
    with open(template_path, encoding="utf-8") as f:
        content = f.read()
    content = content.replace("{RaceName}", race_label).replace("{Year}", year)
    content = replace_section(content, "## 結果", result_section)
    content = replace_section(content, "## 関連記事", related_section)
    content = replace_section(content, "## 回顧", review_section)
    return content


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
