"""今回のレースの基本情報を取得するモジュール。"""

import pandas as pd
from mykeibadb import RaceGetter
from mykeibadb.config import ConfigManager
from mykeibadb.connection import ConnectionManager

from .race_history import fetch_race_info_from_history


def load_race_info(race_code: str, tokubetsu_kyoso_bango: str | None) -> pd.DataFrame:
    """今回のレースの基本情報を返す。

    tokubetsu_kyoso_bango が None の場合は race_shosai から引き、指定した場合は
    fetch_race_info_from_history() で同じ特別競走番号の直近の開催から組み立てる。

    Args:
        race_code (str): 今回のレースの16桁のレースコード。
        tokubetsu_kyoso_bango (str | None): レースが DB に入る前に生成する場合の特別競走番号。

    Returns:
        pd.DataFrame: 1行のレース基本情報（raw英語カラム名）。

    Raises:
        ValueError: tokubetsu_kyoso_bango を指定せず、レースが DB に無い場合。
            fetch_race_info_from_history() が ValueError を出す場合。
    """
    if tokubetsu_kyoso_bango is not None:
        manager = ConnectionManager(ConfigManager.from_env())
        return fetch_race_info_from_history(manager, race_code, tokubetsu_kyoso_bango)
    race_info = RaceGetter().get_race_shosai(race_code=race_code, convert_codes=False)
    if race_info.empty:
        raise ValueError(
            f"レースが DB にありません: {race_code}。"
            "DB に入る前は --tokubetsu-kyoso-bango で特別競走番号を指定してください"
        )
    return race_info
