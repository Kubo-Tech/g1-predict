"""remove_section の単体テスト。"""

from g1_predict.modules.utils.md_utils import remove_section


def test_remove_section_removes_heading_and_body() -> None:
    """指定した見出しのセクションを、次の見出しの手前まで本文ごと削除する。"""
    content = "## 総評\n\n本文\n\n## 展開評価\n\n表\n\n## 回顧\n"
    assert remove_section(content, "## 展開評価") == "## 総評\n\n本文\n\n## 回顧\n"


def test_remove_section_last_section() -> None:
    """末尾のセクションも削除できる。"""
    assert remove_section("## 総評\n\n## 展開評価\n\n表\n", "## 展開評価") == "## 総評\n\n"
