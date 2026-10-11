"""generate_trend の単体テスト。"""

import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from matplotlib.figure import Figure

from g1_predict.modules.gen_trend.trend_section import TrendSections
from scripts.gen_trend import generate_trend


def _make_race_info(
    race_name: str = "天皇賞春",
    year: str = "2026",
) -> pd.DataFrame:
    """レース基本情報を生成する。

    Args:
        race_name (str): レース名。
        year (str): 開催年。

    Returns:
        pd.DataFrame: レース基本情報（1行）。
    """
    return pd.DataFrame({"kyosomei_hondai": [race_name], "kaisai_nen": [year]})


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
    race_info: pd.DataFrame,
    public_dir: str,
    race_code: str = "2026013105010110",
    trend_sections: TrendSections | None = None,
) -> None:
    """generate_trend をパッチ環境で実行する。

    Args:
        race_info (pd.DataFrame): レース基本情報。
        public_dir (str): public ディレクトリパス。
        race_code (str): 16桁 JRA-VAN 形式の race_code。
        trend_sections (TrendSections | None): 集計対象の注記と傾向セクション。
    """
    if trend_sections is None:
        trend_sections = TrendSections(scope_note="", sections={})

    with (
        patch("scripts.gen_trend.load_race_info", return_value=race_info),
        patch("scripts.gen_trend._PUBLIC_DIR", public_dir),
        patch("scripts.gen_trend._build_trend_sections", return_value=trend_sections),
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
    path = os.path.join(public_dir, year, f"{race_code}_{race_name}", "過去の傾向.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


# 正常系
def test_generate_trend_creates_file_in_race_subdir(public_dir: str) -> None:
    """生成ファイルが {race_code}_{race_name}/過去の傾向.md に作成される。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(_make_race_info(), public_dir)
    assert os.path.exists(
        os.path.join(public_dir, "2026", "2026013105010110_天皇賞春", "過去の傾向.md")
    )


def test_generate_trend_title_format(public_dir: str) -> None:
    """傾向ファイルのタイトルが # 【{race_name}{year}】傾向分析 になる。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(_make_race_info(race_name="天皇賞春", year="2026"), public_dir)
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert content.startswith("# 【天皇賞春2026】傾向分析")


def test_generate_trend_contains_dynamic_sections(public_dir: str) -> None:
    """傾向ファイルに config 由来の h2 セクション群が出力される。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(
        _make_race_info(),
        public_dir,
        trend_sections=TrendSections(
            scope_note="※集計対象は、過去10年（2016〜2025年）に京都芝3200mで行われた天皇賞春（10回）。",
            sections={
                "基本項目": "## 基本項目\n\n同じG1レースの過去10年における傾向",
                "前走": "## 前走\n\n出走馬の前走に関する傾向",
            },
        ),
    )
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert "## 基本項目" in content
    assert "## 前走" in content


def test_generate_trend_scope_note_follows_title(public_dir: str) -> None:
    """集計対象の注記がタイトルの直後、最初のカテゴリより前に出力される。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    scope_note = "※集計対象は、過去10年（2016〜2025年）に京都芝3200mで行われた天皇賞春（10回）。"
    _run(
        _make_race_info(),
        public_dir,
        trend_sections=TrendSections(
            scope_note=scope_note,
            sections={"基本項目": "## 基本項目\n\n同じG1レースの過去10年における傾向"},
        ),
    )
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert content == (
        "# 【天皇賞春2026】傾向分析\n\n"
        f"{scope_note}\n\n"
        "## 基本項目\n\n同じG1レースの過去10年における傾向\n"
    )


def test_generate_trend_without_sections_has_title_only(public_dir: str) -> None:
    """カテゴリが無い場合は、注記を出さずタイトルだけを出力する。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(_make_race_info(), public_dir)
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert content == "# 【天皇賞春2026】傾向分析\n"


def test_generate_trend_passes_with_entries_to_section_builder(public_dir: str) -> None:
    """--with-entries の指定を傾向セクションの生成に渡す。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    with (
        patch("scripts.gen_trend.load_race_info", return_value=_make_race_info()),
        patch("scripts.gen_trend._PUBLIC_DIR", public_dir),
        patch(
            "scripts.gen_trend._build_trend_sections",
            return_value=TrendSections(scope_note="", sections={}),
        ) as mock_build,
    ):
        generate_trend("2026013105010110", with_entries=True)
    assert mock_build.call_args[0][2:] == ("2026013105010110", True)


def test_generate_trend_saves_comparison_images(public_dir: str) -> None:
    """比較表の画像を記事ディレクトリに保存する。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    figure = Figure(figsize=(1.0, 1.0))
    figure.add_axes((0.0, 0.0, 1.0, 1.0)).text(0.5, 0.5, "A")
    sections = TrendSections(
        scope_note="※注記",
        sections={"基本項目": "## 基本項目\n\n説明"},
        images={"img/trend_table/基本項目.png": figure},
    )
    _run(_make_race_info(), public_dir, trend_sections=sections)
    image_path = os.path.join(
        public_dir, "2026", "2026013105010110_天皇賞春", "img", "trend_table", "基本項目.png"
    )
    assert os.path.exists(image_path)


def test_generate_trend_with_tokubetsu_loads_race_info(public_dir: str) -> None:
    """特別競走番号を指定した場合は、load_race_info に渡す。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    race_info = pd.DataFrame({"kyosomei_hondai": ["秋華賞"], "kaisai_nen": ["2026"]})
    with (
        patch("scripts.gen_trend.load_race_info", return_value=race_info) as mock_load,
        patch("scripts.gen_trend._PUBLIC_DIR", public_dir),
        patch(
            "scripts.gen_trend._build_trend_sections",
            return_value=TrendSections(scope_note="", sections={}),
        ) as mock_build,
    ):
        generate_trend("2026101808040711", tokubetsu_kyoso_bango="0018")
    mock_load.assert_called_once_with("2026101808040711", "0018")
    assert mock_build.call_args[0][1] is race_info
    assert _read_output(public_dir, "2026", "2026101808040711", "秋華賞") == (
        "# 【秋華賞2026】傾向分析\n"
    )


# 異常系
def test_generate_trend_with_entries_and_tokubetsu_raises(public_dir: str) -> None:
    """--with-entries と特別競走番号を同時に指定した場合は ValueError。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    with pytest.raises(ValueError, match="同時に指定できません"):
        generate_trend("2026101808040711", with_entries=True, tokubetsu_kyoso_bango="0018")
