"""同じG1の過去の開催の展開をまとめた記事の本文を生成するモジュール。"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd
from evaluation import RaceDynamicsResult
from keiba_data_interface import DataInterface
from keiba_domain import keibajo_from_code
from matplotlib.figure import Figure
from mykeibadb.connection import ConnectionManager

from g1_predict.modules.utils.course_days import fetch_course_days
from g1_predict.modules.utils.race_dynamics import (
    DYNAMICS_COLUMNS,
    DYNAMICS_DESCRIPTION,
    HistoryPoint,
    build_dynamics_table_lines,
    evaluate_race_dynamics_with_plot,
    make_dynamics_history_chart,
    make_total_evaluation_chart,
)
from g1_predict.modules.utils.race_history import (
    TrendContext,
    build_race_context,
    fetch_past_races,
)

# 画像を保存する、記事ディレクトリからの相対ディレクトリ
_IMAGE_DIR = "img/dynamics_history"
_HISTORY_CHART_PATH = f"{_IMAGE_DIR}/dynamics.png"
# 推移の折れ線グラフの点の塗りつぶしと白抜きの説明
_TRACK_MARK_DESCRIPTION = (
    "グラフの点は、塗りつぶし（●）が良馬場、白抜き（○）が稍重・重・不良で行われた年。"
)
# 馬場状態コード -> 馬場状態の名称
_BABAJOTAI_NAMES: dict[str, str] = {"1": "良", "2": "稍重", "3": "重", "4": "不良"}
_GOOD_BABAJOTAI_CODE = "1"
# 通過タイムを求める地点（m）
_PASSAGE_DISTANCE = 1000
# 1ラップの標準の長さ（m）
_LAP_LENGTH = 200
# race_shosai のラップ列の数
_LAP_COLUMN_COUNT = 25
# 0.1秒単位で数えた1分
_TENTHS_PER_MINUTE = 600


@dataclass(frozen=True)
class DynamicsHistoryBody:
    """過去の展開記事の本文と画像。

    Attributes:
        content (str): タイトルを含む記事全文の Markdown。
        images (dict[str, Figure]): 記事ディレクトリからの相対パス -> 画像。
    """

    content: str
    images: dict[str, Figure]


@dataclass(frozen=True)
class _YearEvaluation:
    """集計対象の1年分の展開評価と表示に使う値。

    Attributes:
        race_code (str): 集計対象のレースのレースコード。
        year (int): 開催年。
        heading (str): 年ごとの節の見出し（`## ` を含む）。
        win_time (str): 表示用の勝ちタイム。
        passage_time (str): 表示用の1000m通過タイム。
        is_good_track (bool): 良馬場か。
        dynamics (RaceDynamicsResult): 展開評価の結果。
        figure (Figure): 標準化散布図。
        result_df (pd.DataFrame): レース結果。
    """

    race_code: str
    year: int
    heading: str
    win_time: str
    passage_time: str
    is_good_track: bool
    dynamics: RaceDynamicsResult
    figure: Figure
    result_df: pd.DataFrame


def format_race_time(tenths: int) -> str:
    """0.1秒単位のタイムを表示用の文字列にする。

    Args:
        tenths (int): 0.1秒単位のタイム（例: 1183）。

    Returns:
        str: 1分以上は `1:58.3`、1分未満は `59.9` の形式の文字列。
    """
    minutes, rest = divmod(tenths, _TENTHS_PER_MINUTE)
    seconds, tenth = divmod(rest, 10)
    if minutes == 0:
        return f"{seconds}.{tenth}"
    return f"{minutes}:{seconds:02d}.{tenth}"


def parse_soha_time(soha_time: str) -> int:
    """race 結果の走破タイム（MSSS 形式）を0.1秒単位に直す。

    Args:
        soha_time (str): MSSS 形式の走破タイム（例: "1583"）。

    Returns:
        int: 0.1秒単位のタイム（例: 1183）。

    Raises:
        ValueError: 3〜4桁の数字でない場合。
    """
    text = soha_time.strip()
    if not text.isdigit() or not 3 <= len(text) <= 4:
        raise ValueError(f"走破タイムは3〜4桁の数字で指定してください: {soha_time!r}")
    value = int(text)
    return (value // 1000) * _TENTHS_PER_MINUTE + (value % 1000)


def calc_passage_1000m(distance: int, laps: Sequence[int]) -> int:
    """ラップから1000m通過タイムを求める。

    最初のラップは距離を200で割った余り（余りが0なら200m）の長さで、以降は200mずつとする。
    1000m地点がラップの区切りに当たらない場合は、1000m地点を含むラップを距離で案分する。
    案分した値は0.1秒単位に四捨五入する。

    Args:
        distance (int): レースの距離（m）。
        laps (Sequence[int]): 0.1秒単位のラップ。先頭が最初のラップ。

    Returns:
        int: 0.1秒単位の1000m通過タイム。

    Raises:
        ValueError: ラップが1000m地点に届かない場合。1000m地点までのラップが0以下の場合。
    """
    first_length = distance % _LAP_LENGTH or _LAP_LENGTH
    lengths = [first_length] + [_LAP_LENGTH] * (len(laps) - 1)
    elapsed = 0
    run = 0
    for length, lap in zip(lengths, laps):
        if lap <= 0:
            raise ValueError(f"{run}m地点からのラップが記録されていません: distance={distance}")
        if run + length <= _PASSAGE_DISTANCE:
            elapsed += lap
            run += length
            if run == _PASSAGE_DISTANCE:
                return elapsed
            continue
        # 整数のまま四捨五入する（浮動小数点の丸め誤差を避ける）
        remaining = _PASSAGE_DISTANCE - run
        return elapsed + (lap * remaining * 2 + length) // (length * 2)
    raise ValueError(f"ラップが{_PASSAGE_DISTANCE}m地点に届きません: distance={distance}")


def build_section_heading(
    year: int, course_kubun: str, course_day: int | None, babajotai_code: str
) -> str:
    """年ごとの節の見出しを返す。

    Args:
        year (int): 開催年（西暦）。
        course_kubun (str): コース区分。空の場合はコース区分と何日目を出さない。
        course_day (int | None): コース区分の何日目か。コース区分が空の場合は None。
        babajotai_code (str): 馬場状態コード（"1"〜"4"）。

    Returns:
        str: `## 25年 Aコース7日目 (良)` の形式の見出し。

    Raises:
        ValueError: 馬場状態コードが "1"〜"4" でない場合。
            コース区分があるのに何日目が None の場合。
    """
    baba = _BABAJOTAI_NAMES.get(babajotai_code)
    if baba is None:
        raise ValueError(f"馬場状態コードが不正です: {babajotai_code!r}")
    prefix = f"## {year % 100:02d}年"
    if not course_kubun:
        return f"{prefix} ({baba})"
    if course_day is None:
        raise ValueError(f"コース区分があるのに何日目が不明です: year={year}")
    return f"{prefix} {course_kubun}コース{course_day}日目 ({baba})"


def build_dynamics_history(race_info: pd.DataFrame, race_label: str) -> DynamicsHistoryBody:
    """同じG1の過去の開催の展開をまとめた記事を生成する。

    冒頭に差し有利度・外枠有利度・外有利度の年ごとの推移の折れ線グラフを載せ、
    続けて集計対象の年を新しい順に、勝ちタイム・1000m通過・有利度の表・標準化散布図・
    展開評価値の棒グラフを載せる。展開評価の基準日は開催日の翌日にする。

    Args:
        race_info (pd.DataFrame): 今回のレースの基本情報（load_race_info() の戻り値）。
        race_label (str): 記事に出力するレース名。

    Returns:
        DynamicsHistoryBody: 記事全文と画像。

    Raises:
        ValueError: 集計対象のレースが1つも無い場合。集計対象のレースが展開評価の対象外
            （1000m直線コース）の場合。
        CornerDataError: 集計対象のレースの結果情報または4コーナーの通過順データが無い場合。
    """
    context = build_race_context(race_info)
    races = fetch_past_races(context.manager, context.condition)
    if races.empty:
        raise ValueError(
            f"集計対象のレースがありません: {race_label} {context.first_year}年〜"
            f"{context.race_year - 1}年"
        )
    data_interface = DataInterface("mykeibadb")
    race_codes = [str(code) for code in races["race_code"]]
    win_times = _fetch_win_times(context.manager, race_codes)
    laps = _fetch_laps(context.manager, race_codes)
    evaluations = [
        _evaluate_year(context, row, win_times, laps, data_interface)
        for _, row in races.iterrows()
    ]

    images: dict[str, Figure] = {}
    years = list(range(context.first_year, context.race_year))
    points = [
        HistoryPoint(
            evaluation.year,
            {
                column: float(evaluation.dynamics.cor_df[column].iloc[0])
                for column in DYNAMICS_COLUMNS
            },
            evaluation.is_good_track,
        )
        for evaluation in evaluations
    ]
    images[_HISTORY_CHART_PATH] = make_dynamics_history_chart(points, years)

    title = f"# 【{race_label}{context.race_year}】過去{context.years}年の展開"
    last_year = context.race_year - 1
    course = f"{keibajo_from_code(context.keibajo_code)}{context.shiba_da}{context.kyori}m"
    lines = [
        title,
        "",
        # 末尾の半角スペース2つで、次の文を改行して表示する
        f"過去{context.years}年（{context.first_year}年〜{last_year}年）の{race_label}の展開を"
        "まとめる。  ",
        f"集計対象は{course}で行われた{len(evaluations)}年分。",
        "",
        f"## 過去{context.years}年の推移",
        "",
        f"{DYNAMICS_DESCRIPTION}  ",
        _TRACK_MARK_DESCRIPTION,
        "",
        f"![過去{context.years}年の推移]({_HISTORY_CHART_PATH})",
    ]
    for evaluation in sorted(evaluations, key=lambda item: item.year, reverse=True):
        image_path = f"{_IMAGE_DIR}/{evaluation.race_code}.png"
        chart_path = f"{_IMAGE_DIR}/{evaluation.race_code}_evaluation.png"
        images[image_path] = evaluation.figure
        images[chart_path] = make_total_evaluation_chart(
            evaluation.dynamics.eval_df, evaluation.result_df
        )
        lines += [
            "",
            evaluation.heading,
            "",
            f"勝ちタイム: {evaluation.win_time}  ",
            f"1000m通過: {evaluation.passage_time}",
            "",
            *build_dynamics_table_lines(evaluation.dynamics.cor_df),
            "",
            f"![標準化散布図]({image_path})",
            "",
            f"![展開評価値]({chart_path})",
        ]
    return DynamicsHistoryBody(content="\n".join(lines) + "\n", images=images)


def _evaluate_year(
    context: TrendContext,
    race: pd.Series,
    win_times: dict[str, int],
    laps: dict[str, list[int]],
    data_interface: DataInterface,
) -> _YearEvaluation:
    """集計対象の1年分の展開評価と表示に使う値を求める。

    Args:
        context (TrendContext): 対象レースと集計対象の情報。
        race (pd.Series): fetch_past_races() の1行。
        win_times (dict[str, int]): レースコード -> 0.1秒単位の勝ちタイム。
        laps (dict[str, list[int]]): レースコード -> 0.1秒単位のラップ。
        data_interface (DataInterface): 展開評価に使う DataInterface。

    Returns:
        _YearEvaluation: 1年分の展開評価と表示に使う値。

    Raises:
        ValueError: 1000m直線コースの場合。勝ちタイムまたはラップが無い場合。
        CornerDataError: 結果情報または4コーナーの通過順データが無い場合。
    """
    race_code = str(race["race_code"])
    year = int(race["kaisai_nen"])
    course_kubun = str(race["course_kubun"])
    course_day: int | None = None
    if course_kubun:
        course_days = fetch_course_days(context.manager, str(race["keibajo_code"]), str(year))
        course_day = course_days[str(race["kaisai_gappi"])]
    race_date = datetime.strptime(race_code[0:8], "%Y%m%d").date()
    dynamics, figure = evaluate_race_dynamics_with_plot(
        race_code, data_interface, _reference_date(race_date)
    )
    if dynamics is None or figure is None:
        raise ValueError(f"1000m直線コースは展開評価の対象外です: {race_code}")
    if race_code not in win_times:
        raise ValueError(f"勝ちタイムがありません: {race_code}")
    if race_code not in laps:
        raise ValueError(f"ラップがありません: {race_code}")
    babajotai_code = str(race["babajotai_code"])
    return _YearEvaluation(
        race_code=race_code,
        year=year,
        heading=build_section_heading(year, course_kubun, course_day, babajotai_code),
        win_time=format_race_time(win_times[race_code]),
        passage_time=format_race_time(calc_passage_1000m(context.kyori, laps[race_code])),
        is_good_track=babajotai_code == _GOOD_BABAJOTAI_CODE,
        dynamics=dynamics,
        figure=figure,
        result_df=data_interface.get_result(race_code),
    )


def _reference_date(race_date: date) -> date:
    """展開評価の基準日を返す。開催日当日でも確定済みのレースとして評価するため翌日にする。

    Args:
        race_date (date): 開催日。

    Returns:
        date: 開催日の翌日。
    """
    return race_date + timedelta(days=1)


def _fetch_win_times(manager: ConnectionManager, race_codes: Sequence[str]) -> dict[str, int]:
    """確定着順1着の馬の走破タイムを返す。

    Args:
        manager (ConnectionManager): DB接続マネージャ。
        race_codes (Sequence[str]): 対象のレースコード。

    Returns:
        dict[str, int]: レースコード -> 0.1秒単位の勝ちタイム。同着の場合は最も速いタイム。
    """
    sql = """
        SELECT TRIM(u.race_code) AS race_code, TRIM(u.soha_time) AS soha_time
        FROM umagoto_race_joho u
        WHERE u.race_code = ANY(%s) AND TRIM(u.kakutei_chakujun) = '01'
    """
    df = manager.fetch_dataframe(sql, params=(list(race_codes),))
    result: dict[str, int] = {}
    for race_code, soha_time in zip(df["race_code"], df["soha_time"]):
        tenths = parse_soha_time(str(soha_time))
        result[str(race_code)] = min(tenths, result.get(str(race_code), tenths))
    return result


def _fetch_laps(manager: ConnectionManager, race_codes: Sequence[str]) -> dict[str, list[int]]:
    """レースごとの0.1秒単位のラップを返す。

    Args:
        manager (ConnectionManager): DB接続マネージャ。
        race_codes (Sequence[str]): 対象のレースコード。

    Returns:
        dict[str, list[int]]: レースコード -> 0.1秒単位のラップ（先頭が最初のラップ）。
            末尾のラップが記録されていない列は含めない。途中の記録されていない列は 0 になる。
    """
    columns = [f"lap_time{i}" for i in range(1, _LAP_COLUMN_COUNT + 1)]
    select_columns = ", ".join(f"TRIM(r.{column}) AS {column}" for column in columns)
    sql = f"""
        SELECT TRIM(r.race_code) AS race_code, {select_columns}
        FROM race_shosai r
        WHERE r.race_code = ANY(%s)
    """
    df = manager.fetch_dataframe(sql, params=(list(race_codes),))
    result: dict[str, list[int]] = {}
    for _, row in df.iterrows():
        values = [int(row[column]) if str(row[column]).strip() else 0 for column in columns]
        while values and values[-1] == 0:
            values.pop()
        result[str(row["race_code"])] = values
    return result
