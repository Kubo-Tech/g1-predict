"""load_categories の単体テスト"""

from pathlib import Path

import pytest

from scripts.hatena_publish import load_categories

_RACE_DIR = Path("public/2026/2026092706040911_スプリンターズS")


@pytest.fixture
def hatena_config(tmp_path: Path) -> Path:
    """テスト用hatena.yml"""
    config_path = tmp_path / "hatena.yml"
    config_path.write_text(
        "categories:\n"
        "  default:\n    - 競馬\n"
        "  race:\n    - 競馬\n    - G1\n"
        "  article:\n"
        "    予想:\n      - 競馬予想\n"
        "    回顧:\n      - レース回顧\n      - 競馬\n",
        encoding="utf-8",
    )
    return config_path


# 正常系
def test_load_categories_race_article(hatena_config: Path) -> None:
    """レース記事には race・article のカテゴリとレース名をこの順で付ける"""
    result = load_categories(hatena_config, _RACE_DIR / "予想.md")
    assert result == ["競馬", "G1", "競馬予想", "スプリンターズS"]


def test_load_categories_removes_duplicates(hatena_config: Path) -> None:
    """race と article に同じカテゴリがある場合は1つにまとめる"""
    result = load_categories(hatena_config, _RACE_DIR / "回顧.md")
    assert result == ["競馬", "G1", "レース回顧", "スプリンターズS"]


def test_load_categories_race_name_with_underscore(hatena_config: Path) -> None:
    """レース名に含まれるアンダースコアはそのままカテゴリにする"""
    md_path = Path("public/2026/2026092706040911_A_B/予想.md")
    assert load_categories(hatena_config, md_path)[-1] == "A_B"


def test_load_categories_returns_default_for_non_race_article(hatena_config: Path) -> None:
    """レース記事以外には default のカテゴリを付ける"""
    result = load_categories(hatena_config, Path("public/馬券の印ルール.md"))
    assert result == ["競馬"]


# 準正常系
def test_load_categories_raises_for_unknown_article_stem(hatena_config: Path) -> None:
    """レース記事で article に無いファイル名の場合KeyErrorが発生する"""
    with pytest.raises(KeyError, match="article.予想 copy"):
        load_categories(hatena_config, _RACE_DIR / "予想 copy.md")


def test_load_categories_raises_when_no_default_for_non_race_article(tmp_path: Path) -> None:
    """default が無い設定でレース記事以外を渡すとKeyErrorが発生する"""
    config_path = tmp_path / "hatena.yml"
    config_path.write_text("categories:\n  race:\n    - 競馬\n  article: {}\n", encoding="utf-8")
    with pytest.raises(KeyError, match="default"):
        load_categories(config_path, Path("public/馬券の印ルール.md"))


def test_load_categories_raises_when_race_missing(tmp_path: Path) -> None:
    """race が無い設定でレース記事を渡すとKeyErrorが発生する"""
    config_path = tmp_path / "hatena.yml"
    config_path.write_text("categories:\n  default:\n    - 競馬\n", encoding="utf-8")
    with pytest.raises(KeyError, match="race / article"):
        load_categories(config_path, _RACE_DIR / "予想.md")
