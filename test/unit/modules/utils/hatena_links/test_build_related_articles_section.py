"""build_related_articles_section の単体テスト"""

from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from g1_predict.modules.utils.hatena_links import build_related_articles_section

from .conftest import RACE_DIR_NAME, make_feed_xml, make_response, write_state

_PATCH_TARGET = "g1_predict.modules.utils.hatena_links.requests.get"
_NAMES = ["過去の傾向", "前日の傾向", "当日の傾向"]


def _key(name: str) -> str:
    return f"2026/{RACE_DIR_NAME}/{name}.md"


def _build(public_dir: Path, race_dir: Path, hatena_config: Path) -> str:
    return build_related_articles_section(
        str(public_dir), str(race_dir), _NAMES, "自作AIの予想", str(hatena_config)
    )


# 正常系
def test_build_related_articles_section_lists_links_in_order(
    public_dir: Path, race_dir: Path, hatena_config: Path
) -> None:
    """記事名の順にリンクを並べ、最後に URL が空のリンクを付ける"""
    entries = {_key("過去の傾向"): "1", _key("前日の傾向"): "2", _key("当日の傾向"): "3"}
    write_state(public_dir, entries)
    xml = make_feed_xml(
        [
            ("3", "当日タイトル", "https://example.com/3"),
            ("1", "過去タイトル", "https://example.com/1"),
            ("2", "前日タイトル", "https://example.com/2"),
        ]
    )
    with patch(_PATCH_TARGET, return_value=make_response(xml)) as mock_get:
        result = _build(public_dir, race_dir, hatena_config)
    assert result == (
        "## 関連記事\n\n"
        "- [過去タイトル](https://example.com/1)\n"
        "- [前日タイトル](https://example.com/2)\n"
        "- [当日タイトル](https://example.com/3)\n"
        "- [自作AIの予想]()"
    )
    assert mock_get.call_count == 1


def test_build_related_articles_section_skips_missing_links(
    public_dir: Path, race_dir: Path, hatena_config: Path
) -> None:
    """リンクを引けない記事は行ごと省く"""
    write_state(public_dir, {_key("過去の傾向"): "1", _key("前日の傾向"): "2"})
    xml = make_feed_xml([("1", "過去タイトル", "https://example.com/1")])
    with patch(_PATCH_TARGET, return_value=make_response(xml)):
        result = _build(public_dir, race_dir, hatena_config)
    assert result == (
        "## 関連記事\n\n- [過去タイトル](https://example.com/1)\n- [自作AIの予想]()"
    )


def test_build_related_articles_section_without_any_link(
    public_dir: Path, race_dir: Path, hatena_config: Path
) -> None:
    """リンクが1つも無い場合は URL が空のリンクだけを出力する"""
    with patch(_PATCH_TARGET, return_value=make_response(make_feed_xml([]))):
        result = _build(public_dir, race_dir, hatena_config)
    assert result == "## 関連記事\n\n- [自作AIの予想]()"


# 準正常系
def test_build_related_articles_section_raises_when_feed_fails(
    public_dir: Path, race_dir: Path, hatena_config: Path
) -> None:
    """フィードの取得に失敗した場合は例外になる"""
    with (
        patch(_PATCH_TARGET, side_effect=requests.ConnectionError("down")),
        pytest.raises(requests.ConnectionError),
    ):
        _build(public_dir, race_dir, hatena_config)
