"""レース名・レース結果の馬毎の行を記事の表示用に整形するユーティリティ。"""

from collections.abc import Mapping

import pandas as pd

from g1_predict.modules.constants import GRADE_CODE_DISPLAY

# 脚質判定コード → 表示名
KYAKUSHITSU_DISPLAY: dict[str, str] = {"1": "逃げ", "2": "先行", "3": "差し", "4": "追込"}
# 脚質の表示名 → 表で使う1文字の略称
KYAKUSHITSU_SHORT: dict[str, str] = {"逃げ": "逃", "先行": "先", "差し": "差", "追込": "追"}
# 競走条件コード → 条件名の表示名
_KYOSO_JOKEN_CODE_DISPLAY: dict[str, str] = {
    "701": "新馬",
    "703": "未勝利",
    "005": "1勝クラス",
    "010": "2勝クラス",
    "016": "3勝クラス",
    "999": "オープン",
}


def race_condition_display(race_info: pd.DataFrame) -> str:
    """競走条件の表示名を返す。

    競走条件名称があればそれを使い、無ければ競走条件コードから表示名を引く。

    Args:
        race_info (pd.DataFrame): レース基本情報DataFrame（1行）。

    Returns:
        str: 競走条件の表示名。

    Raises:
        ValueError: 競走条件名称が無く、競走条件コードが無いか表示名の無いコードの場合。
    """
    cond_raw = race_info["競走条件名称"].iloc[0]
    if pd.notna(cond_raw) and str(cond_raw).strip():
        return str(cond_raw).strip()
    joken_code_raw = race_info["競走条件コード"].iloc[0]
    joken_code = str(joken_code_raw) if pd.notna(joken_code_raw) else ""
    if joken_code not in _KYOSO_JOKEN_CODE_DISPLAY:
        raise ValueError(f"競走条件コードの表示名が無い: {joken_code!r}")
    return _KYOSO_JOKEN_CODE_DISPLAY[joken_code]


def grade_display(race_info: pd.DataFrame) -> str:
    """レースのグレードの表示名を返す。

    Args:
        race_info (pd.DataFrame): レース基本情報DataFrame（1行）。

    Returns:
        str: グレードの表示名（G1・G2・G3・Lなど）。グレードが無いレースは空文字列。
    """
    grade_code = str(race_info["グレードコード"].iloc[0])
    return GRADE_CODE_DISPLAY.get(grade_code, "")


def race_display_name(race_info: pd.DataFrame, unified_names: Mapping[str, str]) -> str:
    """記事に載せるレース名を返す。

    競走名本題があるレース（特別レース）は、重賞を特別競走番号ごとの最新名に統一した名前、
    競走名本題が無い条件戦は競走条件の表示名を返す。

    Args:
        race_info (pd.DataFrame): レース基本情報DataFrame（1行）。
        unified_names (Mapping[str, str]): race_code → 統一した競走名本題。
            競走名本題があるレースのrace_codeを含むこと。

    Returns:
        str: 記事に載せるレース名。

    Raises:
        KeyError: 競走名本題があるレースのrace_codeが unified_names に無い場合。
    """
    hondai = race_info["競走名本題"].iloc[0]
    if pd.isna(hondai) or not str(hondai).strip():
        return race_condition_display(race_info)
    return unified_names[str(race_info["レースコード"].iloc[0])].strip()


def kyakushitsu_display(row: pd.Series) -> str:
    """馬毎レース結果の行から脚質の表示名を返す。

    Args:
        row (pd.Series): 馬毎レース結果の行。

    Returns:
        str: 脚質の表示名（逃げ/先行/差し/追込）。脚質判定コードが無い場合は空文字列。
    """
    code = row.get("脚質判定コード", "")
    if pd.isna(code):
        return ""
    return KYAKUSHITSU_DISPLAY.get(str(code).strip(), "")


def halon_rank(horse_row: pd.Series, result_df: pd.DataFrame) -> int:
    """result_df内での後3ハロン順位（昇順、1位が最速）を返す。

    Args:
        horse_row (pd.Series): 順位を計算する馬の行。
        result_df (pd.DataFrame): 全馬のresult DataFrame。

    Returns:
        int: 後3ハロン順位（1始まり）。
    """
    halon = float(horse_row["後3ハロン"])
    series = pd.to_numeric(result_df["後3ハロン"], errors="coerce").dropna()
    return int((series < halon).sum()) + 1


def format_corner4(horse_row: pd.Series, unit: str = "") -> str:
    """4角通過順位を、脚質の略称付きの文字列に整形する。

    Args:
        horse_row (pd.Series): 馬毎レース結果の行。
        unit (str): 順位に付ける単位（例: "番手"）。

    Returns:
        str: 例: "1番手 (逃)"。順位が無い場合は "-"。脚質判定が無い場合は括弧を付けない。
    """
    corner4 = horse_row["4コーナー順位"]
    if pd.isna(corner4):
        return "-"
    text = f"{int(corner4)}{unit}"
    kyakushitsu = kyakushitsu_display(horse_row)
    if kyakushitsu:
        text += f" ({KYAKUSHITSU_SHORT[kyakushitsu]})"
    return text


def format_halon(horse_row: pd.Series, result_df: pd.DataFrame) -> str:
    """後3ハロンのタイムと、レース内の上がり順位を文字列に整形する。

    Args:
        horse_row (pd.Series): 馬毎レース結果の行。
        result_df (pd.DataFrame): 全馬のresult DataFrame。

    Returns:
        str: 例: "35.8秒 (9位)"。後3ハロンが無い場合は "-"。
    """
    halon = horse_row["後3ハロン"]
    if pd.isna(halon):
        return "-"
    return f"{float(halon):.1f}秒 ({halon_rank(horse_row, result_df)}位)"
