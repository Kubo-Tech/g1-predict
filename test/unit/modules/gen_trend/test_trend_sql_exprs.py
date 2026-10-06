"""_trend_sql_exprs の単体テスト。"""

from collections.abc import Callable

import pytest

from g1_predict.modules.gen_trend._trend_sql_exprs import (
    BIRTH_MONTH_EXPR,
    CORNER4_JUNI_EXPR,
    HORSE_WEIGHT_EXPR,
    build_debut_month_expr,
    build_good_baba_top3_count_expr,
    build_prev_corner4_juni_expr,
    build_prev_distance_diff_expr,
    build_prev_race_class_expr,
    build_prev_race_finish_by_class_expr,
    build_soft_baba_top3_count_expr,
    build_transport_expr,
)

_RACE_CODES = ["2024092906040911", "2025092806040911"]
_DANGEROUS_TOKENS = (";", "--", "/*", "%")

_HISTORY_BUILDERS = [
    build_prev_corner4_juni_expr,
    build_prev_distance_diff_expr,
    build_prev_race_class_expr,
    build_transport_expr,
    build_good_baba_top3_count_expr,
    build_soft_baba_top3_count_expr,
    build_debut_month_expr,
]


# 正常系
@pytest.mark.parametrize("builder", _HISTORY_BUILDERS)
def test_history_expr_embeds_race_codes(builder: Callable[[list[str]], str]) -> None:
    """集計対象レースのコードが式に埋め込まれる。"""
    expr = builder(_RACE_CODES)
    assert "'2024092906040911', '2025092806040911'" in expr


@pytest.mark.parametrize("builder", _HISTORY_BUILDERS)
def test_history_expr_has_no_dangerous_token(builder: Callable[[list[str]], str]) -> None:
    """式に analytics が拒否するトークンや、パラメータ置換と衝突する % を含まない。"""
    expr = builder(_RACE_CODES)
    assert not any(token in expr for token in _DANGEROUS_TOKENS)


@pytest.mark.parametrize("builder", _HISTORY_BUILDERS)
def test_history_expr_looks_up_by_target_race_and_horse(
    builder: Callable[[list[str]], str],
) -> None:
    """出走ごとに、レースコードと血統登録番号を連結したキーで値を引く。"""
    expr = builder(_RACE_CODES)
    assert "->> (u.race_code || u.ketto_toroku_bango)" in expr


@pytest.mark.parametrize(
    "expr",
    [CORNER4_JUNI_EXPR, HORSE_WEIGHT_EXPR, BIRTH_MONTH_EXPR],
)
def test_simple_expr_is_parenthesized(expr: str) -> None:
    """::TEXT へのキャストと結合しても評価順が変わらないよう、括弧で囲まれている。"""
    assert expr.startswith("(") and expr.endswith(")")


def test_prev_race_class_expr_contains_all_classes() -> None:
    """前走クラスの全ラベルが式に含まれる。"""
    expr = build_prev_race_class_expr(_RACE_CODES)
    for label in [
        "G1",
        "G2",
        "G3",
        "リステッド",
        "オープン",
        "3勝クラス",
        "2勝クラス",
        "1勝クラス",
        "未勝利",
        "新馬",
        "地方",
        "海外",
    ]:
        assert f"'{label}'" in expr


def test_prev_race_finish_by_class_expr_filters_by_class() -> None:
    """指定したクラスの前走だけを対象にする。"""
    expr = build_prev_race_finish_by_class_expr(_RACE_CODES, "新馬")
    assert "= '新馬' THEN CAST(kakutei_chakujun AS INTEGER)" in expr


def test_debut_month_expr_counts_started_runs_without_finish() -> None:
    """デビュー月は、確定着順の無い競走中止なども含め、出走取消・除外を除いた最初の出走で決める。"""
    expr = build_debut_month_expr(_RACE_CODES)
    assert "TRIM(ijo_kubun) NOT IN ('1', '2', '3')" in expr
    assert "kakutei_chakujun ~" not in expr.split("jsonb_object_agg")[-1]


def test_transport_expr_has_all_labels() -> None:
    """輸送の3ラベルが式に含まれる。"""
    expr = build_transport_expr(_RACE_CODES)
    assert "'輸送なし'" in expr
    assert "'輸送あり'" in expr
    assert "'初輸送'" in expr


def test_baba_top3_count_exprs_use_baba_codes() -> None:
    """良は馬場状態コード1、稍重以上は2・3・4で数える。"""
    assert "baba IN ('1')" in build_good_baba_top3_count_expr(_RACE_CODES)
    assert "baba IN ('2', '3', '4')" in build_soft_baba_top3_count_expr(_RACE_CODES)


# 準正常系
@pytest.mark.parametrize("builder", _HISTORY_BUILDERS)
def test_history_expr_empty_race_codes_raises(builder: Callable[[list[str]], str]) -> None:
    """レースコードが空の場合は ValueError になる。"""
    with pytest.raises(ValueError, match="race_codes"):
        builder([])


@pytest.mark.parametrize("race_code", ["2025", "20250928060409AB", "2025092806040911'; --"])
def test_history_expr_invalid_race_code_raises(race_code: str) -> None:
    """16桁の数字でないレースコードは ValueError になる。"""
    with pytest.raises(ValueError, match="race_code"):
        build_prev_corner4_juni_expr([race_code])


def test_prev_race_finish_by_class_expr_quote_in_class_raises() -> None:
    """クラス名に引用符が含まれる場合は ValueError になる。"""
    with pytest.raises(ValueError, match="race_class"):
        build_prev_race_finish_by_class_expr(_RACE_CODES, "新馬' OR '1'='1")
