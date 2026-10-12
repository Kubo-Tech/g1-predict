"""fetch_past_races の単体テスト。"""

from unittest.mock import MagicMock

import pandas as pd
from mykeibadb.analytics import RaceCondition

from g1_predict.modules.utils.race_history import fetch_past_races


def test_fetch_past_races_passes_condition_params() -> None:
    """競馬場・距離・芝ダ・特別競走番号・年の範囲がSQLパラメータに渡る。"""
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame()
    condition = RaceCondition(
        keibajo_codes=["06"],
        kyori=1200,
        shiba_da="芝",
        tokubetsu_kyoso_bango="0016",
        year_from="2016",
        year_to="2025",
    )
    fetch_past_races(manager, condition)

    sql = manager.fetch_dataframe.call_args[0][0]
    params = manager.fetch_dataframe.call_args[1]["params"]
    assert "r.keibajo_code = ANY(%s)" in sql
    assert params[0] == ["06"]
    assert params[1] == 1200
    assert "10" in params[2] and "59" in params[2] and "23" not in params[2]
    assert params[3:] == ("0016", "2016", "2025")


def test_fetch_past_races_filters_by_nichime_and_baba() -> None:
    """開催日目と、芝ダに応じた馬場状態で絞り込む。"""
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame()
    fetch_past_races(manager, RaceCondition(kaisai_nichime=[4, 8], babajotai_codes=["1"]))

    sql = manager.fetch_dataframe.call_args[0][0]
    params = manager.fetch_dataframe.call_args[1]["params"]
    assert "TRIM(r.kaisai_nichime)::INTEGER = ANY(%s)" in sql
    assert "TRIM(r.dirt_babajotai_code) ELSE TRIM(r.shiba_babajotai_code)" in sql
    assert params == ([4, 8], ["1"])


def test_fetch_past_races_without_condition_has_no_filter() -> None:
    """条件が無い場合は絞り込まない。"""
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame()
    fetch_past_races(manager, RaceCondition())

    assert "WHERE TRUE" in manager.fetch_dataframe.call_args[0][0]
    assert manager.fetch_dataframe.call_args[1]["params"] == ()


def test_fetch_past_races_returns_babajotai_code_by_shiba_da() -> None:
    """馬場状態コードの列は、ダートのレースはダート、それ以外は芝の馬場状態から選ぶ。"""
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame()
    fetch_past_races(manager, RaceCondition())

    sql = manager.fetch_dataframe.call_args[0][0]
    select_clause = sql[: sql.index("FROM race_shosai")]
    assert (
        "(CASE WHEN TRIM(r.track_code) BETWEEN '23' AND '29' "
        "THEN TRIM(r.dirt_babajotai_code) ELSE TRIM(r.shiba_babajotai_code) END) "
        "AS babajotai_code"
    ) in select_clause
