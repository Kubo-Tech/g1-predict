"""_trend_stats の単体テスト。"""

import pandas as pd

from g1_predict.modules.gen_predict._trend_models import Db, sire_cache_key
from g1_predict.modules.gen_predict._trend_stats import (
    _build_payout_lookup, _classify, _compute_boolean_labels, _compute_value,
    _history_before, _match_op, _safe_int, compute_stats)

# --- _safe_int ---


def test_safe_int_none() -> None:
    """None は None を返す。"""
    assert _safe_int(None) is None


def test_safe_int_nan() -> None:
    """Float nan は None を返す。"""
    assert _safe_int(float("nan")) is None


def test_safe_int_int() -> None:
    """Int はそのまま返す。"""
    assert _safe_int(3) == 3


def test_safe_int_float() -> None:
    """Float は小数部を切り捨て返す。"""
    assert _safe_int(3.7) == 3


def test_safe_int_string_digit() -> None:
    """数字文字列は int に変換する。"""
    assert _safe_int("5") == 5


def test_safe_int_string_non_digit() -> None:
    """非数字文字列は None を返す。"""
    assert _safe_int("abc") is None


def test_safe_int_pd_na() -> None:
    """pd.NA は None を返す。"""
    assert _safe_int(pd.NA) is None


# --- _match_op ---


def test_match_op_none_value() -> None:
    """Value が None は False。"""
    assert _match_op(None, "==", 1) is False


def test_match_op_nan_value() -> None:
    """Value が NaN は False。"""
    assert _match_op(float("nan"), "==", 1) is False


def test_match_op_eq_true() -> None:
    """== 一致は True。"""
    assert _match_op(3, "==", 3) is True


def test_match_op_eq_false() -> None:
    """== 不一致は False。"""
    assert _match_op(3, "==", 4) is False


def test_match_op_ne_true() -> None:
    """!= 不一致は True。"""
    assert _match_op(3, "!=", 4) is True


def test_match_op_ne_false() -> None:
    """!= 一致は False。"""
    assert _match_op(3, "!=", 3) is False


def test_match_op_gte_true() -> None:
    """>= 以上は True。"""
    assert _match_op(3, ">=", 3) is True


def test_match_op_gte_false() -> None:
    """>= 未満は False。"""
    assert _match_op(2, ">=", 3) is False


def test_match_op_lte_true() -> None:
    """<= 以下は True。"""
    assert _match_op(3, "<=", 3) is True


def test_match_op_lte_false() -> None:
    """<= 超過は False。"""
    assert _match_op(4, "<=", 3) is False


def test_match_op_gt_true() -> None:
    """> 超過は True。"""
    assert _match_op(4, ">", 3) is True


def test_match_op_gt_false() -> None:
    """> 同値は False。"""
    assert _match_op(3, ">", 3) is False


def test_match_op_lt_true() -> None:
    """< 未満は True。"""
    assert _match_op(2, "<", 3) is True


def test_match_op_lt_false() -> None:
    """< 同値は False。"""
    assert _match_op(3, "<", 3) is False


def test_match_op_in_true() -> None:
    """In 含む場合は True。"""
    assert _match_op("A", "in", ["A", "B"]) is True


def test_match_op_in_false() -> None:
    """In 含まない場合は False。"""
    assert _match_op("C", "in", ["A", "B"]) is False


def test_match_op_not_in_true() -> None:
    """Not_in 含まない場合は True。"""
    assert _match_op("C", "not_in", ["A", "B"]) is True


def test_match_op_not_in_false() -> None:
    """Not_in 含む場合は False。"""
    assert _match_op("A", "not_in", ["A", "B"]) is False


def test_match_op_unknown_op() -> None:
    """未知の演算子は False。"""
    assert _match_op(1, "??", 1) is False


# --- _build_payout_lookup ---


def _make_payoff_row(**kwargs: object) -> pd.Series:
    """払戻 Series を生成する。"""
    return pd.Series(kwargs)


def test_build_payout_lookup_none() -> None:
    """None は空辞書を返す。"""
    assert _build_payout_lookup(None) == {}


def test_build_payout_lookup_tansho() -> None:
    """単勝払戻を正しく登録する。"""
    row = _make_payoff_row(**{"単勝1馬番": 3, "単勝1払戻金": 500})
    lookup = _build_payout_lookup(row)
    assert lookup[3] == (500, None)


def test_build_payout_lookup_fukusho() -> None:
    """複勝払戻を正しく登録する。"""
    row = _make_payoff_row(**{"複勝1馬番": 3, "複勝1払戻金": 200})
    lookup = _build_payout_lookup(row)
    assert lookup[3] == (None, 200)


def test_build_payout_lookup_combined() -> None:
    """単勝・複勝を同一馬番で結合する。"""
    row = _make_payoff_row(**{
        "単勝1馬番": 5,
        "単勝1払戻金": 600,
        "複勝1馬番": 5,
        "複勝1払戻金": 150,
    })
    lookup = _build_payout_lookup(row)
    assert lookup[5] == (600, 150)


def test_build_payout_lookup_umaban_zero_ignored() -> None:
    """馬番=0 のエントリは無視する。"""
    row = _make_payoff_row(**{"単勝1馬番": 0, "単勝1払戻金": 300})
    assert _build_payout_lookup(row) == {}


# --- _history_before ---


def _make_history(rows: list[dict]) -> pd.DataFrame:
    """履歴 DataFrame を生成する。"""
    return pd.DataFrame(rows)


def test_history_before_empty_history() -> None:
    """空の履歴は空 DataFrame を返す。"""
    result = _history_before("001", "2026010101010101", pd.DataFrame())
    assert result.empty


def test_history_before_horse_not_found() -> None:
    """該当馬なしの場合は空 DataFrame を返す。"""
    history = _make_history([
        {"ketto_toroku_bango": "002", "race_code": "2025010101010101"},
    ])
    result = _history_before("001", "2026010101010101", history)
    assert result.empty


def test_history_before_filters_by_race_code() -> None:
    """指定 race_code より古いレースのみ返す。"""
    history = _make_history([
        {"ketto_toroku_bango": "001", "race_code": "2025010101010101"},
        {"ketto_toroku_bango": "001", "race_code": "2026020101010101"},
    ])
    result = _history_before("001", "2026010101010101", history)
    assert len(result) == 1
    assert result.iloc[0]["race_code"] == "2025010101010101"


def test_history_before_excludes_same_race_code() -> None:
    """同一 race_code は除外する。"""
    history = _make_history([
        {"ketto_toroku_bango": "001", "race_code": "2026010101010101"},
    ])
    result = _history_before("001", "2026010101010101", history)
    assert result.empty


# --- _classify ---


def test_classify_fixed_match() -> None:
    """Fixed 型で一致するラベルを返す。"""
    rows_cfg = {
        "type": "fixed",
        "items": [{"label": "1枠", "op": "==", "value": 1}],
    }
    assert _classify(1, rows_cfg, {}) == "1枠"


def test_classify_fixed_no_match() -> None:
    """Fixed 型で一致なしの場合は None を返す。"""
    rows_cfg = {
        "type": "fixed",
        "items": [{"label": "1枠", "op": "==", "value": 1}],
    }
    assert _classify(5, rows_cfg, {}) is None


def test_classify_fixed_first_match_wins() -> None:
    """Fixed 型で最初に一致したラベルを返す。"""
    rows_cfg = {
        "type": "fixed",
        "items": [
            {"label": "低人気", "op": ">=", "value": 7},
            {"label": "上位人気", "op": "<=", "value": 3},
        ],
    }
    assert _classify(2, rows_cfg, {}) == "上位人気"


def test_classify_dynamic_returns_string() -> None:
    """Dynamic 型は値を文字列で返す。"""
    rows_cfg = {"type": "dynamic"}
    assert _classify("ディープインパクト", rows_cfg, {}) == "ディープインパクト"


def test_classify_dynamic_none_returns_none() -> None:
    """Dynamic 型で value=None は None を返す。"""
    rows_cfg = {"type": "dynamic"}
    assert _classify(None, rows_cfg, {}) is None


# --- _compute_value ---


def _make_db_empty() -> Db:
    """空の Db インスタンスを生成する。"""
    return Db(
        past_race_codes=[],
        results={},
        payoffs={},
        history=pd.DataFrame(),
        shosai={},
        kyosoba={},
        sire_finisher_sets={},
        matched_years=0,
    )


def _make_result_row(**kwargs: object) -> pd.Series:
    """結果 Series を生成する。"""
    return pd.Series(kwargs)


def test_compute_value_gate_number() -> None:
    """Gate_number は枠番を返す。"""
    row = _make_result_row(**{"枠番": 3})
    cfg = {"source": {"type": "gate_number"}, "rows": {"type": "dynamic"}}
    assert _compute_value("001", "2026010101010101", row, cfg, _make_db_empty()) == 3


def test_compute_value_popularity() -> None:
    """Popularity source は単勝人気順を返す。"""
    row = _make_result_row(**{"単勝人気順": 5})
    cfg = {"source": {"type": "popularity"}, "rows": {"type": "dynamic"}}
    assert _compute_value("001", "2026010101010101", row, cfg, _make_db_empty()) == 5


def test_compute_value_running_style() -> None:
    """running_style は脚質判定コードを返す。"""
    row = _make_result_row(**{"脚質判定コード": "2"})
    cfg = {"source": {"type": "running_style"}, "rows": {"type": "dynamic"}}
    assert _compute_value("001", "2026010101010101", row, cfg, _make_db_empty()) == "2"


def test_compute_value_running_style_empty() -> None:
    """running_style が空文字の場合は None を返す。"""
    row = _make_result_row(**{"脚質判定コード": ""})
    cfg = {"source": {"type": "running_style"}, "rows": {"type": "dynamic"}}
    assert _compute_value("001", "2026010101010101", row, cfg, _make_db_empty()) is None


def test_compute_value_jockey_name() -> None:
    """jockey_name は騎手名略称を返す。"""
    row = _make_result_row(**{"騎手名略称": "武豊"})
    cfg = {"source": {"type": "jockey_name"}, "rows": {"type": "dynamic"}}
    assert _compute_value("001", "2026010101010101", row, cfg, _make_db_empty()) == "武豊"


def test_compute_value_breeder_name() -> None:
    """breeder_name は生産者名を返す。"""
    ky = pd.Series({"seisanshamei_hojinkaku_nashi": "ノーザンファーム"})
    db = _make_db_empty()
    db.kyosoba["001"] = ky
    cfg = {"source": {"type": "breeder_name"}, "rows": {"type": "dynamic"}}
    row = _make_result_row()
    assert _compute_value("001", "2026010101010101", row, cfg, db) == "ノーザンファーム"


def test_compute_value_breeder_name_no_kyosoba() -> None:
    """Kyosoba が未登録の場合は None を返す。"""
    cfg = {"source": {"type": "breeder_name"}, "rows": {"type": "dynamic"}}
    assert (
        _compute_value("001", "2026010101010101", _make_result_row(), cfg, _make_db_empty())
        is None
    )


def test_compute_value_sire_name() -> None:
    """Sire_name は父馬名を返す。"""
    ky = pd.Series({"ketto1_bamei": "ディープインパクト"})
    db = _make_db_empty()
    db.kyosoba["001"] = ky
    cfg = {"source": {"type": "sire_name"}, "rows": {"type": "dynamic"}}
    row = _make_result_row()
    assert _compute_value("001", "2026010101010101", row, cfg, db) == "ディープインパクト"


def test_compute_value_unknown_type_returns_none() -> None:
    """未知の source.type は None を返す。"""
    row = _make_result_row()
    cfg = {"source": {"type": "unknown_type"}, "rows": {"type": "dynamic"}}
    assert _compute_value("001", "2026010101010101", row, cfg, _make_db_empty()) is None


def test_compute_value_career_count() -> None:
    """career_count は異常コード以外の出走数を返す。"""
    history = pd.DataFrame([
        {
            "ketto_toroku_bango": "001",
            "race_code": "2025010101010101",
            "ijo_kubun_code": "0",
        },
        {
            "ketto_toroku_bango": "001",
            "race_code": "2025020101010101",
            "ijo_kubun_code": "0",
        },
        {
            "ketto_toroku_bango": "001",
            "race_code": "2025030101010101",
            "ijo_kubun_code": "1",
        },
    ])
    db = _make_db_empty()
    db.history = history
    cfg = {"source": {"type": "career_count"}, "rows": {"type": "dynamic"}}
    row = _make_result_row()
    result = _compute_value("001", "2026010101010101", row, cfg, db)
    assert result == 2


def test_compute_value_jockey_continuity_keizoku() -> None:
    """直前レースと同騎手は「継続」を返す。"""
    history = pd.DataFrame([
        {
            "ketto_toroku_bango": "001",
            "race_code": "2025010101010101",
            "kishu_code": "00111",
        },
    ])
    db = _make_db_empty()
    db.history = history
    cfg = {"source": {"type": "jockey_continuity"}, "rows": {"type": "dynamic"}}
    row = _make_result_row(**{"騎手コード": "00111"})
    assert _compute_value("001", "2026010101010101", row, cfg, db) == "継続"


def test_compute_value_jockey_continuity_ten_nori() -> None:
    """初騎乗は「テン乗り」を返す。"""
    history = pd.DataFrame([
        {
            "ketto_toroku_bango": "001",
            "race_code": "2025010101010101",
            "kishu_code": "00222",
        },
    ])
    db = _make_db_empty()
    db.history = history
    cfg = {"source": {"type": "jockey_continuity"}, "rows": {"type": "dynamic"}}
    row = _make_result_row(**{"騎手コード": "00111"})
    assert _compute_value("001", "2026010101010101", row, cfg, db) == "テン乗り"


def test_compute_value_jockey_continuity_nori_modori() -> None:
    """過去に騎乗歴あり直前は別騎手は「乗り戻り」を返す。"""
    history = pd.DataFrame([
        {
            "ketto_toroku_bango": "001",
            "race_code": "2025010101010101",
            "kishu_code": "00222",
        },
        {
            "ketto_toroku_bango": "001",
            "race_code": "2024010101010101",
            "kishu_code": "00111",
        },
    ])
    db = _make_db_empty()
    db.history = history
    cfg = {"source": {"type": "jockey_continuity"}, "rows": {"type": "dynamic"}}
    row = _make_result_row(**{"騎手コード": "00111"})
    assert _compute_value("001", "2026010101010101", row, cfg, db) == "乗り戻り"


def test_compute_value_past_finish_count() -> None:
    """past_finish_count は top_n 以内の着順数を返す。"""
    history = pd.DataFrame([
        {
            "ketto_toroku_bango": "001",
            "race_code": "2025010101010101",
            "kakutei_chakujun": 1,
        },
        {
            "ketto_toroku_bango": "001",
            "race_code": "2025020101010101",
            "kakutei_chakujun": 2,
        },
        {
            "ketto_toroku_bango": "001",
            "race_code": "2025030101010101",
            "kakutei_chakujun": 3,
        },
    ])
    db = _make_db_empty()
    db.history = history
    cfg = {"source": {"type": "past_finish_count", "top_n": 1}, "rows": {"type": "dynamic"}}
    row = _make_result_row()
    assert _compute_value("001", "2026010101010101", row, cfg, db) == 1


def test_compute_value_prev_race_name() -> None:
    """prev_race_name は直前レース名を返す。"""
    history = pd.DataFrame([
        {"ketto_toroku_bango": "001", "race_code": "2025030101010101"},
        {"ketto_toroku_bango": "001", "race_code": "2025010101010101"},
    ])
    db = _make_db_empty()
    db.history = history
    db.shosai["2025030101010101"] = {
        "grade_code": "A",
        "kyosomei_hondai": "天皇賞春",
        "keibajo_code": "05",
    }
    cfg = {"source": {"type": "prev_race_name"}, "rows": {"type": "dynamic"}}
    row = _make_result_row()
    assert _compute_value("001", "2026010101010101", row, cfg, db) == "天皇賞春"


# --- _compute_boolean_labels ---


def test_compute_boolean_labels_sire_in_set() -> None:
    """父馬が winner_set に含まれる場合、ラベルを返す。"""
    ky = pd.Series({"ketto1_bamei": "ディープインパクト"})
    src = {"type": "sire_race_condition_finisher", "race_name": "天皇賞春"}
    key = sire_cache_key(src)
    db = _make_db_empty()
    db.kyosoba["001"] = ky
    db.sire_finisher_sets[key] = {"ディープインパクト"}

    cfg = {
        "rows": {
            "type": "boolean_multi",
            "items": [{"label": "天皇賞春産駒", "source": src}],
        }
    }
    labels = _compute_boolean_labels("001", "2026010101010101", pd.Series(), cfg, db)
    assert labels == ["天皇賞春産駒"]


def test_compute_boolean_labels_sire_not_in_set() -> None:
    """父馬が winner_set にない場合、空リストを返す。"""
    ky = pd.Series({"ketto1_bamei": "キングカメハメハ"})
    src = {"type": "sire_race_condition_finisher", "race_name": "天皇賞春"}
    key = sire_cache_key(src)
    db = _make_db_empty()
    db.kyosoba["001"] = ky
    db.sire_finisher_sets[key] = {"ディープインパクト"}

    cfg = {
        "rows": {
            "type": "boolean_multi",
            "items": [{"label": "天皇賞春産駒", "source": src}],
        }
    }
    labels = _compute_boolean_labels("001", "2026010101010101", pd.Series(), cfg, db)
    assert labels == []


def test_compute_boolean_labels_multiple_items() -> None:
    """複数 item の中から合致するラベルのみ返す。"""
    ky = pd.Series({"ketto1_bamei": "ディープインパクト"})
    src_a = {"type": "sire_race_condition_finisher", "race_name": "天皇賞春"}
    src_b = {"type": "sire_race_condition_finisher", "race_name": "有馬記念"}
    db = _make_db_empty()
    db.kyosoba["001"] = ky
    db.sire_finisher_sets[sire_cache_key(src_a)] = {"ディープインパクト"}
    db.sire_finisher_sets[sire_cache_key(src_b)] = set()

    cfg = {
        "rows": {
            "type": "boolean_multi",
            "items": [
                {"label": "天皇賞春産駒", "source": src_a},
                {"label": "有馬記念産駒", "source": src_b},
            ],
        }
    }
    labels = _compute_boolean_labels("001", "2026010101010101", pd.Series(), cfg, db)
    assert labels == ["天皇賞春産駒"]


# --- compute_stats ---


def _make_db_with_result(
    race_code: str,
    result_rows: list[dict],
    payoff_row: pd.Series | None = None,
) -> Db:
    """単一レース結果を持つ Db を生成する。"""
    result_df = pd.DataFrame(result_rows)
    return Db(
        past_race_codes=[race_code],
        results={race_code: result_df},
        payoffs={race_code: payoff_row},
        history=pd.DataFrame(),
        shosai={},
        kyosoba={},
        sire_finisher_sets={},
        matched_years=5,
    )


def test_compute_stats_empty_past_races() -> None:
    """past_race_codes が空の場合は空辞書を返す。"""
    db = _make_db_empty()
    cfg = {"source": {"type": "gate_number"}, "rows": {"type": "dynamic"}}
    assert compute_stats(cfg, db) == {}


def test_compute_stats_counts_chakujun() -> None:
    """各着順が正しくカウントされる。"""
    db = _make_db_with_result("2025010101010101", [
        {"確定着順": 1, "枠番": 3, "馬番": 1, "血統登録番号": "001"},
        {"確定着順": 2, "枠番": 3, "馬番": 2, "血統登録番号": "002"},
        {"確定着順": 3, "枠番": 5, "馬番": 3, "血統登録番号": "003"},
        {"確定着順": 4, "枠番": 5, "馬番": 4, "血統登録番号": "004"},
    ])
    cfg = {"source": {"type": "gate_number"}, "rows": {"type": "dynamic"}}
    stats = compute_stats(cfg, db)
    assert stats["3"].first == 1
    assert stats["3"].second == 1
    assert stats["3"].total == 2
    assert stats["5"].third == 1
    assert stats["5"].fourth_plus == 1
    assert stats["5"].total == 2


def test_compute_stats_skips_none_chakujun() -> None:
    """確定着順が None の馬はスキップする。"""
    db = _make_db_with_result("2025010101010101", [
        {"確定着順": None, "枠番": 1, "馬番": 1, "血統登録番号": "001"},
    ])
    cfg = {"source": {"type": "gate_number"}, "rows": {"type": "dynamic"}}
    stats = compute_stats(cfg, db)
    assert stats == {}


def test_compute_stats_with_payoff() -> None:
    """払戻情報を正しく集計する。"""
    payoff = pd.Series({
        "単勝1馬番": 1,
        "単勝1払戻金": 1000,
        "複勝1馬番": 1,
        "複勝1払戻金": 300,
    })
    db = _make_db_with_result(
        "2025010101010101",
        [{"確定着順": 1, "枠番": 3, "馬番": 1, "血統登録番号": "001"}],
        payoff_row=payoff,
    )
    cfg = {"source": {"type": "gate_number"}, "rows": {"type": "dynamic"}}
    stats = compute_stats(cfg, db)
    assert stats["3"].tansho_total == 1000
    assert stats["3"].fukusho_total == 300
