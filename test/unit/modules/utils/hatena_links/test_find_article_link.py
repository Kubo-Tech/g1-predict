"""find_article_link の単体テスト"""

from pathlib import Path

from g1_predict.modules.utils.hatena_links import ArticleLink, find_article_link

from .conftest import RACE_DIR_NAME, write_state

_FEED = {"111": ArticleLink("【スプリンターズS2026】予想", "https://example.com/entry/1")}
_KEY = f"2026/{RACE_DIR_NAME}/予想.md"


# 正常系
def test_find_article_link_returns_link(public_dir: Path, race_dir: Path) -> None:
    """状態ファイルとフィードの両方にある記事のリンクを返す"""
    write_state(public_dir, {_KEY: "111"})
    result = find_article_link(str(public_dir), str(race_dir), "予想.md", _FEED)
    assert result == _FEED["111"]


# 準正常系
def test_find_article_link_returns_none_without_state_file(
    public_dir: Path, race_dir: Path
) -> None:
    """状態ファイルが無い場合は None を返す"""
    assert find_article_link(str(public_dir), str(race_dir), "予想.md", _FEED) is None


def test_find_article_link_returns_none_when_not_in_state(
    public_dir: Path, race_dir: Path
) -> None:
    """状態ファイルに記事が無い場合は None を返す"""
    write_state(public_dir, {f"2026/{RACE_DIR_NAME}/回顧.md": "111"})
    assert find_article_link(str(public_dir), str(race_dir), "予想.md", _FEED) is None


def test_find_article_link_returns_none_when_not_in_feed(
    public_dir: Path, race_dir: Path
) -> None:
    """フィードにエントリが無い場合は None を返す"""
    write_state(public_dir, {_KEY: "999"})
    assert find_article_link(str(public_dir), str(race_dir), "予想.md", _FEED) is None
