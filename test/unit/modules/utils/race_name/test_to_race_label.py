"""to_race_label の単体テスト。"""

from g1_predict.modules.utils.race_name import to_race_label


# 正常系
def test_to_race_label_returns_abbreviation_for_registered_race() -> None:
    """対応表に登録されたレースは略称に変換される。"""
    assert to_race_label("スプリンターズステークス") == "スプリンターズS"


def test_to_race_label_returns_input_for_unregistered_race() -> None:
    """対応表に登録されていないレースは引数をそのまま返す。"""
    assert to_race_label("宝塚記念") == "宝塚記念"
