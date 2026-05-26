"""main の単体テスト。"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests as requests_mod

from scripts.qiita_publish import main


def _make_article(year_dir: Path, filename: str, content: str) -> Path:
    year_dir.mkdir(parents=True, exist_ok=True)
    path = year_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def _make_ids_file(year_dir: Path, ids: dict[str, str]) -> None:
    ids_path = year_dir / ".qiita_ids.json"
    ids_path.write_text(json.dumps(ids, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_ids_file(year_dir: Path) -> dict[str, str]:
    ids_path = year_dir / ".qiita_ids.json"
    return json.loads(ids_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _mock_post_resp(item_id: str = "abc123") -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"id": item_id}
    return resp


def _run(
    monkeypatch: pytest.MonkeyPatch,
    files: list[str],
    post_response: MagicMock | None = None,
    token: str = "fake_token",
) -> tuple[MagicMock, MagicMock]:
    """main() をパッチ環境で実行し (mock_post, mock_patch) を返す。"""
    monkeypatch.setattr(sys, "argv", ["qiita_publish.py"] + files)
    monkeypatch.setenv("QIITA_ACCESS_TOKEN", token)
    if post_response is None:
        post_response = _mock_post_resp()
    patch_response = MagicMock()
    with (
        patch("scripts.qiita_publish.requests.post", return_value=post_response) as mock_post,
        patch("scripts.qiita_publish.requests.patch", return_value=patch_response) as mock_patch,
    ):
        main()
    return mock_post, mock_patch


# 正常系
def test_main_posts_new_article(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """新規ファイルは POST される。"""
    year_dir = tmp_path / "2026"
    path = _make_article(year_dir, "01_天皇賞春.md", "# content\n")
    mock_post, mock_patch = _run(monkeypatch, [str(path)])
    mock_post.assert_called_once()
    mock_patch.assert_not_called()


def test_main_patches_existing_article(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """既存ファイルは PATCH される。"""
    year_dir = tmp_path / "2026"
    path = _make_article(year_dir, "01_天皇賞春.md", "# content\n")
    _make_ids_file(year_dir, {"01_天皇賞春.md": "existing_id"})
    mock_post, mock_patch = _run(monkeypatch, [str(path)])
    mock_post.assert_not_called()
    mock_patch.assert_called_once()


def test_main_patches_with_correct_item_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PATCH リクエスト URL に .qiita_ids.json の item_id が含まれる。"""
    year_dir = tmp_path / "2026"
    path = _make_article(year_dir, "01_天皇賞春.md", "# content\n")
    _make_ids_file(year_dir, {"01_天皇賞春.md": "qiita_item_xyz"})
    _, mock_patch = _run(monkeypatch, [str(path)])
    assert "qiita_item_xyz" in mock_patch.call_args.args[0]


def test_main_saves_item_id_after_post(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST 後に item_id が .qiita_ids.json に保存される。"""
    year_dir = tmp_path / "2026"
    path = _make_article(year_dir, "01_天皇賞春.md", "# content\n")
    _run(monkeypatch, [str(path)], post_response=_mock_post_resp("new_id_xyz"))
    assert _load_ids_file(year_dir)["01_天皇賞春.md"] == "new_id_xyz"


def test_main_does_not_modify_ids_on_patch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PATCH 時は .qiita_ids.json が変更されない。"""
    year_dir = tmp_path / "2026"
    path = _make_article(year_dir, "01_天皇賞春.md", "# content\n")
    _make_ids_file(year_dir, {"01_天皇賞春.md": "original_id"})
    _run(monkeypatch, [str(path)])
    assert _load_ids_file(year_dir) == {"01_天皇賞春.md": "original_id"}


def test_main_processes_multiple_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """複数ファイルをすべて POST する。"""
    year_dir = tmp_path / "2026"
    path1 = _make_article(year_dir, "01_天皇賞春.md", "content1\n")
    path2 = _make_article(year_dir, "02_オークス.md", "content2\n")
    mock_post, _ = _run(monkeypatch, [str(path1), str(path2)])
    assert mock_post.call_count == 2


@pytest.mark.parametrize(
    "filename, expected_title",
    [
        ("01_天皇賞春.md", "天皇賞春2026"),
        ("10_オークス.md", "オークス2026"),
        ("99_日本ダービー.md", "日本ダービー2026"),
    ],
)
def test_main_derives_title_from_filename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    expected_title: str,
) -> None:
    """フロントマターなし → {レース名}{年} のタイトルが使われる。"""
    year_dir = tmp_path / "2026"
    path = _make_article(year_dir, filename, "# content\n")
    mock_post, _ = _run(monkeypatch, [str(path)])
    assert mock_post.call_args.kwargs["json"]["title"] == expected_title


def test_main_uses_title_from_frontmatter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """フロントマターの title フィールドがそのまま使われる。"""
    year_dir = tmp_path / "2026"
    content = '---\ntitle: "カスタムタイトル2026"\n---\n\n# 本文\n'
    path = _make_article(year_dir, "01_天皇賞春.md", content)
    mock_post, _ = _run(monkeypatch, [str(path)])
    assert mock_post.call_args.kwargs["json"]["title"] == "カスタムタイトル2026"


def test_main_sends_body_without_frontmatter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """フロントマターを除いた本文が body として送られる。"""
    year_dir = tmp_path / "2026"
    content = '---\ntitle: "天皇賞春2026"\n---\n\n# 本文内容\n'
    path = _make_article(year_dir, "01_天皇賞春.md", content)
    mock_post, _ = _run(monkeypatch, [str(path)])
    body = mock_post.call_args.kwargs["json"]["body"]
    assert "---" not in body
    assert "# 本文内容" in body


def test_main_sends_fixed_tags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """API payload に 競馬/G1/予想 のタグが含まれる。"""
    year_dir = tmp_path / "2026"
    path = _make_article(year_dir, "01_天皇賞春.md", "# content\n")
    mock_post, _ = _run(monkeypatch, [str(path)])
    tag_names = [t["name"] for t in mock_post.call_args.kwargs["json"]["tags"]]
    assert tag_names == ["競馬", "G1", "予想"]


def test_main_sends_private_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """API payload の private が False。"""
    year_dir = tmp_path / "2026"
    path = _make_article(year_dir, "01_天皇賞春.md", "# content\n")
    mock_post, _ = _run(monkeypatch, [str(path)])
    assert mock_post.call_args.kwargs["json"]["private"] is False


def test_main_handles_malformed_frontmatter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """閉じマーカーのないフロントマターはコンテンツ全体を body にしてタイトルをファイル名から導出する。"""
    year_dir = tmp_path / "2026"
    content = "---\nno closing marker\n# 本文\n"
    path = _make_article(year_dir, "01_天皇賞春.md", content)
    mock_post, _ = _run(monkeypatch, [str(path)])
    payload = mock_post.call_args.kwargs["json"]
    assert payload["title"] == "天皇賞春2026"
    assert payload["body"] == content


# 準正常系
def test_main_raises_when_token_not_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """QIITA_ACCESS_TOKEN 未設定で EnvironmentError が発生する。"""
    year_dir = tmp_path / "2026"
    path = _make_article(year_dir, "01_天皇賞春.md", "# content\n")
    monkeypatch.setattr(sys, "argv", ["qiita_publish.py", str(path)])
    monkeypatch.delenv("QIITA_ACCESS_TOKEN", raising=False)
    with pytest.raises(EnvironmentError):
        main()


def test_main_raises_when_no_files_given(monkeypatch: pytest.MonkeyPatch) -> None:
    """ファイル引数なしで ValueError が発生する。"""
    monkeypatch.setattr(sys, "argv", ["qiita_publish.py"])
    monkeypatch.setenv("QIITA_ACCESS_TOKEN", "fake_token")
    with pytest.raises(ValueError):
        main()


def test_main_raises_on_api_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """API エラー時に HTTPError が伝播する。"""
    year_dir = tmp_path / "2026"
    path = _make_article(year_dir, "01_天皇賞春.md", "# content\n")
    monkeypatch.setattr(sys, "argv", ["qiita_publish.py", str(path)])
    monkeypatch.setenv("QIITA_ACCESS_TOKEN", "fake_token")
    error_resp = MagicMock()
    error_resp.raise_for_status.side_effect = requests_mod.HTTPError("API error")
    with patch("scripts.qiita_publish.requests.post", return_value=error_resp):
        with pytest.raises(requests_mod.HTTPError):
            main()
