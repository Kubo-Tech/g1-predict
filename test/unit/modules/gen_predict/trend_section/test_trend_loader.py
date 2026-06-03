"""_trend_loader の単体テスト。"""

from g1_predict.modules.gen_predict._trend_loader import (
    _is_valid_race_code, extract_sire_condition_sources)

# --- _is_valid_race_code ---


def test_is_valid_race_code_valid() -> None:
    """正常な16桁コードは True。"""
    assert _is_valid_race_code("2026050505010106") is True


def test_is_valid_race_code_too_short() -> None:
    """15桁は False。"""
    assert _is_valid_race_code("202605050501010") is False


def test_is_valid_race_code_too_long() -> None:
    """17桁は False。"""
    assert _is_valid_race_code("20260505050101060") is False


def test_is_valid_race_code_invalid_month_zero() -> None:
    """月=00 は False。"""
    assert _is_valid_race_code("2026000505010106") is False


def test_is_valid_race_code_invalid_month_13() -> None:
    """月=13 は False。"""
    assert _is_valid_race_code("2026130505010106") is False


def test_is_valid_race_code_invalid_day_zero() -> None:
    """日=00 は False。"""
    assert _is_valid_race_code("2026050005010106") is False


def test_is_valid_race_code_invalid_day_32() -> None:
    """日=32 は False。"""
    assert _is_valid_race_code("2026053205010106") is False


def test_is_valid_race_code_invalid_race_no_zero() -> None:
    """レース番号=00 は False。"""
    assert _is_valid_race_code("2026050505010100") is False


def test_is_valid_race_code_invalid_race_no_13() -> None:
    """レース番号=13 は False。"""
    assert _is_valid_race_code("2026050505010113") is False


def test_is_valid_race_code_non_digit_race_no() -> None:
    """レース番号が非数字は False。"""
    assert _is_valid_race_code("20260505050101ab") is False


# --- extract_sire_condition_sources ---


def _make_config(
    rows_type: str = "boolean_multi",
    source_type: str = "sire_race_condition_finisher",
    extra: dict | None = None,
) -> dict:
    """テスト用 trends_config を生成する。"""
    src: dict = {"type": source_type, "race_name": "天皇賞春"}
    if extra:
        src.update(extra)
    return {
        "出走馬傾向": [
            {
                "name": "父馬実績",
                "rows": {
                    "type": rows_type,
                    "items": [{"label": "天皇賞春出走", "source": src}],
                },
            }
        ]
    }


def test_extract_sire_condition_sources_empty_config() -> None:
    """空の config は空リストを返す。"""
    assert extract_sire_condition_sources({}) == []


def test_extract_sire_condition_sources_non_boolean_multi() -> None:
    """rows.type が boolean_multi 以外はスキップ。"""
    config = _make_config(rows_type="fixed")
    assert extract_sire_condition_sources(config) == []


def test_extract_sire_condition_sources_wrong_source_type() -> None:
    """source.type が sire_race_condition_finisher 以外はスキップ。"""
    config = _make_config(source_type="gate_number")
    assert extract_sire_condition_sources(config) == []


def test_extract_sire_condition_sources_returns_source() -> None:
    """合致する source を返す。"""
    config = _make_config()
    sources = extract_sire_condition_sources(config)
    assert len(sources) == 1
    assert sources[0]["race_name"] == "天皇賞春"


def test_extract_sire_condition_sources_deduplicates() -> None:
    """同一条件の source は1件のみ返す。"""
    src = {"type": "sire_race_condition_finisher", "race_name": "天皇賞春"}
    config = {
        "カテゴリA": [
            {
                "name": "metricA",
                "rows": {
                    "type": "boolean_multi",
                    "items": [
                        {"label": "ラベル1", "source": src},
                        {"label": "ラベル2", "source": src},
                    ],
                },
            }
        ]
    }
    sources = extract_sire_condition_sources(config)
    assert len(sources) == 1


def test_extract_sire_condition_sources_multiple_categories() -> None:
    """複数カテゴリから収集、重複なし。"""
    src_a = {"type": "sire_race_condition_finisher", "race_name": "天皇賞春"}
    src_b = {"type": "sire_race_condition_finisher", "race_name": "有馬記念"}
    config = {
        "カテゴリA": [
            {
                "name": "metricA",
                "rows": {
                    "type": "boolean_multi",
                    "items": [{"label": "A", "source": src_a}],
                },
            }
        ],
        "カテゴリB": [
            {
                "name": "metricB",
                "rows": {
                    "type": "boolean_multi",
                    "items": [{"label": "B", "source": src_b}],
                },
            }
        ],
    }
    sources = extract_sire_condition_sources(config)
    names = {s["race_name"] for s in sources}
    assert names == {"天皇賞春", "有馬記念"}
