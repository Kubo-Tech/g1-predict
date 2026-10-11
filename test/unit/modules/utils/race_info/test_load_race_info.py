"""load_race_info の単体テスト。"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from g1_predict.modules.utils.race_info import load_race_info

_MODULE = "g1_predict.modules.utils.race_info"
_RACE_CODE = "2026101808040711"


# 正常系
def test_load_race_info_from_db_without_tokubetsu_kyoso_bango() -> None:
    """特別競走番号を指定しない場合は、race_shosai から引いた1行をそのまま返す。"""
    race_info = pd.DataFrame({"kyosomei_hondai": ["秋華賞"], "kaisai_nen": ["2026"]})
    with (
        patch(f"{_MODULE}.RaceGetter") as mock_getter_cls,
        patch(f"{_MODULE}.fetch_race_info_from_history") as mock_history,
    ):
        mock_getter_cls.return_value.get_race_shosai.return_value = race_info
        result = load_race_info(_RACE_CODE, None)
    assert result is race_info
    mock_getter_cls.return_value.get_race_shosai.assert_called_once_with(
        race_code=_RACE_CODE, convert_codes=False
    )
    mock_history.assert_not_called()


def test_load_race_info_with_tokubetsu_kyoso_bango_uses_history() -> None:
    """特別競走番号を指定した場合は、DB から引かず直近の開催から組み立てる。"""
    race_info = pd.DataFrame({"kyosomei_hondai": ["秋華賞"], "kaisai_nen": ["2026"]})
    manager = MagicMock()
    with (
        patch(f"{_MODULE}.RaceGetter") as mock_getter_cls,
        patch(f"{_MODULE}.ConfigManager"),
        patch(f"{_MODULE}.ConnectionManager", return_value=manager),
        patch(f"{_MODULE}.fetch_race_info_from_history", return_value=race_info) as mock_history,
    ):
        result = load_race_info(_RACE_CODE, "0018")
    assert result is race_info
    mock_history.assert_called_once_with(manager, _RACE_CODE, "0018")
    mock_getter_cls.assert_not_called()


# 準正常系
def test_load_race_info_race_not_in_db_raises() -> None:
    """特別競走番号を指定せず、今回のレースが DB に無い場合は ValueError。"""
    with patch(f"{_MODULE}.RaceGetter") as mock_getter_cls:
        mock_getter_cls.return_value.get_race_shosai.return_value = pd.DataFrame()
        with pytest.raises(ValueError, match="--tokubetsu-kyoso-bango"):
            load_race_info(_RACE_CODE, None)


def test_load_race_info_propagates_history_error() -> None:
    """直近の開催から組み立てられない場合の ValueError はそのまま出す。"""
    with (
        patch(f"{_MODULE}.ConfigManager"),
        patch(f"{_MODULE}.ConnectionManager"),
        patch(f"{_MODULE}.fetch_race_info_from_history", side_effect=ValueError("無い")),
        pytest.raises(ValueError, match="無い"),
    ):
        load_race_info(_RACE_CODE, "0018")
