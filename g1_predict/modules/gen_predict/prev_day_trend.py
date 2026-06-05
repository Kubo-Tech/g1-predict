"""前日の傾向セクションを生成するモジュール。"""

from datetime import date, datetime, timedelta

import pandas as pd
from keiba_data_interface import DataInterface
from keiba_data_interface.utils.race_code import keibajo_code_to_name
from mykeibadb import RaceGetter

_TRACK_CODE_TO_SHIBA_DA: dict[str, str] = {
    **{str(code): "芝" for code in range(10, 23)},
    **{str(code): "ダ" for code in range(23, 30)},
    **{str(code): "芝" for code in range(51, 60)},
}

_KYOSO_JOKEN_CODE_DISPLAY: dict[str, str] = {
    "701": "新馬",
    "703": "未勝利",
    "005": "1勝クラス",
    "010": "2勝クラス",
    "016": "3勝クラス",
    "999": "オープン",
}

GRADE_CODE_DISPLAY: dict[str, str] = {
    "A": "G1",
    "B": "G2",
    "C": "G3",
    "D": "重賞",
    "E": "特別",
    "F": "J・G1",
    "G": "J・G2",
    "H": "J・G3",
    "L": "L",
}


def build_prev_day_trend_section(
    race_code: str,
    race_info: pd.DataFrame,
    di: DataInterface,
) -> str:
    """前日の傾向セクションを生成する。

    対象レースの前日に同競馬場・同芝ダで行われたレースの上位3頭を列挙する。

    Args:
        race_code (str): 16桁レースコード。
        race_info (pd.DataFrame): 対象レースの基本情報DataFrame。
        di (DataInterface): DataInterface インスタンス。

    Returns:
        str: 前日の傾向セクション文字列。
    """
    keibajo_code = str(race_info["競馬場コード"].iloc[0])
    target_shiba_da = str(race_info["芝ダ"].iloc[0])

    year = int(race_code[0:4])
    mmdd = race_code[4:8]
    race_date = datetime.strptime(f"{year}{mmdd}", "%Y%m%d").date()
    prev_date = race_date - timedelta(days=1)

    matched = _get_prev_day_matched_races(prev_date, keibajo_code, target_shiba_da)
    if matched.empty:
        return "## 前日の傾向\n"

    venue_name = keibajo_code_to_name(keibajo_code)

    race_data: list[tuple[pd.DataFrame, pd.DataFrame]] = []
    for _, raw_row in matched.iterrows():
        prev_race_code = str(raw_row["race_code"])
        prev_race_info = di.get_race_basic_info(prev_race_code)
        result_df = di.get_result(prev_race_code)
        race_data.append((prev_race_info, result_df))

    top3_entries: list[tuple[pd.Series, pd.DataFrame]] = []
    for prev_race_info, result_df in race_data:
        top3 = result_df[result_df["確定着順"].isin([1, 2, 3])].sort_values("確定着順")
        for _, horse_row in top3.iterrows():
            top3_entries.append((horse_row, result_df))

    blocks: list[str] = ["## 前日の傾向", ""]
    blocks.append(_build_dememe_section(top3_entries))
    blocks.append("")

    for prev_race_info, result_df in race_data:
        blocks.append(_format_race_block(prev_race_info, result_df, venue_name))
        blocks.append("")

    return "\n".join(blocks)


def _get_prev_day_matched_races(
    prev_date: date,
    keibajo_code: str,
    shiba_da: str,
) -> pd.DataFrame:
    """前日の同競馬場・同芝ダのレース一覧を返す。

    Args:
        prev_date (date): 前日の日付。
        keibajo_code (str): 競馬場コード（例: "05"）。
        shiba_da (str): 芝ダ区分（"芝" または "ダ"）。

    Returns:
        pd.DataFrame: 条件一致したレースのraw RACE_SHOSAI DataFrame（race_bango昇順）。
    """
    rg = RaceGetter()
    raw = rg.get_race_shosai(start_date=prev_date, end_date=prev_date, convert_codes=False)

    if raw.empty:
        return raw

    keibajo_mask = raw["keibajo_code"].astype(str).str.strip() == keibajo_code
    raw = raw[keibajo_mask]

    if raw.empty:
        return raw

    # 障害コード（51-59）を除外し、平地の芝ダのみ対象とする
    barrier_codes = {str(code) for code in range(51, 60)}
    not_barrier = ~raw["track_code"].apply(lambda tc: str(tc).strip() in barrier_codes)
    raw = raw[not_barrier]

    shiba_da_series = raw["track_code"].apply(
        lambda tc: _TRACK_CODE_TO_SHIBA_DA.get(str(tc).strip(), "")
    )
    raw = raw[shiba_da_series == shiba_da]

    return raw.sort_values("race_bango").reset_index(drop=True)


def _format_race_block(
    race_info: pd.DataFrame,
    result_df: pd.DataFrame,
    venue_name: str,
) -> str:
    """1レース分のトレンドブロックを生成する。

    Args:
        race_info (pd.DataFrame): レース基本情報DataFrame。
        result_df (pd.DataFrame): レース結果DataFrame（全馬）。
        venue_name (str): 競馬場表示名（例: "東京"）。

    Returns:
        str: フォーマットされたレースブロック文字列。
    """
    race_no = int(race_info["レース番号"].iloc[0])
    grade_code = str(race_info["グレードコード"].iloc[0])
    grade_display = GRADE_CODE_DISPLAY.get(grade_code, "")

    cond_raw = race_info["競走条件名称"].iloc[0]
    if pd.notna(cond_raw) and str(cond_raw).strip():
        condition = str(cond_raw).strip()
    else:
        joken_code_raw = race_info["競走条件コード"].iloc[0]
        joken_code = str(joken_code_raw) if pd.notna(joken_code_raw) else ""
        condition = _KYOSO_JOKEN_CODE_DISPLAY.get(joken_code, "")

    distance = int(race_info["距離"].iloc[0])
    runners = len(result_df)

    if grade_display:
        heading = f"### {venue_name}{race_no}R {condition}({grade_display}) {distance}m {runners}頭"
    else:
        heading = f"### {venue_name}{race_no}R {condition} {distance}m {runners}頭"

    top3 = result_df[result_df["確定着順"].isin([1, 2, 3])].sort_values("確定着順")

    lines: list[str] = [
        heading,
        "",
        "| 着順 | 枠 | 馬番 | 人気 | 4角通過順位 | 後3ハロン | 後3ハロン順位 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, horse_row in top3.iterrows():
        place = int(horse_row["確定着順"])
        gate = int(horse_row["枠番"]) if pd.notna(horse_row["枠番"]) else "-"
        horse_no = int(horse_row["馬番"]) if pd.notna(horse_row["馬番"]) else "-"
        ninki = int(horse_row["単勝人気順"]) if pd.notna(horse_row["単勝人気順"]) else "-"

        corner4 = horse_row["4コーナー順位"]
        corner4_str = f"{int(corner4)}番手" if pd.notna(corner4) else "-"

        halon = horse_row["後3ハロン"]
        if pd.notna(halon):
            halon_str = f"{float(halon):.1f}秒"
            rank_str = f"{_halon_rank(horse_row, result_df)}位"
        else:
            halon_str = "-"
            rank_str = "-"

        cols = [
            f"{place}着", f"{gate}枠", f"{horse_no}番", f"{ninki}人気",
            corner4_str, halon_str, rank_str,
        ]
        lines.append("| " + " | ".join(cols) + " |")

    return "\n".join(lines)


def _build_dememe_section(top3_entries: list[tuple[pd.Series, pd.DataFrame]]) -> str:
    """前日全レースの出目集計セクションを生成する。

    Args:
        top3_entries (list[tuple[pd.Series, pd.DataFrame]]): (horse_row, result_df) のリスト。

    Returns:
        str: 出目セクション文字列（### 出目から始まる）。
    """
    rows = [row for row, _ in top3_entries]

    ninki_vals = [f"{c}頭" for c in _count_ninki(rows)]
    waku_vals = [f"{_count_waku(rows).get(i, 0)}頭" for i in range(1, 9)]
    kyaku_counts = _count_kyakushitsu(rows)
    kyaku_vals = [f"{kyaku_counts.get(k, 0)}頭" for k in ["逃", "先", "差", "追"]]
    agari_vals = [f"{c}頭" for c in _count_agari_rank(top3_entries)]

    lines: list[str] = [
        "### 出目",
        "",
        "3着以内に入った頭数",
        "",
        "**人気**",
        "| 1人気 | 2人気 | 3人気 | 4-6人気 | 7-9人気 | 10人気以下 |",
        "| --- | --- | --- | --- | --- | --- |",
        "| " + " | ".join(ninki_vals) + " |",
        "",
        "**枠番**",
        "| 1枠 | 2枠 | 3枠 | 4枠 | 5枠 | 6枠 | 7枠 | 8枠 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        "| " + " | ".join(waku_vals) + " |",
        "",
        "**脚質**",
        "| 逃げ | 先行 | 差し | 追込 |",
        "| --- | --- | --- | --- |",
        "| " + " | ".join(kyaku_vals) + " |",
        "",
        "**上がり順位**",
        "| 1位 | 2位 | 3位 | 4-6位 | 7-9位 | 10位以下 |",
        "| --- | --- | --- | --- | --- | --- |",
        "| " + " | ".join(agari_vals) + " |",
    ]
    return "\n".join(lines)


def _count_ninki(rows: list[pd.Series]) -> list[int]:
    """人気グループ[1人気,2人気,3人気,4-6,7-9,10以下]の頭数を返す。

    Args:
        rows (list[pd.Series]): 馬毎レース結果の行リスト。

    Returns:
        list[int]: 各グループの頭数リスト（6要素）。
    """
    counts = [0, 0, 0, 0, 0, 0]
    for row in rows:
        ninki = row["単勝人気順"]
        if pd.isna(ninki):
            continue
        ninki = int(ninki)
        if ninki == 1:
            counts[0] += 1
        elif ninki == 2:
            counts[1] += 1
        elif ninki == 3:
            counts[2] += 1
        elif 4 <= ninki <= 6:
            counts[3] += 1
        elif 7 <= ninki <= 9:
            counts[4] += 1
        else:
            counts[5] += 1
    return counts


def _count_waku(rows: list[pd.Series]) -> dict[int, int]:
    """枠番ごとの頭数を返す。

    Args:
        rows (list[pd.Series]): 馬毎レース結果の行リスト。

    Returns:
        dict[int, int]: 枠番（1-8）をキーとした頭数辞書。
    """
    counts: dict[int, int] = {i: 0 for i in range(1, 9)}
    for row in rows:
        waku = row["枠番"]
        if pd.isna(waku):
            continue
        waku_int = int(waku)
        if waku_int in counts:
            counts[waku_int] += 1
    return counts


def _count_kyakushitsu(rows: list[pd.Series]) -> dict[str, int]:
    """脚質（逃/先/差/追）ごとの頭数を返す。

    Args:
        rows (list[pd.Series]): 馬毎レース結果の行リスト。

    Returns:
        dict[str, int]: 脚質名をキーとした頭数辞書。
    """
    code_map = {"1": "逃", "2": "先", "3": "差", "4": "追"}
    counts: dict[str, int] = {"逃": 0, "先": 0, "差": 0, "追": 0}
    for row in rows:
        code = row.get("脚質判定コード", "")
        if pd.isna(code) or str(code).strip() == "":
            continue
        display = code_map.get(str(code).strip())
        if display:
            counts[display] += 1
    return counts


def _count_agari_rank(
    top3_entries: list[tuple[pd.Series, pd.DataFrame]],
) -> list[int]:
    """上がり順位グループ[1位,2位,3位,4-6,7-9,10以下]の頭数を返す。

    Args:
        top3_entries (list[tuple[pd.Series, pd.DataFrame]]): (horse_row, result_df) のリスト。

    Returns:
        list[int]: 各グループの頭数リスト（6要素）。
    """
    counts = [0, 0, 0, 0, 0, 0]
    for horse_row, result_df in top3_entries:
        halon = horse_row["後3ハロン"]
        if pd.isna(halon):
            continue
        rank = _halon_rank(horse_row, result_df)
        if rank == 1:
            counts[0] += 1
        elif rank == 2:
            counts[1] += 1
        elif rank == 3:
            counts[2] += 1
        elif 4 <= rank <= 6:
            counts[3] += 1
        elif 7 <= rank <= 9:
            counts[4] += 1
        else:
            counts[5] += 1
    return counts


def _halon_rank(horse_row: pd.Series, result_df: pd.DataFrame) -> int:
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
