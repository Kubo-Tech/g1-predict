"""はてなブログへMarkdownファイルを自動投稿・更新するスクリプト"""

import base64
import datetime
import hashlib
import html
import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

import requests
import yaml

_FOTOLIFE_POST_URL = "https://f.hatena.ne.jp/atom/post"
_ATOM_NS = "http://www.w3.org/2005/Atom"
_APP_NS = "http://www.w3.org/2007/app"
_HATENA_NS = "http://www.hatena.ne.jp/info/xmlns#"
_DC_NS = "http://purl.org/dc/elements/1.1/"

_REQUEST_TIMEOUT = 30

_CONTENT_TYPES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


@dataclass
class HatenaConfig:
    """はてなAPI接続設定

    Attributes:
        hatena_id (str): はてなID
        blog_id (str): ブログID（例: example.hatenablog.com）
        api_key (str): APIキー
    """

    hatena_id: str
    blog_id: str
    api_key: str


def extract_title(content: str) -> str:
    """MarkdownコンテンツからH1見出しを抽出する

    Args:
        content (str): Markdownコンテンツ

    Returns:
        str: H1見出しテキスト

    Raises:
        ValueError: H1見出しが存在しない場合
    """
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    raise ValueError("H1見出しが見つかりません")


def build_wsse_header(hatena_id: str, api_key: str) -> str:
    """WSSE認証ヘッダ文字列を生成する

    Args:
        hatena_id (str): はてなID
        api_key (str): APIキー

    Returns:
        str: X-WSSEヘッダの値
    """
    nonce = os.urandom(16)
    created = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    digest_bytes = hashlib.sha1(nonce + created.encode() + api_key.encode()).digest()
    digest = base64.b64encode(digest_bytes).decode()
    nonce_b64 = base64.b64encode(nonce).decode()
    return (
        f'UsernameToken Username="{hatena_id}", '
        f'PasswordDigest="{digest}", '
        f'Nonce="{nonce_b64}", '
        f'Created="{created}"'
    )


def load_categories(config_path: Path, stem: str) -> list[str]:
    """hatena.ymlからファイルstemに対応するカテゴリ一覧を取得する

    Args:
        config_path (Path): hatena.ymlのパス
        stem (str): ファイルstem（例: "予想", "結果"）

    Returns:
        list[str]: カテゴリ名のリスト

    Raises:
        KeyError: stemに対応するカテゴリが設定ファイルに存在しない場合
    """
    with open(config_path, encoding="utf-8") as f:
        config: dict[str, object] = yaml.safe_load(f) or {}
    categories: dict[str, list[str]] = config.get("categories", {})  # type: ignore[assignment]
    if stem not in categories:
        raise KeyError(f"カテゴリ設定が見つかりません: {stem}")
    return categories[stem]


def main() -> None:
    """メイン関数"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger(__name__)

    config = HatenaConfig(
        hatena_id=os.environ["HATENA_ID"],
        blog_id=os.environ["HATENA_BLOG_ID"],
        api_key=os.environ["HATENA_API_KEY"],
    )

    repo_dir = Path(__file__).parent.parent
    public_dir = repo_dir / "public"
    config_path = repo_dir / "configs" / "hatena.yml"

    changed_files = _get_changed_md_files(repo_dir)
    logger.info("変更されたMarkdownファイル: %d件", len(changed_files))

    files_by_year: dict[str, list[Path]] = {}
    for md_path in changed_files:
        rel_parts = md_path.relative_to(public_dir).parts
        year = rel_parts[0] if len(rel_parts) >= 2 else ""
        files_by_year.setdefault(year, []).append(md_path)

    for year, files in files_by_year.items():
        state_dir = public_dir / year if year else public_dir
        state_path = state_dir / ".hatena_entry_ids.json"
        state = _load_state(state_path)
        for md_path in files:
            _publish_md(md_path, public_dir, config_path, state_path, state, config, logger)

    logger.info("完了")


# private


def _get_changed_md_files(repo_dir: Path) -> list[Path]:
    """git diffで変更されたpublic配下のMarkdownファイルを取得する

    Args:
        repo_dir (Path): リポジトリルートディレクトリ

    Returns:
        list[Path]: 変更されたMarkdownファイルの絶対パスリスト
    """
    result = subprocess.run(
        ["git", "diff", "HEAD~1", "HEAD", "--name-only", "--diff-filter=AM"],
        capture_output=True,
        text=True,
        check=True,
        cwd=repo_dir,
    )
    changed = []
    for line in result.stdout.splitlines():
        path = Path(line)
        if path.parts[0] == "public" and path.suffix == ".md":
            changed.append(repo_dir / path)
    return changed


def _load_state(state_path: Path) -> dict[str, dict[str, str]]:
    """状態ファイルを読み込む

    Args:
        state_path (Path): 状態ファイルのパス

    Returns:
        dict[str, dict[str, str]]: entries と images を含む状態dict
    """
    if not state_path.exists():
        return {"entries": {}, "images": {}}
    with open(state_path, encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def _save_state(state_path: Path, state: dict[str, dict[str, str]]) -> None:
    """状態ファイルを保存する

    Args:
        state_path (Path): 状態ファイルのパス
        state (dict[str, dict[str, str]]): 保存する状態dict
    """
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _upload_image(img_path: Path, config: HatenaConfig, logger: logging.Logger) -> str:
    """Hatena Fotolifeに画像をアップロードする

    Args:
        img_path (Path): アップロードする画像ファイルのパス
        config (HatenaConfig): はてなAPI接続設定
        logger (logging.Logger): ロガー

    Returns:
        str: アップロードされた画像のURL

    Raises:
        RuntimeError: アップロードに失敗した場合
    """
    content_type = _CONTENT_TYPES.get(img_path.suffix.lower(), "image/jpeg")
    img_b64 = base64.b64encode(img_path.read_bytes()).decode()

    xml_body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<entry xmlns="{_ATOM_NS}" xmlns:dc="{_DC_NS}">'
        f"<title>{html.escape(img_path.name)}</title>"
        f'<content mode="base64" type="{content_type}">{img_b64}</content>'
        "<dc:subject>KeibaAI</dc:subject>"
        "</entry>"
    )

    wsse = build_wsse_header(config.hatena_id, config.api_key)
    headers = {"Content-Type": "application/xml", "X-WSSE": wsse}

    logger.info("画像アップロード: %s", img_path.name)
    response = requests.post(
        _FOTOLIFE_POST_URL, data=xml_body.encode("utf-8"), headers=headers, timeout=_REQUEST_TIMEOUT
    )
    if response.status_code != 201:
        logger.error("画像アップロード失敗: %s %s", response.status_code, response.text)
        raise RuntimeError(f"画像アップロード失敗: {response.status_code}")

    root = ElementTree.fromstring(response.text)
    imageurl_elem = root.find(f"{{{_HATENA_NS}}}imageurl")
    if imageurl_elem is None or imageurl_elem.text is None:
        raise RuntimeError("Fotolifeレスポンスから画像URLを取得できませんでした")

    return imageurl_elem.text


def _replace_image_paths(
    content: str,
    md_path: Path,
    public_dir: Path,
    state: dict[str, dict[str, str]],
    config: HatenaConfig,
    logger: logging.Logger,
) -> str:
    """Markdown内の相対画像パスをFotolife URLに置換する

    Args:
        content (str): Markdownコンテンツ
        md_path (Path): Markdownファイルの絶対パス
        public_dir (Path): publicディレクトリの絶対パス
        state (dict[str, dict[str, str]]): 状態dict（images キーを更新する）
        config (HatenaConfig): はてなAPI接続設定
        logger (logging.Logger): ロガー

    Returns:
        str: 画像パスをFotolife URLに置換したMarkdownコンテンツ
    """
    image_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    md_dir = md_path.parent
    images_state: dict[str, str] = state.setdefault("images", {})

    def replace_match(match: re.Match[str]) -> str:
        alt = match.group(1)
        img_rel = match.group(2)

        if img_rel.startswith("http"):
            return match.group(0)

        img_abs = (md_dir / img_rel).resolve()

        try:
            img_key = str(img_abs.relative_to(public_dir))
        except ValueError:
            return match.group(0)

        if img_key not in images_state:
            if not img_abs.exists():
                logger.error("画像ファイルが存在しません: %s", img_abs)
                raise FileNotFoundError(f"画像ファイルが存在しません: {img_abs}")
            fotolife_url = _upload_image(img_abs, config, logger)
            images_state[img_key] = fotolife_url
            logger.info("画像URL取得: %s", img_key)
        else:
            logger.info("画像URLキャッシュ使用: %s", img_key)

        return f"![{alt}]({images_state[img_key]})"

    return image_pattern.sub(replace_match, content)


def _build_entry_xml(title: str, content: str, categories: list[str]) -> str:
    """Atom XMLエントリ文字列を生成する

    Args:
        title (str): 記事タイトル
        content (str): Markdownコンテンツ
        categories (list[str]): カテゴリ名のリスト

    Returns:
        str: Atom XML文字列
    """
    category_elems = "".join(
        f'<category xmlns="{_ATOM_NS}" term="{html.escape(cat)}" />' for cat in categories
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<entry xmlns="{_ATOM_NS}" xmlns:app="{_APP_NS}">'
        f"<title>{html.escape(title)}</title>"
        f'<content type="text/x-markdown">{html.escape(content)}</content>'
        f"{category_elems}"
        "<app:control><app:draft>no</app:draft></app:control>"
        "</entry>"
    )


def _post_entry(xml: str, config: HatenaConfig, logger: logging.Logger) -> str:
    """はてなブログに新規エントリを投稿する

    Args:
        xml (str): Atom XMLエントリ文字列
        config (HatenaConfig): はてなAPI接続設定
        logger (logging.Logger): ロガー

    Returns:
        str: 投稿されたエントリのID

    Raises:
        RuntimeError: 投稿に失敗した場合
    """
    url = f"https://blog.hatena.ne.jp/{config.hatena_id}/{config.blog_id}/atom/entry"
    headers = {"Content-Type": "application/xml"}
    auth = (config.hatena_id, config.api_key)

    logger.info("エントリ投稿: %s", url)
    response = requests.post(
        url, data=xml.encode("utf-8"), headers=headers, auth=auth, timeout=_REQUEST_TIMEOUT
    )
    if response.status_code != 201:
        logger.error("エントリ投稿失敗: %s %s", response.status_code, response.text)
        raise RuntimeError(f"エントリ投稿失敗: {response.status_code}")

    return _extract_entry_id(response.text)


def _put_entry(
    entry_id: str, xml: str, config: HatenaConfig, logger: logging.Logger
) -> None:
    """はてなブログのエントリを更新する

    Args:
        entry_id (str): 更新するエントリのID
        xml (str): Atom XMLエントリ文字列
        config (HatenaConfig): はてなAPI接続設定
        logger (logging.Logger): ロガー

    Raises:
        RuntimeError: 更新に失敗した場合
    """
    url = (
        f"https://blog.hatena.ne.jp/{config.hatena_id}/{config.blog_id}/atom/entry/{entry_id}"
    )
    headers = {"Content-Type": "application/xml"}
    auth = (config.hatena_id, config.api_key)

    logger.info("エントリ更新: %s", url)
    response = requests.put(
        url, data=xml.encode("utf-8"), headers=headers, auth=auth, timeout=_REQUEST_TIMEOUT
    )
    if response.status_code != 200:
        logger.error("エントリ更新失敗: %s %s", response.status_code, response.text)
        raise RuntimeError(f"エントリ更新失敗: {response.status_code}")


def _extract_entry_id(response_xml: str) -> str:
    """レスポンスXMLのedit linkからエントリIDを抽出する

    Args:
        response_xml (str): Atom APIレスポンスのXML文字列

    Returns:
        str: エントリID

    Raises:
        RuntimeError: エントリIDを抽出できなかった場合
    """
    root = ElementTree.fromstring(response_xml)
    for link in root.findall(f"{{{_ATOM_NS}}}link"):
        if link.get("rel") == "edit":
            href = link.get("href", "")
            return href.rstrip("/").split("/")[-1]
    raise RuntimeError("レスポンスXMLからエントリIDを抽出できませんでした")


def _publish_md(
    md_path: Path,
    public_dir: Path,
    config_path: Path,
    state_path: Path,
    state: dict[str, dict[str, str]],
    config: HatenaConfig,
    logger: logging.Logger,
) -> None:
    """Markdownファイルをはてなブログに投稿または更新する

    Args:
        md_path (Path): Markdownファイルの絶対パス
        public_dir (Path): publicディレクトリの絶対パス
        config_path (Path): hatena.ymlのパス
        state_path (Path): 状態ファイルのパス
        state (dict[str, dict[str, str]]): 状態dict
        config (HatenaConfig): はてなAPI接続設定
        logger (logging.Logger): ロガー
    """
    content = md_path.read_text(encoding="utf-8")
    title = extract_title(content)
    categories = load_categories(config_path, md_path.stem)

    content_with_urls = _replace_image_paths(content, md_path, public_dir, state, config, logger)
    _save_state(state_path, state)

    xml = _build_entry_xml(title, content_with_urls, categories)
    entry_key = str(md_path.relative_to(public_dir))
    entries_state: dict[str, str] = state.setdefault("entries", {})

    if entry_key in entries_state:
        _put_entry(entries_state[entry_key], xml, config, logger)
        logger.info("エントリ更新完了: %s", title)
    else:
        entry_id = _post_entry(xml, config, logger)
        entries_state[entry_key] = entry_id
        logger.info("エントリ投稿完了: %s (ID: %s)", title, entry_id)

    _save_state(state_path, state)


if __name__ == "__main__":
    main()
