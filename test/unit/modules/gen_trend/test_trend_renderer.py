"""_trend_renderer の単体テスト。"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from mykeibadb.analytics import RaceColFilter, RaceCondition

from g1_predict.modules.gen_trend._trend_catalog import TrendCategory, TrendItem
from g1_predict.modules.gen_trend._trend_loader import TrendContext
from g1_predict.modules.gen_trend._trend_models import OTHER_LABEL, RowStats, TrendCondition
from g1_predict.modules.gen_trend._trend_renderer import (
    ItemTable,
    _aggregate_other_stats,
    _format_chakudo,
    _format_item_section,
    _format_percent,
    _format_table_row,
    _get_dynamic_labels,
    build_category_section,
    build_comparison_section,
    build_item_table,
    format_condition_note,
    format_scope_note,
)

_RENDERER = "g1_predict.modules.gen_trend._trend_renderer"


def _render_item(item: TrendItem, context: TrendContext) -> str | None:
    """項目の表を作り、Markdownセクションにする。表を出さない項目は None。"""
    table = build_item_table(item, context)
    return None if table is None else _format_item_section(table, with_entries=False)


def _render_category(category: TrendCategory, context: TrendContext) -> str:
    """カテゴリの各項目の表を作り、カテゴリのセクションにする。"""
    tables: list[ItemTable] = []
    for item in category.items:
        table = build_item_table(item, context)
        if table is not None:
            tables.append(table)
    return build_category_section(category, context, tables)


def _make_context(
    first_year: int = 2016,
    years: int = 10,
    race_count: int = 10,
    keibajo_code: str = "05",
    shiba_da: str = "芝",
    kyori: int = 2400,
) -> TrendContext:
    """テスト用 TrendContext を生成する。"""
    return TrendContext(
        manager=MagicMock(),
        condition=RaceCondition(
            keibajo_codes=[keibajo_code],
            kyori=kyori,
            year_from=str(first_year),
            year_to="2025",
        ),
        race_year=2026,
        race_name="東京優駿",
        kyori=kyori,
        keibajo_code=keibajo_code,
        shiba_da=shiba_da,
        first_year=first_year,
        years=years,
        race_count=race_count,
    )


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


def test_get_dynamic_labels_exclude_no_top3() -> None:
    """exclude_no_top3 指定時、3着内数が0のラベルは上位に入れない。"""
    stats_map = {
        "A": RowStats(first=1, total=3),
        "B": RowStats(fourth_plus=5, total=5),
        "C": RowStats(fourth_plus=2, total=2),
    }
    assert _get_dynamic_labels(stats_map, top_n=2, exclude_no_top3=True) == ["A"]
    assert _get_dynamic_labels(stats_map, top_n=2) == ["A", "B", "C"]


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
    assert "2-1-1-6" in row
    assert "20%" in row
    assert "80%" in row


def test_format_table_row_zero_total() -> None:
    """Total が 0 の場合、払戻率は "-" になる。"""
    s = RowStats()
    row = _format_table_row("ラベル", s)
    assert "0-0-0-0" in row
    assert "- |" in row


@pytest.mark.parametrize(
    "tansho, fukusho, expected",
    [
        (100.4, 99.0, "| 100% | 99% |"),
        (100.6, 250.0, "| **101%** | **250%** |"),
        (180.0, 60.0, "| **180%** | 60% |"),
    ],
)
def test_format_table_row_bolds_kaishuu_over_100(
    tansho: float, fukusho: float, expected: str
) -> None:
    """単回・複回は、四捨五入した値が100%を超える場合に太字にする。"""
    s = RowStats(first=1, fourth_plus=1, total=2, tansho_kaishuu=tansho, fukusho_kaishuu=fukusho)
    assert _format_table_row("A", s).endswith(expected)


# --- _format_chakudo ---


def test_format_chakudo_formats_counts() -> None:
    """着度数が「1着-2着-3着-着外」形式の文字列になる。"""
    s = RowStats(first=0, second=1, third=1, fourth_plus=15)
    assert _format_chakudo(s) == "0-1-1-15"


# --- build_category_section ---


def _make_fixed_config(**rows_options: Any) -> dict[str, Any]:
    """fixed 型の項目定義を生成する。"""
    return {
        "rows": {
            "type": "fixed",
            "items": [
                {"label": "1-4枠", "op": "<=", "value": 4},
                {"label": "5-8枠", "op": ">=", "value": 5},
            ],
            **rows_options,
        },
        "source": {"type": "gate_number"},
    }


def _make_item(
    name: str = "枠番",
    condition: TrendCondition | None = None,
    **config_options: Any,
) -> TrendItem:
    """テスト用 TrendItem を生成する。"""
    config = _make_fixed_config()
    config.update(config_options)
    return TrendItem(name=name, config=config, condition=condition)


def _make_category(
    items: list[TrendItem] | None = None,
    description: str = "同じG1レースの過去{years}年における傾向",
) -> TrendCategory:
    """テスト用 TrendCategory を生成する。"""
    return TrendCategory(
        name="基本項目", description=description, items=items if items else [_make_item()]
    )


def test_build_category_section_has_header_and_description() -> None:
    """## カテゴリ名 の直後にカテゴリの説明文が続く。"""
    with patch(f"{_RENDERER}.compute_stats", return_value={}):
        result = _render_category(_make_category(), _make_context())
    assert result.startswith("## 基本項目\n\n同じG1レースの過去10年における傾向\n\n### 枠番")


def test_build_category_section_embeds_actual_years_in_description() -> None:
    """説明文の {years} には実際に集計した年数が入る。"""
    with patch(f"{_RENDERER}.compute_stats", return_value={}):
        result = _render_category(_make_category(), _make_context(first_year=2017, years=9))
    assert "同じG1レースの過去9年における傾向" in result


def test_build_category_section_description_without_years() -> None:
    """{years} を含まない説明文はそのまま出力される。"""
    category = _make_category(description="調教の内容")
    with patch(f"{_RENDERER}.compute_stats", return_value={}):
        result = _render_category(category, _make_context())
    assert result.startswith("## 基本項目\n\n調教の内容\n\n")


def test_build_comparison_section_has_heading_description_and_image() -> None:
    """比較表のセクションは、## 比較表・説明文・画像の順に並ぶ。"""
    assert build_comparison_section("img/trend_table/比較表.png") == (
        "## 比較表\n\n今回の出走馬を項目ごとに見比べる表\n\n![比較表](img/trend_table/比較表.png)"
    )


def test_build_category_section_keeps_item_order() -> None:
    """項目は渡された順に並ぶ。"""
    category = _make_category([_make_item("人気"), _make_item("枠順")])
    with patch(f"{_RENDERER}.compute_stats", return_value={}):
        result = _render_category(category, _make_context())
    assert result.index("### 人気") < result.index("### 枠順")


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

    item = TrendItem(
        name="前走レース",
        config={
            "source": {"type": "prev_race_name", "overseas_label": "海外"},
            "rows": {
                "type": "dynamic",
                "top_n": 5,
                "always_include_grades": ["A", "B", "C"],
            },
        },
        condition=None,
    )

    with (
        patch(f"{_RENDERER}.compute_stats", return_value=stats_map),
        patch(
            f"{_RENDERER}.get_juusho_race_names",
            return_value={"天皇賞", "マイルCS", "スプリンターズS", "ヴィクトリアM"},
        ),
    ):
        result = _render_item(item, _make_context())

    assert "ヴィクトリアM" in result
    assert "天皇賞" in result


def test_build_metric_section_always_include_grades_overseas_not_added() -> None:
    """海外ラベルは重賞名セットに含まれないため追加されない。"""
    stats_map = {
        "海外": RowStats(first=1, second=0, third=0, total=3),
        "マイルCS": RowStats(first=5, second=3, third=2, total=20),
    }

    item = TrendItem(
        name="前走レース",
        config={
            "source": {"type": "prev_race_name", "overseas_label": "海外"},
            "rows": {
                "type": "dynamic",
                "top_n": 1,
                "always_include_grades": ["A"],
            },
        },
        condition=None,
    )

    with (
        patch(f"{_RENDERER}.compute_stats", return_value=stats_map),
        patch(f"{_RENDERER}.get_juusho_race_names", return_value={"マイルCS"}),
    ):
        result = _render_item(item, _make_context())

    lines = result.split("\n")
    row_lines = [
        ln for ln in lines
        if ln.startswith("| ") and "---" not in ln and "前走レース" not in ln
    ]
    labels_in_result = [ln.split("|")[1].strip() for ln in row_lines]
    assert "海外" not in labels_in_result


# --- _build_metric_section: dynamic ---


def test_build_metric_section_dynamic_top_n_adds_other_row() -> None:
    """top_n 指定の dynamic は上位の行と「その他」行を出力する。"""
    stats_map = {
        "A": RowStats(first=3, fourth_plus=1, total=4),
        "B": RowStats(first=1, fourth_plus=2, total=3),
        "C": RowStats(fourth_plus=5, total=5),
    }
    item = TrendItem(
        name="騎手",
        config={"source": {"type": "jockey_name"}, "rows": {"type": "dynamic", "top_n": 2}},
        condition=None,
    )
    with patch(f"{_RENDERER}.compute_stats", return_value=stats_map):
        result = _render_item(item, _make_context())

    assert "| A | 3-0-0-1 |" in result
    assert "| B | 1-0-0-2 |" in result
    assert "| C |" not in result
    assert f"| {OTHER_LABEL} | 0-0-0-5 |" in result


def test_build_metric_section_does_not_require_entries() -> None:
    """騎手・生産者・種牡馬は集計対象の過去の出走馬から行を作り、出走馬の情報を必要としない。"""
    stats_map = {"武豊": RowStats(first=1, fourth_plus=5, total=6)}
    item = TrendItem(
        name="騎手",
        config={"source": {"type": "jockey_name"}, "rows": {"type": "dynamic", "top_n": 10}},
        condition=None,
    )
    context = _make_context()
    with patch(f"{_RENDERER}.compute_stats", return_value=stats_map):
        result = _render_item(item, context)

    assert "| 武豊 | 1-0-0-5 |" in result
    context.manager.fetch_dataframe.assert_not_called()


# --- _build_metric_section: hide_empty ---


def test_build_metric_section_hide_empty_omits_zero_rows() -> None:
    """hide_empty 指定時、頭数が0の行を出力しない。"""
    stats_map = {"1-4枠": RowStats(first=1, fourth_plus=3, total=4)}
    item = TrendItem(name="枠番", config=_make_fixed_config(hide_empty=True), condition=None)
    with patch(f"{_RENDERER}.compute_stats", return_value=stats_map):
        result = _render_item(item, _make_context())

    assert "| 1-4枠 |" in result
    assert "5-8枠" not in result


def test_build_metric_section_without_hide_empty_keeps_zero_rows() -> None:
    """hide_empty を指定しない場合、頭数が0の行も出力する。"""
    stats_map = {"1-4枠": RowStats(first=1, fourth_plus=3, total=4)}
    with patch(f"{_RENDERER}.compute_stats", return_value=stats_map):
        result = _render_item(_make_item(), _make_context())

    assert "| 5-8枠 | 0-0-0-0 | - | - | - | - |" in result


# --- hide_if_empty ---


def test_build_metric_section_hide_if_empty_returns_none_without_horses() -> None:
    """hide_if_empty 指定時、該当馬が1頭もいなければ表を出力しない。"""
    stats_map = {"1-4枠": RowStats(), "5-8枠": RowStats()}
    with patch(f"{_RENDERER}.compute_stats", return_value=stats_map):
        assert _render_item(_make_item(hide_if_empty=True), _make_context()) is None


def test_build_metric_section_hide_if_empty_keeps_table_with_horses() -> None:
    """hide_if_empty 指定時でも、該当馬がいれば0頭の行を含めて表を出力する。"""
    stats_map = {"1-4枠": RowStats(first=1, fourth_plus=3, total=4)}
    with patch(f"{_RENDERER}.compute_stats", return_value=stats_map):
        result = _render_item(_make_item(hide_if_empty=True), _make_context())

    assert result is not None
    assert "| 5-8枠 | 0-0-0-0 | - | - | - | - |" in result


def test_build_category_section_omits_hidden_item() -> None:
    """該当馬がいない hide_if_empty の項目は、カテゴリのセクションから見出しごと除く。"""
    items = [_make_item(name="前走新馬着順", hide_if_empty=True), _make_item(name="枠番")]
    stats_map = {"1-4枠": RowStats()}
    with patch(f"{_RENDERER}.compute_stats", return_value=stats_map):
        result = _render_category(_make_category(items), _make_context())

    assert "### 前走新馬着順" not in result
    assert "### 枠番" in result


# --- format_scope_note ---


def test_format_scope_note_full_period() -> None:
    """過去 TREND_YEARS 年を集計した場合の注記。"""
    context = _make_context(
        first_year=2016, years=10, race_count=10, keibajo_code="06", kyori=1200
    )
    assert format_scope_note(context, "スプリンターズS") == (
        "※集計対象は、過去10年（2016〜2025年）に中山芝1200mで行われたスプリンターズS（10回）。"
    )


def test_format_scope_note_since_g1_promotion() -> None:
    """G1になってから TREND_YEARS 年に満たない場合の注記。"""
    context = _make_context(
        first_year=2017, years=9, race_count=9, keibajo_code="09", kyori=2000
    )
    assert format_scope_note(context, "大阪杯") == (
        "※集計対象は、G1になった2017年から前年まで（2017〜2025年）"
        "に阪神芝2000mで行われた大阪杯（9回）。"
    )


def test_format_scope_note_counts_races_not_years() -> None:
    """回数は年数ではなく集計対象のレース数になる。"""
    context = _make_context(
        first_year=2016, years=10, race_count=9, keibajo_code="09", kyori=2200
    )
    assert format_scope_note(context, "宝塚記念").endswith("宝塚記念（9回）。")


def test_format_scope_note_dirt() -> None:
    """ダートのレースは芝ダに「ダ」を使う。"""
    context = _make_context(shiba_da="ダ", keibajo_code="05", kyori=1600)
    assert "東京ダ1600mで" in format_scope_note(context, "フェブラリーS")


# --- format_condition_note ---


def test_format_condition_note_none_returns_empty() -> None:
    """condition が None の場合は空文字を返す。"""
    assert format_condition_note(None) == ""


def test_format_condition_note_full() -> None:
    """全項目指定時は「・」で区切って並べる。"""
    condition = TrendCondition(
        keibajo_codes=("09",),
        course_kubun="B",
        course_days=(7, 8),
        kaisai_nichime=(4,),
        babajotai_codes=("1",),
    )
    assert format_condition_note(condition) == "※阪神・4日目・Bコース7・8日目・良のみ"


def test_format_condition_note_hanshin_4th_day_good_track() -> None:
    """宝塚記念の条件（阪神・4日目・良）の注記。"""
    condition = TrendCondition(
        keibajo_codes=("09",), kaisai_nichime=(4,), babajotai_codes=("1",)
    )
    assert format_condition_note(condition) == "※阪神・4日目・良のみ"


def test_format_condition_note_multiple_values_joined() -> None:
    """複数値は「・」で連結される。"""
    condition = TrendCondition(
        keibajo_codes=("09", "06"), kaisai_nichime=(3, 4), babajotai_codes=("1", "2")
    )
    note = format_condition_note(condition)
    assert "阪神・中山" in note
    assert "3・4日目" in note
    assert "良・稍" in note


def test_format_condition_note_course_kubun_only() -> None:
    """course_kubun のみの場合は「{区分}コース」だけが出る。"""
    assert format_condition_note(TrendCondition(course_kubun="B")) == "※Bコースのみ"


def test_format_condition_note_course_days_only() -> None:
    """course_days のみの場合は「コース{日数}日目」になる。"""
    assert format_condition_note(TrendCondition(course_days=(4,))) == "※コース4日目のみ"


@pytest.mark.parametrize(
    "babajotai_codes, expected_baba_str",
    [
        (("1",), "良"),
        (("2",), "稍"),
        (("3",), "重"),
        (("4",), "不"),
    ],
)
def test_format_condition_note_baba_uses_domain_names(
    babajotai_codes: tuple[str, ...], expected_baba_str: str
) -> None:
    """馬場状態は keiba-domain の名称をそのまま使い、「馬場」を付けない。"""
    condition = TrendCondition(babajotai_codes=babajotai_codes)
    assert format_condition_note(condition) == f"※{expected_baba_str}のみ"


# --- _build_metric_section: condition ---


def test_build_metric_section_with_condition_appends_note() -> None:
    """条件を注入した項目は、表の直下に開催条件の注記を出力する。"""
    condition = TrendCondition(
        keibajo_codes=("09",), kaisai_nichime=(4,), babajotai_codes=("1",)
    )
    item = _make_item(condition=condition)
    context = _make_context(keibajo_code="09")
    with patch(f"{_RENDERER}.compute_stats", return_value={}):
        result = _render_item(item, context)

    assert result.endswith("\n\n※阪神・4日目・良のみ")


def test_build_metric_section_without_condition_no_note() -> None:
    """条件を注入しない項目には、※注記を出力しない。"""
    with patch(f"{_RENDERER}.compute_stats", return_value={}):
        result = _render_item(_make_item(), _make_context())

    assert "※" not in result


def test_build_metric_section_passes_applied_condition_to_compute_stats() -> None:
    """注入した条件で絞り込んだ RaceCondition とエントリフィルタで集計する。"""
    condition = TrendCondition(kaisai_nichime=(4,), course_kubun="B")
    item = _make_item(condition=condition)
    context = _make_context(keibajo_code="09")
    narrowed = RaceCondition(keibajo_codes=["09"], kaisai_nichime=[4])
    entry_filters = [RaceColFilter(column="u.race_code", values=["2018062409030811"])]
    with (
        patch(f"{_RENDERER}.apply_trend_condition", return_value=(narrowed, entry_filters)),
        patch(f"{_RENDERER}.compute_stats", return_value={}) as mock_compute,
    ):
        _render_item(item, context)

    args = mock_compute.call_args[0]
    assert args[1] is context.manager
    assert args[2] is narrowed
    assert args[3] is entry_filters


def test_build_metric_section_without_condition_uses_base_condition() -> None:
    """条件を注入しない項目は、既定の集計対象で集計する。"""
    context = _make_context()
    with patch(f"{_RENDERER}.compute_stats", return_value={}) as mock_compute:
        _render_item(_make_item(), context)

    args = mock_compute.call_args[0]
    assert args[2] is context.condition
    assert args[3] == []


# --- _build_metric_section: note ---


def test_build_metric_section_appends_item_note() -> None:
    """項目に note がある場合は、表の直下に出力する。"""
    item = _make_item(note="※父の実績は過去30年のレースで判定")
    with patch(f"{_RENDERER}.compute_stats", return_value={}):
        result = _render_item(item, _make_context())

    assert result.endswith("\n\n※父の実績は過去30年のレースで判定")


def test_build_metric_section_condition_note_precedes_item_note() -> None:
    """開催条件の注記の後に項目の note を出力する。"""
    item = _make_item(condition=TrendCondition(kaisai_nichime=(4,)), note="※補足")
    context = _make_context(keibajo_code="09")
    with (
        patch(f"{_RENDERER}.apply_trend_condition", return_value=(RaceCondition(), [])),
        patch(f"{_RENDERER}.compute_stats", return_value={}),
    ):
        result = _render_item(item, context)

    assert result.endswith("\n\n※4日目のみ\n\n※補足")
