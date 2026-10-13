"""to_config_dir_name の単体テスト。"""

import pytest

from g1_predict.modules.utils.race_name import to_config_dir_name


# 正常系
def test_to_config_dir_name_joins_tokubetsu_kyoso_bango_and_race_label() -> None:
    """特別競走番号とレース名を「_」でつなぐ。"""
    assert to_config_dir_name("0018", "秋華賞") == "0018_秋華賞"


# 異常系
@pytest.mark.parametrize("bango", ["18", "00018", "ab12", "0000"])
def test_to_config_dir_name_invalid_tokubetsu_kyoso_bango_raises(bango: str) -> None:
    """特別競走番号が4桁の数字でない、または 0000 の場合は ValueError。"""
    with pytest.raises(ValueError, match="特別競走番号"):
        to_config_dir_name(bango, "秋華賞")
