"""Qiita への記事投稿・更新スクリプト。"""

import json
import os
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import requests

_QIITA_API_BASE: str = "https://qiita.com/api/v2"
_TAGS: list[dict[str, str]] = [{"name": "競馬"}, {"name": "G1"}, {"name": "予想"}]
_REQUEST_TIMEOUT: int = 30
_MAX_RETRIES: int = 3
_RETRY_WAIT: int = 60


def main() -> None:
    """エントリポイント。

    Raises:
        EnvironmentError: QIITA_ACCESS_TOKEN が未設定の場合。
        ValueError: ファイル引数が指定されていない場合。
    """
    token = os.environ.get("QIITA_ACCESS_TOKEN")
    if not token:
        raise EnvironmentError("QIITA_ACCESS_TOKEN is not set")

    if len(sys.argv) < 2:
        raise ValueError("Usage: qiita_publish.py <file1.md> [file2.md ...]")

    headers: dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    for filepath in sys.argv[1:]:
        _publish(filepath, headers)


def _publish(filepath: str, headers: dict[str, str]) -> None:
    path = Path(filepath)
    ids_path = path.parent / ".qiita_ids.json"
    ids = _load_ids(ids_path)

    raw = path.read_text(encoding="utf-8")
    title, body = _extract_content(raw, path)

    payload: dict[str, Any] = {
        "title": title,
        "tags": _TAGS,
        "body": body,
        "private": False,
    }

    key = path.name
    if key in ids:
        _patch(ids[key], payload, headers)
    else:
        item_id = _post(payload, headers)
        ids[key] = item_id
        _save_ids(ids_path, ids)


def _extract_content(raw: str, path: Path) -> tuple[str, str]:
    if raw.startswith("---\n"):
        try:
            end = raw.index("---\n", 4)
        except ValueError:
            return _title_from_path(path), raw
        fm = raw[4:end]
        body = raw[end + 4:].lstrip("\n")
        m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', fm, re.MULTILINE)
        title = m.group(1) if m else _title_from_path(path)
        return title, body
    return _title_from_path(path), raw


def _title_from_path(path: Path) -> str:
    year = path.parent.name
    m = re.match(r"\d+_(.*)", path.stem)
    race_name = m.group(1) if m else path.stem
    return f"{race_name}{year}"


def _load_ids(ids_path: Path) -> dict[str, str]:
    if ids_path.exists():
        return cast(dict[str, str], json.loads(ids_path.read_text(encoding="utf-8")))
    return {}


def _save_ids(ids_path: Path, ids: dict[str, str]) -> None:
    ids_path.write_text(
        json.dumps(ids, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _request_with_retry(fn: Callable[[], Any]) -> Any:
    resp = fn()
    for i in range(1, _MAX_RETRIES):
        if resp.status_code != 429:
            break
        wait = int(resp.headers.get("Retry-After", _RETRY_WAIT))
        print(f"Rate limited. Waiting {wait}s (retry {i}/{_MAX_RETRIES - 1})...")
        time.sleep(wait)
        resp = fn()
    resp.raise_for_status()
    return resp


def _post(payload: dict[str, Any], headers: dict[str, str]) -> str:
    resp = _request_with_retry(
        lambda: requests.post(
            f"{_QIITA_API_BASE}/items", json=payload, headers=headers, timeout=_REQUEST_TIMEOUT
        )
    )
    item_id: str = resp.json()["id"]
    print(f"Posted: {payload['title']} (id={item_id})")
    return item_id


def _patch(item_id: str, payload: dict[str, Any], headers: dict[str, str]) -> None:
    _request_with_retry(
        lambda: requests.patch(
            f"{_QIITA_API_BASE}/items/{item_id}",
            json=payload,
            headers=headers,
            timeout=_REQUEST_TIMEOUT,
        )
    )
    print(f"Updated: {payload['title']} (id={item_id})")


if __name__ == "__main__":
    main()
