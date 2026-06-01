"""Markdown ユーティリティ。"""

import re


def replace_section(content: str, header: str, new_section: str) -> str:
    """Markdown のセクションを置換する。

    Args:
        content: 対象の Markdown 文字列。
        header: 置換対象のセクションヘッダー（例: "## 結果"）。
        new_section: 置換後のセクション文字列。
    """
    pattern = re.compile(rf"(?ms)^{re.escape(header)}\n.*?(?=^## |\Z)")
    return pattern.sub(new_section.rstrip("\n") + "\n\n", content)
