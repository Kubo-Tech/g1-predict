"""結果定型文を KEK_COM へ追記するスクリプト。"""
import argparse
import os
from typing import Any

import pandas as pd
from keiba_data_interface import DataInterface
from mykeibadb.code_converter import convert_chakusa_code

from scripts.tfjv import race_code_to_tfjv, write_kek_comment

_DEFAULT_DATA_DIR = "/KeibaAI/repos/g1-predict/MY_DATA"
_NO_SUFFIX = {"大差", "同着"}


def generate_result_comments(race_code: str, base_dir: str) -> None:
    """指定レースの結果定型文を KEK_COM へ追記する。

    Args:
        race_code: 16桁 JRA-VAN 形式の race_code。
        base_dir: TFJV データディレクトリのパス。
    """
    di = DataInterface("mykeibadb")
    race_info = di.get_race_basic_info(race_code)
    race_name = race_info["競走名本題"].iloc[0]
    result_df = di.get_result(race_code)
    venue, year2, tfjv_code = race_code_to_tfjv(race_code)
    race_no = int(race_code[14:16])

    for _, row in result_df.iterrows():
        chakusa = int(row["確定着順"])
        time_diff = float(row["タイム差"])
        margin_code = row["着差コード1"]
        umaban = int(row["馬番"])
        gap = _determine_gap(time_diff, margin_code)
        comment = f"[{race_name}] {gap}{chakusa}着。"
        write_kek_comment(base_dir, venue, year2, tfjv_code, race_no, umaban, comment)


def _determine_gap(time_diff: float, margin_code: Any) -> str:
    """タイム差・着差コードから着差文字列を返す。"""
    abs_diff = abs(time_diff)
    if abs_diff != 0.0:
        return f"{abs_diff}秒差"
    code = str(margin_code) if pd.notna(margin_code) else ""
    text = convert_chakusa_code(code)
    return text if text in _NO_SUFFIX else text + "差"


def main() -> None:
    """エントリポイント。"""
    parser = argparse.ArgumentParser(description="結果定型文を KEK_COM へ追記する")
    parser.add_argument("--race-code", required=True, help="16桁 race_code")
    args = parser.parse_args()
    base_dir = os.environ.get("TFJV_DATA_DIR", _DEFAULT_DATA_DIR)
    generate_result_comments(args.race_code, base_dir)


if __name__ == "__main__":
    main()
