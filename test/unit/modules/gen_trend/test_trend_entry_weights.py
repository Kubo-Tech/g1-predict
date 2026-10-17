"""_trend_entry_weights モジュールの単体テスト。"""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from g1_predict.modules.gen_trend._trend_entry_weights import EntryWeights, resolve_entry_weights

_RACE_CODE = "2026101808040711"
_HORSES = pd.DataFrame({"umaban": [1, 2, 3], "bamei": ["A", "B", "C"]})


# 正常系
def test_resolve_entry_weights_uses_race_day_weights_when_all_horses_have_them() -> None:
    """全出走馬の当日の馬体重が DB にあれば、当日の馬体重を注記なしで使う。"""
    manager = _make_manager(race_day=["480", "502", "456"])
    result = resolve_entry_weights(manager, _RACE_CODE, _HORSES, {"A": 470, "B": 500, "C": 450})
    assert result == EntryWeights({1: "480", 2: "502", 3: "456"}, "")
    assert manager.fetch_dataframe.call_count == 1


@pytest.mark.parametrize("missing_weight", ["", "0", "999"])
def test_resolve_entry_weights_uses_chokyo_when_race_day_weight_is_missing(
    missing_weight: str,
) -> None:
    """当日の馬体重が無い（空・計量前・計量不能）馬がいれば、調教後馬体重を使って注記する。

    Args:
        missing_weight (str): DB の馬体重の値。
    """
    manager = _make_manager(race_day=["480", missing_weight, "456"])
    result = resolve_entry_weights(manager, _RACE_CODE, _HORSES, {"A": 470, "B": 500, "C": 450})
    assert result == EntryWeights({1: "470", 2: "500", 3: "450"}, "※該当馬は調教後馬体重")


def test_resolve_entry_weights_uses_previous_weights_without_chokyo() -> None:
    """当日の馬体重も調教後馬体重も無ければ、前走の馬体重を使って注記する。"""
    manager = _make_manager(
        race_day=["", "", ""],
        past={1: ["478", "470"], 2: ["500"], 3: ["452", ""]},
    )
    result = resolve_entry_weights(manager, _RACE_CODE, _HORSES, None)
    assert result == EntryWeights({1: "478", 2: "500", 3: "452"}, "※該当馬は前走馬体重")


def test_resolve_entry_weights_uses_latest_weight_when_previous_race_has_none() -> None:
    """前走に馬体重が無い（前走海外など）馬は、さかのぼって最新の馬体重を使い、その旨を注記する。"""
    manager = _make_manager(
        race_day=["", "", ""], past={1: ["478"], 2: ["", "", "498"], 3: ["452"]}
    )
    result = resolve_entry_weights(manager, _RACE_CODE, _HORSES, None)
    assert result == EntryWeights(
        {1: "478", 2: "498", 3: "452"}, "※該当馬は前走馬体重。前走海外の場合は最新の馬体重"
    )


def test_resolve_entry_weights_excludes_horses_without_any_weight() -> None:
    """過去走に馬体重が1つも無い馬と、過去走の無い馬は判定に使わず、馬番を注記する。"""
    manager = _make_manager(race_day=["", "", ""], past={1: ["478"], 2: [""]})
    result = resolve_entry_weights(manager, _RACE_CODE, _HORSES, None)
    assert result == EntryWeights({1: "478"}, "※該当馬は前走馬体重  \n※2, 3は馬体重情報なし")


# 準正常系
def test_resolve_entry_weights_with_horse_missing_from_chokyo_raises() -> None:
    """調教後馬体重に載っていない出走馬がいる場合は ValueError になる。"""
    manager = _make_manager(race_day=["", "", ""])
    with pytest.raises(ValueError, match=r"\['C'\]"):
        resolve_entry_weights(manager, _RACE_CODE, _HORSES, {"A": 470, "B": 500})


def _make_manager(race_day: list[str], past: dict[int, list[str]] | None = None) -> MagicMock:
    """当日の馬体重と過去走の馬体重を返す DB 接続マネージャのモックを生成する。

    Args:
        race_day (list[str]): 馬番1から順の、当日の馬体重の文字列。
        past (dict[int, list[str]] | None): 馬番 -> 過去走の馬体重の文字列（新しい順）。

    Returns:
        MagicMock: fetch_dataframe が1回目に当日の馬体重、2回目に過去走の馬体重を返すモック。
    """
    race_day_df = pd.DataFrame({"umaban": list(range(1, len(race_day) + 1)), "bataiju": race_day})
    past_rows = [(umaban, weight) for umaban, weights in (past or {}).items() for weight in weights]
    past_df = pd.DataFrame(past_rows, columns=["umaban", "bataiju"])
    manager = MagicMock()
    manager.fetch_dataframe.side_effect = [race_day_df, past_df]
    return manager
