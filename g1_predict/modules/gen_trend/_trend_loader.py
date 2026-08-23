"""傾向計算に必要な DB コンテキストを構築するモジュール。"""

from dataclasses import replace
from typing import Any

import pandas as pd
from mykeibadb.analytics import RaceCondition
from mykeibadb.config import ConfigManager
from mykeibadb.connection import ConnectionManager

from g1_predict.modules.constants import TRACK_CODE_TO_SHIBA_DA

from ._trend_models import TREND_YEARS


def build_race_context(
    race_code: str,
    race_info: pd.DataFrame,
) -> tuple[ConnectionManager, RaceCondition]:
    """レース情報から ConnectionManager と RaceCondition を構築して返す。

    過去 TREND_YEARS 年分のコース一致レースを集計対象とする RaceCondition を生成する。

    Args:
        race_code (str): 対象レースの16桁レースコード（未使用、シグネチャ統一のため保持）。
        race_info (pd.DataFrame): 対象レースの基本情報DataFrame（raw英語カラム名）。

    Returns:
        ConnectionManager: DB接続マネージャ。
        RaceCondition: 集計対象のレース絞り込み条件。
    """
    keibajo_code = str(race_info["keibajo_code"].iloc[0]).strip()
    kyori = int(race_info["kyori"].iloc[0])
    track_code = str(race_info["track_code"].iloc[0]).strip()
    shiba_da = TRACK_CODE_TO_SHIBA_DA.get(track_code)
    race_year = int(str(race_info["kaisai_nen"].iloc[0]))
    tokubetsu_kyoso_bango = str(race_info["tokubetsu_kyoso_bango"].iloc[0]).strip().zfill(4)

    config = ConfigManager.from_env()
    manager = ConnectionManager(config)
    condition = RaceCondition(
        keibajo_codes=[keibajo_code],
        kyori=kyori,
        shiba_da=shiba_da,
        year_from=str(race_year - TREND_YEARS),
        year_to=str(race_year - 1),
        tokubetsu_kyoso_bango=tokubetsu_kyoso_bango,
    )
    return manager, condition


def build_metric_condition(
    base_condition: RaceCondition,
    race_year: int,
    condition_cfg: dict[str, Any] | None,
) -> RaceCondition:
    """metric 個別の condition 設定を反映した RaceCondition を返す。

    condition_cfg が None の場合は base_condition をそのまま返す。
    指定時は years から year_from / year_to を再計算し、
    keibajo_codes / kaisai_nichime / babajotai_codes を上書きする。

    Args:
        base_condition (RaceCondition): build_race_context が生成した基本条件。
        race_year (int): 対象レースの開催年。
        condition_cfg (dict[str, Any] | None): metric の condition 設定dict。

    Returns:
        RaceCondition: metric 個別条件を反映した RaceCondition。

    Raises:
        ValueError: condition_cfg["years"] が1未満の場合。
    """
    if condition_cfg is None:
        return base_condition

    years = condition_cfg.get("years", TREND_YEARS)
    if years < 1:
        raise ValueError(f"years は1以上の整数を指定してください: {years!r}")

    return replace(
        base_condition,
        year_from=str(race_year - years),
        year_to=str(race_year - 1),
        keibajo_codes=condition_cfg.get("keibajo_codes", base_condition.keibajo_codes),
        kaisai_nichime=condition_cfg.get("kaisai_nichime", base_condition.kaisai_nichime),
        babajotai_codes=condition_cfg.get("babajotai_codes", base_condition.babajotai_codes),
    )
