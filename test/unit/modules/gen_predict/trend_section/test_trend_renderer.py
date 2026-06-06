"""_trend_renderer の単体テスト。"""

from unittest.mock import MagicMock, patch

import pytest
from mykeibadb.analytics import RaceCondition

from g1_predict.modules.gen_predict._trend_models import OTHER_LABEL, TREND_YEARS, RowStats
from g1_predict.modules.gen_predict._trend_renderer import (
    _aggregate_other_stats,
    _build_metric_section,
    _format_percent,
    _format_table_row,
    _get_dynamic_labels,
    build_category_section,
)


def _make_manager() -> MagicMock:
    """ConnectionManager のモックを生成する。"""
    return MagicMock()


def _make_condition() -> RaceCondition:
    """テスト用 RaceCondition を生成する。"""
    return RaceCondition(keibajo_code="05", kyori=2400, year_from="2016", year_to="2025")


# --- _format_percent ---


@pytest.mark.parametrize(
    "count, total, expected",
    [
        (0, 0, "-"),
        (0, 10, "0%"),
        (5, 10, "50%"),
        (1, 3, "33%"),
        (3, 3, "100%"),
    ],
)
def test_format_percent(count: int, total: int, expected: str) -> None:
    """_format_percent が count/total から正しいパーセント文字列を返す。"""
    assert _format_percent(count, total) == expected


# --- _get_dynamic_labels ---


def test_get_dynamic_labels_sorted_by_top3() -> None:
    """3着内数の多い順に並ぶ。"""
    stats_map = {
        "A": RowStats(first=3, second=2, third=1),
        "B": RowStats(first=0, second=0, third=0),
        "C": RowStats(first=1, second=1, third=1),
    }
    labels = _get_dynamic_labels(stats_map, top_n=None)
    assert labels[0] == "A"
    assert labels[1] == "C"
    assert labels[2] == "B"


def test_get_dynamic_labels_top_n() -> None:
    """top_n 件のみ返す（タイなし）。"""
    stats_map = {
        "A": RowStats(first=3),
        "B": RowStats(first=2),
        "C": RowStats(first=1),
    }
    labels = _get_dynamic_labels(stats_map, top_n=2)
    assert labels == ["A", "B"]


def test_get_dynamic_labels_top_n_tie_includes_all() -> None:
    """top_n 位と同数のラベルを全て含める。"""
    stats_map = {
        "A": RowStats(first=3),
        "B": RowStats(first=2),
        "C": RowStats(first=2),
        "D": RowStats(first=2),
        "E": RowStats(first=1),
        "F": RowStats(first=1),
    }
    labels = _get_dynamic_labels(stats_map, top_n=2)
    assert "A" in labels
    assert "B" in labels
    assert "C" in labels
    assert "D" in labels
    assert "E" not in labels
    assert len(labels) == 4


def test_get_dynamic_labels_excludes_other_label() -> None:
    """OTHER_LABEL は除外される。"""
    stats_map = {
        "A": RowStats(first=1),
        OTHER_LABEL: RowStats(first=100),
    }
    labels = _get_dynamic_labels(stats_map, top_n=None)
    assert OTHER_LABEL not in labels
    assert labels == ["A"]


def test_get_dynamic_labels_top_n_none_returns_all() -> None:
    """top_n=None の場合は全件返す。"""
    stats_map = {"A": RowStats(first=1), "B": RowStats(first=2)}
    labels = _get_dynamic_labels(stats_map, top_n=None)
    assert len(labels) == 2


# --- _aggregate_other_stats ---


def test_aggregate_other_stats_sums_non_top() -> None:
    """top_labels 以外のラベルを合算する。"""
    stats_map = {
        "A": RowStats(first=2, second=1, third=0, fourth_plus=1, total=4),
        "B": RowStats(first=1, second=0, third=1, fourth_plus=2, total=4),
        "C": RowStats(first=0, second=0, third=1, fourth_plus=3, total=4),
    }
    other = _aggregate_other_stats(stats_map, top_labels={"A"})
    assert other.first == 1
    assert other.second == 0
    assert other.third == 2
    assert other.total == 8


def test_aggregate_other_stats_all_in_top_labels() -> None:
    """全ラベルが top_labels の場合、合算値は 0。"""
    stats_map = {"A": RowStats(first=5, total=5)}
    other = _aggregate_other_stats(stats_map, top_labels={"A"})
    assert other.first == 0
    assert other.total == 0


def test_aggregate_other_stats_weighted_kaishuu() -> None:
    """回収率が加重平均で合算される。"""
    stats_map = {
        "A": RowStats(tansho_kaishuu=100.0, fukusho_kaishuu=80.0, total=10),
        "B": RowStats(tansho_kaishuu=60.0, fukusho_kaishuu=40.0, total=10),
    }
    other = _aggregate_other_stats(stats_map, top_labels=set())
    assert other.tansho_kaishuu == 80.0
    assert other.fukusho_kaishuu == 60.0
    assert other.total == 20


# --- _format_table_row ---


def test_format_table_row_basic() -> None:
    """テーブル行文字列が正しい形式になる。"""
    s = RowStats(
        first=2,
        second=1,
        third=1,
        fourth_plus=6,
        total=10,
        tansho_kaishuu=80.0,
        fukusho_kaishuu=60.0,
    )
    row = _format_table_row("東京", s)
    assert row.startswith("| 東京 |")
    assert "2頭" in row
    assert "20%" in row
    assert "80%" in row


def test_format_table_row_zero_total() -> None:
    """Total が 0 の場合、払戻率は "-" になる。"""
    s = RowStats()
    row = _format_table_row("ラベル", s)
    assert "0頭" in row
    assert "- |" in row


# --- build_category_section ---


def _make_fixed_metric_cfg(name: str = "枠番") -> dict:
    """Metric 設定（fixed 型）を生成する。"""
    return {
        "name": name,
        "rows": {
            "type": "fixed",
            "items": [
                {"label": "1-4枠", "op": "<=", "value": 4},
                {"label": "5-8枠", "op": ">=", "value": 5},
            ],
        },
        "source": {"type": "gate_number"},
    }


def _empty_stats_map(_metric_cfg: object, _manager: object, _condition: object) -> dict:
    """空の stats_map を返すモック。"""
    return {}


def test_build_category_section_has_header() -> None:
    """## カテゴリ名 ヘッダーで始まる。"""
    with patch(
        "g1_predict.modules.gen_predict._trend_renderer.compute_stats",
        side_effect=_empty_stats_map,
    ):
        result = build_category_section(
            "出走馬傾向", [_make_fixed_metric_cfg()], _make_manager(), _make_condition()
        )
    assert result.startswith("## 出走馬傾向")


def test_build_category_section_has_hikaku_table() -> None:
    """### 比較表 プレースホルダーを含む。"""
    with patch(
        "g1_predict.modules.gen_predict._trend_renderer.compute_stats",
        side_effect=_empty_stats_map,
    ):
        result = build_category_section(
            "出走馬傾向", [_make_fixed_metric_cfg()], _make_manager(), _make_condition()
        )
    assert "### 比較表" in result


def test_build_category_section_has_metric_header() -> None:
    """Metric 名の h3 ヘッダーを含む。"""
    with patch(
        "g1_predict.modules.gen_predict._trend_renderer.compute_stats",
        side_effect=_empty_stats_map,
    ):
        result = build_category_section(
            "出走馬傾向",
            [_make_fixed_metric_cfg("枠番")],
            _make_manager(),
            _make_condition(),
        )
    assert "### 枠番" in result


def test_build_category_section_hikaku_table_at_end() -> None:
    """### 比較表 が末尾に配置される。"""
    with patch(
        "g1_predict.modules.gen_predict._trend_renderer.compute_stats",
        side_effect=_empty_stats_map,
    ):
        result = build_category_section(
            "出走馬傾向", [_make_fixed_metric_cfg()], _make_manager(), _make_condition()
        )
    assert result.rstrip().endswith("### 比較表")


def test_build_category_section_trend_years_in_header() -> None:
    """過去N年の記述がヘッダーに含まれる。"""
    with patch(
        "g1_predict.modules.gen_predict._trend_renderer.compute_stats",
        side_effect=_empty_stats_map,
    ):
        result = build_category_section(
            "出走馬傾向", [_make_fixed_metric_cfg()], _make_manager(), _make_condition()
        )
    assert f"過去{TREND_YEARS}年" in result


# --- _build_metric_section: always_include_grades ---


def test_build_metric_section_always_include_grades_adds_missing_juusho() -> None:
    """always_include_grades 指定時、top_n 外の重賞が表示される。"""
    stats_map = {
        "天皇賞": RowStats(first=5, second=3, third=2, total=20),
        "マイルCS": RowStats(first=4, second=2, third=2, total=18),
        "スプリンターズS": RowStats(first=3, second=2, third=1, total=15),
        "京王杯SC": RowStats(first=2, second=1, third=1, total=12),
        "阪神C": RowStats(first=1, second=1, third=0, total=10),
        "ヴィクトリアM": RowStats(first=1, second=0, third=0, total=8),
    }

    metric_cfg = {
        "name": "前走レース",
        "source": {"type": "prev_race_name", "overseas_label": "海外"},
        "rows": {
            "type": "dynamic",
            "top_n": 5,
            "always_include_grades": ["A", "B", "C"],
        },
    }

    with (
        patch(
            "g1_predict.modules.gen_predict._trend_renderer.compute_stats",
            return_value=stats_map,
        ),
        patch(
            "g1_predict.modules.gen_predict._trend_renderer.get_juusho_race_names",
            return_value={"天皇賞", "マイルCS", "スプリンターズS", "ヴィクトリアM"},
        ),
    ):
        result = _build_metric_section(metric_cfg, _make_manager(), _make_condition())

    assert "ヴィクトリアM" in result
    assert "天皇賞" in result


def test_build_metric_section_always_include_grades_overseas_not_added() -> None:
    """海外ラベルは重賞名セットに含まれないため追加されない。"""
    stats_map = {
        "海外": RowStats(first=1, second=0, third=0, total=3),
        "マイルCS": RowStats(first=5, second=3, third=2, total=20),
    }

    metric_cfg = {
        "name": "前走レース",
        "source": {"type": "prev_race_name", "overseas_label": "海外"},
        "rows": {
            "type": "dynamic",
            "top_n": 1,
            "always_include_grades": ["A"],
        },
    }

    with (
        patch(
            "g1_predict.modules.gen_predict._trend_renderer.compute_stats",
            return_value=stats_map,
        ),
        patch(
            "g1_predict.modules.gen_predict._trend_renderer.get_juusho_race_names",
            return_value={"マイルCS"},
        ),
    ):
        result = _build_metric_section(metric_cfg, _make_manager(), _make_condition())

    lines = result.split("\n")
    row_lines = [
        ln for ln in lines
        if ln.startswith("| ") and "---" not in ln and "前走レース" not in ln
    ]
    labels_in_result = [ln.split("|")[1].strip() for ln in row_lines]
    assert "海外" not in labels_in_result
