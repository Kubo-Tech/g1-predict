"""to_short_race_name の単体テスト。"""

from unittest.mock import patch

import pytest

from g1_predict.modules.utils.race_name import to_short_race_name

_MODULE = "g1_predict.modules.utils.race_name"


# 正常系
def test_to_short_race_name_uses_registered_name() -> None:
    """対応表に登録されたレースは、対応表の表記にする。"""
    with patch.dict(f"{_MODULE}.SHORT_RACE_NAMES", {"Ａ賞Ｂステークス": "BS"}, clear=True):
        assert to_short_race_name("Ａ賞Ｂステークス") == "BS"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("紫苑ステークス", "紫苑S"),
        ("キーンランドカップ", "キーンランドC"),
        ("ニュージーランドトロフィー", "ニュージーランドT"),
        ("ＣＢＣ賞", "CBC賞"),
        ("京王杯２歳ステークス", "京王杯2歳S"),
        ("天皇賞（春）", "天皇賞（春）"),
        ("ステークス特別", "ステークス特別"),
        ("マリーンカップ（中央交流）　Ｊｐｎ３", "マリーンC"),
        ("東京大賞典（中央交流）　Ｇ１", "東京大賞典"),
    ],
)
def test_to_short_race_name_abbreviates_suffix_and_fullwidth(name: str, expected: str) -> None:
    """対応表に無いレースは、交流重賞の印を除き、末尾の語を略記し、全角英数字を半角にする。"""
    with patch.dict(f"{_MODULE}.SHORT_RACE_NAMES", {}, clear=True):
        assert to_short_race_name(name) == expected
