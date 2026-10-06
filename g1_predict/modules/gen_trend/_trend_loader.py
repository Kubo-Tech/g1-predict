"""傾向計算に必要な DB コンテキストを構築するモジュール。"""

from dataclasses import dataclass, replace

import pandas as pd
from mykeibadb.analytics import RaceCondition
from mykeibadb.config import ConfigManager
from mykeibadb.connection import ConnectionManager

from g1_predict.modules.constants import TRACK_CODE_TO_SHIBA_DA

from ._trend_models import TREND_YEARS

# 傾向の集計対象にするグレード（G1）
_G1_GRADE_CODE = "A"


@dataclass(frozen=True)
class TrendContext:
    """傾向の集計に使う、対象レースと集計対象の情報。

    Attributes:
        manager (ConnectionManager): DB接続マネージャ。
        condition (RaceCondition): 集計対象のレース絞り込み条件。
        race_year (int): 対象レースの開催年。
        race_name (str): 対象レースの競走名本題。
        kyori (int): 対象レースの距離（m）。
        keibajo_code (str): 対象レースの競馬場コード。
        shiba_da (str): 対象レースの芝ダ。
        first_year (int): 集計対象の初年。
        years (int): 集計した年数（初年から前年まで）。
        race_count (int): 集計対象のレース数。
    """

    manager: ConnectionManager
    condition: RaceCondition
    race_year: int
    race_name: str
    kyori: int
    keibajo_code: str
    shiba_da: str
    first_year: int
    years: int
    race_count: int


def build_race_context(race_info: pd.DataFrame) -> TrendContext:
    """レース情報から集計対象の情報を構築して返す。

    対象レースと同じ特別競走番号・競馬場・距離・芝ダの過去の開催を集計対象とする。
    集計する期間は decide_trend_years で決める。

    Args:
        race_info (pd.DataFrame): 対象レースの基本情報DataFrame（raw英語カラム名）。

    Returns:
        TrendContext: DB接続マネージャと集計対象の情報。

    Raises:
        ValueError: track_code から芝ダを判定できない場合。
    """
    keibajo_code = str(race_info["keibajo_code"].iloc[0]).strip()
    race_name = str(race_info["kyosomei_hondai"].iloc[0]).strip()
    kyori = int(race_info["kyori"].iloc[0])
    track_code = str(race_info["track_code"].iloc[0]).strip()
    shiba_da = TRACK_CODE_TO_SHIBA_DA.get(track_code)
    if shiba_da is None:
        raise ValueError(f"track_code から芝ダを判定できません: {track_code!r}")
    race_year = int(str(race_info["kaisai_nen"].iloc[0]))
    tokubetsu_kyoso_bango = str(race_info["tokubetsu_kyoso_bango"].iloc[0]).strip().zfill(4)

    config = ConfigManager.from_env()
    manager = ConnectionManager(config)
    base_condition = RaceCondition(
        keibajo_codes=[keibajo_code],
        kyori=kyori,
        shiba_da=shiba_da,
        tokubetsu_kyoso_bango=tokubetsu_kyoso_bango,
    )
    first_year, years = decide_trend_years(manager, race_year, base_condition)
    condition = replace(base_condition, year_from=str(first_year), year_to=str(race_year - 1))
    race_count = len(fetch_past_races(manager, condition))
    return TrendContext(
        manager=manager,
        condition=condition,
        race_year=race_year,
        race_name=race_name,
        kyori=kyori,
        keibajo_code=keibajo_code,
        shiba_da=shiba_da,
        first_year=first_year,
        years=years,
        race_count=race_count,
    )


def decide_trend_years(
    manager: ConnectionManager,
    race_year: int,
    base_condition: RaceCondition,
) -> tuple[int, int]:
    """集計対象の初年と年数を決める。

    既定は対象レース年の前年までの過去 TREND_YEARS 年。
    同じ特別競走番号のレースがG1として行われた最初の年（G1でない開催がある場合は、
    最後のG1でない開催より後の最初のG1の年）がその期間内にある場合は、その年から前年までを集計する。
    G1になった年は、競馬場・距離・芝ダによらず特別競走番号だけで判定する。

    Args:
        manager (ConnectionManager): DB接続マネージャ。
        race_year (int): 対象レースの開催年。
        base_condition (RaceCondition): 同じレースを特定する条件。特別競走番号だけを使う。

    Returns:
        int: 集計対象の初年。
        int: 集計する年数（初年から前年まで）。

    Raises:
        ValueError: 前年までにG1として行われた年が無い場合。
    """
    history = RaceCondition(
        tokubetsu_kyoso_bango=base_condition.tokubetsu_kyoso_bango, year_to=str(race_year - 1)
    )
    past_races = fetch_past_races(manager, history)
    is_g1 = past_races["grade_code"] == _G1_GRADE_CODE
    race_years = past_races["kaisai_nen"].astype(int)
    g1_years = race_years[is_g1]
    non_g1_years = race_years[~is_g1]
    if not non_g1_years.empty:
        g1_years = g1_years[g1_years > non_g1_years.max()]
    if g1_years.empty:
        raise ValueError(f"前年までにG1として行われた開催がありません: race_year={race_year}")
    first_year = max(race_year - TREND_YEARS, int(g1_years.min()))
    return first_year, race_year - first_year


def fetch_past_races(manager: ConnectionManager, condition: RaceCondition) -> pd.DataFrame:
    """条件に合う過去のレースを返す。

    condition の keibajo_codes・kyori・shiba_da・tokubetsu_kyoso_bango・
    year_from・year_to・kaisai_nichime・babajotai_codes のうち指定されたものだけで絞り込む。
    馬場状態は、ダートのレースはダート、それ以外は芝の馬場状態と比べる。

    Args:
        manager (ConnectionManager): DB接続マネージャ。
        condition (RaceCondition): レース絞り込み条件。

    Returns:
        pd.DataFrame: 開催年月日順のレース。
            race_code・kaisai_nen・kaisai_gappi・keibajo_code・grade_code・course_kubun の列を持つ
            （いずれも前後の空白を除いた文字列）。
    """
    where_parts: list[str] = []
    params: list[object] = []
    if condition.keibajo_codes:
        where_parts.append("r.keibajo_code = ANY(%s)")
        params.append(list(condition.keibajo_codes))
    if condition.kyori:
        where_parts.append("TRIM(r.kyori)::INTEGER = %s")
        params.append(int(condition.kyori))
    if condition.shiba_da:
        track_codes = [
            code for code, kind in TRACK_CODE_TO_SHIBA_DA.items() if kind == condition.shiba_da
        ]
        where_parts.append("TRIM(r.track_code) = ANY(%s)")
        params.append(track_codes)
    if condition.tokubetsu_kyoso_bango:
        where_parts.append("TRIM(r.tokubetsu_kyoso_bango) = %s")
        params.append(condition.tokubetsu_kyoso_bango)
    if condition.year_from:
        where_parts.append("r.kaisai_nen >= %s")
        params.append(condition.year_from)
    if condition.year_to:
        where_parts.append("r.kaisai_nen <= %s")
        params.append(condition.year_to)
    if condition.kaisai_nichime:
        where_parts.append("TRIM(r.kaisai_nichime)::INTEGER = ANY(%s)")
        params.append([int(n) for n in condition.kaisai_nichime])
    if condition.babajotai_codes:
        where_parts.append(
            "(CASE WHEN TRIM(r.track_code) BETWEEN '23' AND '29' "
            "THEN TRIM(r.dirt_babajotai_code) ELSE TRIM(r.shiba_babajotai_code) END) = ANY(%s)"
        )
        params.append(list(condition.babajotai_codes))
    where_clause = " AND ".join(where_parts) if where_parts else "TRUE"
    sql = f"""
        SELECT TRIM(r.race_code) AS race_code,
               TRIM(r.kaisai_nen) AS kaisai_nen,
               TRIM(r.kaisai_gappi) AS kaisai_gappi,
               TRIM(r.keibajo_code) AS keibajo_code,
               TRIM(r.grade_code) AS grade_code,
               TRIM(r.course_kubun) AS course_kubun
        FROM race_shosai r
        WHERE {where_clause}
        ORDER BY r.kaisai_nen, r.kaisai_gappi
    """
    return manager.fetch_dataframe(sql, params=tuple(params))
