"""generate_trend の単体テスト。"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from matplotlib.figure import Figure

from g1_predict.modules.gen_trend.trend_section import EntrySettings, TrendSections
from scripts.gen_trend import _build_trend_sections, generate_trend


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
    trend_sections: TrendSections | None = None,
) -> None:
    """generate_trend をパッチ環境で実行する。

    Args:
        mock_race_getter (MagicMock): RaceGetter のモック。
        public_dir (str): public ディレクトリパス。
        race_code (str): 16桁 JRA-VAN 形式の race_code。
        trend_sections (TrendSections | None): 集計対象の注記と傾向セクション。
    """
    if trend_sections is None:
        trend_sections = TrendSections(scope_note="", sections={})

    with (
        patch("scripts.gen_trend.RaceGetter", return_value=mock_race_getter),
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
    _run(_make_mock_race_getter(), public_dir)
    assert os.path.exists(
        os.path.join(public_dir, "2026", "2026013105010110_天皇賞春", "過去の傾向.md")
    )


def test_generate_trend_title_format(public_dir: str) -> None:
    """傾向ファイルのタイトルが # 【{race_name}{year}】傾向分析 になる。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(_make_mock_race_getter(race_name="天皇賞春", year="2026"), public_dir)
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert content.startswith("# 【天皇賞春2026】傾向分析")


def test_generate_trend_contains_dynamic_sections(public_dir: str) -> None:
    """傾向ファイルに config 由来の h2 セクション群が出力される。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(
        _make_mock_race_getter(),
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
        _make_mock_race_getter(),
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
    _run(_make_mock_race_getter(), public_dir)
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert content == "# 【天皇賞春2026】傾向分析\n"


def test_generate_trend_passes_with_entries_to_section_builder(public_dir: str) -> None:
    """--with-entries の指定を傾向セクションの生成に渡す。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    mock_race_getter = _make_mock_race_getter()
    with (
        patch("scripts.gen_trend.RaceGetter", return_value=mock_race_getter),
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
    _run(_make_mock_race_getter(), public_dir, trend_sections=sections)
    image_path = os.path.join(
        public_dir, "2026", "2026013105010110_天皇賞春", "img", "trend_table", "基本項目.png"
    )
    assert os.path.exists(image_path)


# --- _build_trend_sections ---


@pytest.fixture
def configs_dir(tmp_path: Path) -> Path:
    """trends.yml だけを持つレースの configs ディレクトリ。

    Args:
        tmp_path (Path): pytest が提供する一時ディレクトリ。

    Returns:
        Path: configs ディレクトリ。
    """
    race_dir = tmp_path / "configs" / "天皇賞春"
    race_dir.mkdir(parents=True)
    (race_dir / "trends.yml").write_text("基本項目:\n  - 人気\n", encoding="utf-8")
    return tmp_path / "configs"


def test_build_trend_sections_without_entries_does_not_read_table_yml(configs_dir: Path) -> None:
    """--with-entries が無い場合は、table.yml が無くても生成できる。

    Args:
        configs_dir (Path): configs ディレクトリ。
    """
    expected = TrendSections(scope_note="※", sections={})
    with (
        patch("scripts.gen_trend._CONFIGS_DIR", str(configs_dir)),
        patch("scripts.gen_trend.build_trend_sections", return_value=expected) as mock_build,
    ):
        result = _build_trend_sections("天皇賞春", pd.DataFrame(), "2026013105010110", False)
    assert result is expected
    assert mock_build.call_args[0][4] is None


def test_build_trend_sections_with_entries_reads_table_yml(configs_dir: Path) -> None:
    """--with-entries の場合は、table.yml を読み込んで出走馬の設定を渡す。

    Args:
        configs_dir (Path): configs ディレクトリ。
    """
    (configs_dir / "天皇賞春" / "table.yml").write_text("基本項目:\n  - 人気\n", encoding="utf-8")
    with (
        patch("scripts.gen_trend._CONFIGS_DIR", str(configs_dir)),
        patch(
            "scripts.gen_trend.build_trend_sections",
            return_value=TrendSections(scope_note="", sections={}),
        ) as mock_build,
    ):
        _build_trend_sections("天皇賞春", pd.DataFrame(), "2026013105010110", True)
    assert mock_build.call_args[0][4] == EntrySettings(
        race_code="2026013105010110", table_config={"基本項目": ["人気"]}
    )


def test_build_trend_sections_with_entries_without_table_yml_raises(configs_dir: Path) -> None:
    """--with-entries で table.yml が無い場合は FileNotFoundError になる。

    Args:
        configs_dir (Path): configs ディレクトリ。
    """
    with (
        patch("scripts.gen_trend._CONFIGS_DIR", str(configs_dir)),
        patch("scripts.gen_trend.build_trend_sections"),
        pytest.raises(FileNotFoundError),
    ):
        _build_trend_sections("天皇賞春", pd.DataFrame(), "2026013105010110", True)
