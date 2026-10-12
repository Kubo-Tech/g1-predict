"""fetch_race_info_from_history の単体テスト。"""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from g1_predict.modules.utils.race_history import fetch_race_info_from_history


def test_fetch_race_info_from_history_combines_latest_edition_and_race_code() -> None:
    """競走名・距離・トラックは直近の開催から、開催年・開催月日・競馬場は race_code から取る。"""
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame({
        "kyosomei_hondai": ["秋華賞"],
        "kyori": ["2000"],
        "track_code": ["10"],
    })

    race_info = fetch_race_info_from_history(manager, "2026101808040711", "0018")

    assert race_info.to_dict("records") == [{
        "race_code": "2026101808040711",
        "kaisai_nen": "2026",
        "kaisai_gappi": "1018",
        "keibajo_code": "08",
        "kyosomei_hondai": "秋華賞",
        "kyori": "2000",
        "track_code": "10",
        "tokubetsu_kyoso_bango": "0018",
    }]
    sql = manager.fetch_dataframe.call_args[0][0]
    assert "ORDER BY r.kaisai_nen DESC, r.kaisai_gappi DESC" in sql
    assert manager.fetch_dataframe.call_args[1]["params"] == ("0018", "2026")


def test_fetch_race_info_from_history_without_past_edition_raises() -> None:
    """今回の開催年より前に同じ特別競走番号のレースが無い場合は ValueError。"""
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame()

    with pytest.raises(ValueError, match="特別競走番号 0018 のレースがありません"):
        fetch_race_info_from_history(manager, "2026101808040711", "0018")


@pytest.mark.parametrize("bango", ["18", "00180", "abcd"])
def test_fetch_race_info_from_history_invalid_bango_raises(bango: str) -> None:
    """特別競走番号が4桁の数字でない場合は ValueError。"""
    with pytest.raises(ValueError, match="4桁の数字"):
        fetch_race_info_from_history(MagicMock(), "2026101808040711", bango)
