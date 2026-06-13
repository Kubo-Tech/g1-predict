"""_trend_stats の単体テスト。"""

from unittest.mock import MagicMock

import pytest
from mykeibadb.analytics import ChakudoResult, ChakudoRow, RaceCondition

from g1_predict.modules.gen_predict._trend_models import RowStats
from g1_predict.modules.gen_predict._trend_stats import (
    _chakudo_row_to_stats,
    _group_by_rows_cfg,
    _group_matches,
    _merge_stats,
    _yaml_rows_to_rowsdef,
    compute_stats,
)


def _make_manager() -> MagicMock:
    """ConnectionManager のモックを生成する。"""
    return MagicMock()


def _make_condition() -> RaceCondition:
    """テスト用 RaceCondition を生成する。"""
    return RaceCondition(keibajo_codes=["05"], kyori=2400, year_from="2016", year_to="2025")


def _make_chakudo_row(
    group: str = "1",
    total: int = 10,
    wins: int = 2,
    second: int = 1,
    third: int = 1,
    chakugai: int = 6,
    win_rate: float = 20.0,
    fukusho_rate: float = 40.0,
    tansho_kaishuu: float = 85.0,
    fukusho_kaishuu: float = 72.0,
) -> ChakudoRow:
    """テスト用 ChakudoRow を生成する。"""
    return ChakudoRow(
        group=group,
        total=total,
        wins=wins,
        second=second,
        third=third,
        chakugai=chakugai,
        win_rate=win_rate,
        fukusho_rate=fukusho_rate,
        tansho_kaishuu=tansho_kaishuu,
        fukusho_kaishuu=fukusho_kaishuu,
    )


def _make_chakudo_result(rows: list[ChakudoRow] | None = None) -> ChakudoResult:
    """テスト用 ChakudoResult を生成する。"""
    return ChakudoResult(success=True, rows=rows or [])


# --- _chakudo_row_to_stats ---


def test_chakudo_row_to_stats_maps_fields() -> None:
    """ChakudoRow → RowStats のフィールドが正しくマップされる。"""
    row = _make_chakudo_row(
        wins=3, second=2, third=1, chakugai=4, tansho_kaishuu=90.5, fukusho_kaishuu=75.0, total=10
    )
    s = _chakudo_row_to_stats(row)
    assert s.first == 3
    assert s.second == 2
    assert s.third == 1
    assert s.fourth_plus == 4
    assert s.tansho_kaishuu == 90.5
    assert s.fukusho_kaishuu == 75.0
    assert s.total == 10


# --- _merge_stats ---


def test_merge_stats_empty_list() -> None:
    """空リストは全ゼロの RowStats を返す。"""
    result = _merge_stats([])
    assert result.total == 0
    assert result.tansho_kaishuu == 0.0


def test_merge_stats_single() -> None:
    """1要素はそのまま返す。"""
    s = RowStats(first=2, total=5, tansho_kaishuu=80.0, fukusho_kaishuu=60.0)
    result = _merge_stats([s])
    assert result.first == 2
    assert result.total == 5
    assert result.tansho_kaishuu == 80.0


def test_merge_stats_weighted_average() -> None:
    """回収率が出走頭数で加重平均される。"""
    s1 = RowStats(total=10, tansho_kaishuu=100.0, fukusho_kaishuu=80.0)
    s2 = RowStats(total=10, tansho_kaishuu=60.0, fukusho_kaishuu=40.0)
    result = _merge_stats([s1, s2])
    assert result.total == 20
    assert result.tansho_kaishuu == 80.0
    assert result.fukusho_kaishuu == 60.0


def test_merge_stats_sums_chakujun_counts() -> None:
    """着順カウントが合算される。"""
    s1 = RowStats(first=1, second=2, third=3, fourth_plus=4, total=10)
    s2 = RowStats(first=2, second=1, third=0, fourth_plus=7, total=10)
    result = _merge_stats([s1, s2])
    assert result.first == 3
    assert result.second == 3
    assert result.third == 3
    assert result.fourth_plus == 11


# --- _group_matches ---


@pytest.mark.parametrize(
    "group_str, op, threshold, expected",
    [
        ("3", "==", 3, True),
        ("3", "==", 4, False),
        ("継続", "==", "継続", True),
        ("継続", "==", "テン乗り", False),
        ("10", ">=", 10, True),
        ("9", ">=", 10, False),
        ("2", "<=", 2, True),
        ("3", "<=", 2, False),
        ("4", "in", [4, 5, 6], True),
        ("7", "in", [4, 5, 6], False),
        ("1", "in", ["1", "2"], True),
        ("3", "in", ["1", "2"], False),
        ("01", "==", 1, True),
    ],
)
def test_group_matches(group_str: str, op: str, threshold: object, expected: bool) -> None:
    """_group_matches が各演算子と入力パターンを正しく評価する。"""
    assert _group_matches(group_str, op, threshold) is expected


# --- _group_by_rows_cfg ---


def test_group_by_rows_cfg_dynamic_returns_all() -> None:
    """dynamic 型はそのまま変換する。"""
    rows_cfg = {"type": "dynamic"}
    result = _make_chakudo_result([_make_chakudo_row(group="武豊", wins=5, total=20)])
    stats = _group_by_rows_cfg(result, rows_cfg)
    assert "武豊" in stats
    assert stats["武豊"].first == 5


def test_group_by_rows_cfg_fixed_eq() -> None:
    """fixed 型の == 条件で正しくグループ化される。"""
    rows_cfg = {
        "type": "fixed",
        "items": [{"label": "1枠", "op": "==", "value": 1}],
    }
    result = _make_chakudo_result([
        _make_chakudo_row(group="1", wins=3, total=10),
        _make_chakudo_row(group="2", wins=2, total=10),
    ])
    stats = _group_by_rows_cfg(result, rows_cfg)
    assert "1枠" in stats
    assert stats["1枠"].first == 3
    assert "2枠" not in stats


def test_group_by_rows_cfg_fixed_in_merges() -> None:
    """fixed 型の in 条件で複数グループが合算される。"""
    rows_cfg = {
        "type": "fixed",
        "items": [{"label": "4-6人気", "op": "in", "value": [4, 5, 6]}],
    }
    result = _make_chakudo_result([
        _make_chakudo_row(group="4", wins=1, total=5, tansho_kaishuu=100.0, fukusho_kaishuu=80.0),
        _make_chakudo_row(group="5", wins=2, total=5, tansho_kaishuu=80.0, fukusho_kaishuu=60.0),
        _make_chakudo_row(group="7", wins=3, total=5),
    ])
    stats = _group_by_rows_cfg(result, rows_cfg)
    assert "4-6人気" in stats
    assert stats["4-6人気"].first == 3
    assert stats["4-6人気"].total == 10
    assert "7" not in stats


def test_group_by_rows_cfg_failed_result_returns_empty() -> None:
    """success=False の場合は空辞書を返す。"""
    rows_cfg = {"type": "fixed", "items": [{"label": "1枠", "op": "==", "value": 1}]}
    result = ChakudoResult(success=False, error="DB error")
    assert _group_by_rows_cfg(result, rows_cfg) == {}


# --- compute_stats ---


def test_compute_stats_gate_number_calls_analyze_chakudo() -> None:
    """gate_number source は analyze_chakudo を呼び出す。"""
    from unittest.mock import patch

    mock_result = _make_chakudo_result([_make_chakudo_row(group="1", wins=2, total=10)])
    with patch(
        "g1_predict.modules.gen_predict._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ):
        metric_cfg = {
            "source": {"type": "gate_number"},
            "rows": {"type": "fixed", "items": [{"label": "1枠", "op": "==", "value": 1}]},
        }
        stats = compute_stats(metric_cfg, _make_manager(), _make_condition())
    assert "1枠" in stats


def test_compute_stats_prev_race_col_builds_fixed_group_by() -> None:
    """prev_race_col source は fixed GroupBy で analyze_chakudo を呼ぶ。"""
    from unittest.mock import patch

    from mykeibadb.analytics import AttrSource

    mock_result = _make_chakudo_result([_make_chakudo_row(group="逃げ", wins=1, total=5)])
    with patch(
        "g1_predict.modules.gen_predict._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        metric_cfg = {
            "source": {"type": "prev_race_col", "column": "kyakushitsu_hantei"},
            "rows": {
                "type": "fixed",
                "items": [{"label": "逃げ", "op": "==", "value": "1"}],
            },
        }
        compute_stats(metric_cfg, _make_manager(), _make_condition())

    _, _, _, group_by = mock_analyze.call_args[0]
    assert group_by.kind == "fixed"
    assert isinstance(group_by.source, AttrSource)
    assert group_by.source.type == "prev_race_col"
    assert group_by.source.column == "kyakushitsu_hantei"


def test_compute_stats_same_race_prev_year_finish_cumulative() -> None:
    """same_race_prev_year_finish は history 取得 + _group_by_rows_cfg で累積計上される。"""
    from unittest.mock import patch

    from mykeibadb.analytics import AttrSource

    raw_rows = [
        _make_chakudo_row(group="1", wins=1, second=0, third=0, chakugai=0, total=1),
        _make_chakudo_row(group="2", wins=0, second=1, third=0, chakugai=0, total=1),
        _make_chakudo_row(group="前年出走無し", wins=0, second=0, third=0, chakugai=5, total=5),
    ]
    mock_result = _make_chakudo_result(raw_rows)
    with patch(
        "g1_predict.modules.gen_predict._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        metric_cfg = {
            "source": {
                "type": "same_race_prev_year_finish",
                "tokubetsu_kyoso_bango": "0010",
                "absent_label": "前年出走無し",
            },
            "rows": {
                "type": "fixed",
                "items": [
                    {"label": "前年3着以内", "op": "<=", "value": 3},
                    {"label": "前年出走無し", "op": "==", "value": "前年出走無し"},
                ],
            },
        }
        stats = compute_stats(metric_cfg, _make_manager(), _make_condition())

    _, _, _, group_by = mock_analyze.call_args[0]
    assert group_by.kind == "history"
    assert isinstance(group_by.source, AttrSource)
    assert group_by.source.type == "same_race_prev_year_finish"
    assert "前年3着以内" in stats
    assert stats["前年3着以内"].first == 1
    assert stats["前年3着以内"].second == 1
    assert "前年出走無し" in stats
    assert stats["前年出走無し"].fourth_plus == 5


def test_compute_stats_past_race_top_n_count_builds_fixed_group_by() -> None:
    """past_race_top_n_count source は fixed GroupBy で analyze_chakudo を呼ぶ。"""
    from unittest.mock import patch

    from mykeibadb.analytics import AttrSource

    mock_result = _make_chakudo_result([_make_chakudo_row(group="0勝", wins=0, total=5)])
    with patch(
        "g1_predict.modules.gen_predict._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        metric_cfg = {
            "source": {
                "type": "past_race_top_n_count",
                "keibajo_codes": ["05"],
                "top_n": 1,
            },
            "rows": {
                "type": "fixed",
                "items": [{"label": "0勝", "op": "==", "value": 0}],
            },
        }
        compute_stats(metric_cfg, _make_manager(), _make_condition())

    _, _, _, group_by = mock_analyze.call_args[0]
    assert group_by.kind == "fixed"
    assert isinstance(group_by.source, AttrSource)
    assert group_by.source.type == "past_race_top_n_count"
    assert group_by.source.keibajo_codes == ["05"]
    assert group_by.source.top_n == 1


def test_compute_stats_past_race_top_n_count_converts_filters_field_to_column() -> None:
    """past_race_top_n_count の filters はfield名がmykeibadbのcolumn名に変換される。"""
    from unittest.mock import patch

    from mykeibadb.analytics import AttrSource

    mock_result = _make_chakudo_result([_make_chakudo_row(group="0回", wins=0, total=5)])
    with patch(
        "g1_predict.modules.gen_predict._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        metric_cfg = {
            "source": {
                "type": "past_race_top_n_count",
                "filters": [{"field": "グレードコード", "op": "in", "value": ["A", "B", "C"]}],
            },
            "rows": {
                "type": "fixed",
                "items": [{"label": "0回", "op": "==", "value": 0}],
            },
        }
        compute_stats(metric_cfg, _make_manager(), _make_condition())

    _, _, _, group_by = mock_analyze.call_args[0]
    assert isinstance(group_by.source, AttrSource)
    assert group_by.source.filters == [
        {"column": "grade_code", "op": "in", "value": ["A", "B", "C"]}
    ]


def test_compute_stats_past_race_top_n_count_unsupported_field_raises() -> None:
    """past_race_top_n_count の filters に未対応fieldを指定するとValueError。"""
    metric_cfg = {
        "source": {
            "type": "past_race_top_n_count",
            "filters": [{"field": "未対応フィールド", "op": "==", "value": 1}],
        },
        "rows": {
            "type": "fixed",
            "items": [{"label": "0回", "op": "==", "value": 0}],
        },
    }
    with pytest.raises(ValueError, match="未対応フィールド"):
        compute_stats(metric_cfg, _make_manager(), _make_condition())


def test_compute_stats_past_race_top_n_count_top_n_less_than_one_raises() -> None:
    """past_race_top_n_count の top_n が 1 未満なら ValueError。"""
    metric_cfg = {
        "source": {"type": "past_race_top_n_count", "top_n": 0},
        "rows": {
            "type": "fixed",
            "items": [{"label": "0回", "op": "==", "value": 0}],
        },
    }
    with pytest.raises(ValueError, match="top_n は 1 以上"):
        compute_stats(metric_cfg, _make_manager(), _make_condition())


def test_compute_stats_unknown_type_returns_empty() -> None:
    """未知の source.type は空辞書を返す。"""
    metric_cfg = {
        "source": {"type": "unknown_type"},
        "rows": {"type": "dynamic"},
    }
    stats = compute_stats(metric_cfg, _make_manager(), _make_condition())
    assert stats == {}


@pytest.mark.parametrize(
    "src_type, expected_column",
    [
        ("affiliation", "u.tozai_shozoku_code"),
        ("horse_age", "u.barei"),
        ("sex", "u.seibetsu_code"),
        ("gate_number", "u.wakuban"),
        ("popularity", "u.tansho_ninkijun"),
        ("running_style", "u.kyakushitsu_hantei"),
    ],
)
def test_compute_stats_race_col_map(src_type: str, expected_column: str) -> None:
    """_RACE_COL_MAP の各 src_type が正しい column で analyze_chakudo を呼ぶ。"""
    from unittest.mock import patch

    from mykeibadb.analytics import GroupBy

    mock_result = _make_chakudo_result([_make_chakudo_row(group="1", wins=1, total=5)])
    with patch(
        "g1_predict.modules.gen_predict._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        metric_cfg = {
            "source": {"type": src_type},
            "rows": {"type": "fixed", "items": [{"label": "x", "op": "==", "value": 1}]},
        }
        compute_stats(metric_cfg, _make_manager(), _make_condition())

    assert mock_analyze.call_count == 1
    _, _, _, group_by = mock_analyze.call_args[0]
    assert group_by == GroupBy(kind="race_col", column=expected_column)


# --- _yaml_rows_to_rowsdef ---


@pytest.mark.parametrize(
    "op, value, expected",
    [
        ("<", 1600, (0, 1599)),
        (">", 1600, (1601, 9999)),
    ],
)
def test_yaml_rows_to_rowsdef_lt_gt(op: str, value: int, expected: tuple[int, int]) -> None:
    """< / > op が (lo, hi) タプルに正しく変換される。"""
    rows_cfg = {
        "type": "fixed",
        "items": [{"label": "test", "op": op, "value": value}],
    }
    result = _yaml_rows_to_rowsdef(rows_cfg)
    assert result["test"] == expected
