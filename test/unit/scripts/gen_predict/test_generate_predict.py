"""generate_predict の単体テスト。"""
import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scripts.gen_predict import generate_predict


def _make_mock_di(
    race_name: str = "天皇賞春",
    year: str = "2026",
    horses: list[dict] | None = None,
) -> MagicMock:
    """DataInterface のモックを生成する。"""
    if horses is None:
        horses = [
            {"馬番": 1, "馬名": "ホースA"},
            {"馬番": 2, "馬名": "ホースB"},
        ]
    mock = MagicMock()
    mock.get_race_basic_info.return_value = pd.DataFrame(
        {"競走名本題": [race_name], "開催年": [year]}
    )
    mock.get_entry.return_value = pd.DataFrame(horses)
    return mock


@pytest.fixture
def dirs(tmp_path: pytest.TempPathFactory) -> tuple[str, str]:
    """public・templates ディレクトリを用意する。"""
    public_dir = str(tmp_path / "public")  # type: ignore[operator]
    templates_dir = str(tmp_path / "templates")  # type: ignore[operator]
    os.makedirs(os.path.join(templates_dir, "points"))
    return public_dir, templates_dir


def _run(
    mock_di: MagicMock,
    public_dir: str,
    templates_dir: str,
    race_code: str = "2026013105010110",
) -> None:
    """generate_predict をパッチ環境で実行する。"""
    with (
        patch("scripts.gen_predict.DataInterface", return_value=mock_di),
        patch("scripts.gen_predict._PUBLIC_DIR", public_dir),
        patch("scripts.gen_predict._TEMPLATES_DIR", templates_dir),
    ):
        generate_predict(race_code)


def _read_output(public_dir: str, year: str, filename: str) -> str:
    """生成ファイルの内容を返す。"""
    with open(os.path.join(public_dir, year, filename), encoding="utf-8") as f:
        return f.read()


# 正常系
def test_generate_predict_title_format(dirs: tuple[str, str]) -> None:
    """生成ファイルのタイトルが # {race_name}{year} になる。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_di(race_name="天皇賞春", year="2026"), public_dir, templates_dir)
    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
    assert content.startswith("# 天皇賞春2026")


def test_generate_predict_marks_section_contains_all_horses(
    dirs: tuple[str, str],
) -> None:
    """印セクションに全馬が出力される。"""
    public_dir, templates_dir = dirs
    horses = [
        {"馬番": 1, "馬名": "アイウエオ"},
        {"馬番": 2, "馬名": "カキクケコ"},
        {"馬番": 3, "馬名": "サシスセソ"},
    ]
    _run(_make_mock_di(horses=horses), public_dir, templates_dir)
    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
    marks_section = content[content.index("## 印") : content.index("## 見解")]
    assert "1アイウエオ" in marks_section
    assert "2カキクケコ" in marks_section
    assert "3サシスセソ" in marks_section


def test_generate_predict_marks_section_horse_order(dirs: tuple[str, str]) -> None:
    """印セクションの馬は DataFrame の順序で出力される。"""
    public_dir, templates_dir = dirs
    horses = [
        {"馬番": 1, "馬名": "ホースA"},
        {"馬番": 2, "馬名": "ホースB"},
        {"馬番": 3, "馬名": "ホースC"},
    ]
    _run(_make_mock_di(horses=horses), public_dir, templates_dir)
    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
    marks_section = content[content.index("## 印") : content.index("## 見解")]
    assert (
        marks_section.index("1ホースA")
        < marks_section.index("2ホースB")
        < marks_section.index("3ホースC")
    )


def test_generate_predict_has_insight_section(dirs: tuple[str, str]) -> None:
    """見解セクションが出力される。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_di(), public_dir, templates_dir)
    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
    assert "## 見解" in content


def test_generate_predict_has_kaimoku_section(dirs: tuple[str, str]) -> None:
    """買い目セクションが出力される。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_di(), public_dir, templates_dir)
    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
    assert "## 買い目" in content


def test_generate_predict_serial_starts_at_01_when_no_files_exist(
    dirs: tuple[str, str],
) -> None:
    """year_dir が空の場合、連番は 01 になる。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_di(), public_dir, templates_dir)
    assert os.path.exists(os.path.join(public_dir, "2026", "01_天皇賞春.md"))


def test_generate_predict_serial_increments_from_existing_files(
    dirs: tuple[str, str],
) -> None:
    """既存ファイルの最大番号 +1 が連番になる。"""
    public_dir, templates_dir = dirs
    year_dir = os.path.join(public_dir, "2026")
    os.makedirs(year_dir)
    with open(os.path.join(year_dir, "05_大阪杯.md"), "w"):
        pass
    with open(os.path.join(year_dir, "03_桜花賞.md"), "w"):
        pass

    _run(_make_mock_di(), public_dir, templates_dir)

    assert os.path.exists(os.path.join(public_dir, "2026", "06_天皇賞春.md"))


def test_generate_predict_uses_points_template_when_exists(
    dirs: tuple[str, str],
) -> None:
    """ポイントテンプレートが存在する場合、その内容が記事に含まれる。"""
    public_dir, templates_dir = dirs
    with open(os.path.join(templates_dir, "points", "天皇賞春.md"), "w", encoding="utf-8") as f:
        f.write("## ポイント\n\n- 先行有利\n")

    _run(_make_mock_di(), public_dir, templates_dir)

    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
    assert "先行有利" in content


def test_generate_predict_uses_default_points_when_template_missing(
    dirs: tuple[str, str],
) -> None:
    """ポイントテンプレートがない場合、デフォルトのポイントセクションが使われる。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_di(), public_dir, templates_dir)
    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
    assert "## ポイント" in content
    assert "先行有利" not in content
