"""_trend_renderer の単体テスト。"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from mykeibadb.analytics import RaceCondition, Subject

from g1_predict.modules.gen_predict._trend_models import OTHER_LABEL, TREND_YEARS, RowStats
from g1_predict.modules.gen_predict._trend_renderer import (
    _aggregate_other_stats,
    _build_metric_section,
    _format_chakudo,
    _format_percent,
    _format_table_row,
    _get_dynamic_labels,
    build_category_section,
    format_condition_note,
    get_race_subject_entries,
    sort_entry_labels,
)


def _make_manager() -> MagicMock:
    """ConnectionManager のモックを生成する。"""
    return MagicMock()


def _make_condition() -> RaceCondition:
    """テスト用 RaceCondition を生成する。"""
    return RaceCondition(keibajo_codes=["05"], kyori=2400, year_from="2016", year_to="2025")


RACE_YEAR = 2026


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
    assert "2-1-1-6" in row
    assert "20%" in row
    assert "80%" in row


def test_format_table_row_zero_total() -> None:
    """Total が 0 の場合、払戻率は "-" になる。"""
    s = RowStats()
    row = _format_table_row("ラベル", s)
    assert "0-0-0-0" in row
    assert "- |" in row


# --- _format_chakudo ---


def test_format_chakudo_formats_counts() -> None:
    """着度数が「1着-2着-3着-着外」形式の文字列になる。"""
    s = RowStats(first=0, second=1, third=1, fourth_plus=15)
    assert _format_chakudo(s) == "0-1-1-15"


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
            "出走馬傾向", [_make_fixed_metric_cfg()], _make_manager(), _make_condition(), RACE_YEAR
        )
    assert result.startswith("## 出走馬傾向")


def test_build_category_section_has_hikaku_table() -> None:
    """### 比較表 プレースホルダーを含む。"""
    with patch(
        "g1_predict.modules.gen_predict._trend_renderer.compute_stats",
        side_effect=_empty_stats_map,
    ):
        result = build_category_section(
            "出走馬傾向", [_make_fixed_metric_cfg()], _make_manager(), _make_condition(), RACE_YEAR
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
            RACE_YEAR,
        )
    assert "### 枠番" in result


def test_build_category_section_hikaku_table_at_end() -> None:
    """### 比較表 が末尾に配置される。"""
    with patch(
        "g1_predict.modules.gen_predict._trend_renderer.compute_stats",
        side_effect=_empty_stats_map,
    ):
        result = build_category_section(
            "出走馬傾向", [_make_fixed_metric_cfg()], _make_manager(), _make_condition(), RACE_YEAR
        )
    assert result.rstrip().endswith("### 比較表")


def test_build_category_section_trend_years_in_header() -> None:
    """過去N年の記述がヘッダーに含まれる。"""
    with patch(
        "g1_predict.modules.gen_predict._trend_renderer.compute_stats",
        side_effect=_empty_stats_map,
    ):
        result = build_category_section(
            "出走馬傾向", [_make_fixed_metric_cfg()], _make_manager(), _make_condition(), RACE_YEAR
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
        result = _build_metric_section(metric_cfg, _make_manager(), _make_condition(), RACE_YEAR)

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
        result = _build_metric_section(metric_cfg, _make_manager(), _make_condition(), RACE_YEAR)

    lines = result.split("\n")
    row_lines = [
        ln for ln in lines
        if ln.startswith("| ") and "---" not in ln and "前走レース" not in ln
    ]
    labels_in_result = [ln.split("|")[1].strip() for ln in row_lines]
    assert "海外" not in labels_in_result


# --- format_condition_note ---


def test_format_condition_note_none_returns_empty() -> None:
    """condition_cfg が None の場合は空文字を返す。"""
    assert format_condition_note(None) == ""


def test_format_condition_note_full() -> None:
    """全項目指定時、SPEC04 の出力例と一致する。"""
    condition_cfg = {
        "years": 10,
        "keibajo_codes": ["09"],
        "kaisai_nichime": [4],
        "babajotai_codes": ["1"],
    }
    assert format_condition_note(condition_cfg) == "※過去10年阪神4日目良のみ"


def test_format_condition_note_multiple_values_joined() -> None:
    """複数値は「・」で連結される。"""
    condition_cfg = {
        "years": 5,
        "keibajo_codes": ["09", "06"],
        "kaisai_nichime": [3, 4],
        "babajotai_codes": ["1", "2"],
    }
    note = format_condition_note(condition_cfg)
    assert "阪神・中山" in note
    assert "3・4日目" in note
    assert "良・稍" in note


def test_format_condition_note_years_only() -> None:
    """years のみ指定時は「※過去N年のみ」になる。"""
    assert format_condition_note({"years": 5}) == "※過去5年のみ"


@pytest.mark.parametrize(
    "babajotai_codes, expected_baba_str",
    [
        (["1"], "良"),
        (["2"], "稍"),
        (["3"], "重"),
        (["4"], "不"),
    ],
)
def test_format_condition_note_baba_uses_domain_names(
    babajotai_codes: list[str], expected_baba_str: str
) -> None:
    """馬場状態は keiba-domain の名称をそのまま使い、「馬場」を付けない。"""
    condition_cfg = {"years": 5, "babajotai_codes": babajotai_codes}
    assert format_condition_note(condition_cfg) == f"※過去5年{expected_baba_str}のみ"


def test_format_condition_note_baba_code_zero_is_skipped() -> None:
    """babajotai_codes に未設定コード"0"が含まれる場合、注記から除外される。"""
    condition_cfg = {"years": 5, "babajotai_codes": ["0"]}
    assert format_condition_note(condition_cfg) == "※過去5年のみ"


# --- _build_metric_section: condition note ---


def test_build_metric_section_with_condition_appends_note() -> None:
    """metric_cfg に condition がある場合、注記行が末尾に追加される。"""
    metric_cfg = {
        "name": "枠番",
        "rows": {
            "type": "fixed",
            "items": [{"label": "1-4枠", "op": "<=", "value": 4}],
        },
        "source": {"type": "gate_number"},
        "condition": {
            "years": 10,
            "keibajo_codes": ["09"],
            "kaisai_nichime": [4],
            "babajotai_codes": ["1"],
        },
    }

    with patch(
        "g1_predict.modules.gen_predict._trend_renderer.compute_stats",
        return_value={},
    ):
        result = _build_metric_section(metric_cfg, _make_manager(), _make_condition(), RACE_YEAR)

    assert "※過去10年阪神4日目良のみ" in result


def test_build_metric_section_without_condition_no_note() -> None:
    """metric_cfg に condition がない場合、※注記行は出力されない。"""
    with patch(
        "g1_predict.modules.gen_predict._trend_renderer.compute_stats",
        return_value={},
    ):
        result = _build_metric_section(
            _make_fixed_metric_cfg(), _make_manager(), _make_condition(), RACE_YEAR
        )

    assert "※" not in result


# --- get_race_subject_entries ---


def _make_entries_manager(umaban: list[int], label: list[str]) -> MagicMock:
    """fetch_dataframe が umaban/label の DataFrame を返すモックを生成する。"""
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame({"umaban": umaban, "label": label})
    return manager


def test_get_race_subject_entries_kishu_no_join() -> None:
    """Subject.KISHU は km2 への JOIN なしで kishumei_ryakusho を取得する。"""
    manager = _make_entries_manager([1, 2], ["武豊", "ルメール"])
    entries = get_race_subject_entries(manager, "2026061409030411", Subject.KISHU)

    sql = manager.fetch_dataframe.call_args[0][0]
    assert "u.kishumei_ryakusho" in sql
    assert "kyosoba_master2" not in sql
    assert entries == [(1, "武豊"), (2, "ルメール")]


def test_get_race_subject_entries_seisansha_with_join() -> None:
    """Subject.SEISANSHA は kyosoba_master2 への JOIN を含む。"""
    manager = _make_entries_manager([1], ["社台ファーム"])
    entries = get_race_subject_entries(manager, "2026061409030411", Subject.SEISANSHA)

    sql = manager.fetch_dataframe.call_args[0][0]
    assert "km2.seisanshamei_hojinkaku_nashi" in sql
    assert "kyosoba_master2" in sql
    assert entries == [(1, "社台ファーム")]


def test_get_race_subject_entries_dedup_uses_min_umaban() -> None:
    """同一ラベルが複数馬に出る場合、最小馬番のみ残る。"""
    manager = _make_entries_manager([1, 2, 3], ["社台ファーム", "社台ファーム", "ノーザンファーム"])
    entries = get_race_subject_entries(manager, "2026061409030411", Subject.SEISANSHA)

    assert entries == [(1, "社台ファーム"), (3, "ノーザンファーム")]


# --- sort_entry_labels ---


def test_sort_entry_labels_order() -> None:
    """1着数→2着数→3着数 降順、着外数 昇順、馬番昇順でソートされる。"""
    stats_map = {
        "A": RowStats(first=1, second=0, third=0, fourth_plus=5),
        "B": RowStats(first=1, second=1, third=0, fourth_plus=3),
        "C": RowStats(first=0, second=0, third=0, fourth_plus=10),
    }
    entries = [(3, "A"), (1, "B"), (2, "C")]
    labels = sort_entry_labels(stats_map, entries)
    assert labels == ["B", "A", "C"]


def test_sort_entry_labels_tie_breaks_by_chakugai_then_umaban() -> None:
    """1-2-3着が同数の場合、着外数が少ない順で並ぶ。"""
    stats_map = {
        "A": RowStats(first=1, second=1, third=1, fourth_plus=5),
        "B": RowStats(first=1, second=1, third=1, fourth_plus=2),
    }
    entries = [(1, "A"), (2, "B")]
    labels = sort_entry_labels(stats_map, entries)
    assert labels == ["B", "A"]


def test_sort_entry_labels_no_stats_uses_umaban() -> None:
    """stats_map にないラベルは着度数0として馬番昇順で並ぶ。"""
    entries = [(2, "B"), (1, "A")]
    labels = sort_entry_labels({}, entries)
    assert labels == ["A", "B"]


# --- _build_metric_section: all_entries ---


def _make_all_entries_metric_cfg(source_type: str = "jockey_name") -> dict:
    """all_entries 型の metric 設定を生成する。"""
    return {
        "name": "騎手",
        "rows": {"type": "all_entries"},
        "source": {"type": source_type},
    }


def test_build_metric_section_all_entries_shows_all_runners() -> None:
    """all_entries 指定時、今回出走対象を全表示する。"""
    stats_map = {
        "武豊": RowStats(first=1, second=0, third=0, fourth_plus=5, total=6),
        "ルメール": RowStats(first=0, second=0, third=0, fourth_plus=3, total=3),
    }
    entries = [(1, "武豊"), (2, "ルメール")]

    with (
        patch(
            "g1_predict.modules.gen_predict._trend_renderer.compute_stats",
            return_value=stats_map,
        ),
        patch(
            "g1_predict.modules.gen_predict._trend_renderer.get_race_subject_entries",
            return_value=entries,
        ),
    ):
        result = _build_metric_section(
            _make_all_entries_metric_cfg(),
            _make_manager(),
            _make_condition(),
            RACE_YEAR,
            race_code="2026061409030411",
        )

    assert "武豊" in result
    assert "ルメール" in result
    assert "1-0-0-5" in result
    assert "0-0-0-3" in result


def test_build_metric_section_all_entries_empty_race_code_raises() -> None:
    """all_entries 指定時、race_code が空なら ValueError になる。"""
    with patch(
        "g1_predict.modules.gen_predict._trend_renderer.compute_stats",
        return_value={},
    ):
        with pytest.raises(ValueError):
            _build_metric_section(
                _make_all_entries_metric_cfg(),
                _make_manager(),
                _make_condition(),
                RACE_YEAR,
                race_code="",
            )


def test_build_metric_section_all_entries_unsupported_source_raises() -> None:
    """all_entries 指定時、SUBJECT_MAP に存在しない source.type は ValueError になる。"""
    with patch(
        "g1_predict.modules.gen_predict._trend_renderer.compute_stats",
        return_value={},
    ):
        with pytest.raises(ValueError):
            _build_metric_section(
                _make_all_entries_metric_cfg(source_type="gate_number"),
                _make_manager(),
                _make_condition(),
                RACE_YEAR,
                race_code="2026061409030411",
            )
