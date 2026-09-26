"""load_categories の単体テスト"""

from pathlib import Path

import pytest

from scripts.hatena_publish import load_categories


@pytest.fixture
def hatena_config(tmp_path: Path) -> Path:
    """テスト用hatena.yml"""
    config_path = tmp_path / "hatena.yml"
    config_path.write_text(
        "categories:\n  default:\n    - 競馬\n  予想:\n    - G1予想\n"
        "  結果:\n    - G1結果\n    - レース結果\n",
        encoding="utf-8",
    )
    return config_path


# 正常系
def test_load_categories_returns_list_for_existing_stem(hatena_config: Path) -> None:
    """存在するstemに対してカテゴリリストを返す"""
    result = load_categories(hatena_config, "予想")
    assert result == ["G1予想"]


def test_load_categories_returns_multiple_categories(hatena_config: Path) -> None:
    """複数カテゴリが設定されている場合すべて返す"""
    result = load_categories(hatena_config, "結果")
    assert result == ["G1結果", "レース結果"]


def test_load_categories_returns_list_type(hatena_config: Path) -> None:
    """戻り値がlist型である"""
    result = load_categories(hatena_config, "予想")
    assert isinstance(result, list)


def test_load_categories_returns_default_for_missing_stem(hatena_config: Path) -> None:
    """未登録stemに対してdefaultカテゴリを返す"""
    result = load_categories(hatena_config, "馬券の印ルール")
    assert result == ["競馬"]


# 準正常系
def test_load_categories_raises_when_no_default_and_stem_missing(tmp_path: Path) -> None:
    """defaultキーなしで未登録stemに対してKeyErrorが発生する"""
    config_path = tmp_path / "hatena.yml"
    config_path.write_text("categories:\n  予想:\n    - G1予想\n", encoding="utf-8")
    with pytest.raises(KeyError, match="カテゴリ設定が見つかりません"):
        load_categories(config_path, "unknown_stem")


def test_load_categories_raises_on_empty_categories(tmp_path: Path) -> None:
    """categoriesセクションが空の場合KeyErrorが発生する"""
    config_path = tmp_path / "hatena.yml"
    config_path.write_text("categories: {}\n", encoding="utf-8")
    with pytest.raises(KeyError):
        load_categories(config_path, "予想")
