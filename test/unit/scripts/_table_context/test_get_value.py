"""TableContext.get_value の単体テスト。"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scripts._table_context import TableContext

_HORSE_ID = "0000000001"
_RACE_NAME = "東京優駿"


@pytest.fixture
def mock_cache() -> MagicMock:
    """TableDataCacheのモック。"""
    cache = MagicMock()
    cache.build_past_df.return_value = pd.DataFrame()
    cache.get_kishu_df.return_value = pd.DataFrame()
    cache.get_seisansha_df.return_value = pd.DataFrame()
    cache.get_umagoto_df.return_value = pd.DataFrame()
    cache.get_kyosoba_row.return_value = None
    cache.get_horse_umagoto_df.return_value = pd.DataFrame()
    return cache


@pytest.fixture
def ctx(mock_cache: MagicMock) -> TableContext:
    """モックキャッシュを使うTableContext。"""
    with patch("scripts._table_context.TableDataCache", return_value=mock_cache):
        return TableContext(
            race_code="202601011234",
            race_year=2026,
            race_name=_RACE_NAME,
            entry_df=pd.DataFrame(),
            di=MagicMock(),
        )


def _horse(fields: dict[str, object] | None = None) -> pd.Series:
    return pd.Series(fields or {})


# 正常系
def test_get_value_entry_field_returns_horse_field(
    ctx: TableContext, mock_cache: MagicMock
) -> None:
    """entry_field typeは出走馬のフィールド値を返す。"""
    horse = _horse({"馬名": "テスト馬"})
    result = ctx.get_value(horse, _HORSE_ID, {"type": "entry_field", "field": "馬名"})
    assert result == "テスト馬"


def test_get_value_entry_field_returns_none_for_missing_field(
    ctx: TableContext, mock_cache: MagicMock
) -> None:
    """entry_fieldで存在しないフィールドはNoneを返す。"""
    horse = _horse({})
    result = ctx.get_value(horse, _HORSE_ID, {"type": "entry_field", "field": "存在しない"})
    assert result is None


def test_get_value_past_count_returns_zero_when_no_past(
    ctx: TableContext, mock_cache: MagicMock
) -> None:
    """past_countで過去成績がないとき0を返す。"""
    mock_cache.build_past_df.return_value = pd.DataFrame()
    result = ctx.get_value(_horse(), _HORSE_ID, {"type": "past_count", "filters": []})
    assert result == 0


def test_get_value_past_count_counts_filtered_rows(
    ctx: TableContext, mock_cache: MagicMock
) -> None:
    """past_countはフィルタ適用後の行数を返す。"""
    mock_cache.build_past_df.return_value = pd.DataFrame(
        {"chakujun": [1, 2, 3], "kyori": [2000, 2000, 1600]}
    )
    filters = [{"field": "kyori", "op": "==", "value": 2000}]
    result = ctx.get_value(_horse(), _HORSE_ID, {"type": "past_count", "filters": filters})
    assert result == 2


def test_get_value_past_field_returns_field_at_index(
    ctx: TableContext, mock_cache: MagicMock
) -> None:
    """past_fieldはindex=0のレコードの指定フィールドを返す。"""
    mock_cache.build_past_df.return_value = pd.DataFrame(
        {"レースコード": ["2025010101"], "着順": [2]}
    )
    result = ctx.get_value(
        _horse(), _HORSE_ID, {"type": "past_field", "field": "着順", "filters": []}
    )
    assert result == 2


def test_get_value_debut_field_returns_last_row(
    ctx: TableContext, mock_cache: MagicMock
) -> None:
    """debut_fieldは最後（最古）の行のフィールドを返す。"""
    mock_cache.build_past_df.return_value = pd.DataFrame({"着順": [1, 3, 5]})
    result = ctx.get_value(_horse(), _HORSE_ID, {"type": "debut_field", "field": "着順"})
    assert result == 5


def test_get_value_past_best_returns_min(ctx: TableContext, mock_cache: MagicMock) -> None:
    """past_bestはデフォルト(min)で最小値を返す。"""
    mock_cache.build_past_df.return_value = pd.DataFrame({"time": [91.4, 89.2, 93.0]})
    result = ctx.get_value(
        _horse(), _HORSE_ID, {"type": "past_best", "field": "time", "filters": []}
    )
    assert result == 89.2


def test_get_value_past_best_returns_max(ctx: TableContext, mock_cache: MagicMock) -> None:
    """past_bestはagg='max'で最大値を返す。"""
    mock_cache.build_past_df.return_value = pd.DataFrame({"time": [91.4, 89.2, 93.0]})
    result = ctx.get_value(
        _horse(),
        _HORSE_ID,
        {"type": "past_best", "field": "time", "filters": [], "agg": "max"},
    )
    assert result == 93.0


def test_get_value_kishu_venue_stat_returns_field_value(
    ctx: TableContext, mock_cache: MagicMock
) -> None:
    """kishu_venue_statは騎手データのフィールド値を返す。"""
    mock_cache.get_kishu_df.return_value = pd.DataFrame(
        {
            "ketto_toroku_bango": [_HORSE_ID],
            "win_rate_all": [0.25],
        }
    )
    result = ctx.get_value(
        _horse(),
        _HORSE_ID,
        {"type": "kishu_venue_stat", "field": "win_rate", "period": "all"},
    )
    assert result == 0.25


def test_get_value_kishu_venue_stat_returns_none_when_empty(
    ctx: TableContext, mock_cache: MagicMock
) -> None:
    """kishu_venue_statでデータなしのときNoneを返す。"""
    mock_cache.get_kishu_df.return_value = pd.DataFrame()
    result = ctx.get_value(
        _horse(), _HORSE_ID, {"type": "kishu_venue_stat", "field": "win_rate", "period": ""}
    )
    assert result is None


def test_get_value_umagoto_field_returns_field_value(
    ctx: TableContext, mock_cache: MagicMock
) -> None:
    """umagoto_fieldはumagoto_dfのフィールド値を返す。"""
    mock_cache.get_umagoto_df.return_value = pd.DataFrame(
        {"ketto_toroku_bango": [_HORSE_ID], "bataiju": [500]}
    )
    result = ctx.get_value(_horse(), _HORSE_ID, {"type": "umagoto_field", "field": "bataiju"})
    assert result == 500


def test_get_value_kyosoba_field_returns_kyosoba_value(
    ctx: TableContext, mock_cache: MagicMock
) -> None:
    """kyosoba_fieldは競走馬マスタのフィールド値を返す。"""
    row = MagicMock()
    row.get.return_value = "牡"
    mock_cache.get_kyosoba_row.return_value = row
    result = ctx.get_value(_horse(), _HORSE_ID, {"type": "kyosoba_field", "field": "seibetsu"})
    assert result == "牡"


def test_get_value_kyosoba_field_returns_none_when_no_row(
    ctx: TableContext, mock_cache: MagicMock
) -> None:
    """kyosoba_fieldで競走馬マスタがないときNoneを返す。"""
    mock_cache.get_kyosoba_row.return_value = None
    result = ctx.get_value(_horse(), _HORSE_ID, {"type": "kyosoba_field", "field": "seibetsu"})
    assert result is None


def test_get_value_recent_umagoto_field_returns_latest(
    ctx: TableContext, mock_cache: MagicMock
) -> None:
    """recent_umagoto_fieldは最新レコードの値を返す。"""
    mock_cache.get_horse_umagoto_df.return_value = pd.DataFrame({"bataiju": [510, 500, 490]})
    result = ctx.get_value(
        _horse(), _HORSE_ID, {"type": "recent_umagoto_field", "field": "bataiju"}
    )
    assert result == 510


def test_get_value_kishu_continuity_delegates_to_stat(
    ctx: TableContext, mock_cache: MagicMock
) -> None:
    """kishu_continuityは_table_statのkishu_continuityに委譲する。"""
    with patch("scripts._table_context.kishu_continuity", return_value="継続") as mock_fn:
        result = ctx.get_value(_horse(), _HORSE_ID, {"type": "kishu_continuity"})
    mock_fn.assert_called_once_with(_HORSE_ID, mock_cache)
    assert result == "継続"


def test_get_value_waku_stat_delegates_to_stat(
    ctx: TableContext, mock_cache: MagicMock
) -> None:
    """waku_statは_table_statのwaku_statに委譲する。"""
    source = {"type": "waku_stat", "keibajo_code": "05", "track": "shiba", "kyori": 2000,
              "years": 3, "stat": "wins"}
    with patch("scripts._table_context.waku_stat", return_value=2) as mock_fn:
        result = ctx.get_value(_horse(), _HORSE_ID, source)
    mock_fn.assert_called_once_with(_HORSE_ID, source, mock_cache)
    assert result == 2


# 準正常系
def test_get_value_raises_for_unknown_src_type(ctx: TableContext) -> None:
    """不明なsrc typeはValueErrorを発生させる。"""
    with pytest.raises(ValueError, match="不明なsource type"):
        ctx.get_value(_horse(), _HORSE_ID, {"type": "nonexistent_type"})
