"""tokubetsu_race_finish の単体テスト。"""
from unittest.mock import MagicMock

import pandas as pd
import pytest

from g1_predict.modules.gen_table.table_stat import tokubetsu_race_finish

_HORSE_ID = "0000000001"


def _make_past_df(
    tokubetsu_kyoso_bango: str, kaisai_nen: int, kakutei_chakujun: str
) -> pd.DataFrame:
    """テスト用の過去成績DataFrameを生成する。"""
    return pd.DataFrame(
        {
            "特別競走番号": [tokubetsu_kyoso_bango],
            "開催年": [kaisai_nen],
            "確定着順": [kakutei_chakujun],
        }
    )


# 正常系
def test_tokubetsu_race_finish_returns_finish_for_prev_year(mock_cache: MagicMock) -> None:
    """year_offset=1で前年の対象レース確定着順を返す。"""
    mock_cache.build_past_df.return_value = _make_past_df("0010", 2025, "3")
    source = {"tokubetsu_kyoso_bango": "0010", "year_offset": 1, "absent_label": "前年出走無し"}
    result = tokubetsu_race_finish(_HORSE_ID, source, 2026, mock_cache)
    assert result == 3


def test_tokubetsu_race_finish_returns_finish_for_same_year(mock_cache: MagicMock) -> None:
    """year_offset=0で同年の対象レース確定着順を返す。"""
    mock_cache.build_past_df.return_value = _make_past_df("0019", 2026, "1")
    source = {"tokubetsu_kyoso_bango": "0019", "year_offset": 0, "absent_label": "不出走"}
    result = tokubetsu_race_finish(_HORSE_ID, source, 2026, mock_cache)
    assert result == 1


def test_tokubetsu_race_finish_returns_absent_label_when_not_entered(
    mock_cache: MagicMock,
) -> None:
    """対象年に出走していない場合はabsent_labelを返す。"""
    mock_cache.build_past_df.return_value = _make_past_df("0010", 2024, "3")
    source = {"tokubetsu_kyoso_bango": "0010", "year_offset": 1, "absent_label": "前年出走無し"}
    result = tokubetsu_race_finish(_HORSE_ID, source, 2026, mock_cache)
    assert result == "前年出走無し"


def test_tokubetsu_race_finish_returns_absent_label_when_past_df_empty(
    mock_cache: MagicMock,
) -> None:
    """過去成績が空の場合はabsent_labelを返す。"""
    mock_cache.build_past_df.return_value = pd.DataFrame()
    source = {"tokubetsu_kyoso_bango": "0010", "year_offset": 1, "absent_label": "前年出走無し"}
    result = tokubetsu_race_finish(_HORSE_ID, source, 2026, mock_cache)
    assert result == "前年出走無し"


def test_tokubetsu_race_finish_returns_absent_label_when_finish_not_numeric(
    mock_cache: MagicMock,
) -> None:
    """確定着順が数値変換不能な場合はabsent_labelを返す。"""
    mock_cache.build_past_df.return_value = _make_past_df("0010", 2025, "中止")
    source = {"tokubetsu_kyoso_bango": "0010", "year_offset": 1, "absent_label": "前年出走無し"}
    result = tokubetsu_race_finish(_HORSE_ID, source, 2026, mock_cache)
    assert result == "前年出走無し"


# 準正常系
def test_tokubetsu_race_finish_raises_when_tokubetsu_kyoso_bango_missing(
    mock_cache: MagicMock,
) -> None:
    """tokubetsu_kyoso_bango未指定でValueError。"""
    source = {"year_offset": 1, "absent_label": "前年出走無し"}
    with pytest.raises(ValueError, match="tokubetsu_kyoso_bango と year_offset"):
        tokubetsu_race_finish(_HORSE_ID, source, 2026, mock_cache)


def test_tokubetsu_race_finish_raises_when_year_offset_missing(mock_cache: MagicMock) -> None:
    """year_offset未指定でValueError。"""
    source = {"tokubetsu_kyoso_bango": "0010", "absent_label": "前年出走無し"}
    with pytest.raises(ValueError, match="tokubetsu_kyoso_bango と year_offset"):
        tokubetsu_race_finish(_HORSE_ID, source, 2026, mock_cache)


def test_tokubetsu_race_finish_raises_when_year_offset_negative(mock_cache: MagicMock) -> None:
    """year_offsetが負の場合ValueError。"""
    source = {"tokubetsu_kyoso_bango": "0010", "year_offset": -1, "absent_label": "前年出走無し"}
    with pytest.raises(ValueError, match="year_offset は0以上"):
        tokubetsu_race_finish(_HORSE_ID, source, 2026, mock_cache)
