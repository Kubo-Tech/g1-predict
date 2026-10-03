"""race_result の単体テスト。"""

import pandas as pd

from g1_predict.modules.utils.race_result import (
    format_corner4,
    format_halon,
    halon_rank,
    kyakushitsu_display,
)


def _row(**kwargs: object) -> pd.Series:
    base: dict[str, object] = {
        "4コーナー順位": 3,
        "後3ハロン": 35.0,
        "脚質判定コード": "1",
    }
    return pd.Series({**base, **kwargs})


def _result_df() -> pd.DataFrame:
    return pd.DataFrame({"後3ハロン": [34.5, 35.0, float("nan"), 35.0, 36.0]})


# kyakushitsu_display
def test_kyakushitsu_display_returns_name() -> None:
    """脚質判定コードから表示名を返す。"""
    assert [kyakushitsu_display(_row(脚質判定コード=c)) for c in "1234"] == [
        "逃げ",
        "先行",
        "差し",
        "追込",
    ]


def test_kyakushitsu_display_returns_empty_when_missing() -> None:
    """脚質判定コードが無い場合は空文字列を返す。"""
    assert kyakushitsu_display(_row(脚質判定コード=None)) == ""
    assert kyakushitsu_display(pd.Series({"馬番": 1})) == ""


# halon_rank
def test_halon_rank_ties_share_rank_and_nan_ignored() -> None:
    """同タイムは同順位になり、欠損は順位計算に含めない。"""
    df = _result_df()
    assert halon_rank(_row(後3ハロン=34.5), df) == 1
    assert halon_rank(_row(後3ハロン=35.0), df) == 2
    assert halon_rank(_row(後3ハロン=36.0), df) == 4


# format_corner4
def test_format_corner4_with_unit_and_kyakushitsu() -> None:
    """単位と脚質の略称が付く。"""
    assert format_corner4(_row(), "番手") == "3番手 (逃)"


def test_format_corner4_without_unit() -> None:
    """単位を省略すると順位と略称だけになる。"""
    assert format_corner4(_row(脚質判定コード="3")) == "3 (差)"


def test_format_corner4_without_kyakushitsu() -> None:
    """脚質判定が無い場合は括弧を付けない。"""
    assert format_corner4(_row(脚質判定コード=None)) == "3"


def test_format_corner4_without_corner() -> None:
    """順位が無い場合は「-」になる。"""
    assert format_corner4(_row(**{"4コーナー順位": float("nan")}, 脚質判定コード=None)) == "-"


# format_halon
def test_format_halon_with_rank() -> None:
    """タイムと上がり順位を整形する。"""
    assert format_halon(_row(後3ハロン=36.0), _result_df()) == "36.0秒 (4位)"


def test_format_halon_without_value() -> None:
    """後3ハロンが無い場合は「-」になる。"""
    assert format_halon(_row(後3ハロン=float("nan")), _result_df()) == "-"
