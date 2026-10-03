"""前日の傾向記事の本文を生成するモジュール。"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd
from evaluation import evaluate_race_dynamics, make_time_plot
from keiba_data_interface import DataInterface
from keiba_domain import keibajo_from_code
from matplotlib.figure import Figure
from mykeibadb import RaceGetter
from race_data import RaceData

from g1_predict.modules.constants import GRADE_CODE_DISPLAY, TRACK_CODE_TO_SHIBA_DA

_KYOSO_JOKEN_CODE_DISPLAY: dict[str, str] = {
    "701": "新馬",
    "703": "未勝利",
    "005": "1勝クラス",
    "010": "2勝クラス",
    "016": "3勝クラス",
    "999": "オープン",
}


@dataclass(frozen=True)
class PrevDayTrendBody:
    """前日の傾向記事の本文と画像。

    Attributes:
        text (str): 記事本文（Markdown）。対象レースが1件もない場合は空文字列。
        images (dict[str, Figure]): 記事ディレクトリからの相対パス
            （例: "img/prev_day/xxx.png"）から、展開評価の標準化散布図への
            マッピング。対象レースが1件もない、または全レースが展開評価の
            対象外の場合は空辞書。
    """

    text: str
    images: dict[str, Figure]


@dataclass(frozen=True)
class _MatchedRace:
    """前日にマッチした1レース分のデータ。

    Attributes:
        prev_race_code (str): 前日レースのrace_code。
        race_info (pd.DataFrame): 前日レースの基本情報DataFrame（日本語カラム名）。
        result_df (pd.DataFrame): 前日レースの結果DataFrame（日本語カラム名）。
        cor_df (pd.DataFrame | None): 展開評価の相関係数DataFrame（1行）。
            展開評価の対象外レースはNone。
        figure (Figure | None): 展開評価の標準化散布図。展開評価の対象外レースはNone。
    """

    prev_race_code: str
    race_info: pd.DataFrame
    result_df: pd.DataFrame
    cor_df: pd.DataFrame | None
    figure: Figure | None


def build_prev_day_trend_body(
    race_code: str,
    race_info: pd.DataFrame,
) -> PrevDayTrendBody:
    """前日の傾向記事の本文を生成する。

    対象レースの前日に同競馬場・同芝ダで行われたレースの上位3頭を列挙する。
    本文は `## 出目` `## 展開` `## 各レース` の3セクションから構成され、
    H1見出しは含まない。画像は展開評価の標準化散布図で、対象外レース
    （1000m直線コース）には生成しない。

    Args:
        race_code (str): 16桁レースコード。
        race_info (pd.DataFrame): 対象レースの基本情報DataFrame（raw英語カラム名）。

    Returns:
        PrevDayTrendBody: 前日の傾向記事の本文と画像。対象レースが1件もない場合は
            本文が空文字列、画像は空辞書。
    """
    di = DataInterface("mykeibadb")
    keibajo_code = str(race_info["keibajo_code"].iloc[0])
    track_code = str(race_info["track_code"].iloc[0]).strip()
    target_shiba_da = TRACK_CODE_TO_SHIBA_DA.get(track_code, "")

    year = int(race_code[0:4])
    mmdd = race_code[4:8]
    race_date = datetime.strptime(f"{year}{mmdd}", "%Y%m%d").date()
    prev_date = race_date - timedelta(days=1)

    matched = _get_prev_day_matched_races(prev_date, keibajo_code, target_shiba_da)
    if matched.empty:
        return PrevDayTrendBody(text="", images={})

    venue_name = keibajo_from_code(keibajo_code)

    matched_races: list[_MatchedRace] = []
    for _, raw_row in matched.iterrows():
        prev_race_code = str(raw_row["race_code"])
        prev_race_info = di.get_race_basic_info(prev_race_code)
        result_df = di.get_result(prev_race_code)
        cor_df, figure = _evaluate_race_dynamics(prev_race_code, di, race_date)
        matched_races.append(
            _MatchedRace(prev_race_code, prev_race_info, result_df, cor_df, figure)
        )

    top3_entries: list[tuple[pd.Series, pd.DataFrame]] = []
    for race in matched_races:
        result_df = race.result_df
        top3 = result_df[result_df["確定着順"].isin([1, 2, 3])].sort_values("確定着順")
        for _, horse_row in top3.iterrows():
            top3_entries.append((horse_row, result_df))

    blocks: list[str] = [
        _build_dememe_section(top3_entries),
        "",
        _build_dynamics_section(matched_races, venue_name),
        "",
        "## 各レース",
        "",
    ]

    for race in matched_races:
        blocks.append(_format_race_block(race, venue_name))
        blocks.append("")

    images = {
        f"img/prev_day/{race.prev_race_code}.png": race.figure
        for race in matched_races
        if race.figure is not None
    }

    return PrevDayTrendBody(text="\n".join(blocks), images=images)


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
        lambda tc: TRACK_CODE_TO_SHIBA_DA.get(str(tc).strip(), "")
    )
    raw = raw[shiba_da_series == shiba_da]

    return raw.sort_values("race_bango").reset_index(drop=True)


def _evaluate_race_dynamics(
    prev_race_code: str,
    data_interface: DataInterface,
    target_race_date: date,
) -> tuple[pd.DataFrame | None, Figure | None]:
    """前日レースの展開評価を計算する。

    RaceDataを1回だけ取得し、相関係数の計算と標準化散布図の生成の両方に使い回す。
    未来レースの判定基準日を対象レースの開催日にすることで、前日レースの当日中
    （対象レースの前日）でも前日レースを確定済みのレースとして評価する。
    1000m直線コースは展開評価の対象外のため、両方Noneを返す。
    展開評価が使うのはレース結果とコーナー通過順のみのため、払戻情報は取得しない。

    Args:
        prev_race_code (str): 前日レースのrace_code。
        data_interface (DataInterface): 展開評価に使うDataInterface。
        target_race_date (date): 対象レースの開催日。未来レース判定の基準日に使う。

    Returns:
        pd.DataFrame | None: 展開評価の相関係数DataFrame（1行）。対象外レースはNone。
        Figure | None: 標準化散布図。対象外レースはNone。

    Raises:
        CornerDataError: レース結果情報または4コーナーの通過順データが存在しない場合。
    """
    race_data = RaceData(
        race_code=prev_race_code,
        data_interface=data_interface,
        reference_date=target_race_date,
    )
    if race_data.is_straight_race():
        return None, None

    race_data.fetch_race_result()
    race_data.fetch_race_result_info()
    result = evaluate_race_dynamics(race_data)
    figure = make_time_plot(race_data)
    return result.cor_df, figure


def _race_label(race_info: pd.DataFrame, venue_name: str, race_no: int) -> str:
    """レースラベル（{競馬場}{R}R {条件}(グレード)）を生成する。

    Args:
        race_info (pd.DataFrame): レース基本情報DataFrame。
        venue_name (str): 競馬場表示名。
        race_no (int): レース番号。

    Returns:
        str: レースラベル文字列。
    """
    condition = _race_condition(race_info)
    grade_code = str(race_info["グレードコード"].iloc[0])
    grade_display = GRADE_CODE_DISPLAY.get(grade_code, "")

    if grade_display:
        return f"{venue_name}{race_no}R {condition}({grade_display})"
    return f"{venue_name}{race_no}R {condition}"


def _race_condition(race_info: pd.DataFrame) -> str:
    """競走条件の表示名を返す。

    競走条件名称があればそれを使い、無ければ競走条件コードから表示名を引く。

    Args:
        race_info (pd.DataFrame): レース基本情報DataFrame。

    Returns:
        str: 競走条件の表示名。
    """
    cond_raw = race_info["競走条件名称"].iloc[0]
    if pd.notna(cond_raw) and str(cond_raw).strip():
        return str(cond_raw).strip()
    joken_code_raw = race_info["競走条件コード"].iloc[0]
    joken_code = str(joken_code_raw) if pd.notna(joken_code_raw) else ""
    return _KYOSO_JOKEN_CODE_DISPLAY.get(joken_code, "")


def _format_correlation(cor_df: pd.DataFrame | None, column: str) -> str:
    """相関係数を符号付き小数2桁の文字列に整形する。

    Args:
        cor_df (pd.DataFrame | None): 展開評価の相関係数DataFrame（1行）。
            対象外レースはNone。
        column (str): カラム名（差し有利度 / 外枠有利度 / 外有利度）。

    Returns:
        str: 符号付き小数2桁の文字列。NaN、または対象外レースは "-"。
    """
    if cor_df is None:
        return "-"
    value = cor_df[column].iloc[0]
    if pd.isna(value):
        return "-"
    # 0に丸まる負の値を "-0.00" と表示しないよう、丸めてから -0.0 を 0.0 に正規化する
    return f"{round(float(value), 2) + 0.0:+.2f}"


def _build_dynamics_section(matched_races: list[_MatchedRace], venue_name: str) -> str:
    """展開セクションを生成する。

    Args:
        matched_races (list[_MatchedRace]): 前日にマッチしたレースのリスト。
        venue_name (str): 競馬場表示名。

    Returns:
        str: 展開セクション文字列（## 展開から始まる）。
    """
    lines: list[str] = [
        "## 展開",
        "",
        "差し有利度・外枠有利度・外有利度は、それぞれ4角通過位置・馬番・コーナーでの"
        "内外の位置と走破タイムの相関係数。正なら差し・外枠・外を回した馬が有利。",
        "",
        "| レース | 差し有利度 | 外枠有利度 | 外有利度 |",
        "| --- | --- | --- | --- |",
    ]
    for race in matched_races:
        race_no = int(race.race_info["レース番号"].iloc[0])
        label = _race_label(race.race_info, venue_name, race_no)
        sashi = _format_correlation(race.cor_df, "差し有利度")
        soto_waku = _format_correlation(race.cor_df, "外枠有利度")
        soto = _format_correlation(race.cor_df, "外有利度")
        lines.append(f"| {label} | {sashi} | {soto_waku} | {soto} |")
    return "\n".join(lines)


def _format_race_block(race: _MatchedRace, venue_name: str) -> str:
    """1レース分のトレンドブロックを生成する。

    Args:
        race (_MatchedRace): 前日にマッチした1レース分のデータ。
        venue_name (str): 競馬場表示名（例: "東京"）。

    Returns:
        str: フォーマットされたレースブロック文字列。
    """
    race_no = int(race.race_info["レース番号"].iloc[0])
    label = _race_label(race.race_info, venue_name, race_no)
    distance = int(race.race_info["距離"].iloc[0])
    runners = len(race.result_df)
    heading = f"### {label} {distance}m {runners}頭"

    top3 = race.result_df[race.result_df["確定着順"].isin([1, 2, 3])].sort_values("確定着順")

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
            rank_str = f"{_halon_rank(horse_row, race.result_df)}位"
        else:
            halon_str = "-"
            rank_str = "-"

        cols = [
            f"{place}着", f"{gate}枠", f"{horse_no}番", f"{ninki}人気",
            corner4_str, halon_str, rank_str,
        ]
        lines.append("| " + " | ".join(cols) + " |")

    if race.figure is not None:
        image_path = f"img/prev_day/{race.prev_race_code}.png"
        lines.append("")
        lines.append(f"![{venue_name}{race_no}R 標準化散布図]({image_path})")

    return "\n".join(lines)


def _build_dememe_section(top3_entries: list[tuple[pd.Series, pd.DataFrame]]) -> str:
    """前日全レースの出目集計セクションを生成する。

    Args:
        top3_entries (list[tuple[pd.Series, pd.DataFrame]]): (horse_row, result_df) のリスト。

    Returns:
        str: 出目セクション文字列（## 出目から始まる）。
    """
    rows = [row for row, _ in top3_entries]

    ninki_vals = [f"{c}頭" for c in _count_ninki(rows)]
    waku_vals = [f"{_count_waku(rows).get(i, 0)}頭" for i in range(1, 9)]
    kyaku_counts = _count_kyakushitsu(rows)
    kyaku_vals = [f"{kyaku_counts.get(k, 0)}頭" for k in ["逃", "先", "差", "追"]]
    agari_vals = [f"{c}頭" for c in _count_agari_rank(top3_entries)]

    lines: list[str] = [
        "## 出目",
        "",
        "3着以内に入った頭数",
        "",
        "**人気**",
        "",
        "| 1人気 | 2人気 | 3人気 | 4-6人気 | 7-9人気 | 10人気以下 |",
        "| --- | --- | --- | --- | --- | --- |",
        "| " + " | ".join(ninki_vals) + " |",
        "",
        "**枠番**",
        "",
        "| 1枠 | 2枠 | 3枠 | 4枠 | 5枠 | 6枠 | 7枠 | 8枠 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        "| " + " | ".join(waku_vals) + " |",
        "",
        "**脚質**",
        "",
        "| 逃げ | 先行 | 差し | 追込 |",
        "| --- | --- | --- | --- |",
        "| " + " | ".join(kyaku_vals) + " |",
        "",
        "**上がり順位**",
        "",
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
