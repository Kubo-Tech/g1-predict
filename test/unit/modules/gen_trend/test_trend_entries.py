"""_trend_entries の単体テスト。"""

from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from mykeibadb.analytics import RaceCondition
from mykeibadb.exceptions import MykeibaDBError

from g1_predict.modules.gen_trend._trend_catalog import TrendItem
from g1_predict.modules.gen_trend._trend_entries import fetch_entry_horses, find_entry_rows
from g1_predict.modules.gen_trend._trend_loader import TrendContext

_ENTRIES = "g1_predict.modules.gen_trend._trend_entries"
_STATS = "g1_predict.modules.gen_trend._trend_stats"
_RACE_CODE = "2026092706040911"


def _make_context() -> TrendContext:
    """テスト用 TrendContext を生成する。"""
    return TrendContext(
        manager=MagicMock(),
        condition=RaceCondition(
            keibajo_codes=["06"],
            kyori=1200,
            tokubetsu_kyoso_bango="0013",
            year_from="2016",
            year_to="2025",
        ),
        race_year=2026,
        race_name="スプリンターズステークス",
        kyori=1200,
        keibajo_code="06",
        shiba_da="芝",
        first_year=2016,
        years=10,
        race_count=10,
    )


def _make_item(config: dict[str, Any], **options: Any) -> TrendItem:
    """テスト用 TrendItem を生成する。"""
    return TrendItem(name="項目", config=config, condition=None, **options)


def _find(item: TrendItem, groups: dict[int, str | None]) -> dict[int, list[str]]:
    """get_race_entry_groups の結果を差し替えて find_entry_rows を実行する。"""
    with patch(f"{_ENTRIES}.get_race_entry_groups", return_value=groups):
        return find_entry_rows(item, _make_context(), _RACE_CODE)


# --- find_entry_rows: fixed ---


def test_find_entry_rows_fixed_assigns_rows_by_op() -> None:
    """fixed の項目は、集計と同じ op で行に割り当てる。"""
    item = _make_item(
        {
            "source": {"type": "gate_number"},
            "rows": {
                "type": "fixed",
                "items": [
                    {"label": "1-4枠", "op": "<=", "value": 4},
                    {"label": "5-8枠", "op": ">=", "value": 5},
                ],
            },
        }
    )
    assert _find(item, {1: "1", 2: "4", 3: "5", 4: "8"}) == {
        1: ["1-4枠"],
        2: ["1-4枠"],
        3: ["5-8枠"],
        4: ["5-8枠"],
    }


def test_find_entry_rows_fixed_overlapping_rows_return_all_hits() -> None:
    """fixed の項目で条件が重なる行は、すべて返す。"""
    item = _make_item(
        {
            "source": {"type": "tokubetsu_race_finish", "year_offset": 1, "absent_label": "無し"},
            "rows": {
                "type": "fixed",
                "items": [
                    {"label": "3着以内", "op": "<=", "value": 3},
                    {"label": "4着以内", "op": "<=", "value": 4},
                    {"label": "出走無し", "op": "==", "value": "無し"},
                ],
            },
        }
    )
    assert _find(item, {1: "3", 2: "無し", 3: "5"}) == {
        1: ["3着以内", "4着以内"],
        2: ["出走無し"],
        3: [],
    }


def test_find_entry_rows_excludes_horses_without_value() -> None:
    """グループの値が求まらない馬（前走が無いなど）は含めない。"""
    item = _make_item(
        {
            "source": {"type": "prev_race_col", "column": "kyakushitsu_hantei"},
            "rows": {"type": "fixed", "items": [{"label": "逃げ", "op": "==", "value": "1"}]},
        }
    )
    assert _find(item, {1: "逃げ", 2: None}) == {1: ["逃げ"]}


# --- find_entry_rows: dynamic ---


def test_find_entry_rows_dynamic_returns_group_value_as_row() -> None:
    """dynamic の項目は、グループの値をそのまま行の名前として返す。"""
    item = _make_item({"source": {"type": "jockey_name"}, "rows": {"type": "dynamic", "top_n": 5}})
    assert _find(item, {1: "ルメール", 2: "未登場の騎手"}) == {
        1: ["ルメール"],
        2: ["未登場の騎手"],
    }


# --- find_entry_rows: chokyo_match_days ---


def test_find_entry_rows_chokyo_match_days_assigns_rows_by_op() -> None:
    """chokyo_match_days の項目は、集計と同じ op で行に割り当てる。"""
    item = _make_item(
        {
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
    )
    groups = {1: "[[7, true], [3, false]]", 2: "[[7, false]]", 3: "[]"}
    assert _find(item, groups) == {1: ["該当"], 2: ["非該当"], 3: ["記録なし"]}


# --- find_entry_rows: boolean_multi ---


def test_find_entry_rows_boolean_multi_horse_can_hit_multiple_rows() -> None:
    """boolean_multi の項目は、父が条件を満たす行すべてに当たる。"""
    item = _make_item(
        {
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
    )
    winner_sets = [{"ロードカナロア", "ダイワメジャー"}, {"ロードカナロア"}]
    with patch(f"{_STATS}._get_sire_winner_set", side_effect=winner_sets):
        rows = _find(item, {1: "ロードカナロア", 2: "ダイワメジャー", 3: "無名の種牡馬"})
    assert rows == {1: ["父勝ち", "父G1勝ち"], 2: ["父勝ち"], 3: []}


# --- find_entry_rows: GroupBy の共有 ---


def test_find_entry_rows_uses_same_group_by_as_stats() -> None:
    """集計と同じ GroupBy で出走馬のグループの値を求める。"""
    item = _make_item({"source": {"type": "jockey_name"}, "rows": {"type": "dynamic"}})
    with patch(f"{_ENTRIES}.get_race_entry_groups", return_value={}) as mock_groups:
        find_entry_rows(item, _make_context(), _RACE_CODE)
    context_manager, race_code, group_by = mock_groups.call_args[0]
    assert race_code == _RACE_CODE
    assert group_by.kind == "subject"
    assert group_by.subject.name == "KISHU"
    assert context_manager is not None


def test_find_entry_rows_history_expr_targets_only_current_race() -> None:
    """過去走を参照する SQL 式は、対象レースの出走馬だけを対象に組み立てる。"""
    item = _make_item(
        {
            "source": {"type": "prev_race_class"},
            "rows": {"type": "fixed", "items": [{"label": "G1", "op": "==", "value": "G1"}]},
        }
    )
    with patch(f"{_ENTRIES}.get_race_entry_groups", return_value={}) as mock_groups:
        find_entry_rows(item, _make_context(), _RACE_CODE)
    group_by = mock_groups.call_args[0][2]
    assert group_by.kind == "race_col"
    assert f"u3.race_code IN ('{_RACE_CODE}')" in group_by.column


def test_find_entry_rows_does_not_use_item_condition() -> None:
    """項目に注入された開催条件は、出走馬の判定に使わない。"""
    item = TrendItem(
        name="枠順",
        config={
            "source": {"type": "gate_number"},
            "rows": {"type": "fixed", "items": [{"label": "1枠", "op": "==", "value": 1}]},
        },
        condition=MagicMock(),
    )
    with patch(f"{_ENTRIES}.get_race_entry_groups", return_value={1: "1"}):
        assert find_entry_rows(item, _make_context(), _RACE_CODE) == {1: ["1枠"]}


# --- find_entry_rows: 今走の結果で決まる項目 ---


def test_find_entry_rows_race_result_item_returns_empty_without_db_access() -> None:
    """今走の結果で決まる項目は、レース前に値が無いため DB を参照せず空を返す。"""
    item = _make_item(
        {
            "source": {"type": "running_style"},
            "rows": {"type": "fixed", "items": [{"label": "逃げ", "op": "==", "value": "1"}]},
        },
        uses_race_result=True,
    )
    with patch(f"{_ENTRIES}.get_race_entry_groups") as mock_groups:
        assert find_entry_rows(item, _make_context(), _RACE_CODE) == {}
    mock_groups.assert_not_called()


# 準正常系
def test_find_entry_rows_propagates_mykeibadb_error() -> None:
    """mykeibadb の例外はそのまま送出する。"""
    item = _make_item({"source": {"type": "jockey_name"}, "rows": {"type": "dynamic"}})
    with (
        patch(f"{_ENTRIES}.get_race_entry_groups", side_effect=MykeibaDBError("出走馬なし")),
        pytest.raises(MykeibaDBError),
    ):
        find_entry_rows(item, _make_context(), _RACE_CODE)


# --- fetch_entry_horses ---


def test_fetch_entry_horses_returns_frame_and_excludes_cancelled_by_query() -> None:
    """取消・除外を除く条件で出走馬を取得する。"""
    manager = MagicMock()
    horses = pd.DataFrame({"waku": [1, 1], "umaban": [1, 2], "bamei": ["A", "B"]})
    manager.fetch_dataframe.return_value = horses
    result = fetch_entry_horses(manager, _RACE_CODE)
    assert result is horses
    sql = manager.fetch_dataframe.call_args[0][0]
    assert "NOT (u.ijo_kubun_code = ANY(%s))" in sql
    assert manager.fetch_dataframe.call_args[1]["params"] == (_RACE_CODE, ["1", "2", "3"])


def test_fetch_entry_horses_without_entries_raises() -> None:
    """出走馬が DB に無い場合は MykeibaDBError になる。"""
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame({"waku": [], "umaban": [], "bamei": []})
    with pytest.raises(MykeibaDBError):
        fetch_entry_horses(manager, _RACE_CODE)
