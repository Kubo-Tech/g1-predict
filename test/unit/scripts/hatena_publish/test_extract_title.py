"""extract_title の単体テスト"""

import pytest

from scripts.hatena_publish import extract_title


# 正常系
def test_extract_title_returns_h1_text() -> None:
    """H1見出しテキストを返す"""
    content = "# 東京優駿2026\n\n本文"
    assert extract_title(content) == "東京優駿2026"


def test_extract_title_ignores_h2_and_below() -> None:
    """H2以下の見出しは無視してH1のみ返す"""
    content = "# タイトル\n## サブタイトル\n### 小見出し"
    assert extract_title(content) == "タイトル"


def test_extract_title_returns_first_h1_when_multiple_exist() -> None:
    """H1が複数存在する場合、最初のものを返す"""
    content = "# 最初のH1\n# 二番目のH1"
    assert extract_title(content) == "最初のH1"


def test_extract_title_strips_trailing_whitespace() -> None:
    """H1テキストの前後の空白を除去する"""
    content = "#   スペースあり   \n本文"
    assert extract_title(content) == "スペースあり"


def test_extract_title_works_when_h1_is_not_first_line() -> None:
    """H1が先頭行でなくても取得できる"""
    content = "前置きテキスト\n# 見出し\n本文"
    assert extract_title(content) == "見出し"


# 準正常系
def test_extract_title_raises_when_no_h1() -> None:
    """H1見出しが存在しない場合ValueErrorが発生する"""
    with pytest.raises(ValueError, match="H1見出しが見つかりません"):
        extract_title("## H2のみ\n本文")


def test_extract_title_raises_on_empty_content() -> None:
    """空文字列でValueErrorが発生する"""
    with pytest.raises(ValueError):
        extract_title("")


def test_extract_title_raises_when_hash_without_space() -> None:
    """'# 'のスペースがない場合H1と認識しない"""
    with pytest.raises(ValueError):
        extract_title("#スペースなし\n本文")
