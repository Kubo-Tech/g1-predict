"""出走馬の過去走の展開評価記事の本文を生成するモジュール。"""

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from evaluation import RaceDynamicsResult
from keiba_data_interface import DataInterface
from keiba_data_interface.utils.race_code import race_code_to_race_id
from keiba_domain import CENTRAL_KEIBAJO_CODES, RaceShubetsu
from matplotlib.figure import Figure
from mykeibadb import RaceGetter
from mykeibadb.analytics import get_race_display_names
from race_data import RaceData

from g1_predict.modules.utils.race_dynamics import (
    DYNAMICS_DESCRIPTION,
    TOTAL_EVALUATION_DESCRIPTION,
    build_dynamics_table_lines,
    evaluate_race_dynamics_with_plot,
    make_total_evaluation_chart,
)
from g1_predict.modules.utils.race_result import grade_display, race_display_name

# 標準化散布図と展開評価値の棒グラフを保存する、記事ディレクトリからの相対ディレクトリ
_IMAGE_DIR = "img/past_dynamics"
_NETKEIBA_RESULT_URL = "https://race.netkeiba.com/race/result.html?race_id={race_id}"
_STRAIGHT_RACE_NOTE = "1000m直線コースのため展開評価の対象外。"
_NO_PAST_RACE_NOTE = "中央の平地で出走した過去走なし。"
_SUMMARY_TEXT = "過去走の展開評価を開く"
# 出走取消・発走除外・競走除外の異常区分コード
_NOT_STARTED_IJO_CODES: frozenset[str] = frozenset({"1", "2", "3"})


@dataclass(frozen=True)
class PastRaceDynamicsBody:
    """出走馬の過去走の展開評価記事の本文と画像。

    Attributes:
        text (str): 記事本文（Markdown）。H1見出しは含まない。
        images (dict[str, Figure]): 記事ディレクトリからの相対パス
            （例: "img/past_dynamics/xxx.png"）から画像へのマッピング。
            標準化散布図は、同じ過去走が出走馬を複数含んでいても1枚。
            展開評価値の棒グラフは、強調する馬が違うため過去走と出走馬の組ごとに1枚。
    """

    text: str
    images: dict[str, Figure]


@dataclass(frozen=True)
class _PastRace:
    """展開評価を終えた過去走1レース分のデータ。

    Attributes:
        race_code (str): 過去走のrace_code。
        title (str): 見出し行（日付・レース名へのリンク・グレード）。
        result_df (pd.DataFrame): 過去走のレース結果DataFrame。
        dynamics (RaceDynamicsResult | None): 展開評価の結果。1000m直線コースはNone。
        figure (Figure | None): 標準化散布図。1000m直線コースはNone。
    """

    race_code: str
    title: str
    result_df: pd.DataFrame
    dynamics: RaceDynamicsResult | None
    figure: Figure | None


def build_past_race_dynamics_body(
    race_code: str,
    num_past_races: int = 5,
) -> PastRaceDynamicsBody:
    """出走馬の過去走の展開評価記事の本文を生成する。

    出走馬を馬番順に並べ、馬ごとに折りたたみ要素の中へ、中央の平地で出走した
    直近の過去走の展開評価（有利度の表・標準化散布図・展開評価値の棒グラフ）を新しい順に載せる。
    同じ過去走が複数の出走馬に出てくる場合は、展開評価を1回だけ行って使い回す。

    Args:
        race_code (str): 対象レースの16桁レースコード。
        num_past_races (int): 馬ごとに載せる過去走の数。

    Returns:
        PastRaceDynamicsBody: 記事本文（H1見出しを除く）と画像。

    Raises:
        CornerDataError: 過去走のレース結果情報または4コーナーの通過順データが存在しない場合。
    """
    data_interface = DataInterface("mykeibadb")
    race_date = datetime.strptime(race_code[0:8], "%Y%m%d").date()
    race_data = RaceData(race_code, data_interface, reference_date=race_date)
    race_data.fetch_past_performances()
    race_data.fetch_past_race_basic_info()

    horses = race_data.entry_df.set_index(race_data.entry_df["馬番"].astype(int))
    horse_ids = {
        umaban: str(horses.loc[umaban, "血統登録番号"]).strip()
        for umaban in race_data.valid_horse_num
    }
    selected = {
        umaban: _select_past_race_codes(race_data, umaban, num_past_races)
        for umaban in race_data.valid_horse_num
    }
    past_races = _evaluate_past_races(race_data, selected, data_interface)

    images = {
        _image_path(past_race.race_code): past_race.figure
        for past_race in past_races.values()
        if past_race.figure is not None
    }
    lines = [DYNAMICS_DESCRIPTION, "", TOTAL_EVALUATION_DESCRIPTION, ""]
    for umaban in race_data.valid_horse_num:
        horse_name = str(horses.loc[umaban, "馬名"]).strip()
        other_ids = {horse_id for num, horse_id in horse_ids.items() if num != umaban}
        horse_races = [(runs_ago, past_races[code]) for runs_ago, code in selected[umaban]]
        args = (umaban, horse_name, horse_ids[umaban], other_ids, horse_races)
        horse_lines, horse_images = _build_horse_details_lines(*args)
        lines.extend(horse_lines)
        lines.append("")
        images.update(horse_images)

    return PastRaceDynamicsBody(text="\n".join(lines), images=images)


def _select_past_race_codes(
    race_data: RaceData, umaban: int, num_past_races: int
) -> list[tuple[int, str]]:
    """馬の直近の過去走のうち、展開評価を載せるレースを新しい順に選ぶ。

    何走前かは、地方・海外・障害を含めて実際に出走したレースで数える。出走取消・発走除外・
    競走除外のレースと、レース自体が成立していない（結果が無い）レースは走数に数えない。
    そのうち中央の平地のレースだけを、num_past_races 件まで選ぶ。

    Args:
        race_data (RaceData): 対象レースのRaceData（過去成績・過去走の基本情報を取得済み）。
        umaban (int): 馬番。
        num_past_races (int): 選ぶ過去走の数。

    Returns:
        list[tuple[int, str]]: (何走前, 過去走のrace_code) のリスト（新しい順）。
    """
    pp_df = race_data.past_performances_dict[umaban]
    basic_info = race_data.past_race_basic_info_df.set_index("レースコード")
    ijo_codes = pp_df["異常区分コード"].astype(str).str.strip()
    # 結果が1件も無いレース（開催中止など）は、確定着順が無く異常区分も正常のまま
    held = pp_df["確定着順"].notna() | (ijo_codes != "0")
    started = held & ~ijo_codes.isin(_NOT_STARTED_IJO_CODES)
    pp_df = pp_df[started].sort_values("レースコード", ascending=False)

    selected: list[tuple[int, str]] = []
    for runs_ago, (_, row) in enumerate(pp_df.iterrows(), start=1):
        code = str(row["レースコード"])
        if str(row["競馬場コード"]).strip() not in CENTRAL_KEIBAJO_CODES:
            continue
        if basic_info.loc[code, "レース種別"] != RaceShubetsu.HEICHI:
            continue
        selected.append((runs_ago, code))
        if len(selected) == num_past_races:
            break
    return selected


def _evaluate_past_races(
    race_data: RaceData,
    selected: dict[int, list[tuple[int, str]]],
    data_interface: DataInterface,
) -> dict[str, _PastRace]:
    """選ばれた過去走を、重複を除いて1レースずつ展開評価する。

    Args:
        race_data (RaceData): 対象レースのRaceData（過去走の基本情報を取得済み）。
        selected (dict[int, list[tuple[int, str]]]): 馬番 → (何走前, 過去走のrace_code) のリスト。
        data_interface (DataInterface): 展開評価に使うDataInterface。

    Returns:
        dict[str, _PastRace]: 過去走のrace_code → 展開評価を終えた過去走。
    """
    race_codes = list(
        dict.fromkeys(code for horse_races in selected.values() for _, code in horse_races)
    )
    basic_info = race_data.past_race_basic_info_df.set_index("レースコード", drop=False)
    unified_names = get_race_display_names(RaceGetter().connection_manager, race_codes)

    past_races: dict[str, _PastRace] = {}
    for code in race_codes:
        race_info = basic_info.loc[[code]].reset_index(drop=True)
        dynamics, figure = evaluate_race_dynamics_with_plot(
            code, data_interface, race_data.reference_date
        )
        past_races[code] = _PastRace(
            race_code=code,
            title=_build_race_title(code, race_info, unified_names),
            result_df=data_interface.get_result(code),
            dynamics=dynamics,
            figure=figure,
        )
    return past_races


def _build_race_title(
    race_code: str,
    race_info: pd.DataFrame,
    unified_names: dict[str, str],
) -> str:
    """過去走の見出し行を生成する。

    Args:
        race_code (str): 過去走のrace_code。
        race_info (pd.DataFrame): 過去走のレース基本情報DataFrame（1行）。
        unified_names (dict[str, str]): race_code → 統一した競走名本題。

    Returns:
        str: `{年}年{月}月{日}日 [{レース名}]({結果ページのURL}) ({グレード})`。
            グレードが無いレースは括弧を付けない。
    """
    race_date = datetime.strptime(race_code[0:8], "%Y%m%d")
    url = _NETKEIBA_RESULT_URL.format(race_id=race_code_to_race_id(race_code))
    name = race_display_name(race_info, unified_names)
    title = f"{race_date.year}年{race_date.month}月{race_date.day}日 [{name}]({url})"
    grade = grade_display(race_info)
    if grade:
        title += f" ({grade})"
    return title


def _build_horse_details_lines(
    umaban: int,
    horse_name: str,
    horse_id: str,
    other_horse_ids: set[str],
    horse_races: list[tuple[int, _PastRace]],
) -> tuple[list[str], dict[str, Figure]]:
    """1頭分のセクション（馬名のh2見出しと、過去走を収めた折りたたみ要素）を生成する。

    `<details>` の直後と `</details>` の直前に空行を入れる。空行が無いと、
    はてなブログで中のMarkdownが変換されない。

    Args:
        umaban (int): 馬番。
        horse_name (str): 馬名。
        horse_id (str): 馬の血統登録番号。
        other_horse_ids (set[str]): 対象レースの他の出走馬の血統登録番号。
        horse_races (list[tuple[int, _PastRace]]): (何走前, 過去走) のリスト（新しい順）。

    Returns:
        list[str]: Markdownの行リスト。
        dict[str, Figure]: 記事ディレクトリからの相対パス → 展開評価値の棒グラフ。
    """
    images: dict[str, Figure] = {}
    lines = [
        f"## {umaban}. {horse_name}",
        "",
        f"<details><summary>{_SUMMARY_TEXT}</summary>",
        "",
    ]
    if not horse_races:
        lines.extend([_NO_PAST_RACE_NOTE, ""])
    for runs_ago, past_race in horse_races:
        past_race_lines, chart = _build_past_race_lines(
            umaban, runs_ago, past_race, horse_id, other_horse_ids
        )
        lines.extend(past_race_lines)
        lines.append("")
        if chart is not None:
            images[_chart_image_path(past_race.race_code, umaban)] = chart
    lines.append("</details>")
    return lines, images


def _build_past_race_lines(
    umaban: int,
    runs_ago: int,
    past_race: _PastRace,
    horse_id: str,
    other_horse_ids: set[str],
) -> tuple[list[str], Figure | None]:
    """過去走1レース分の行リストと、展開評価値の棒グラフを生成する。

    Args:
        umaban (int): 折りたたみの主の馬の、対象レースでの馬番。
        runs_ago (int): 何走前か。
        past_race (_PastRace): 展開評価を終えた過去走。
        horse_id (str): 折りたたみの主の馬の血統登録番号。
        other_horse_ids (set[str]): 対象レースの他の出走馬の血統登録番号。

    Returns:
        list[str]: Markdownの行リスト（末尾に空行は含まない）。
        Figure | None: 展開評価値の棒グラフ。1000m直線コースはNone。
    """
    lines = [f"### {runs_ago}走前: {past_race.title}", ""]
    dynamics = past_race.dynamics
    if dynamics is None:
        lines.append(_STRAIGHT_RACE_NOTE)
        return lines, None
    result_df = past_race.result_df
    ids = result_df["血統登録番号"].astype(str).str.strip()
    highlight = result_df.loc[ids == horse_id, "馬番"].astype(int).tolist()
    name_bold = result_df.loc[ids.isin(other_horse_ids), "馬番"].astype(int).tolist()
    chart = make_total_evaluation_chart(dynamics.eval_df, result_df, highlight, name_bold)
    lines.extend(
        [
            *build_dynamics_table_lines(dynamics.cor_df),
            "",
            f"![標準化散布図]({_image_path(past_race.race_code)})",
            "",
            f"![展開評価値]({_chart_image_path(past_race.race_code, umaban)})",
        ]
    )
    return lines, chart


def _image_path(race_code: str) -> str:
    """標準化散布図の記事ディレクトリからの相対パスを返す。

    Args:
        race_code (str): 過去走のrace_code。

    Returns:
        str: 相対パス。
    """
    return f"{_IMAGE_DIR}/{race_code}.png"


def _chart_image_path(race_code: str, umaban: int) -> str:
    """展開評価値の棒グラフの記事ディレクトリからの相対パスを返す。

    Args:
        race_code (str): 過去走のrace_code。
        umaban (int): 折りたたみの主の馬の、対象レースでの馬番。

    Returns:
        str: 相対パス。
    """
    return f"{_IMAGE_DIR}/{race_code}_{umaban}.png"
