"""_trend_renderer の単体テスト。"""

import pandas as pd

from g1_predict.modules.gen_predict._trend_models import OTHER_LABEL, TREND_YEARS, Db, RowStats
from g1_predict.modules.gen_predict._trend_renderer import (
    _aggregate_other_stats,
    _format_percent,
    _format_rate,
    _format_table_row,
    _get_dynamic_labels,
    build_category_section,
)

# --- _format_percent ---


def test_format_percent_total_zero() -> None:
    """Total が 0 の場合は "-" を返す。"""
    assert _format_percent(0, 0) == "-"


def test_format_percent_zero_count() -> None:
    """Count が 0 の場合は "0%" を返す。"""
    assert _format_percent(0, 10) == "0%"


def test_format_percent_half() -> None:
    """50% を正しく返す。"""
    assert _format_percent(5, 10) == "50%"


def test_format_percent_rounds() -> None:
    """四捨五入して返す。"""
    assert _format_percent(1, 3) == "33%"


def test_format_percent_all() -> None:
    """100% を正しく返す。"""
    assert _format_percent(3, 3) == "100%"


# --- _format_rate ---


def test_format_rate_total_zero() -> None:
    """Total が 0 の場合は "-" を返す。"""
    assert _format_rate(0, 0) == "-"


def test_format_rate_basic() -> None:
    """回収率 100% を正しく返す。"""
    assert _format_rate(300, 3) == "100%"


def test_format_rate_rounds() -> None:
    """四捨五入して返す。"""
    assert _format_rate(100, 3) == "33%"


def test_format_rate_low() -> None:
    """低い回収率を正しく返す。"""
    assert _format_rate(50, 10) == "5%"


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
    """top_n 件のみ返す。"""
    stats_map = {
        "A": RowStats(first=3),
        "B": RowStats(first=2),
        "C": RowStats(first=1),
    }
    labels = _get_dynamic_labels(stats_map, top_n=2)
    assert labels == ["A", "B"]


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


def test_aggregate_other_stats_payout() -> None:
    """払戻金も正しく合算する。"""
    stats_map = {
        "A": RowStats(tansho_total=1000, fukusho_total=500, total=2),
        "B": RowStats(tansho_total=800, fukusho_total=300, total=2),
    }
    other = _aggregate_other_stats(stats_map, top_labels={"A"})
    assert other.tansho_total == 800
    assert other.fukusho_total == 300


# --- _format_table_row ---


def test_format_table_row_basic() -> None:
    """テーブル行文字列が正しい形式になる。"""
    s = RowStats(
        first=2,
        second=1,
        third=1,
        fourth_plus=6,
        total=10,
        tansho_total=2000,
        fukusho_total=600,
    )
    row = _format_table_row("東京", s)
    assert row.startswith("| 東京 |")
    assert "2頭" in row
    assert "20%" in row


def test_format_table_row_zero_total() -> None:
    """Total が 0 の場合、払戻率は "-" になる。"""
    s = RowStats()
    row = _format_table_row("ラベル", s)
    assert "0頭" in row
    assert "- |" in row


# --- build_category_section ---


def _make_empty_db(matched_years: int = TREND_YEARS) -> Db:
    """空の Db インスタンスを生成する。"""
    return Db(
        past_race_codes=[],
        results={},
        payoffs={},
        history=pd.DataFrame(),
        shosai={},
        kyosoba={},
        sire_finisher_sets={},
        matched_years=matched_years,
    )


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


def test_build_category_section_has_header() -> None:
    """## カテゴリ名 ヘッダーで始まる。"""
    db = _make_empty_db()
    result = build_category_section("出走馬傾向", [_make_fixed_metric_cfg()], db)
    assert result.startswith("## 出走馬傾向")


def test_build_category_section_has_hikaku_table() -> None:
    """### 比較表 プレースホルダーを含む。"""
    db = _make_empty_db()
    result = build_category_section("出走馬傾向", [_make_fixed_metric_cfg()], db)
    assert "### 比較表" in result


def test_build_category_section_has_metric_header() -> None:
    """Metric 名の h3 ヘッダーを含む。"""
    db = _make_empty_db()
    result = build_category_section(
        "出走馬傾向", [_make_fixed_metric_cfg("枠番")], db
    )
    assert "### 枠番" in result


def test_build_category_section_note_when_few_years() -> None:
    """TREND_YEARS 未満の場合、年数注釈を付ける。"""
    db = _make_empty_db(matched_years=3)
    result = build_category_section("出走馬傾向", [_make_fixed_metric_cfg()], db)
    assert "3年分のみ対象" in result


def test_build_category_section_no_note_when_full_years() -> None:
    """TREND_YEARS 年分あれば注釈なし。"""
    db = _make_empty_db(matched_years=TREND_YEARS)
    result = build_category_section("出走馬傾向", [_make_fixed_metric_cfg()], db)
    assert "のみ対象" not in result


def test_build_category_section_hikaku_table_at_end() -> None:
    """### 比較表 が末尾に配置される。"""
    db = _make_empty_db()
    result = build_category_section("出走馬傾向", [_make_fixed_metric_cfg()], db)
    assert result.rstrip().endswith("### 比較表")
