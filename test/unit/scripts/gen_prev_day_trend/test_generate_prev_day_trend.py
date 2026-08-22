"""generate_prev_day_trend の単体テスト。"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scripts.gen_prev_day_trend import generate_prev_day_trend


def _make_mock_race_getter(
    race_name: str = "天皇賞春",
    year: str = "2026",
) -> MagicMock:
    """RaceGetter のモックを生成する。

    Args:
        race_name (str): レース名。
        year (str): 開催年。

    Returns:
        MagicMock: RaceGetter のモック。
    """
    mock = MagicMock()
    mock.get_race_shosai.return_value = pd.DataFrame(
        {"kyosomei_hondai": [race_name], "kaisai_nen": [year]}
    )
    return mock


@pytest.fixture
def public_dir(tmp_path: Path) -> str:
    """public ディレクトリを用意する。

    Args:
        tmp_path (Path): pytest が提供する一時ディレクトリ。

    Returns:
        str: public ディレクトリパス。
    """
    return str(tmp_path / "public")


def _run(
    mock_race_getter: MagicMock,
    public_dir: str,
    race_code: str = "2026013105010110",
    body: str = "",
) -> None:
    """generate_prev_day_trend をパッチ環境で実行する。

    Args:
        mock_race_getter (MagicMock): RaceGetter のモック。
        public_dir (str): public ディレクトリパス。
        race_code (str): 16桁 JRA-VAN 形式の race_code。
        body (str): 前日の傾向記事本文。
    """
    with (
        patch("scripts.gen_prev_day_trend.RaceGetter", return_value=mock_race_getter),
        patch("scripts.gen_prev_day_trend._PUBLIC_DIR", public_dir),
        patch("scripts.gen_prev_day_trend.build_prev_day_trend_body", return_value=body),
    ):
        generate_prev_day_trend(race_code)


def _read_output(public_dir: str, year: str, race_code: str, race_name: str) -> str:
    """生成ファイルの内容を返す。

    Args:
        public_dir (str): public ディレクトリパス。
        year (str): 開催年。
        race_code (str): 16桁 JRA-VAN 形式の race_code。
        race_name (str): レース名。

    Returns:
        str: 生成ファイルの内容。
    """
    path = os.path.join(public_dir, year, f"{race_code}_{race_name}", "前日の傾向.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


# 正常系
def test_generate_prev_day_trend_title_format(public_dir: str) -> None:
    """生成ファイルのタイトルが # {race_name}{year}前日の傾向 になる。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(
        _make_mock_race_getter(race_name="天皇賞春", year="2026"),
        public_dir,
        body="## 出目\n\n本文\n",
    )
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert content.startswith("# 天皇賞春2026前日の傾向")


def test_generate_prev_day_trend_creates_file_in_race_subdir(public_dir: str) -> None:
    """生成ファイルが {race_code}_{race_name}/前日の傾向.md に作成される。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(_make_mock_race_getter(), public_dir, body="## 出目\n\n本文\n")
    assert os.path.exists(
        os.path.join(public_dir, "2026", "2026013105010110_天皇賞春", "前日の傾向.md")
    )


def test_generate_prev_day_trend_contains_body(public_dir: str) -> None:
    """生成ファイルに本文が埋め込まれる。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(
        _make_mock_race_getter(),
        public_dir,
        body="## 出目\n\n出目本文\n\n## 各レース\n\n### 東京6R 未勝利 1800m 16頭\n",
    )
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert "## 出目" in content
    assert "## 各レース" in content
    assert "### 東京6R 未勝利 1800m 16頭" in content


def test_generate_prev_day_trend_title_only_when_body_empty(public_dir: str) -> None:
    """本文が空文字列の場合、タイトル行のみが出力される。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(_make_mock_race_getter(race_name="天皇賞春", year="2026"), public_dir, body="")
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert content == "# 天皇賞春2026前日の傾向\n"
