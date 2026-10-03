"""出走馬の過去走の展開評価記事の本文を生成するモジュール。"""

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from evaluation import RaceDynamicsResult
from keiba_data_interface import DataInterface
from keiba_data_interface.utils.race_code import race_code_to_race_id
from keiba_domain import RaceShubetsu
from matplotlib.figure import Figure
from mykeibadb import RaceGetter
from mykeibadb.analytics import get_race_display_names
from race_data import RaceData

from g1_predict.modules.utils.race_dynamics import (
    DYNAMICS_DESCRIPTION,
    TOTAL_EVALUATION_DESCRIPTION,
    build_dynamics_table_lines,
    build_total_evaluation_table_lines,
    evaluate_race_dynamics_with_plot,
)
from g1_predict.modules.utils.race_result import grade_display, race_display_name

# 標準化散布図を保存する、記事ディレクトリからの相対ディレクトリ
_IMAGE_DIR = "img/past_dynamics"
_NETKEIBA_SHUTUBA_URL = "https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
_STRAIGHT_RACE_NOTE = "1000m直線コースのため展開評価の対象外。"
_NO_PAST_RACE_NOTE = "中央の平地で出走した過去走なし。"
# 出走取消・発走除外・競走除外の異常区分コード
_NOT_STARTED_IJO_CODES: frozenset[str] = frozenset({"1", "2", "3"})


@dataclass(frozen=True)
class PastRaceDynamicsBody:
    """出走馬の過去走の展開評価記事の本文と画像。

    Attributes:
        text (str): 記事本文（Markdown）。H1見出しは含まない。
        images (dict[str, Figure]): 記事ディレクトリからの相対パス
            （例: "img/past_dynamics/xxx.png"）から標準化散布図へのマッピング。
            同じ過去走は出走馬が複数いても1枚。
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
    直近の過去走の展開評価（有利度の表・標準化散布図・展開評価値の表）を新しい順に載せる。
    同じ過去走が複数の出走馬に出てくる場合は、展開評価を1回だけ行って使い回す。

    Args:
        race_code (str): 対象レースの16桁レースコード。
        num_past_races (int): 馬ごとに載せる過去走の数。

    Returns:
        PastRaceDynamicsBody: 記事本文（H1見出しを除く）と標準化散布図。

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

    lines = [DYNAMICS_DESCRIPTION, "", TOTAL_EVALUATION_DESCRIPTION, ""]
    for umaban in race_data.valid_horse_num:
        horse_name = str(horses.loc[umaban, "馬名"]).strip()
        other_ids = {horse_id for num, horse_id in horse_ids.items() if num != umaban}
        horse_races = [past_races[code] for code in selected[umaban]]
        args = (umaban, horse_name, horse_ids[umaban], other_ids, horse_races)
        lines.extend(_build_horse_details_lines(*args))
        lines.append("")

    images = {
        _image_path(past_race.race_code): past_race.figure
        for past_race in past_races.values()
        if past_race.figure is not None
    }
    return PastRaceDynamicsBody(text="\n".join(lines), images=images)


def _select_past_race_codes(race_data: RaceData, umaban: int, num_past_races: int) -> list[str]:
    """馬の直近の過去走のrace_codeを新しい順に選ぶ。

    対象レースより前に、中央の平地で実際に出走したレースだけを数える。
    出走取消・発走除外・競走除外のレースと、レース自体が成立していない（結果が無い）レース、
    障害レースは数えない。

    Args:
        race_data (RaceData): 対象レースのRaceData（過去成績・過去走の基本情報を取得済み）。
        umaban (int): 馬番。
        num_past_races (int): 選ぶ過去走の数。

    Returns:
        list[str]: 過去走のrace_codeのリスト（新しい順、最大num_past_races件）。
    """
    pp_df = race_data.get_filtered_past_performances(umaban)
    basic_info = race_data.past_race_basic_info_df.set_index("レースコード")
    ijo_codes = pp_df["異常区分コード"].astype(str).str.strip()
    # 結果が1件も無いレース（開催中止など）は、確定着順が無く異常区分も正常のまま
    held = pp_df["確定着順"].notna() | (ijo_codes != "0")
    started = held & ~ijo_codes.isin(_NOT_STARTED_IJO_CODES)
    pp_df = pp_df[started].sort_values("レースコード", ascending=False)

    codes: list[str] = []
    for code in pp_df["レースコード"].astype(str):
        if basic_info.loc[code, "レース種別"] != RaceShubetsu.HEICHI:
            continue
        codes.append(code)
        if len(codes) == num_past_races:
            break
    return codes


def _evaluate_past_races(
    race_data: RaceData,
    selected: dict[int, list[str]],
    data_interface: DataInterface,
) -> dict[str, _PastRace]:
    """選ばれた過去走を、重複を除いて1レースずつ展開評価する。

    Args:
        race_data (RaceData): 対象レースのRaceData（過去走の基本情報を取得済み）。
        selected (dict[int, list[str]]): 馬番 → 過去走のrace_codeのリスト。
        data_interface (DataInterface): 展開評価に使うDataInterface。

    Returns:
        dict[str, _PastRace]: 過去走のrace_code → 展開評価を終えた過去走。
    """
    race_codes = list(dict.fromkeys(code for codes in selected.values() for code in codes))
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
        str: `{年}年{月}月{日}日 [{レース名}]({出馬表URL}) ({グレード})`。
            グレードが無いレースは括弧を付けない。
    """
    race_date = datetime.strptime(race_code[0:8], "%Y%m%d")
    url = _NETKEIBA_SHUTUBA_URL.format(race_id=race_code_to_race_id(race_code))
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
    horse_races: list[_PastRace],
) -> list[str]:
    """1頭分の折りたたみ要素の行リストを生成する。

    `<details>` の直後と `</details>` の直前に空行を入れる。空行が無いと、
    はてなブログで中のMarkdownが変換されない。

    Args:
        umaban (int): 馬番。
        horse_name (str): 馬名。
        horse_id (str): 馬の血統登録番号。
        other_horse_ids (set[str]): 対象レースの他の出走馬の血統登録番号。
        horse_races (list[_PastRace]): 馬の過去走（新しい順）。

    Returns:
        list[str]: Markdownの行リスト。
    """
    lines = [f"<details><summary>{umaban}. {horse_name}</summary>", ""]
    if not horse_races:
        lines.extend([_NO_PAST_RACE_NOTE, ""])
    for past_race in horse_races:
        lines.extend(_build_past_race_lines(past_race, horse_id, other_horse_ids))
        lines.append("")
    lines.append("</details>")
    return lines


def _build_past_race_lines(
    past_race: _PastRace,
    horse_id: str,
    other_horse_ids: set[str],
) -> list[str]:
    """過去走1レース分の行リストを生成する。

    Args:
        past_race (_PastRace): 展開評価を終えた過去走。
        horse_id (str): 折りたたみの主の馬の血統登録番号。
        other_horse_ids (set[str]): 対象レースの他の出走馬の血統登録番号。

    Returns:
        list[str]: Markdownの行リスト（末尾に空行は含まない）。
    """
    lines = [past_race.title, ""]
    dynamics = past_race.dynamics
    if dynamics is None:
        lines.append(_STRAIGHT_RACE_NOTE)
        return lines
    result_df = past_race.result_df
    ids = result_df["血統登録番号"].astype(str).str.strip()
    bold_row = result_df.loc[ids == horse_id, "馬番"].astype(int).tolist()
    bold_name = result_df.loc[ids.isin(other_horse_ids), "馬番"].astype(int).tolist()
    lines.extend(
        [
            *build_dynamics_table_lines(dynamics.cor_df),
            "",
            f"![標準化散布図]({_image_path(past_race.race_code)})",
            "",
            *build_total_evaluation_table_lines(dynamics.eval_df, result_df, bold_row, bold_name),
        ]
    )
    return lines


def _image_path(race_code: str) -> str:
    """標準化散布図の記事ディレクトリからの相対パスを返す。

    Args:
        race_code (str): 過去走のrace_code。

    Returns:
        str: 相対パス。
    """
    return f"{_IMAGE_DIR}/{race_code}.png"
