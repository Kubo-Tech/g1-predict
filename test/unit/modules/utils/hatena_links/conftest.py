"""hatena_links のテスト共通fixture"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

BLOG_URL = "https://example.hatenadiary.com"
RACE_DIR_NAME = "2026092706040911_スプリンターズS"


def make_feed_xml(entries: list[tuple[str, str, str]]) -> bytes:
    """テスト用の Atom フィードXMLを生成する

    Args:
        entries (list[tuple[str, str, str]]): (エントリID, タイトル, URL) のリスト

    Returns:
        bytes: フィードXML
    """
    body = "".join(
        f"<entry><title>{title}</title><link href=\"{url}\"/>"
        f"<id>hatenablog://entry/{entry_id}</id></entry>"
        for entry_id, title, url in entries
    )
    xml = f'<feed xmlns="http://www.w3.org/2005/Atom"><title>blog</title>{body}</feed>'
    return xml.encode("utf-8")


def make_response(content: bytes) -> MagicMock:
    """フィード取得のレスポンスのモックを生成する

    Args:
        content (bytes): レスポンスボディ

    Returns:
        MagicMock: requests.Response のモック
    """
    response = MagicMock()
    response.content = content
    return response


def write_state(public_dir: Path, entries: dict[str, str]) -> None:
    """2026年の状態ファイルを書き出す

    Args:
        public_dir (Path): public ディレクトリ
        entries (dict[str, str]): 記事の相対パス -> エントリID
    """
    year_dir = public_dir / "2026"
    year_dir.mkdir(parents=True, exist_ok=True)
    state = {"entries": entries, "images": {}}
    (year_dir / ".hatena_entry_ids.json").write_text(json.dumps(state), encoding="utf-8")


@pytest.fixture
def public_dir(tmp_path: Path) -> Path:
    """public ディレクトリ"""
    return tmp_path / "public"


@pytest.fixture
def race_dir(public_dir: Path) -> Path:
    """レース単位の出力ディレクトリ"""
    path = public_dir / "2026" / RACE_DIR_NAME
    path.mkdir(parents=True)
    return path


@pytest.fixture
def hatena_config(tmp_path: Path) -> Path:
    """blog_url を持つテスト用hatena.yml"""
    path = tmp_path / "hatena.yml"
    config = f"blog_url: {BLOG_URL}/\ncategories:\n  default:\n    - 競馬\n"
    path.write_text(config, encoding="utf-8")
    return path
