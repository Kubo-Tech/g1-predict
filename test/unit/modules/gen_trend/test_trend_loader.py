"""_trend_loader の単体テスト。"""

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import yaml
from mykeibadb.analytics import RaceCondition

from g1_predict.modules.gen_trend._trend_loader import build_metric_condition, build_race_context
from g1_predict.modules.gen_trend._trend_models import TREND_YEARS

_CONFIGS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "configs")
)


def _make_race_info(
    keibajo_code: str = "05",
    kyori: int = 2400,
    track_code: str = "10",
    kaisai_nen: int = 2026,
    tokubetsu_kyoso_bango: str = "0008",
) -> pd.DataFrame:
    """build_race_context 用の race_info DataFrame を生成する。"""
    return pd.DataFrame({
        "keibajo_code": [keibajo_code],
        "kyori": [kyori],
        "track_code": [track_code],
        "kaisai_nen": [kaisai_nen],
        "tokubetsu_kyoso_bango": [tokubetsu_kyoso_bango],
    })


def test_build_race_context_returns_correct_keibajo_codes() -> None:
    """keibajo_codes が RaceCondition に正しく設定される。"""
    race_info = _make_race_info(keibajo_code="05")
    with (
        patch("g1_predict.modules.gen_trend._trend_loader.ConfigManager"),
        patch("g1_predict.modules.gen_trend._trend_loader.ConnectionManager"),
    ):
        _, condition = build_race_context("2026050505010101", race_info)
    assert condition.keibajo_codes == ["05"]


def test_build_race_context_returns_correct_kyori() -> None:
    """kyori が RaceCondition に正しく設定される。"""
    race_info = _make_race_info(kyori=2400)
    with (
        patch("g1_predict.modules.gen_trend._trend_loader.ConfigManager"),
        patch("g1_predict.modules.gen_trend._trend_loader.ConnectionManager"),
    ):
        _, condition = build_race_context("2026050505010101", race_info)
    assert condition.kyori == 2400


def test_build_race_context_shiba_track_code() -> None:
    """芝トラックコードで shiba_da が '芝' になる。"""
    race_info = _make_race_info(track_code="10")
    with (
        patch("g1_predict.modules.gen_trend._trend_loader.ConfigManager"),
        patch("g1_predict.modules.gen_trend._trend_loader.ConnectionManager"),
    ):
        _, condition = build_race_context("2026050505010101", race_info)
    assert condition.shiba_da == "芝"


def test_build_race_context_dirt_track_code() -> None:
    """ダートトラックコードで shiba_da が 'ダ' になる。"""
    race_info = _make_race_info(track_code="23")
    with (
        patch("g1_predict.modules.gen_trend._trend_loader.ConfigManager"),
        patch("g1_predict.modules.gen_trend._trend_loader.ConnectionManager"),
    ):
        _, condition = build_race_context("2026050505010101", race_info)
    assert condition.shiba_da == "ダ"


def test_build_race_context_year_range() -> None:
    """year_from / year_to が TREND_YEARS 分遡った範囲になる。"""
    race_info = _make_race_info(kaisai_nen=2026)
    with (
        patch("g1_predict.modules.gen_trend._trend_loader.ConfigManager"),
        patch("g1_predict.modules.gen_trend._trend_loader.ConnectionManager"),
    ):
        _, condition = build_race_context("2026050505010101", race_info)
    assert condition.year_from == str(2026 - TREND_YEARS)
    assert condition.year_to == "2025"


def test_build_race_context_returns_connection_manager() -> None:
    """ConnectionManager インスタンスを返す。"""
    race_info = _make_race_info()
    mock_manager = MagicMock()
    mock_cm_class = MagicMock(return_value=mock_manager)
    with (
        patch("g1_predict.modules.gen_trend._trend_loader.ConfigManager"),
        patch("g1_predict.modules.gen_trend._trend_loader.ConnectionManager", mock_cm_class),
    ):
        manager, _ = build_race_context("2026050505010101", race_info)
    assert manager is mock_manager


# --- build_metric_condition ---


def _make_base_condition() -> RaceCondition:
    """build_metric_condition テスト用の基本 RaceCondition を生成する。"""
    return RaceCondition(
        keibajo_codes=["05"],
        kyori=2400,
        shiba_da="芝",
        year_from="2016",
        year_to="2025",
        tokubetsu_kyoso_bango="0008",
    )


def test_build_metric_condition_none_returns_base_condition() -> None:
    """condition_cfg が None の場合は base_condition をそのまま返す。"""
    base_condition = _make_base_condition()
    result = build_metric_condition(base_condition, 2026, None)
    assert result == base_condition


def test_build_metric_condition_overrides_years() -> None:
    """years 指定時に year_from / year_to が再計算される。"""
    base_condition = _make_base_condition()
    result = build_metric_condition(base_condition, 2026, {"years": 5})
    assert result.year_from == "2021"
    assert result.year_to == "2025"


def test_build_metric_condition_default_years_is_trend_years() -> None:
    """years 未指定時は TREND_YEARS 分遡る。"""
    base_condition = _make_base_condition()
    result = build_metric_condition(base_condition, 2026, {"keibajo_codes": ["09"]})
    assert result.year_from == str(2026 - TREND_YEARS)
    assert result.year_to == "2025"


def test_build_metric_condition_overrides_keibajo_codes_kaisai_nichime_babajotai_codes() -> None:
    """keibajo_codes / kaisai_nichime / babajotai_codes が condition に反映される。"""
    base_condition = _make_base_condition()
    result = build_metric_condition(
        base_condition,
        2026,
        {"keibajo_codes": ["09"], "kaisai_nichime": [4], "babajotai_codes": ["1"]},
    )
    assert result.keibajo_codes == ["09"]
    assert result.kaisai_nichime == [4]
    assert result.babajotai_codes == ["1"]


def test_build_metric_condition_keeps_base_fields() -> None:
    """condition_cfg に無いフィールドは base_condition の値を維持する。"""
    base_condition = _make_base_condition()
    result = build_metric_condition(base_condition, 2026, {"years": 5})
    assert result.keibajo_codes == ["05"]
    assert result.kyori == 2400
    assert result.shiba_da == "芝"
    assert result.tokubetsu_kyoso_bango == "0008"


def test_build_metric_condition_years_less_than_one_raises() -> None:
    """years が1未満の場合は ValueError が発生する。"""
    base_condition = _make_base_condition()
    with pytest.raises(ValueError, match="years"):
        build_metric_condition(base_condition, 2026, {"years": 0})


# --- configs/宝塚記念.yml ---


def test_takarazuka_yaml_loads_all_trend_categories() -> None:
    """宝塚記念.yml の trends が全カテゴリを欠損なく読み込める。"""
    config_path = os.path.join(_CONFIGS_DIR, "宝塚記念.yml")
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    trends = config["trends"]
    assert set(trends.keys()) == {"出走馬傾向", "騎手傾向", "生産者傾向", "血統傾向"}

    metric_names = [m["name"] for m in trends["出走馬傾向"]]
    assert metric_names == [
        "枠順",
        "人気",
        "脚質",
        "前走脚質",
        "上がり3F順位",
        "前走上がり3F順位",
        "所属",
        "馬齢",
        "性別",
        "前走レース",
        "前走クラス",
        "前走着順",
        "前走G1着順",
        "前走G2着順",
        "前走G3着順",
        "前走非重賞着順",
        "前走距離",
        "阪神重賞好走実績",
    ]


def test_takarazuka_yaml_jockey_and_breeder_use_all_entries() -> None:
    """宝塚記念.yml の騎手・生産者が all_entries で今回出走対象を全表示する。"""
    config_path = os.path.join(_CONFIGS_DIR, "宝塚記念.yml")
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    trends = config["trends"]
    assert trends["騎手傾向"][0]["rows"] == {"type": "all_entries"}
    assert trends["生産者傾向"][0]["rows"] == {"type": "all_entries"}


def test_takarazuka_yaml_gate_number_condition_is_hanshin_4th_day_good_track() -> None:
    """枠順は阪神4日目良馬場のみのconditionを持つ。"""
    config_path = os.path.join(_CONFIGS_DIR, "宝塚記念.yml")
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    gate_number_cfg = config["trends"]["出走馬傾向"][0]
    assert gate_number_cfg["name"] == "枠順"
    assert gate_number_cfg["condition"] == {
        "years": 10,
        "keibajo_codes": ["09"],
        "kaisai_nichime": [4],
        "babajotai_codes": ["1"],
    }
