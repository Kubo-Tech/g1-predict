"""レース結果の馬毎の行を記事の表示用に整形するユーティリティ。"""

import pandas as pd

# 脚質判定コード → 表示名
KYAKUSHITSU_DISPLAY: dict[str, str] = {"1": "逃げ", "2": "先行", "3": "差し", "4": "追込"}
# 脚質の表示名 → 表で使う1文字の略称
KYAKUSHITSU_SHORT: dict[str, str] = {"逃げ": "逃", "先行": "先", "差し": "差", "追込": "追"}


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
