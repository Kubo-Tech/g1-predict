"""generate_trend の単体テスト。"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scripts.gen_trend import generate_trend


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
    trend_sections_map: dict[str, str] | None = None,
) -> None:
    """generate_trend をパッチ環境で実行する。

    Args:
        mock_race_getter (MagicMock): RaceGetter のモック。
        public_dir (str): public ディレクトリパス。
        race_code (str): 16桁 JRA-VAN 形式の race_code。
        trend_sections_map (dict[str, str] | None): 傾向セクションmap。
    """
    if trend_sections_map is None:
        trend_sections_map = {}

    with (
        patch("scripts.gen_trend.RaceGetter", return_value=mock_race_getter),
        patch("scripts.gen_trend._PUBLIC_DIR", public_dir),
        patch("scripts.gen_trend._build_trend_sections", return_value=trend_sections_map),
    ):
        generate_trend(race_code)


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
    path = os.path.join(public_dir, year, f"{race_code}_{race_name}", "傾向.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


# 正常系
def test_generate_trend_creates_file_in_race_subdir(public_dir: str) -> None:
    """生成ファイルが {race_code}_{race_name}/傾向.md に作成される。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(_make_mock_race_getter(), public_dir)
    assert os.path.exists(
        os.path.join(public_dir, "2026", "2026013105010110_天皇賞春", "傾向.md")
    )


def test_generate_trend_title_format(public_dir: str) -> None:
    """傾向ファイルのタイトルが # {race_name}{year}傾向分析 になる。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(_make_mock_race_getter(race_name="天皇賞春", year="2026"), public_dir)
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert content.startswith("# 天皇賞春2026傾向分析")


def test_generate_trend_contains_dynamic_sections(public_dir: str) -> None:
    """傾向ファイルに config 由来の h2 セクション群が出力される。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(
        _make_mock_race_getter(),
        public_dir,
        trend_sections_map={
            "出走馬傾向": "## 出走馬傾向\n\n過去10年出走馬傾向",
            "騎手傾向": "## 騎手傾向\n\n過去10年騎手傾向",
        },
    )
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert "## 出走馬傾向" in content
    assert "## 騎手傾向" in content
