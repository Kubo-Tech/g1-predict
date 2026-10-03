"""load_blog_url の単体テスト"""

from pathlib import Path

import pytest

from g1_predict.modules.utils.hatena_links import load_blog_url


# 正常系
def test_load_blog_url_strips_trailing_slash(hatena_config: Path) -> None:
    """末尾のスラッシュを除いたブログURLを返す"""
    assert load_blog_url(str(hatena_config)) == "https://example.hatenadiary.com"


# 準正常系
def test_load_blog_url_raises_when_missing(tmp_path: Path) -> None:
    """blog_url が無い場合は KeyError になる"""
    config_path = tmp_path / "hatena.yml"
    config_path.write_text("categories:\n  default:\n    - 競馬\n", encoding="utf-8")
    with pytest.raises(KeyError):
        load_blog_url(str(config_path))
