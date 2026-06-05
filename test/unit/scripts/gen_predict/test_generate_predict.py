"""generate_predict の単体テスト。"""
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scripts.gen_predict import _DEFAULT_DATA_DIR, generate_predict


def _make_horse_raw(
    umaban: int,
    bamei: str,
    ketto_toroku_bango: str,
) -> dict[str, Any]:
    return {"umaban": umaban, "bamei": bamei, "ketto_toroku_bango": ketto_toroku_bango}


def _make_mock_race_getter(
    race_name: str = "天皇賞春",
    year: str = "2026",
    grade_code: str = "A",
    horses: list[dict[str, Any]] | None = None,
    past_races: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """RaceGetter のモックを生成する。"""
    if horses is None:
        horses = [
            _make_horse_raw(1, "ホースA", "2020100001"),
            _make_horse_raw(2, "ホースB", "2020100002"),
        ]
    if past_races is None:
        past_races = []

    mock = MagicMock()
    entry_df = pd.DataFrame(horses)
    empty = {"race_code": pd.Series([], dtype=str), "umaban": pd.Series([], dtype=object)}
    past_df = pd.DataFrame(past_races if past_races else empty)

    mock.get_race_shosai.return_value = pd.DataFrame(
        {"kyosomei_hondai": [race_name], "kaisai_nen": [year], "grade_code": [grade_code]}
    )

    def _umagoto(**kwargs: Any) -> pd.DataFrame:
        if "race_code" in kwargs:
            return entry_df.copy()
        return past_df.copy()

    mock.get_umagoto_race_joho.side_effect = _umagoto
    return mock


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[str, str]:
    """public・templates ディレクトリを用意する。"""
    public_dir = str(tmp_path / "public")
    templates_dir = str(tmp_path / "templates")
    os.makedirs(os.path.join(templates_dir, "points"))
    with open(os.path.join(templates_dir, "TEMPLATE_PREDICT.md"), "w", encoding="utf-8") as f:
        f.write(
            "# {RaceName}{Year}予想\n\n"
            "## ポイント\n\n"
            "- \n\n"
            "## 前日の傾向\n\n"
            "## 印\n\n"
            "◎{Umaban}{HorseName}  \n\n"
            "## 見解\n\n"
            "### ◎{Umaban}{HorseName}\n\n"
            "## 買い目\n"
        )
    return public_dir, templates_dir


def _run(
    mock_race_getter: MagicMock,
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
        patch("scripts.gen_predict.RaceGetter", return_value=mock_race_getter),
        patch("scripts.gen_predict._PUBLIC_DIR", public_dir),
        patch("scripts.gen_predict._TEMPLATES_DIR", templates_dir),
        patch("scripts.gen_predict.read_marks", return_value=marks),
        patch("scripts.gen_predict.read_kek_comments", side_effect=_fake_read_kek_comments),
        patch("scripts.gen_predict.build_prev_day_trend_section", return_value="## 前日の傾向\n"),
        patch.dict("os.environ", {"TFJV_DATA_DIR": "/tmp/fake_tfjv"}),
    ):
        generate_predict(race_code)


def _read_output(public_dir: str, year: str, race_code: str, race_name: str) -> str:
    """生成ファイルの内容を返す。"""
    path = os.path.join(public_dir, year, f"{race_code}_{race_name}", "予想.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


# 正常系
def test_generate_predict_title_format(dirs: tuple[str, str]) -> None:
    """生成ファイルのタイトルが # {race_name}{year}予想 になる。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_race_getter(race_name="天皇賞春", year="2026"), public_dir, templates_dir)
    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
    assert content.startswith("# 天皇賞春2026")


def test_generate_predict_marks_section_shows_only_marked_horses(
    dirs: tuple[str, str],
) -> None:
    """印セクションに印のある馬のみ出力される。"""
    public_dir, templates_dir = dirs
    horses = [
        _make_horse_raw(1, "アイウエオ", "2020100001"),
        _make_horse_raw(2, "カキクケコ", "2020100002"),
        _make_horse_raw(3, "サシスセソ", "2020100003"),
    ]
    marks = {2: "◎"}
    _run(_make_mock_race_getter(horses=horses), public_dir, templates_dir, marks=marks)
    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
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
        _make_horse_raw(1, "ホースA", "2020100001"),
        _make_horse_raw(2, "ホースB", "2020100002"),
        _make_horse_raw(3, "ホースC", "2020100003"),
    ]
    marks = {1: "▲", 2: "○", 3: "◎"}
    _run(_make_mock_race_getter(horses=horses), public_dir, templates_dir, marks=marks)
    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
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
        _make_horse_raw(1, "ホースA", "2020100001"),
        _make_horse_raw(5, "ホースB", "2020100002"),
    ]
    marks = {5: "○", 1: "○"}
    _run(_make_mock_race_getter(horses=horses), public_dir, templates_dir, marks=marks)
    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
    marks_section = content[content.index("## 印") : content.index("## 見解")]
    assert marks_section.index("1ホースA") < marks_section.index("5ホースB")


def test_generate_predict_insight_section_shows_marked_horse_header(
    dirs: tuple[str, str],
) -> None:
    """見解セクションに印のある馬の見出しが出力される。"""
    public_dir, templates_dir = dirs
    horses = [_make_horse_raw(3, "ホースA", "2020100001")]
    marks = {3: "◎"}
    _run(_make_mock_race_getter(horses=horses), public_dir, templates_dir, marks=marks)
    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
    assert "### ◎3ホースA" in content


def test_generate_predict_insight_section_skips_unmarked_horse(
    dirs: tuple[str, str],
) -> None:
    """見解セクションに印のない馬は出力されない。"""
    public_dir, templates_dir = dirs
    horses = [
        _make_horse_raw(1, "ホースA", "2020100001"),
        _make_horse_raw(2, "ホースB", "2020100002"),
    ]
    marks = {1: "◎"}
    _run(_make_mock_race_getter(horses=horses), public_dir, templates_dir, marks=marks)
    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
    insight_section = content[content.index("## 見解") : content.index("## 買い目")]
    assert "ホースA" in insight_section
    assert "ホースB" not in insight_section


def test_generate_predict_insight_section_past_comment_zensou(
    dirs: tuple[str, str],
) -> None:
    """前走（1走前）のコメントが「前走」表記で出力される。"""
    public_dir, templates_dir = dirs
    horses = [_make_horse_raw(5, "ホースA", "2020100001")]
    marks = {5: "◎"}
    mock_rg = _make_mock_race_getter(horses=horses)

    past_df = pd.DataFrame({"race_code": ["2025050205021011"], "umaban": [5]})

    def _umagoto(**kwargs: object) -> pd.DataFrame:
        if "race_code" in kwargs:
            return pd.DataFrame(horses)
        return past_df

    mock_rg.get_umagoto_race_joho.side_effect = _umagoto
    mock_rg.get_race_shosai.side_effect = [
        pd.DataFrame({"kyosomei_hondai": ["天皇賞春"], "kaisai_nen": ["2026"], "grade_code": ["A"]}),
        pd.DataFrame({"kyosomei_hondai": ["天皇賞春"], "kaisai_nen": ["2025"], "grade_code": ["A"]}),
    ]
    _run(
        mock_rg,
        public_dir,
        templates_dir,
        marks=marks,
        kek_comments_per_call=[{5: "[天皇賞春] 好内容。"}],
    )
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert "前走G1天皇賞春好内容。" in content


def test_generate_predict_insight_section_past_comment_zenzensou(
    dirs: tuple[str, str],
) -> None:
    """前々走（2走前）のコメントが「前々走」表記で出力される。"""
    public_dir, templates_dir = dirs
    horses = [_make_horse_raw(5, "ホースA", "2020100001")]
    marks = {5: "◎"}
    mock_rg = _make_mock_race_getter(horses=horses)

    past_df = pd.DataFrame({
        "race_code": ["2025060205021011", "2025060205011011"],
        "umaban": [5, 5],
    })

    def _umagoto(**kwargs: object) -> pd.DataFrame:
        if "race_code" in kwargs:
            return pd.DataFrame(horses)
        return past_df

    mock_rg.get_umagoto_race_joho.side_effect = _umagoto
    mock_rg.get_race_shosai.side_effect = [
        pd.DataFrame({"kyosomei_hondai": ["天皇賞春"], "kaisai_nen": ["2026"], "grade_code": ["A"]}),
        pd.DataFrame({"kyosomei_hondai": ["大阪杯"], "kaisai_nen": ["2025"], "grade_code": ["A"]}),
    ]
    _run(
        mock_rg,
        public_dir,
        templates_dir,
        marks=marks,
        kek_comments_per_call=[{}, {5: "[大阪杯] 手応え良好。"}],
    )
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert "前々走G1大阪杯手応え良好。" in content


def test_generate_predict_insight_section_ordinal_3plus(
    dirs: tuple[str, str],
) -> None:
    """3走前以降は「n走前」表記で出力される。"""
    public_dir, templates_dir = dirs
    horses = [_make_horse_raw(1, "ホースA", "2020100001")]
    marks = {1: "◎"}
    mock_rg = _make_mock_race_getter(horses=horses)

    past_df = pd.DataFrame({
        "race_code": [
            "2025060205031011",
            "2025060205021011",
            "2025060205011011",
        ],
        "umaban": [1, 1, 1],
    })

    def _umagoto(**kwargs: object) -> pd.DataFrame:
        if "race_code" in kwargs:
            return pd.DataFrame(horses)
        return past_df

    mock_rg.get_umagoto_race_joho.side_effect = _umagoto
    mock_rg.get_race_shosai.side_effect = [
        pd.DataFrame({"kyosomei_hondai": ["天皇賞春"], "kaisai_nen": ["2026"], "grade_code": ["A"]}),
        pd.DataFrame({"kyosomei_hondai": ["宝塚記念"], "kaisai_nen": ["2025"], "grade_code": ["A"]}),
    ]
    _run(
        mock_rg,
        public_dir,
        templates_dir,
        marks=marks,
        kek_comments_per_call=[{}, {}, {1: "[宝塚記念] 馬場不向き。"}],
    )
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert "3走前G1宝塚記念馬場不向き。" in content


def test_generate_predict_insight_race_without_comment_counted_in_ordinal(
    dirs: tuple[str, str],
) -> None:
    """コメントなしのレースも走数カウントに含まれる。"""
    public_dir, templates_dir = dirs
    horses = [_make_horse_raw(3, "ホースA", "2020100001")]
    marks = {3: "◎"}
    mock_rg = _make_mock_race_getter(horses=horses)

    past_df = pd.DataFrame({
        "race_code": ["2025060205021011", "2025060205011011"],
        "umaban": [3, 3],
    })

    def _umagoto(**kwargs: object) -> pd.DataFrame:
        if "race_code" in kwargs:
            return pd.DataFrame(horses)
        return past_df

    mock_rg.get_umagoto_race_joho.side_effect = _umagoto
    mock_rg.get_race_shosai.side_effect = [
        pd.DataFrame({"kyosomei_hondai": ["天皇賞春"], "kaisai_nen": ["2026"], "grade_code": ["A"]}),
        pd.DataFrame({"kyosomei_hondai": ["大阪杯"], "kaisai_nen": ["2025"], "grade_code": ["A"]}),
    ]
    _run(
        mock_rg,
        public_dir,
        templates_dir,
        marks=marks,
        kek_comments_per_call=[{}, {3: "[大阪杯] 好走。"}],
    )
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    insight_section = content[content.index("## 見解") :]
    assert "前々走G1大阪杯好走。" in insight_section
    assert "前走G1" not in insight_section


def test_generate_predict_insight_section_grade_l(
    dirs: tuple[str, str],
) -> None:
    """グレードコード L が「L」として出力される。"""
    public_dir, templates_dir = dirs
    horses = [_make_horse_raw(1, "ホースA", "2020100001")]
    marks = {1: "◎"}
    mock_rg = _make_mock_race_getter(horses=horses)

    past_df = pd.DataFrame({"race_code": ["2025050205021011"], "umaban": [1]})

    def _umagoto(**kwargs: object) -> pd.DataFrame:
        if "race_code" in kwargs:
            return pd.DataFrame(horses)
        return past_df

    mock_rg.get_umagoto_race_joho.side_effect = _umagoto
    mock_rg.get_race_shosai.side_effect = [
        pd.DataFrame({"kyosomei_hondai": ["天皇賞春"], "kaisai_nen": ["2026"], "grade_code": ["A"]}),
        pd.DataFrame({"kyosomei_hondai": ["テストR"], "kaisai_nen": ["2025"], "grade_code": ["L"]}),
    ]
    _run(
        mock_rg,
        public_dir,
        templates_dir,
        marks=marks,
        kek_comments_per_call=[{1: "[テストR] 内容良好。"}],
    )
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert "前走LテストR内容良好。" in content


def test_generate_predict_insight_section_no_grade_for_general_race(
    dirs: tuple[str, str],
) -> None:
    """一般競走（グレードコード _）はグレード表示なしで出力される。"""
    public_dir, templates_dir = dirs
    horses = [_make_horse_raw(1, "ホースA", "2020100001")]
    marks = {1: "◎"}
    mock_rg = _make_mock_race_getter(horses=horses)

    past_df = pd.DataFrame({"race_code": ["2025050205021011"], "umaban": [1]})

    def _umagoto(**kwargs: object) -> pd.DataFrame:
        if "race_code" in kwargs:
            return pd.DataFrame(horses)
        return past_df

    mock_rg.get_umagoto_race_joho.side_effect = _umagoto
    mock_rg.get_race_shosai.side_effect = [
        pd.DataFrame({"kyosomei_hondai": ["天皇賞春"], "kaisai_nen": ["2026"], "grade_code": ["A"]}),
        pd.DataFrame({"kyosomei_hondai": ["一般戦"], "kaisai_nen": ["2025"], "grade_code": ["_"]}),
    ]
    _run(
        mock_rg,
        public_dir,
        templates_dir,
        marks=marks,
        kek_comments_per_call=[{1: "[一般戦] 凡走。"}],
    )
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert "前走一般戦凡走。" in content


def test_generate_predict_prev_day_trend_section_content_is_embedded(
    dirs: tuple[str, str],
) -> None:
    """build_prev_day_trend_section の戻り値が前日の傾向セクションに埋め込まれる。"""
    public_dir, templates_dir = dirs
    with (
        patch("scripts.gen_predict.DataInterface", return_value=_make_mock_di()),
        patch("scripts.gen_predict._PUBLIC_DIR", public_dir),
        patch("scripts.gen_predict._TEMPLATES_DIR", templates_dir),
        patch("scripts.gen_predict.read_marks", return_value={}),
        patch("scripts.gen_predict.read_kek_comments", return_value={}),
        patch(
            "scripts.gen_predict.build_prev_day_trend_section",
            return_value="## 前日の傾向\n\nダート先行有利\n",
        ),
        patch.dict("os.environ", {"TFJV_DATA_DIR": "/tmp/fake_tfjv"}),
    ):
        generate_predict("2026013105010110")
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert "ダート先行有利" in content


def test_generate_predict_has_insight_section(dirs: tuple[str, str]) -> None:
    """見解セクションが出力される。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_race_getter(), public_dir, templates_dir)
    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
    assert "## 見解" in content


def test_generate_predict_has_kaimoku_section(dirs: tuple[str, str]) -> None:
    """買い目セクションが出力される。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_race_getter(), public_dir, templates_dir)
    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
    assert "## 買い目" in content


def test_generate_predict_creates_file_in_race_subdir(
    dirs: tuple[str, str],
) -> None:
    """生成ファイルが {race_code}_{race_name}/予想.md に作成される。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_race_getter(), public_dir, templates_dir)
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

    _run(_make_mock_race_getter(), public_dir, templates_dir)

    assert os.path.exists(os.path.join(public_dir, "2026", "06_天皇賞春.md"))


def test_generate_predict_uses_points_template_when_exists(
    dirs: tuple[str, str],
) -> None:
    """ポイントテンプレートが存在する場合、その内容が記事に含まれる。"""
    public_dir, templates_dir = dirs
    with open(os.path.join(templates_dir, "points", "天皇賞春.md"), "w", encoding="utf-8") as f:
        f.write("## ポイント\n\n- 先行有利\n")

    _run(_make_mock_race_getter(), public_dir, templates_dir)

    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert "先行有利" in content


def test_generate_predict_uses_default_points_when_template_missing(
    dirs: tuple[str, str],
) -> None:
    """ポイントテンプレートがない場合、デフォルトのポイントセクションが使われる。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_race_getter(), public_dir, templates_dir)
    content = _read_output(public_dir, "2026", "01_天皇賞春.md")
    assert "## ポイント" in content
    assert "先行有利" not in content


def test_generate_predict_insight_deduplicates_postponed_race(
    dirs: tuple[str, str],
) -> None:
    """延期によりMMDDのみ異なる同一レースのコメントは1回だけ出力される。"""
    public_dir, templates_dir = dirs
    horses = [_make_horse_raw(1, "ホースA", "2020100001")]
    marks = {1: "◎"}
    mock_rg = _make_mock_race_getter(horses=horses)

    past_df = pd.DataFrame({
        "race_code": [
            "2025050205021011",
            "2025060205021011",
            "2025070205021011",
        ],
        "umaban": [1, 1, 1],
    })

    def _umagoto(**kwargs: object) -> pd.DataFrame:
        if "race_code" in kwargs:
            return pd.DataFrame(horses)
        return past_df

    mock_rg.get_umagoto_race_joho.side_effect = _umagoto
    mock_rg.get_race_shosai.side_effect = [
        pd.DataFrame({"kyosomei_hondai": ["天皇賞春"], "kaisai_nen": ["2026"], "grade_code": ["A"]}),
        pd.DataFrame({"kyosomei_hondai": ["きさらぎ賞"], "kaisai_nen": ["2025"], "grade_code": ["C"]}),
    ]
    _run(
        mock_rg,
        public_dir,
        templates_dir,
        marks=marks,
        kek_comments_per_call=[{1: "[きさらぎ賞] 好走。"}],
    )
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert content.count("きさらぎ賞好走。") == 1


def test_generate_predict_uses_default_data_dir_when_env_not_set(
    dirs: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """TFJV_DATA_DIR が設定されていない場合、デフォルトのデータディレクトリが使われる。"""
    public_dir, templates_dir = dirs
    mock_rg = _make_mock_race_getter()
    monkeypatch.delenv("TFJV_DATA_DIR", raising=False)
    with (
        patch("scripts.gen_predict.RaceGetter", return_value=mock_rg),
        patch("scripts.gen_predict._PUBLIC_DIR", public_dir),
        patch("scripts.gen_predict._TEMPLATES_DIR", templates_dir),
        patch("scripts.gen_predict.read_marks", return_value={}) as mock_read_marks,
        patch("scripts.gen_predict.read_kek_comments", return_value={}),
        patch("scripts.gen_predict.build_prev_day_trend_section", return_value="## 前日の傾向\n"),
        patch("scripts.gen_predict.um_dat_path", return_value="/fake/path") as mock_um_dat_path,
    ):
        generate_predict("2026013105010110")
        mock_um_dat_path.assert_called_once_with("2026013105010110", _DEFAULT_DATA_DIR)
        mock_read_marks.assert_called_once_with("/fake/path", 1)
