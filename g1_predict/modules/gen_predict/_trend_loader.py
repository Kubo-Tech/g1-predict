"""傾向計算に必要な DB コンテキストを構築するモジュール。"""

import pandas as pd
from mykeibadb.analytics import RaceCondition
from mykeibadb.config import ConfigManager
from mykeibadb.connection import ConnectionManager

from ._constants import TRACK_CODE_TO_SHIBA_DA
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
        keibajo_code=keibajo_code,
        kyori=kyori,
        shiba_da=shiba_da,
        year_from=str(race_year - TREND_YEARS),
        year_to=str(race_year - 1),
        tokubetsu_kyoso_bango=tokubetsu_kyoso_bango,
    )
    return manager, condition
