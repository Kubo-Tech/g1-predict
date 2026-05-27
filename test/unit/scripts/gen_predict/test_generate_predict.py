"""generate_predict の単体テスト。"""
import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scripts.gen_predict import _DEFAULT_DATA_DIR, generate_predict


def _make_mock_di(
    race_name: str = "天皇賞春",
    year: str = "2026",
    horses: list[dict[str, object]] | None = None,
) -> MagicMock:
    """DataInterface のモックを生成する。"""
    if horses is None:
        horses = [
            {"馬番": 1, "馬名": "ホースA", "血統登録番号": "2020100001"},
            {"馬番": 2, "馬名": "ホースB", "血統登録番号": "2020100002"},
        ]
    mock = MagicMock()
    mock.get_race_basic_info.return_value = pd.DataFrame(
        {"競走名本題": [race_name], "開催年": [year], "グレードコード": ["A"]}
    )
    mock.get_entry.return_value = pd.DataFrame(horses)
    mock.get_past_performances.return_value = pd.DataFrame(
        {"レースコード": pd.Series([], dtype=str), "馬番": pd.Series([], dtype=object)}
    )
    return mock


@pytest.fixture
def dirs(tmp_path: pytest.TempPathFactory) -> tuple[str, str]:
    """public・templates ディレクトリを用意する。"""
    public_dir = str(tmp_path / "public")  # type: ignore[operator]
    templates_dir = str(tmp_path / "templates")  # type: ignore[operator]
    os.makedirs(os.path.join(templates_dir, "points"))
    with open(os.path.join(templates_dir, "TEMPLATE.md"), "w", encoding="utf-8") as f:
        f.write(
            "# {RaceName}{Year}\n\n"
            "## ポイント\n\n"
            "- \n\n"
            "## 印\n\n"
            "◎{Umaban}{HorseName}  \n\n"
            "## 見解\n\n"
            "### ◎{Umaban}{HorseName}\n\n"
            "## 買い目\n"
        )
    return public_dir, templates_dir


def _run(
    mock_di: MagicMock,
    public_dir: str,
    templates_dir: str,
    race_code: str = "2026013105010110",
    marks: dict[int, str] | None = None,
    kek_comments_per_call: list[dict[int, str]] | None = None,
) -> None:
    """generate_predict をパッチ環境で実行する。"""
    if marks is None:
        marks = {}
    comment_iter = iter(kek_comments_per_call or [])

    def _fake_read_kek_comments(*_args: object, **_kwargs: object) -> dict[int, str]:
        return next(comment_iter, {})

    with (
        patch("scripts.gen_predict.DataInterface", return_value=mock_di),
        patch("scripts.gen_predict._PUBLIC_DIR", public_dir),
        patch("scripts.gen_predict._TEMPLATES_DIR", templates_dir),
        patch("scripts.gen_predict.read_marks", return_value=marks),
        patch("scripts.gen_predict.read_kek_comments", side_effect=_fake_read_kek_comments),
        patch.dict("os.environ", {"TFJV_DATA_DIR": "/tmp/fake_tfjv"}),
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
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    assert content.startswith("# 天皇賞春2026")


def test_generate_predict_marks_section_shows_only_marked_horses(
    dirs: tuple[str, str],
) -> None:
    """印セクションに印のある馬のみ出力される。"""
    public_dir, templates_dir = dirs
    horses = [
        {"馬番": 1, "馬名": "アイウエオ", "血統登録番号": "2020100001"},
        {"馬番": 2, "馬名": "カキクケコ", "血統登録番号": "2020100002"},
        {"馬番": 3, "馬名": "サシスセソ", "血統登録番号": "2020100003"},
    ]
    marks = {2: "◎"}
    _run(_make_mock_di(horses=horses), public_dir, templates_dir, marks=marks)
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    marks_section = content[content.index("## 印") : content.index("## 見解")]
    assert "カキクケコ" in marks_section
    assert "アイウエオ" not in marks_section
    assert "サシスセソ" not in marks_section


def test_generate_predict_marks_section_ordered_by_mark_priority(
    dirs: tuple[str, str],
) -> None:
    """印セクションは印記号優先度順（◎○▲）に出力される。"""
    public_dir, templates_dir = dirs
    horses = [
        {"馬番": 1, "馬名": "ホースA", "血統登録番号": "2020100001"},
        {"馬番": 2, "馬名": "ホースB", "血統登録番号": "2020100002"},
        {"馬番": 3, "馬名": "ホースC", "血統登録番号": "2020100003"},
    ]
    marks = {1: "▲", 2: "○", 3: "◎"}
    _run(_make_mock_di(horses=horses), public_dir, templates_dir, marks=marks)
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    marks_section = content[content.index("## 印") : content.index("## 見解")]
    assert (
        marks_section.index("◎")
        < marks_section.index("○")
        < marks_section.index("▲")
    )


def test_generate_predict_marks_section_same_mark_ordered_by_umaban(
    dirs: tuple[str, str],
) -> None:
    """同じ印の馬は馬番昇順で出力される。"""
    public_dir, templates_dir = dirs
    horses = [
        {"馬番": 1, "馬名": "ホースA", "血統登録番号": "2020100001"},
        {"馬番": 5, "馬名": "ホースB", "血統登録番号": "2020100002"},
    ]
    marks = {5: "○", 1: "○"}
    _run(_make_mock_di(horses=horses), public_dir, templates_dir, marks=marks)
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    marks_section = content[content.index("## 印") : content.index("## 見解")]
    assert marks_section.index("1ホースA") < marks_section.index("5ホースB")


def test_generate_predict_insight_section_shows_marked_horse_header(
    dirs: tuple[str, str],
) -> None:
    """見解セクションに印のある馬の見出しが出力される。"""
    public_dir, templates_dir = dirs
    horses = [{"馬番": 3, "馬名": "ホースA", "血統登録番号": "2020100001"}]
    marks = {3: "◎"}
    _run(_make_mock_di(horses=horses), public_dir, templates_dir, marks=marks)
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    assert "### ◎3ホースA" in content


def test_generate_predict_insight_section_skips_unmarked_horse(
    dirs: tuple[str, str],
) -> None:
    """見解セクションに印のない馬は出力されない。"""
    public_dir, templates_dir = dirs
    horses = [
        {"馬番": 1, "馬名": "ホースA", "血統登録番号": "2020100001"},
        {"馬番": 2, "馬名": "ホースB", "血統登録番号": "2020100002"},
    ]
    marks = {1: "◎"}
    _run(_make_mock_di(horses=horses), public_dir, templates_dir, marks=marks)
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    insight_section = content[content.index("## 見解") : content.index("## 買い目")]
    assert "ホースA" in insight_section
    assert "ホースB" not in insight_section


def test_generate_predict_insight_section_past_comment_zensou(
    dirs: tuple[str, str],
) -> None:
    """前走（1走前）のコメントが「前走」表記で出力される。"""
    public_dir, templates_dir = dirs
    horses = [{"馬番": 5, "馬名": "ホースA", "血統登録番号": "2020100001"}]
    marks = {5: "◎"}
    mock_di = _make_mock_di(horses=horses)
    mock_di.get_past_performances.return_value = pd.DataFrame(
        {"レースコード": ["2025050205021011"], "馬番": [5]}
    )
    mock_di.get_race_basic_info.side_effect = [
        pd.DataFrame({"競走名本題": ["天皇賞春"], "開催年": ["2026"], "グレードコード": ["A"]}),
        pd.DataFrame({"競走名本題": ["天皇賞春"], "開催年": ["2025"], "グレードコード": ["A"]}),
    ]
    _run(
        mock_di,
        public_dir,
        templates_dir,
        marks=marks,
        kek_comments_per_call=[{5: "[天皇賞春] 好内容。"}],
    )
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    assert "前走G1天皇賞春好内容。" in content


def test_generate_predict_insight_section_past_comment_zenzensou(
    dirs: tuple[str, str],
) -> None:
    """前々走（2走前）のコメントが「前々走」表記で出力される。"""
    public_dir, templates_dir = dirs
    horses = [{"馬番": 5, "馬名": "ホースA", "血統登録番号": "2020100001"}]
    marks = {5: "◎"}
    mock_di = _make_mock_di(horses=horses)
    mock_di.get_past_performances.return_value = pd.DataFrame(
        {
            "レースコード": ["2025060205021011", "2025060205011011"],
            "馬番": [5, 5],
        }
    )
    mock_di.get_race_basic_info.side_effect = [
        pd.DataFrame({"競走名本題": ["天皇賞春"], "開催年": ["2026"], "グレードコード": ["A"]}),
        pd.DataFrame({"競走名本題": ["大阪杯"], "開催年": ["2025"], "グレードコード": ["A"]}),
    ]
    _run(
        mock_di,
        public_dir,
        templates_dir,
        marks=marks,
        kek_comments_per_call=[{}, {5: "[大阪杯] 手応え良好。"}],
    )
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    assert "前々走G1大阪杯手応え良好。" in content


def test_generate_predict_insight_section_ordinal_3plus(
    dirs: tuple[str, str],
) -> None:
    """3走前以降は「n走前」表記で出力される。"""
    public_dir, templates_dir = dirs
    horses = [{"馬番": 1, "馬名": "ホースA", "血統登録番号": "2020100001"}]
    marks = {1: "◎"}
    mock_di = _make_mock_di(horses=horses)
    mock_di.get_past_performances.return_value = pd.DataFrame(
        {
            "レースコード": [
                "2025060205031011",
                "2025060205021011",
                "2025060205011011",
            ],
            "馬番": [1, 1, 1],
        }
    )
    mock_di.get_race_basic_info.side_effect = [
        pd.DataFrame({"競走名本題": ["天皇賞春"], "開催年": ["2026"], "グレードコード": ["A"]}),
        pd.DataFrame({"競走名本題": ["宝塚記念"], "開催年": ["2025"], "グレードコード": ["A"]}),
    ]
    _run(
        mock_di,
        public_dir,
        templates_dir,
        marks=marks,
        kek_comments_per_call=[{}, {}, {1: "[宝塚記念] 馬場不向き。"}],
    )
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    assert "3走前G1宝塚記念馬場不向き。" in content


def test_generate_predict_insight_race_without_comment_counted_in_ordinal(
    dirs: tuple[str, str],
) -> None:
    """コメントなしのレースも走数カウントに含まれる。"""
    public_dir, templates_dir = dirs
    horses = [{"馬番": 3, "馬名": "ホースA", "血統登録番号": "2020100001"}]
    marks = {3: "◎"}
    mock_di = _make_mock_di(horses=horses)
    mock_di.get_past_performances.return_value = pd.DataFrame(
        {
            "レースコード": ["2025060205021011", "2025060205011011"],
            "馬番": [3, 3],
        }
    )
    mock_di.get_race_basic_info.side_effect = [
        pd.DataFrame({"競走名本題": ["天皇賞春"], "開催年": ["2026"], "グレードコード": ["A"]}),
        pd.DataFrame({"競走名本題": ["大阪杯"], "開催年": ["2025"], "グレードコード": ["A"]}),
    ]
    _run(
        mock_di,
        public_dir,
        templates_dir,
        marks=marks,
        kek_comments_per_call=[{}, {3: "[大阪杯] 好走。"}],
    )
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    insight_section = content[content.index("## 見解") :]
    assert "前々走G1大阪杯好走。" in insight_section
    assert "前走G1" not in insight_section


def test_generate_predict_insight_section_grade_l(
    dirs: tuple[str, str],
) -> None:
    """グレードコード L が「L」として出力される。"""
    public_dir, templates_dir = dirs
    horses = [{"馬番": 1, "馬名": "ホースA", "血統登録番号": "2020100001"}]
    marks = {1: "◎"}
    mock_di = _make_mock_di(horses=horses)
    mock_di.get_past_performances.return_value = pd.DataFrame(
        {"レースコード": ["2025050205021011"], "馬番": [1]}
    )
    mock_di.get_race_basic_info.side_effect = [
        pd.DataFrame({"競走名本題": ["天皇賞春"], "開催年": ["2026"], "グレードコード": ["A"]}),
        pd.DataFrame({"競走名本題": ["テストR"], "開催年": ["2025"], "グレードコード": ["L"]}),
    ]
    _run(
        mock_di,
        public_dir,
        templates_dir,
        marks=marks,
        kek_comments_per_call=[{1: "[テストR] 内容良好。"}],
    )
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    assert "前走LテストR内容良好。" in content


def test_generate_predict_insight_section_no_grade_for_general_race(
    dirs: tuple[str, str],
) -> None:
    """一般競走（グレードコード _）はグレード表示なしで出力される。"""
    public_dir, templates_dir = dirs
    horses = [{"馬番": 1, "馬名": "ホースA", "血統登録番号": "2020100001"}]
    marks = {1: "◎"}
    mock_di = _make_mock_di(horses=horses)
    mock_di.get_past_performances.return_value = pd.DataFrame(
        {"レースコード": ["2025050205021011"], "馬番": [1]}
    )
    mock_di.get_race_basic_info.side_effect = [
        pd.DataFrame({"競走名本題": ["天皇賞春"], "開催年": ["2026"], "グレードコード": ["A"]}),
        pd.DataFrame({"競走名本題": ["一般戦"], "開催年": ["2025"], "グレードコード": ["_"]}),
    ]
    _run(
        mock_di,
        public_dir,
        templates_dir,
        marks=marks,
        kek_comments_per_call=[{1: "[一般戦] 凡走。"}],
    )
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    assert "前走一般戦凡走。" in content


def test_generate_predict_has_insight_section(dirs: tuple[str, str]) -> None:
    """見解セクションが出力される。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_di(), public_dir, templates_dir)
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    assert "## 見解" in content


def test_generate_predict_has_kaimoku_section(dirs: tuple[str, str]) -> None:
    """買い目セクションが出力される。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_di(), public_dir, templates_dir)
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    assert "## 買い目" in content


def test_generate_predict_creates_file_with_race_code_prefix(
    dirs: tuple[str, str],
) -> None:
    """生成ファイル名が {race_code}_{race_name}.md 形式になる。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_di(), public_dir, templates_dir)
    assert os.path.exists(os.path.join(public_dir, "2026", "2026013105010110_天皇賞春.md"))


def test_generate_predict_uses_points_template_when_exists(
    dirs: tuple[str, str],
) -> None:
    """ポイントテンプレートが存在する場合、その内容が記事に含まれる。"""
    public_dir, templates_dir = dirs
    with open(os.path.join(templates_dir, "points", "天皇賞春.md"), "w", encoding="utf-8") as f:
        f.write("## ポイント\n\n- 先行有利\n")

    _run(_make_mock_di(), public_dir, templates_dir)

    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    assert "先行有利" in content


def test_generate_predict_uses_default_points_when_template_missing(
    dirs: tuple[str, str],
) -> None:
    """ポイントテンプレートがない場合、デフォルトのポイントセクションが使われる。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_di(), public_dir, templates_dir)
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    assert "## ポイント" in content
    assert "先行有利" not in content


def test_generate_predict_insight_deduplicates_postponed_race(
    dirs: tuple[str, str],
) -> None:
    """延期によりMMDDのみ異なる同一レースのコメントは1回だけ出力される。"""
    public_dir, templates_dir = dirs
    horses = [{"馬番": 1, "馬名": "ホースA", "血統登録番号": "2020100001"}]
    marks = {1: "◎"}
    mock_di = _make_mock_di(horses=horses)
    mock_di.get_past_performances.return_value = pd.DataFrame(
        {
            "レースコード": [
                "2025050205021011",  # 元日程
                "2025060205021011",  # 延期1回目（MMDDのみ異なる同一レース）
                "2025070205021011",  # 延期2回目
            ],
            "馬番": [1, 1, 1],
        }
    )
    mock_di.get_race_basic_info.side_effect = [
        pd.DataFrame({"競走名本題": ["天皇賞春"], "開催年": ["2026"], "グレードコード": ["A"]}),
        pd.DataFrame({"競走名本題": ["きさらぎ賞"], "開催年": ["2025"], "グレードコード": ["C"]}),
    ]
    _run(
        mock_di,
        public_dir,
        templates_dir,
        marks=marks,
        kek_comments_per_call=[{1: "[きさらぎ賞] 好走。"}],
    )
    content = _read_output(public_dir, "2026", "2026013105010110_天皇賞春.md")
    assert content.count("きさらぎ賞好走。") == 1


# 正常系
def test_generate_predict_uses_default_data_dir_when_env_not_set(
    dirs: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """TFJV_DATA_DIR が設定されていない場合、デフォルトのデータディレクトリが使われる。"""
    public_dir, templates_dir = dirs
    mock_di = _make_mock_di()
    monkeypatch.delenv("TFJV_DATA_DIR", raising=False)
    with (
        patch("scripts.gen_predict.DataInterface", return_value=mock_di),
        patch("scripts.gen_predict._PUBLIC_DIR", public_dir),
        patch("scripts.gen_predict._TEMPLATES_DIR", templates_dir),
        patch("scripts.gen_predict.read_marks", return_value={}) as mock_read_marks,
        patch("scripts.gen_predict.read_kek_comments", return_value={}),
        patch("scripts.gen_predict.um_dat_path", return_value="/fake/path") as mock_um_dat_path,
    ):
        generate_predict("2026013105010110")
        mock_um_dat_path.assert_called_once_with("2026013105010110", _DEFAULT_DATA_DIR)
        mock_read_marks.assert_called_once_with("/fake/path", 10)
