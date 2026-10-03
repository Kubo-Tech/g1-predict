"""fetch_feed_entries の単体テスト"""

from unittest.mock import patch
from xml.etree import ElementTree

import pytest
import requests

from g1_predict.modules.utils.hatena_links import ArticleLink, fetch_feed_entries

from .conftest import BLOG_URL, make_feed_xml, make_response

_PATCH_TARGET = "g1_predict.modules.utils.hatena_links.requests.get"


# 正常系
def test_fetch_feed_entries_parses_entries() -> None:
    """エントリIDをキーに、タイトルとURLを返す"""
    xml = make_feed_xml(
        [
            ("111", "【スプリンターズS2026】傾向分析", "https://example.com/entry/1"),
            ("222", "【スプリンターズS2026】予想", "https://example.com/entry/2"),
        ]
    )
    with patch(_PATCH_TARGET, return_value=make_response(xml)) as mock_get:
        result = fetch_feed_entries(BLOG_URL)
    assert result == {
        "111": ArticleLink("【スプリンターズS2026】傾向分析", "https://example.com/entry/1"),
        "222": ArticleLink("【スプリンターズS2026】予想", "https://example.com/entry/2"),
    }
    assert mock_get.call_args.args[0] == f"{BLOG_URL}/feed"


def test_fetch_feed_entries_ignores_non_alternate_link_order() -> None:
    """rel=alternate のリンクがあればそのURLを使う"""
    xml = (
        '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>t</title>'
        '<link rel="edit" href="https://example.com/edit"/>'
        '<link rel="alternate" href="https://example.com/entry/1"/>'
        "<id>hatenablog://entry/111</id></entry></feed>"
    ).encode()
    with patch(_PATCH_TARGET, return_value=make_response(xml)):
        result = fetch_feed_entries(BLOG_URL)
    assert result == {"111": ArticleLink("t", "https://example.com/entry/1")}


def test_fetch_feed_entries_returns_empty_for_feed_without_entries() -> None:
    """エントリが無いフィードは空のdictを返す"""
    with patch(_PATCH_TARGET, return_value=make_response(make_feed_xml([]))):
        assert fetch_feed_entries(BLOG_URL) == {}


# 準正常系
def test_fetch_feed_entries_raises_on_http_error() -> None:
    """HTTPエラーが返った場合は例外になる"""
    response = make_response(b"")
    response.raise_for_status.side_effect = requests.HTTPError("500")
    with patch(_PATCH_TARGET, return_value=response), pytest.raises(requests.HTTPError):
        fetch_feed_entries(BLOG_URL)


def test_fetch_feed_entries_raises_on_connection_error() -> None:
    """通信に失敗した場合は例外になる"""
    with (
        patch(_PATCH_TARGET, side_effect=requests.ConnectionError("down")),
        pytest.raises(requests.ConnectionError),
    ):
        fetch_feed_entries(BLOG_URL)


def test_fetch_feed_entries_raises_on_invalid_xml() -> None:
    """XMLを解析できない場合は例外になる"""
    with (
        patch(_PATCH_TARGET, return_value=make_response(b"<feed>")),
        pytest.raises(ElementTree.ParseError),
    ):
        fetch_feed_entries(BLOG_URL)


def test_fetch_feed_entries_raises_when_entry_has_no_url() -> None:
    """エントリにURLが無い場合は ValueError になる"""
    xml = (
        '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>t</title>'
        "<id>hatenablog://entry/111</id></entry></feed>"
    ).encode()
    with patch(_PATCH_TARGET, return_value=make_response(xml)), pytest.raises(ValueError):
        fetch_feed_entries(BLOG_URL)
