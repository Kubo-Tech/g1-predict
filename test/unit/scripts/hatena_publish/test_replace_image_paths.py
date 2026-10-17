"""replace_image_paths の単体テスト"""

import hashlib
import logging
from pathlib import Path

import pytest

from scripts import hatena_publish
from scripts.hatena_publish import HatenaConfig, replace_image_paths

_CONFIG = HatenaConfig(hatena_id="id", blog_id="blog", api_key="key")
_LOGGER = logging.getLogger(__name__)
_IMG_KEY = "2026/race/img/a.png"


@pytest.fixture
def md_path(tmp_path: Path) -> Path:
    """画像を1枚置いた記事のパス"""
    race_dir = tmp_path / "2026" / "race"
    (race_dir / "img").mkdir(parents=True)
    (race_dir / "img" / "a.png").write_bytes(b"new")
    return race_dir / "記事.md"


@pytest.fixture
def uploads(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """_upload_image を差し替え、アップロードした画像のパスを記録する"""
    uploaded: list[Path] = []

    def fake_upload(img_path: Path, config: HatenaConfig, logger: logging.Logger) -> str:
        uploaded.append(img_path)
        return "https://example.com/new.png"

    monkeypatch.setattr(hatena_publish, "_upload_image", fake_upload)
    return uploaded


def _replace(md_path: Path, state: dict[str, dict[str, str]]) -> str:
    return replace_image_paths(
        "![図](img/a.png)", md_path, md_path.parents[2], state, _CONFIG, _LOGGER
    )


# 正常系
def test_replace_image_paths_uses_recorded_url_when_unchanged(
    md_path: Path, uploads: list[Path]
) -> None:
    """記録したハッシュと中身が同じ画像は、アップロードせずに記録したURLを使う"""
    state = {
        "images": {_IMG_KEY: "https://example.com/old.png"},
        "image_hashes": {_IMG_KEY: hashlib.sha256(b"new").hexdigest()},
    }
    assert _replace(md_path, state) == "![図](https://example.com/old.png)"
    assert uploads == []


@pytest.mark.parametrize(
    "image_hashes",
    [{_IMG_KEY: hashlib.sha256(b"old").hexdigest()}, {}],
    ids=["changed", "no_hash"],
)
def test_replace_image_paths_reuploads_changed_image(
    md_path: Path, uploads: list[Path], image_hashes: dict[str, str]
) -> None:
    """中身が変わった画像とハッシュの記録が無い画像は、アップロードし直して記録を更新する"""
    state = {"images": {_IMG_KEY: "https://example.com/old.png"}, "image_hashes": image_hashes}
    assert _replace(md_path, state) == "![図](https://example.com/new.png)"
    assert len(uploads) == 1
    assert state["images"][_IMG_KEY] == "https://example.com/new.png"
    assert state["image_hashes"][_IMG_KEY] == hashlib.sha256(b"new").hexdigest()


def test_replace_image_paths_uploads_new_image(md_path: Path, uploads: list[Path]) -> None:
    """記録が無い画像はアップロードし、URLとハッシュを記録する"""
    state: dict[str, dict[str, str]] = {}
    assert _replace(md_path, state) == "![図](https://example.com/new.png)"
    assert state == {
        "images": {_IMG_KEY: "https://example.com/new.png"},
        "image_hashes": {_IMG_KEY: hashlib.sha256(b"new").hexdigest()},
    }


# 異常系
def test_replace_image_paths_missing_file(md_path: Path, uploads: list[Path]) -> None:
    """画像ファイルが無い場合は FileNotFoundError"""
    (md_path.parent / "img" / "a.png").unlink()
    with pytest.raises(FileNotFoundError):
        _replace(md_path, {})
