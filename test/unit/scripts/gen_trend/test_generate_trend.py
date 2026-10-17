"""generate_trend の単体テスト。"""

import datetime
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest
from matplotlib.figure import Figure
from mykeibadb.exceptions import MykeibaDBError
from scraping import ChokyoBataijuUnavailableError, NetworkError, PageNotFoundError

from g1_predict.modules.gen_trend.trend_section import EntrySettings, TrendSections
from scripts.gen_trend import _build_trend_sections, generate_trend


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
    return pd.DataFrame(
        {"kyosomei_hondai": [race_name], "kaisai_nen": [year], "tokubetsu_kyoso_bango": ["0006"]}
    )


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
    assert mock_build.call_args[0][3:] == ("2026013105010110", True)


def test_generate_trend_reads_config_dir_with_tokubetsu_kyoso_bango(public_dir: str) -> None:
    """設定ファイルは configs/{特別競走番号}_{レース名}/ から読む。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    with (
        patch("scripts.gen_trend.load_race_info", return_value=_make_race_info()),
        patch("scripts.gen_trend._PUBLIC_DIR", public_dir),
        patch("scripts.gen_trend._CONFIGS_DIR", "/configs"),
        patch(
            "scripts.gen_trend._build_trend_sections",
            return_value=TrendSections(scope_note="", sections={}),
        ) as mock_build,
    ):
        generate_trend("2026013105010110")
    assert mock_build.call_args[0][1] == os.path.join("/configs", "0006_天皇賞春")


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
    race_info = pd.DataFrame(
        {"kyosomei_hondai": ["秋華賞"], "kaisai_nen": ["2026"], "tokubetsu_kyoso_bango": ["0018"]}
    )
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
    assert mock_build.call_args[0][2] is race_info
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


# --- _build_trend_sections ---


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """trends.yml だけを持つレースの設定ファイルのディレクトリ。

    Args:
        tmp_path (Path): pytest が提供する一時ディレクトリ。

    Returns:
        Path: レースの設定ファイルのディレクトリ。
    """
    race_dir = tmp_path / "configs" / "0006_天皇賞春"
    race_dir.mkdir(parents=True)
    (race_dir / "trends.yml").write_text("基本項目:\n  - 人気\n", encoding="utf-8")
    return race_dir


def test_build_trend_sections_without_entries_does_not_require_table_yml(config_dir: Path) -> None:
    """--with-entries が無い場合は、table.yml が無くても生成でき、table.yml を渡さない。

    Args:
        config_dir (Path): レースの設定ファイルのディレクトリ。
    """
    expected = TrendSections(scope_note="※", sections={})
    with (
        patch("scripts.gen_trend.build_trend_sections", return_value=expected) as mock_build,
    ):
        result = _build_trend_sections(
            "天皇賞春", str(config_dir), pd.DataFrame(), "2026013105010110", False
        )
    assert result is expected
    assert mock_build.call_args[0][4] is None
    assert mock_build.call_args[0][5] is None


def test_build_trend_sections_without_entries_reads_table_yml_if_exists(
    config_dir: Path,
) -> None:
    """--with-entries が無い場合でも、table.yml があれば読み込んで渡す。

    Args:
        config_dir (Path): レースの設定ファイルのディレクトリ。
    """
    (config_dir / "table.yml").write_text("基本項目:\n  - 人気\n", encoding="utf-8")
    with (
        patch("scripts.gen_trend.check_race_entries") as mock_check,
        patch(
            "scripts.gen_trend.build_trend_sections",
            return_value=TrendSections(scope_note="", sections={}),
        ) as mock_build,
    ):
        _build_trend_sections(
            "天皇賞春", str(config_dir), pd.DataFrame(), "2026013105010110", False
        )
    mock_check.assert_not_called()
    assert mock_build.call_args[0][4] is None
    assert mock_build.call_args[0][5] == {"基本項目": ["人気"]}


def test_build_trend_sections_with_entries_reads_table_yml(config_dir: Path) -> None:
    """--with-entries の場合は、table.yml を読み込み、出走馬の設定とともに渡す。

    調教後馬体重がまだ発表されていない場合は、調教後馬体重を None にする。

    Args:
        config_dir (Path): レースの設定ファイルのディレクトリ。
    """
    (config_dir / "table.yml").write_text("基本項目:\n  - 人気\n", encoding="utf-8")
    (config_dir / "race.yml").write_text("jra_g1_page: tenno_haru\n", encoding="utf-8")
    with (
        patch("scripts.gen_trend.check_race_entries") as mock_check,
        patch("scripts.gen_trend.JraChokyoBataijuScraper") as mock_scraper,
        patch(
            "scripts.gen_trend.build_trend_sections",
            return_value=TrendSections(scope_note="", sections={}),
        ) as mock_build,
    ):
        mock_scraper.return_value.get_chokyo_bataiju.side_effect = ChokyoBataijuUnavailableError(
            "未発表"
        )
        _build_trend_sections("天皇賞春", str(config_dir), pd.DataFrame(), "2026013105010110", True)
    mock_check.assert_called_once_with("2026013105010110")
    assert mock_build.call_args[0][4] == EntrySettings(race_code="2026013105010110")
    assert mock_build.call_args[0][5] == {"基本項目": ["人気"]}


def test_build_trend_sections_with_entries_without_table_yml_raises(config_dir: Path) -> None:
    """--with-entries で table.yml が無い場合は FileNotFoundError になる。

    Args:
        config_dir (Path): レースの設定ファイルのディレクトリ。
    """
    with (
        patch("scripts.gen_trend.build_trend_sections"),
        pytest.raises(FileNotFoundError),
    ):
        _build_trend_sections("天皇賞春", str(config_dir), pd.DataFrame(), "2026013105010110", True)


def test_build_trend_sections_with_entries_checks_before_trends_yml(tmp_path: Path) -> None:
    """--with-entries では、trends.yml が無いレースでも table.yml が無ければ例外になる。

    Args:
        tmp_path (Path): pytest が提供する一時ディレクトリ。
    """
    race_dir = tmp_path / "0006_天皇賞春"
    race_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        _build_trend_sections("天皇賞春", str(race_dir), pd.DataFrame(), "2026013105010110", True)


def test_build_trend_sections_with_entries_without_entries_raises(tmp_path: Path) -> None:
    """--with-entries では、trends.yml が無いレースでも出走馬が DB に無ければ例外になる。

    Args:
        tmp_path (Path): pytest が提供する一時ディレクトリ。
    """
    race_dir = tmp_path / "0006_天皇賞春"
    race_dir.mkdir()
    (race_dir / "table.yml").write_text("基本項目:\n  - 人気\n", encoding="utf-8")
    with (
        patch(
            "scripts.gen_trend.check_race_entries",
            side_effect=MykeibaDBError("出走馬が見つかりません"),
        ),
        pytest.raises(MykeibaDBError),
    ):
        _build_trend_sections("天皇賞春", str(race_dir), pd.DataFrame(), "2026013105010110", True)


def test_build_trend_sections_with_chokyo_bataiju_passes_weights(config_dir: Path) -> None:
    """--with-entries の場合は、race.yml の G1 特設ページから取得した調教後馬体重を渡す。

    計量日がレース日（2026-05-03）の7日前から前日までなら今回の開催の値として使う。

    Args:
        config_dir (Path): レースの設定ファイルのディレクトリ。
    """
    (config_dir / "table.yml").write_text("基本項目:\n  - 人気\n", encoding="utf-8")
    (config_dir / "race.yml").write_text("jra_g1_page: tenno_haru\n", encoding="utf-8")
    weights = pd.DataFrame(
        {
            "馬名": ["A", "B"],
            "馬体重": [480, 502],
            "計量日": [datetime.date(2026, 5, 2), datetime.date(2026, 4, 26)],
        }
    )
    with (
        patch("scripts.gen_trend.check_race_entries"),
        patch("scripts.gen_trend.JraChokyoBataijuScraper") as mock_scraper,
        patch(
            "scripts.gen_trend.build_trend_sections",
            return_value=TrendSections(scope_note="", sections={}),
        ) as mock_build,
    ):
        mock_scraper.return_value.get_chokyo_bataiju.return_value = weights
        _build_trend_sections("天皇賞春", str(config_dir), pd.DataFrame(), "2026050308030811", True)
    mock_scraper.assert_called_once_with("tenno_haru")
    assert mock_build.call_args[0][4] == EntrySettings(
        race_code="2026050308030811", chokyo_bataiju={"A": 480, "B": 502}
    )


def test_build_trend_sections_with_chokyo_bataiju_without_race_yml_raises(
    config_dir: Path,
) -> None:
    """--with-entries で race.yml が無い場合は FileNotFoundError になる。

    Args:
        config_dir (Path): レースの設定ファイルのディレクトリ。
    """
    (config_dir / "table.yml").write_text("基本項目:\n  - 人気\n", encoding="utf-8")
    with (
        patch("scripts.gen_trend.check_race_entries"),
        patch("scripts.gen_trend.build_trend_sections"),
        pytest.raises(FileNotFoundError),
    ):
        _build_trend_sections("天皇賞春", str(config_dir), pd.DataFrame(), "2026013105010110", True)


@pytest.mark.parametrize(
    "weigh_date",
    [datetime.date(2026, 4, 25), datetime.date(2026, 5, 3), datetime.date(2025, 4, 30)],
)
def test_build_trend_sections_with_chokyo_bataiju_of_other_meeting_is_none(
    config_dir: Path, weigh_date: datetime.date
) -> None:
    """計量日がレース日（2026-05-03）の前の1週間に入らない調教後馬体重は、未発表として扱う。

    Args:
        config_dir (Path): レースの設定ファイルのディレクトリ。
        weigh_date (datetime.date): 計量日。
    """
    weights = pd.DataFrame({"馬名": ["A"], "馬体重": [480], "計量日": [weigh_date]})
    assert _build_with_scraper(config_dir, return_value=weights).chokyo_bataiju is None


@pytest.mark.parametrize(
    "error", [ChokyoBataijuUnavailableError("未発表"), PageNotFoundError("公開前")]
)
def test_build_trend_sections_with_chokyo_bataiju_unavailable_is_none(
    config_dir: Path, error: Exception
) -> None:
    """調教後馬体重の発表前と、特設ページの公開前は、調教後馬体重を None にする。

    Args:
        config_dir (Path): レースの設定ファイルのディレクトリ。
        error (Exception): スクレイパーが送出する例外。
    """
    assert _build_with_scraper(config_dir, side_effect=error).chokyo_bataiju is None


def test_build_trend_sections_with_chokyo_bataiju_network_error_raises(config_dir: Path) -> None:
    """通信の失敗で調教後馬体重を取得できない場合は、例外をそのまま送出する。

    Args:
        config_dir (Path): レースの設定ファイルのディレクトリ。
    """
    with pytest.raises(NetworkError):
        _build_with_scraper(config_dir, side_effect=NetworkError("接続エラー"))


def _build_with_scraper(config_dir: Path, **scraper_result: Any) -> EntrySettings:
    """調教後馬体重の取得結果を差し替えて、出走馬の確定後の設定で _build_trend_sections を実行する。

    Args:
        config_dir (Path): レースの設定ファイルのディレクトリ。
        **scraper_result (Any): get_chokyo_bataiju のモックに設定する return_value か side_effect。

    Returns:
        EntrySettings: build_trend_sections に渡した出走馬の設定。
    """
    (config_dir / "table.yml").write_text("基本項目:\n  - 人気\n", encoding="utf-8")
    (config_dir / "race.yml").write_text("jra_g1_page: tenno_haru\n", encoding="utf-8")
    with (
        patch("scripts.gen_trend.check_race_entries"),
        patch("scripts.gen_trend.JraChokyoBataijuScraper") as mock_scraper,
        patch(
            "scripts.gen_trend.build_trend_sections",
            return_value=TrendSections(scope_note="", sections={}),
        ) as mock_build,
    ):
        mock_scraper.return_value.get_chokyo_bataiju.configure_mock(**scraper_result)
        _build_trend_sections("天皇賞春", str(config_dir), pd.DataFrame(), "2026050308030811", True)
    entries: EntrySettings = mock_build.call_args[0][4]
    return entries
