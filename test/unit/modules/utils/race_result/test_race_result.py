"""race_result の単体テスト。"""

import pandas as pd
import pytest

from g1_predict.modules.utils.race_result import (
    format_corner4,
    format_halon,
    grade_display,
    halon_rank,
    kyakushitsu_display,
    race_condition_display,
    race_display_name,
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


def test_format_corner4_without_corner_but_with_kyakushitsu() -> None:
    """順位が無い場合は、脚質判定があっても「-」だけになる。"""
    assert format_corner4(_row(**{"4コーナー順位": float("nan")}), "番手") == "-"


# format_halon
def test_format_halon_with_rank() -> None:
    """タイムと上がり順位を整形する。"""
    assert format_halon(_row(後3ハロン=36.0), _result_df()) == "36.0秒 (4位)"


def test_format_halon_without_value() -> None:
    """後3ハロンが無い場合は「-」になる。"""
    assert format_halon(_row(後3ハロン=float("nan")), _result_df()) == "-"


def _race_info(
    hondai: object = None,
    condition_name: object = None,
    condition_code: object = "703",
    grade_code: object = "_",
    race_code: str = "2026010105010101",
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "レースコード": [race_code],
            "競走名本題": [hondai],
            "競走条件名称": [condition_name],
            "競走条件コード": [condition_code],
            "グレードコード": [grade_code],
        }
    )


# race_condition_display
def test_race_condition_display_prefers_condition_name() -> None:
    """競走条件名称があればそれを返す。"""
    assert race_condition_display(_race_info(condition_name=" 3歳以上1勝クラス ")) == (
        "3歳以上1勝クラス"
    )


@pytest.mark.parametrize(
    "code, expected",
    [("701", "新馬"), ("703", "未勝利"), ("005", "1勝クラス"), ("999", "オープン"), (None, "")],
)
def test_race_condition_display_falls_back_to_code_name(code: object, expected: str) -> None:
    """競走条件名称が空なら、競走条件コードの表示名を返す。"""
    assert race_condition_display(_race_info(condition_name="", condition_code=code)) == expected


# grade_display
@pytest.mark.parametrize(
    "grade_code, expected", [("A", "G1"), ("B", "G2"), ("C", "G3"), ("L", "L"), ("_", "")]
)
def test_grade_display(grade_code: str, expected: str) -> None:
    """グレードコードの表示名を返す。グレードが無ければ空文字列。"""
    assert grade_display(_race_info(grade_code=grade_code)) == expected


# race_display_name
def test_race_display_name_uses_unified_name_for_special_race() -> None:
    """競走名本題があるレースは、統一した競走名本題を返す。"""
    info = _race_info(hondai="旧名ステークス", race_code="2026010105010111")
    assert race_display_name(info, {"2026010105010111": "新名ステークス"}) == "新名ステークス"


def test_race_display_name_uses_condition_for_condition_race() -> None:
    """競走名本題が無い条件戦は、条件名を返す。"""
    assert race_display_name(_race_info(hondai=None, condition_code="010"), {}) == "2勝クラス"


def test_race_display_name_blank_hondai_uses_condition() -> None:
    """競走名本題が空白だけなら、条件名を返す。"""
    assert race_display_name(_race_info(hondai="  ", condition_code="703"), {}) == "未勝利"


def test_race_display_name_raises_when_unified_name_missing() -> None:
    """競走名本題があるのに統一名が無い場合はKeyErrorを送出する。"""
    with pytest.raises(KeyError):
        race_display_name(_race_info(hondai="X"), {})
