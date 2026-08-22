"""validate_race_code の単体テスト。"""
import pytest

from g1_predict.modules.utils.output_path import validate_race_code


# 正常系
def test_validate_race_code_accepts_16_digit_number() -> None:
    """16桁の数字を渡すと例外が発生しない。"""
    validate_race_code("2026061409030411")


# 準正常系
@pytest.mark.parametrize(
    "race_code",
    [
        "202606140903041",  # 15桁
        "20260614090304111",  # 17桁
        "202606140903041a",  # 英字混在
        "",  # 空文字
        "../../etc",  # パストラバーサル
    ],
)
def test_validate_race_code_raises_for_invalid_format(race_code: str) -> None:
    """16桁の数字でない race_code で ValueError が発生する。"""
    with pytest.raises(ValueError):
        validate_race_code(race_code)
