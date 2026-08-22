"""build_race_dir の単体テスト。"""
import os

import pytest

from g1_predict.modules.utils.output_path import build_race_dir

_PUBLIC_DIR = "/base/public"
_RACE_CODE = "2026061409030411"
_YEAR = "2026"
_RACE_NAME = "宝塚記念"


# 正常系
def test_build_race_dir_returns_expected_path() -> None:
    """正しい引数で {public_dir}/{year}/{race_code}_{race_name} が返る。"""
    result = build_race_dir(_PUBLIC_DIR, _YEAR, _RACE_CODE, _RACE_NAME)
    expected = os.path.join(_PUBLIC_DIR, _YEAR, f"{_RACE_CODE}_{_RACE_NAME}")
    assert result == expected


# 準正常系
@pytest.mark.parametrize(
    "public_dir, year, race_code, race_name",
    [
        (_PUBLIC_DIR, _YEAR, "202606140903041", _RACE_NAME),  # race_code 15桁
        (_PUBLIC_DIR, _YEAR, "../../etc", _RACE_NAME),  # race_code パストラバーサル
        (_PUBLIC_DIR, "202", _RACE_CODE, _RACE_NAME),  # year 3桁
        (_PUBLIC_DIR, "20xx", _RACE_CODE, _RACE_NAME),  # year 英字混在
        (_PUBLIC_DIR, _YEAR, _RACE_CODE, "../evil"),  # race_name に / を含む
        (_PUBLIC_DIR, _YEAR, _RACE_CODE, "a\\b"),  # race_name に \ を含む
        (_PUBLIC_DIR, _YEAR, _RACE_CODE, "."),  # race_name が .
        (_PUBLIC_DIR, _YEAR, _RACE_CODE, ".."),  # race_name が ..
        (_PUBLIC_DIR, _YEAR, _RACE_CODE, ""),  # race_name が空文字
    ],
)
def test_build_race_dir_raises_for_invalid_args(
    public_dir: str, year: str, race_code: str, race_name: str
) -> None:
    """不正な引数で ValueError が発生する。"""
    with pytest.raises(ValueError):
        build_race_dir(public_dir, year, race_code, race_name)
