"""_trend_stats の単体テスト。"""

from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from mykeibadb.analytics import ChakudoResult, ChakudoRow, RaceColFilter, RaceCondition

from g1_predict.modules.gen_trend._trend_models import RowStats
from g1_predict.modules.gen_trend._trend_sql_exprs import (
    BIRTH_MONTH_EXPR,
    CORNER4_JUNI_EXPR,
    HORSE_WEIGHT_EXPR,
)
from g1_predict.modules.gen_trend._trend_stats import (
    _AGARI_3F_RANK_EXPR,
    _chakudo_row_to_stats,
    _group_matches,
    _merge_stats,
    _yaml_rows_to_rowsdef,
    build_item_grouping,
    compute_stats,
    get_juusho_race_names,
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
        ("2", "between", [2, 5], True),
        ("5", "between", [2, 5], True),
        ("6", "between", [2, 5], False),
        ("1", "between", [2, 5], False),
        ("-200", "<", 0, True),
        ("0", "==", 0, True),
        ("None", "between", [2, 5], False),
    ],
)
def test_group_matches(group_str: str, op: str, threshold: object, expected: bool) -> None:
    """_group_matches が各演算子と入力パターンを正しく評価する。"""
    assert _group_matches(group_str, op, threshold) is expected


# --- compute_stats の行の割り当て ---


def _compute_with_rows(rows_cfg: dict[str, Any], rows: list[ChakudoRow]) -> dict[str, RowStats]:
    """gate_number の source に rows_cfg を指定して compute_stats を実行する。"""
    metric_cfg = {"source": {"type": "gate_number"}, "rows": rows_cfg}
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=_make_chakudo_result(rows),
    ):
        return compute_stats(metric_cfg, _make_manager(), _make_condition(), [])


def test_compute_stats_dynamic_rows_returns_all_groups() -> None:
    """dynamic 型はグループをそのまま行にする。"""
    stats = _compute_with_rows(
        {"type": "dynamic"}, [_make_chakudo_row(group="武豊", wins=5, total=20)]
    )
    assert stats["武豊"].first == 5


def test_compute_stats_fixed_eq_assigns_matching_group() -> None:
    """fixed 型の == 条件で、一致するグループだけが行に入る。"""
    rows_cfg = {"type": "fixed", "items": [{"label": "1枠", "op": "==", "value": 1}]}
    stats = _compute_with_rows(
        rows_cfg,
        [
            _make_chakudo_row(group="1", wins=3, total=10),
            _make_chakudo_row(group="2", wins=2, total=10),
        ],
    )
    assert list(stats) == ["1枠"]
    assert stats["1枠"].first == 3


def test_compute_stats_fixed_in_merges_groups() -> None:
    """fixed 型の in 条件で複数グループが合算される。"""
    rows_cfg = {"type": "fixed", "items": [{"label": "4-6人気", "op": "in", "value": [4, 5, 6]}]}
    stats = _compute_with_rows(
        rows_cfg,
        [
            _make_chakudo_row(
                group="4", wins=1, total=5, tansho_kaishuu=100.0, fukusho_kaishuu=80.0
            ),
            _make_chakudo_row(
                group="5", wins=2, total=5, tansho_kaishuu=80.0, fukusho_kaishuu=60.0
            ),
            _make_chakudo_row(group="7", wins=3, total=5),
        ],
    )
    assert list(stats) == ["4-6人気"]
    assert stats["4-6人気"].first == 3
    assert stats["4-6人気"].total == 10


def test_compute_stats_fixed_between_merges_range() -> None:
    """fixed 型の between 条件で下限・上限を含む範囲のグループが合算される。"""
    rows_cfg = {
        "type": "fixed",
        "items": [{"label": "2-5番手", "op": "between", "value": [2, 5]}],
    }
    stats = _compute_with_rows(
        rows_cfg,
        [
            _make_chakudo_row(group="1", wins=9, total=10),
            _make_chakudo_row(group="2", wins=1, total=5),
            _make_chakudo_row(group="5", wins=2, total=5),
            _make_chakudo_row(group="6", wins=3, total=5),
        ],
    )
    assert stats["2-5番手"].first == 3
    assert stats["2-5番手"].total == 10


def test_compute_stats_fixed_without_matching_group_is_empty() -> None:
    """fixed 型で一致するグループが無い行は、全て0の集計値になる。"""
    rows_cfg = {"type": "fixed", "items": [{"label": "8枠", "op": "==", "value": 8}]}
    stats = _compute_with_rows(rows_cfg, [_make_chakudo_row(group="1", wins=3, total=10)])
    assert stats["8枠"] == RowStats()


def test_compute_stats_fixed_overlapping_rows_share_group() -> None:
    """fixed 型で条件が重なる行は、同じグループをそれぞれ集計する。"""
    rows_cfg = {
        "type": "fixed",
        "items": [
            {"label": "3着以内", "op": "<=", "value": 3},
            {"label": "4着以内", "op": "<=", "value": 4},
        ],
    }
    stats = _compute_with_rows(rows_cfg, [_make_chakudo_row(group="3", wins=1, total=4)])
    assert stats["3着以内"].total == 4
    assert stats["4着以内"].total == 4


# --- compute_stats ---


def test_compute_stats_gate_number_calls_analyze_chakudo() -> None:
    """gate_number source は analyze_chakudo を呼び出す。"""
    from unittest.mock import patch

    mock_result = _make_chakudo_result([_make_chakudo_row(group="1", wins=2, total=10)])
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ):
        metric_cfg = {
            "source": {"type": "gate_number"},
            "rows": {"type": "fixed", "items": [{"label": "1枠", "op": "==", "value": 1}]},
        }
        stats = compute_stats(metric_cfg, _make_manager(), _make_condition(), [])
    assert "1枠" in stats


def test_compute_stats_prev_race_col_builds_fixed_group_by() -> None:
    """prev_race_col source は fixed GroupBy で analyze_chakudo を呼ぶ。"""
    from unittest.mock import patch

    from mykeibadb.analytics import AttrSource

    mock_result = _make_chakudo_result([_make_chakudo_row(group="逃げ", wins=1, total=5)])
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        metric_cfg = {
            "source": {"type": "prev_race_col", "column": "kyakushitsu_hantei"},
            "rows": {
                "type": "fixed",
                "items": [{"label": "逃げ", "op": "==", "value": "1"}],
            },
        }
        compute_stats(metric_cfg, _make_manager(), _make_condition(), [])

    _, _, _, group_by = mock_analyze.call_args[0]
    assert group_by.kind == "fixed"
    assert isinstance(group_by.source, AttrSource)
    assert group_by.source.type == "prev_race_col"
    assert group_by.source.column == "kyakushitsu_hantei"


def test_compute_stats_tokubetsu_race_finish_cumulative() -> None:
    """tokubetsu_race_finish は history 取得 + 行の割り当てで累積計上される。"""
    from unittest.mock import patch

    from mykeibadb.analytics import AttrSource

    raw_rows = [
        _make_chakudo_row(group="1", wins=1, second=0, third=0, chakugai=0, total=1),
        _make_chakudo_row(group="2", wins=0, second=1, third=0, chakugai=0, total=1),
        _make_chakudo_row(group="前年出走無し", wins=0, second=0, third=0, chakugai=5, total=5),
    ]
    mock_result = _make_chakudo_result(raw_rows)
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        metric_cfg = {
            "source": {
                "type": "tokubetsu_race_finish",
                "tokubetsu_kyoso_bango": "0010",
                "year_offset": 1,
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
        stats = compute_stats(metric_cfg, _make_manager(), _make_condition(), [])

    _, _, _, group_by = mock_analyze.call_args[0]
    assert group_by.kind == "history"
    assert isinstance(group_by.source, AttrSource)
    assert group_by.source.type == "tokubetsu_race_finish"
    assert group_by.source.year_offset == 1
    assert "前年3着以内" in stats
    assert stats["前年3着以内"].first == 1
    assert stats["前年3着以内"].second == 1
    assert "前年出走無し" in stats
    assert stats["前年出走無し"].fourth_plus == 5


def _chokyo_match_days_metric_cfg() -> dict[str, Any]:
    """chokyo_match_days 用の metric_cfg を生成する。"""
    return {
        "source": {
            "type": "chokyo_match_days",
            "chokyo_condition": [
                {"course": "hanro", "metric": "gokei", "furlong": 2, "max_value": 239}
            ],
            "days_from": 1,
            "days_to": 13,
        },
        "rows": {
            "type": "fixed",
            "items": [
                {"label": "該当", "op": "any_match"},
                {"label": "非該当", "op": "none_match"},
                {"label": "坂路記録なし", "op": "empty"},
            ],
        },
    }


def test_compute_stats_chokyo_match_days_classifies_any_match_none_match_empty() -> None:
    """chokyo_match_days は行ごとの JSON 配列を any_match/none_match/empty で分類する。"""
    from unittest.mock import patch

    from mykeibadb.analytics import AttrSource

    raw_rows = [
        _make_chakudo_row(group="[[3, true], [10, false]]", wins=1, total=3),
        _make_chakudo_row(group="[[5, false], [12, false]]", wins=0, total=2),
        _make_chakudo_row(group="[]", wins=0, total=1),
    ]
    mock_result = _make_chakudo_result(raw_rows)
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        stats = compute_stats(
            _chokyo_match_days_metric_cfg(), _make_manager(), _make_condition(), []
        )

    _, _, _, group_by = mock_analyze.call_args[0]
    assert group_by.kind == "history"
    assert isinstance(group_by.source, AttrSource)
    assert group_by.source.type == "chokyo_match_days"
    assert stats["該当"].first == 1
    assert stats["該当"].total == 3
    assert stats["非該当"].total == 2
    assert stats["坂路記録なし"].total == 1


def test_compute_stats_chokyo_match_days_merges_rows_with_same_label() -> None:
    """同じ分類に属する複数行の RowStats が合算される。"""
    from unittest.mock import patch

    raw_rows = [
        _make_chakudo_row(group="[[1, true]]", wins=1, total=2),
        _make_chakudo_row(group="[[2, true], [9, false]]", wins=0, total=4),
    ]
    mock_result = _make_chakudo_result(raw_rows)
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ):
        stats = compute_stats(
            _chokyo_match_days_metric_cfg(), _make_manager(), _make_condition(), []
        )

    assert stats["該当"].total == 6
    assert stats["該当"].first == 1
    assert stats["非該当"].total == 0
    assert stats["坂路記録なし"].total == 0


def test_compute_stats_chokyo_match_days_unsupported_op_raises() -> None:
    """chokyo_match_days の rows.items で any_match/none_match/empty 以外の op は ValueError。"""
    from unittest.mock import patch

    raw_rows = [_make_chakudo_row(group="[]", wins=0, total=1)]
    mock_result = _make_chakudo_result(raw_rows)
    metric_cfg = {
        "source": {
            "type": "chokyo_match_days",
            "chokyo_condition": [
                {"course": "hanro", "metric": "gokei", "furlong": 2, "max_value": 239}
            ],
            "days_from": 1,
            "days_to": 13,
        },
        "rows": {
            "type": "fixed",
            "items": [{"label": "該当", "op": "=="}],
        },
    }
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ):
        with pytest.raises(ValueError, match="op"):
            compute_stats(metric_cfg, _make_manager(), _make_condition(), [])


def test_compute_stats_prev_race_grade_groups_by_grade_code() -> None:
    """prev_race_grade は history 取得 + 行の割り当てでG1/G2/G3/その他に集計される。"""
    from unittest.mock import patch

    from mykeibadb.analytics import AttrSource

    raw_rows = [
        _make_chakudo_row(group="A", wins=1, total=1),
        _make_chakudo_row(group="B", wins=0, total=1),
        _make_chakudo_row(group="Z", wins=0, total=1),
    ]
    mock_result = _make_chakudo_result(raw_rows)
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        metric_cfg = {
            "source": {"type": "prev_race_grade"},
            "rows": {
                "type": "fixed",
                "items": [
                    {"label": "G1", "op": "==", "value": "A"},
                    {"label": "G2", "op": "==", "value": "B"},
                    {"label": "G3", "op": "==", "value": "C"},
                    {"label": "その他", "op": "not_in", "value": ["A", "B", "C"]},
                ],
            },
        }
        stats = compute_stats(metric_cfg, _make_manager(), _make_condition(), [])

    _, _, _, group_by = mock_analyze.call_args[0]
    assert group_by.kind == "history"
    assert isinstance(group_by.source, AttrSource)
    assert group_by.source.type == "prev_race_col"
    assert group_by.source.column == "grade_code"
    assert stats["G1"].total == 1
    assert stats["G2"].total == 1
    assert stats["その他"].total == 1


def test_compute_stats_prev_race_finish_groups_by_kakutei_chakujun() -> None:
    """prev_race_finish は前走確定着順を固定行へ集計する。"""
    from unittest.mock import patch

    from mykeibadb.analytics import AttrSource

    raw_rows = [
        _make_chakudo_row(group="1", wins=1, total=1),
        _make_chakudo_row(group="6", wins=0, total=1),
        _make_chakudo_row(group="12", wins=0, total=1),
    ]
    mock_result = _make_chakudo_result(raw_rows)
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        metric_cfg = {
            "source": {"type": "prev_race_finish"},
            "rows": {
                "type": "fixed",
                "items": [
                    {"label": "1着", "op": "==", "value": 1},
                    {"label": "6-9着", "op": "in", "value": [6, 7, 8, 9]},
                    {"label": "10着以下", "op": ">=", "value": 10},
                ],
            },
        }
        stats = compute_stats(metric_cfg, _make_manager(), _make_condition(), [])

    _, _, _, group_by = mock_analyze.call_args[0]
    assert isinstance(group_by.source, AttrSource)
    assert group_by.source.type == "prev_race_col"
    assert group_by.source.column == "kakutei_chakujun"
    assert stats["1着"].total == 1
    assert stats["6-9着"].total == 1
    assert stats["10着以下"].total == 1


def test_compute_stats_prev_race_finish_by_grade_with_grade_codes() -> None:
    """prev_race_finish_by_grade の grade_codes は filters(grade_code in ...) に変換される。"""
    from unittest.mock import patch

    from mykeibadb.analytics import AttrSource

    mock_result = _make_chakudo_result([_make_chakudo_row(group="1", wins=1, total=1)])
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        metric_cfg = {
            "source": {"type": "prev_race_finish_by_grade", "grade_codes": ["A"]},
            "rows": {
                "type": "fixed",
                "items": [{"label": "1着", "op": "==", "value": 1}],
            },
        }
        compute_stats(metric_cfg, _make_manager(), _make_condition(), [])

    _, _, _, group_by = mock_analyze.call_args[0]
    assert isinstance(group_by.source, AttrSource)
    assert group_by.source.column == "kakutei_chakujun"
    assert group_by.source.filters == [{"column": "grade_code", "op": "in", "value": ["A"]}]


def test_compute_stats_prev_race_finish_by_grade_with_exclude_grade_codes() -> None:
    """exclude_grade_codes は filters(grade_code not_in ...) に変換される。"""
    from unittest.mock import patch

    from mykeibadb.analytics import AttrSource

    mock_result = _make_chakudo_result([_make_chakudo_row(group="1", wins=1, total=1)])
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        metric_cfg = {
            "source": {
                "type": "prev_race_finish_by_grade",
                "exclude_grade_codes": ["A", "B", "C"],
            },
            "rows": {
                "type": "fixed",
                "items": [{"label": "1着", "op": "==", "value": 1}],
            },
        }
        compute_stats(metric_cfg, _make_manager(), _make_condition(), [])

    _, _, _, group_by = mock_analyze.call_args[0]
    assert isinstance(group_by.source, AttrSource)
    assert group_by.source.filters == [
        {"column": "grade_code", "op": "not_in", "value": ["A", "B", "C"]}
    ]


def test_compute_stats_prev_race_finish_by_grade_both_grade_codes_raises() -> None:
    """grade_codes と exclude_grade_codes を両方指定すると ValueError になる。"""
    metric_cfg = {
        "source": {
            "type": "prev_race_finish_by_grade",
            "grade_codes": ["A"],
            "exclude_grade_codes": ["B"],
        },
        "rows": {
            "type": "fixed",
            "items": [{"label": "1着", "op": "==", "value": 1}],
        },
    }
    with pytest.raises(ValueError, match="grade_codes と exclude_grade_codes"):
        compute_stats(metric_cfg, _make_manager(), _make_condition(), [])


def test_compute_stats_past_race_top_n_count_builds_fixed_group_by() -> None:
    """past_race_top_n_count source は fixed GroupBy で analyze_chakudo を呼ぶ。"""
    from unittest.mock import patch

    from mykeibadb.analytics import AttrSource

    mock_result = _make_chakudo_result([_make_chakudo_row(group="0勝", wins=0, total=5)])
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
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
        compute_stats(metric_cfg, _make_manager(), _make_condition(), [])

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
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
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
        compute_stats(metric_cfg, _make_manager(), _make_condition(), [])

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
        compute_stats(metric_cfg, _make_manager(), _make_condition(), [])


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
        compute_stats(metric_cfg, _make_manager(), _make_condition(), [])


def test_compute_stats_unknown_type_raises() -> None:
    """未知の source.type は ValueError になる。"""
    metric_cfg = {
        "source": {"type": "unknown_type"},
        "rows": {"type": "dynamic"},
    }
    with pytest.raises(ValueError, match="unknown_type"):
        compute_stats(metric_cfg, _make_manager(), _make_condition(), [])


@pytest.mark.parametrize(
    "src_type, expected_column",
    [
        ("affiliation", "u.tozai_shozoku_code"),
        ("horse_age", "u.barei"),
        ("sex", "u.seibetsu_code"),
        ("gate_number", "u.wakuban"),
        ("popularity", "u.tansho_ninkijun"),
        ("running_style", "u.kyakushitsu_hantei"),
        ("agari_3f_rank", _AGARI_3F_RANK_EXPR),
        ("corner4_juni", CORNER4_JUNI_EXPR),
        ("horse_weight", HORSE_WEIGHT_EXPR),
        ("birth_month", BIRTH_MONTH_EXPR),
    ],
)
def test_compute_stats_race_col_map(src_type: str, expected_column: str) -> None:
    """_RACE_COL_MAP の各 src_type が正しい column で analyze_chakudo を呼ぶ。"""
    from unittest.mock import patch

    from mykeibadb.analytics import GroupBy

    mock_result = _make_chakudo_result([_make_chakudo_row(group="1", wins=1, total=5)])
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        metric_cfg = {
            "source": {"type": src_type},
            "rows": {"type": "fixed", "items": [{"label": "x", "op": "==", "value": 1}]},
        }
        compute_stats(metric_cfg, _make_manager(), _make_condition(), [])

    assert mock_analyze.call_count == 1
    _, _, _, group_by = mock_analyze.call_args[0]
    assert group_by == GroupBy(kind="race_col", column=expected_column)


# --- _yaml_rows_to_rowsdef ---


@pytest.mark.parametrize(
    "op, value, expected",
    [
        ("<", 1600, (0, 1599)),
        (">", 1600, (1601, 9999)),
        ("between", [2, 5], (2, 5)),
    ],
)
def test_yaml_rows_to_rowsdef_lt_gt(op: str, value: object, expected: tuple[int, int]) -> None:
    """< / > / between op が (lo, hi) タプルに正しく変換される。"""
    rows_cfg = {
        "type": "fixed",
        "items": [{"label": "test", "op": op, "value": value}],
    }
    result = _yaml_rows_to_rowsdef(rows_cfg)
    assert result["test"] == expected


# --- get_juusho_race_names ---


def test_get_juusho_race_names_returns_unified_display_names() -> None:
    """grade_code該当レースの表示用レース名（統一後）のセットを返す。"""
    manager = _make_manager()
    manager.fetch_dataframe.side_effect = [
        pd.DataFrame({"race_code": ["2016091109040211", "2017091009040211"]}),
        pd.DataFrame(
            {
                "race_code": ["2016091109040211", "2017091009040211"],
                "display_name": ["産経賞セントウルステークス", "産経賞セントウルステークス"],
            }
        ),
    ]

    result = get_juusho_race_names(manager, ["A", "B", "C"])

    assert result == {"産経賞セントウルステークス"}


def test_get_juusho_race_names_empty_when_no_races() -> None:
    """該当レースが無ければ空集合を返しdisplay_name解決を呼ばない。"""
    manager = _make_manager()
    manager.fetch_dataframe.return_value = pd.DataFrame()

    result = get_juusho_race_names(manager, ["A"])

    assert result == set()
    assert manager.fetch_dataframe.call_count == 1


# --- compute_stats: 集計対象レースの過去走から値を求める source.type ---


def _make_past_races_manager(race_codes: list[str]) -> MagicMock:
    """集計対象レースのレースコードを返す ConnectionManager のモックを生成する。"""
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame({"race_code": race_codes})
    return manager


@pytest.mark.parametrize(
    "src",
    [
        {"type": "prev_corner4_juni"},
        {"type": "prev_distance_diff"},
        {"type": "prev_race_class"},
        {"type": "prev_race_finish_by_class", "race_class": "オープン"},
        {"type": "transport"},
        {"type": "good_baba_top3_count"},
        {"type": "soft_baba_top3_count"},
        {"type": "debut_month"},
    ],
)
def test_compute_stats_history_expr_embeds_race_codes_in_race_col(src: dict[str, Any]) -> None:
    """過去走から値を求める source.type は、レースコードを埋め込んだ race_col で集計する。"""
    from unittest.mock import patch

    race_code = "2025092806040911"
    mock_result = _make_chakudo_result([_make_chakudo_row(group="1", wins=1, total=5)])
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        metric_cfg = {
            "source": src,
            "rows": {"type": "fixed", "items": [{"label": "x", "op": "==", "value": 1}]},
        }
        compute_stats(metric_cfg, _make_past_races_manager([race_code]), _make_condition(), [])

    _, _, _, group_by = mock_analyze.call_args[0]
    assert group_by.kind == "race_col"
    assert race_code in group_by.column


def test_compute_stats_prev_race_finish_by_class_without_race_class_raises() -> None:
    """prev_race_finish_by_class に race_class が無い場合は ValueError になる。"""
    metric_cfg = {
        "source": {"type": "prev_race_finish_by_class"},
        "rows": {"type": "dynamic"},
    }
    with pytest.raises(ValueError, match="race_class"):
        compute_stats(
            metric_cfg, _make_past_races_manager(["2025092806040911"]), _make_condition(), []
        )


def test_compute_stats_passes_filters_to_analyze_chakudo() -> None:
    """追加のエントリフィルタが analyze_chakudo の第2引数に渡る。"""
    from unittest.mock import patch

    entry_filters = [RaceColFilter(column="u.race_code", values=["2025061509030411"])]
    mock_result = _make_chakudo_result([_make_chakudo_row(group="1", wins=1, total=5)])
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        metric_cfg = {
            "source": {"type": "gate_number"},
            "rows": {"type": "fixed", "items": [{"label": "1枠", "op": "==", "value": 1}]},
        }
        compute_stats(metric_cfg, _make_manager(), _make_condition(), entry_filters)

    _, filters, _, _ = mock_analyze.call_args[0]
    assert filters == entry_filters


def test_compute_stats_failed_analysis_raises_runtime_error() -> None:
    """集計に失敗した場合は RuntimeError になる。"""
    from unittest.mock import patch

    mock_result = ChakudoResult(success=False, error="DB error")
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ):
        metric_cfg = {
            "source": {"type": "gate_number"},
            "rows": {"type": "fixed", "items": [{"label": "1枠", "op": "==", "value": 1}]},
        }
        with pytest.raises(RuntimeError, match="DB error"):
            compute_stats(metric_cfg, _make_manager(), _make_condition(), [])


def test_compute_stats_tokubetsu_race_finish_uses_target_race_number() -> None:
    """tokubetsu_race_finish の特別競走番号を省略すると対象レースの特別競走番号を使う。"""
    from unittest.mock import patch

    mock_result = _make_chakudo_result([_make_chakudo_row(group="1", wins=1, total=1)])
    condition = RaceCondition(keibajo_codes=["06"], tokubetsu_kyoso_bango="0016")
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ) as mock_analyze:
        metric_cfg = {
            "source": {"type": "tokubetsu_race_finish", "year_offset": 1},
            "rows": {"type": "fixed", "items": [{"label": "3着以内", "op": "<=", "value": 3}]},
        }
        compute_stats(metric_cfg, _make_manager(), condition, [])

    _, _, _, group_by = mock_analyze.call_args[0]
    assert group_by.source.tokubetsu_kyoso_bango == "0016"


def test_compute_stats_tokubetsu_race_finish_without_race_number_raises() -> None:
    """特別競走番号が source にも condition にも無い場合は ValueError になる。"""
    metric_cfg = {
        "source": {"type": "tokubetsu_race_finish", "year_offset": 1},
        "rows": {"type": "dynamic"},
    }
    with pytest.raises(ValueError, match="特別競走番号"):
        compute_stats(metric_cfg, _make_manager(), RaceCondition(keibajo_codes=["06"]), [])


def test_compute_stats_boolean_multi_uses_race_name_and_kyori_from_source() -> None:
    """boolean_multi は source の race_name・kyori で父馬の勝ち鞍を探す。"""
    from unittest.mock import patch

    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame({"sire_name": ["ディープインパクト"]})
    mock_result = _make_chakudo_result(
        [_make_chakudo_row(group="ディープインパクト", wins=2, total=10)]
    )
    metric_cfg = {
        "rows": {
            "type": "boolean_multi",
            "items": [
                {
                    "label": "父東京優駿勝ち",
                    "source": {
                        "type": "sire_race_condition_finisher",
                        "race_name": "東京優駿",
                        "years": 30,
                    },
                },
                {
                    "label": "父2400mG1勝ち",
                    "source": {
                        "type": "sire_race_condition_finisher",
                        "grade_codes": ["A"],
                        "kyori": "2400",
                        "years": 30,
                    },
                },
            ],
        }
    }
    with patch(
        "g1_predict.modules.gen_trend._trend_stats.analyze_chakudo",
        return_value=mock_result,
    ):
        stats = compute_stats(metric_cfg, manager, _make_condition(), [])

    sql_calls = manager.fetch_dataframe.call_args_list
    assert "TRIM(r.kyosomei_hondai) = %s" in sql_calls[0][0][0]
    assert "東京優駿" in sql_calls[0][1]["params"]
    assert 2400 in sql_calls[1][1]["params"]
    assert stats["父東京優駿勝ち"].first == 2
    assert stats["父2400mG1勝ち"].first == 2


# --- build_item_grouping ---


def test_build_item_grouping_fixed_assigns_all_matching_rows() -> None:
    """fixed 型は、グループの値が当てはまる行すべてを返す。"""
    metric_cfg = {
        "source": {"type": "gate_number"},
        "rows": {
            "type": "fixed",
            "items": [
                {"label": "内", "op": "<=", "value": 4},
                {"label": "外", "op": ">=", "value": 5},
                {"label": "1枠", "op": "==", "value": 1},
            ],
        },
    }
    grouping = build_item_grouping(metric_cfg, _make_manager(), _make_condition(), lambda: [])
    assert grouping.group_by.kind == "race_col"
    assert grouping.group_by.column == "u.wakuban"
    assert grouping.assign_rows("1") == ["内", "1枠"]
    assert grouping.assign_rows("6") == ["外"]
    assert grouping.row_labels == ["内", "外", "1枠"]


def test_build_item_grouping_dynamic_returns_group_value() -> None:
    """dynamic 型は、グループの値をそのまま行の名前として返す。"""
    metric_cfg = {"source": {"type": "jockey_name"}, "rows": {"type": "dynamic"}}
    grouping = build_item_grouping(metric_cfg, _make_manager(), _make_condition(), lambda: [])
    assert grouping.group_by.kind == "subject"
    assert grouping.assign_rows("武豊") == ["武豊"]
    assert grouping.row_labels is None


def test_build_item_grouping_history_expr_uses_given_race_codes() -> None:
    """過去走を参照する式には、渡したレースコードだけを埋め込む。"""
    metric_cfg = {
        "source": {"type": "prev_race_class"},
        "rows": {"type": "fixed", "items": [{"label": "G1", "op": "==", "value": "G1"}]},
    }
    grouping = build_item_grouping(
        metric_cfg, _make_manager(), _make_condition(), lambda: ["2026092706040911"]
    )
    assert grouping.group_by.column is not None
    assert "u3.race_code IN ('2026092706040911')" in grouping.group_by.column


def test_build_item_grouping_does_not_load_race_codes_for_plain_column() -> None:
    """過去走を参照しない項目では、レースコードを取得しない。"""
    metric_cfg = {
        "source": {"type": "gate_number"},
        "rows": {"type": "fixed", "items": [{"label": "1枠", "op": "==", "value": 1}]},
    }

    def fail() -> list[str]:
        raise AssertionError("レースコードを取得してはいけない")

    build_item_grouping(metric_cfg, _make_manager(), _make_condition(), fail)


def test_build_item_grouping_chokyo_match_days_assigns_by_op() -> None:
    """chokyo_match_days は、any_match・none_match・empty で行に割り当てる。"""
    metric_cfg = {
        "source": {
            "type": "chokyo_match_days",
            "chokyo_condition": [
                {"course": "hanro", "metric": "gokei", "furlong": 2, "max_value": 239}
            ],
            "days_from": 1,
            "days_to": 13,
        },
        "rows": {
            "type": "fixed",
            "items": [
                {"label": "該当", "op": "any_match"},
                {"label": "非該当", "op": "none_match"},
                {"label": "記録なし", "op": "empty"},
            ],
        },
    }
    grouping = build_item_grouping(metric_cfg, _make_manager(), _make_condition(), lambda: [])
    assert grouping.assign_rows("[[7, true]]") == ["該当"]
    assert grouping.assign_rows("[[7, false]]") == ["非該当"]
    assert grouping.assign_rows("[]") == ["記録なし"]


def test_build_item_grouping_boolean_multi_assigns_rows_by_sire_name() -> None:
    """boolean_multi は、種牡馬名でグループ分けし、父が条件を満たす行すべてを返す。"""
    metric_cfg = {
        "rows": {
            "type": "boolean_multi",
            "items": [
                {"label": "父勝ち", "source": {"type": "sire_race_condition_finisher"}},
                {
                    "label": "父G1勝ち",
                    "source": {"type": "sire_race_condition_finisher", "grade_codes": ["A"]},
                },
            ],
        }
    }
    with patch(
        "g1_predict.modules.gen_trend._trend_stats._get_sire_winner_set",
        side_effect=[{"A", "B"}, {"A"}],
    ):
        grouping = build_item_grouping(metric_cfg, _make_manager(), _make_condition(), lambda: [])
    assert grouping.group_by.kind == "subject"
    assert grouping.assign_rows("A") == ["父勝ち", "父G1勝ち"]
    assert grouping.assign_rows("B") == ["父勝ち"]
    assert grouping.assign_rows("C") == []
    assert grouping.row_labels == ["父勝ち", "父G1勝ち"]


# 準正常系
def test_build_item_grouping_chokyo_match_days_unknown_op_raises() -> None:
    """chokyo_match_days の未対応の op は ValueError になる。"""
    metric_cfg = {
        "source": {
            "type": "chokyo_match_days",
            "chokyo_condition": [
                {"course": "hanro", "metric": "gokei", "furlong": 2, "max_value": 239}
            ],
            "days_from": 1,
            "days_to": 13,
        },
        "rows": {"type": "fixed", "items": [{"label": "該当", "op": "=="}]},
    }
    with pytest.raises(ValueError):
        build_item_grouping(metric_cfg, _make_manager(), _make_condition(), lambda: [])


def test_build_item_grouping_unknown_source_type_raises() -> None:
    """未対応の source.type は ValueError になる。"""
    metric_cfg = {"source": {"type": "unknown"}, "rows": {"type": "dynamic"}}
    with pytest.raises(ValueError):
        build_item_grouping(metric_cfg, _make_manager(), _make_condition(), lambda: [])
