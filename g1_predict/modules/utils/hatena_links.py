"""はてなブログの関連記事リンクを組み立てるユーティリティ。

投稿済みの記事は、はてな投稿スクリプトが `public/{年}/.hatena_entry_ids.json` に
記事ファイルのパスとエントリIDの対応として記録している。
公開 Atom フィードのエントリIDと突き合わせて、記事のタイトルとURLを引く。
"""

import json
import os
from dataclasses import dataclass
from xml.etree import ElementTree

import requests
import yaml

_ATOM_NS = "http://www.w3.org/2005/Atom"
_ENTRY_ID_PREFIX = "hatenablog://entry/"
_STATE_FILE_NAME = ".hatena_entry_ids.json"
_REQUEST_TIMEOUT = 30


@dataclass(frozen=True)
class ArticleLink:
    """記事へのリンク

    Attributes:
        title (str): 記事タイトル
        url (str): 記事URL
    """

    title: str
    url: str


def build_related_articles_section(
    public_dir: str,
    race_dir: str,
    article_names: list[str],
    own_article_label: str,
    config_path: str,
) -> str:
    """関連記事セクションを生成する

    `article_names` の順に、投稿済みでフィードに載っている記事へのリンクを並べる。
    リンクを引けない記事は出力しない。
    最後に URL を手で埋めるための `[{own_article_label}]()` を常に出力する。

    Args:
        public_dir (str): public ディレクトリのパス
        race_dir (str): レース単位の出力ディレクトリのパス（`public_dir` 配下）
        article_names (list[str]): リンク対象の記事ファイル名（拡張子を除く）のリスト
        own_article_label (str): URL が空のリンクに使う文字列
        config_path (str): hatena.yml のパス

    Returns:
        str: `## 関連記事` 見出しから始まる関連記事セクションのMarkdown文字列
    """
    blog_url = load_blog_url(config_path)
    feed = fetch_feed_entries(blog_url)
    lines = ["## 関連記事", ""]
    for article_name in article_names:
        link = find_article_link(public_dir, race_dir, f"{article_name}.md", feed)
        if link is not None:
            lines.append(f"- [{link.title}]({link.url})")
    lines.append(f"- [{own_article_label}]()")
    return "\n".join(lines)


def load_blog_url(config_path: str) -> str:
    """hatena.yml からブログのURLを取得する

    Args:
        config_path (str): hatena.yml のパス

    Returns:
        str: 末尾のスラッシュを除いたブログURL

    Raises:
        KeyError: blog_url が設定されていない場合
    """
    with open(config_path, encoding="utf-8") as f:
        config: dict[str, object] = yaml.safe_load(f) or {}
    if "blog_url" not in config:
        raise KeyError(f"blog_url が設定されていません: {config_path}")
    return str(config["blog_url"]).rstrip("/")


def fetch_feed_entries(blog_url: str) -> dict[str, ArticleLink]:
    """ブログの公開フィード（1ページ目）から記事の一覧を取得する

    Args:
        blog_url (str): ブログのURL

    Returns:
        dict[str, ArticleLink]: エントリID -> 記事リンクのdict

    Raises:
        requests.RequestException: 通信に失敗した場合、またはHTTPエラーが返った場合
        ElementTree.ParseError: フィードのXMLを解析できない場合
        ValueError: エントリにID・タイトル・URLのいずれかが無い場合
    """
    response = requests.get(f"{blog_url}/feed", timeout=_REQUEST_TIMEOUT)
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)

    entries: dict[str, ArticleLink] = {}
    for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
        entry_id = _find_text(entry, "id")
        title = _find_text(entry, "title")
        link = entry.find(f"{{{_ATOM_NS}}}link[@rel='alternate']")
        if link is None:
            link = entry.find(f"{{{_ATOM_NS}}}link")
        url = link.get("href") if link is not None else None
        if not entry_id.startswith(_ENTRY_ID_PREFIX) or not url:
            raise ValueError(f"フィードのエントリを解釈できません: id={entry_id!r} url={url!r}")
        entries[entry_id.removeprefix(_ENTRY_ID_PREFIX)] = ArticleLink(title=title, url=url)
    return entries


def find_article_link(
    public_dir: str,
    race_dir: str,
    file_name: str,
    feed: dict[str, ArticleLink],
) -> ArticleLink | None:
    """記事ファイルに対応するはてなブログの記事リンクを取得する

    状態ファイルに記事が無い場合（未投稿）と、フィードにエントリが無い場合は None を返す。

    Args:
        public_dir (str): public ディレクトリのパス
        race_dir (str): レース単位の出力ディレクトリのパス（`{public_dir}/{年}/...`）
        file_name (str): 記事ファイル名（例: 予想.md）
        feed (dict[str, ArticleLink]): `fetch_feed_entries` で取得した記事の一覧

    Returns:
        ArticleLink | None: 記事リンク。引けない場合は None
    """
    year_dir = os.path.dirname(race_dir)
    state_path = os.path.join(year_dir, _STATE_FILE_NAME)
    if not os.path.isfile(state_path):
        return None
    with open(state_path, encoding="utf-8") as f:
        state: dict[str, dict[str, str]] = json.load(f)

    entry_key = os.path.relpath(os.path.join(race_dir, file_name), public_dir)
    entry_id = state.get("entries", {}).get(entry_key)
    if entry_id is None:
        return None
    return feed.get(entry_id)


def _find_text(entry: ElementTree.Element, tag: str) -> str:
    """フィードのエントリから子要素のテキストを取得する

    Args:
        entry (ElementTree.Element): フィードの entry 要素
        tag (str): 子要素のタグ名

    Returns:
        str: 子要素のテキスト

    Raises:
        ValueError: 子要素が無い、またはテキストが空の場合
    """
    element = entry.find(f"{{{_ATOM_NS}}}{tag}")
    if element is None or not element.text:
        raise ValueError(f"フィードのエントリに {tag} がありません")
    return element.text
