"""gen_result の単体テスト。"""
import json
import os
from collections.abc import Generator
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests
from matplotlib.figure import Figure

from scripts.gen_result import _format_comment_body, generate_result

_RACE_CODE = "2026052405021011"
_RACE_NAME = "優駿牝馬"
_YEAR = "2026"


def _make_result_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _make_mock_di(result_rows: list[dict]) -> MagicMock:
    mock = MagicMock()
    mock.get_race_basic_info.return_value = pd.DataFrame(
        {"競走名本題": [_RACE_NAME], "開催年": [_YEAR]}
    )
    mock.get_result.return_value = _make_result_df(result_rows)
    return mock


def _normal_row(
    chakusa: int,
    umaban: int,
    horse_name: str,
    ninki: float = 1,
    corner4: float = 1,
    halon: float = 35.0,
    kyakushitsu: str | None = "1",
) -> dict:
    return {
        "確定着順": chakusa,
        "馬番": umaban,
        "馬名": horse_name,
        "異常区分コード": "0",
        "単勝人気順": ninki,
        "4コーナー順位": corner4,
        "後3ハロン": halon,
        "脚質判定コード": kyakushitsu,
    }


def _abnormal_row(umaban: int, horse_name: str, ijo_code: str) -> dict:
    return {
        "確定着順": float("nan"),
        "馬番": umaban,
        "馬名": horse_name,
        "異常区分コード": ijo_code,
        "単勝人気順": float("nan"),
        "4コーナー順位": float("nan"),
        "後3ハロン": float("nan"),
        "脚質判定コード": None,
    }


_FEED_PATCH_TARGET = "g1_predict.modules.utils.hatena_links.requests.get"
_FEED_XML = (
    '<feed xmlns="http://www.w3.org/2005/Atom">'
    '<entry><title>予想タイトル</title><link href="https://example.com/1"/>'
    "<id>hatenablog://entry/1</id></entry>"
    "</feed>"
).encode()


@pytest.fixture(autouse=True)
def mock_feed() -> Generator[MagicMock, None, None]:
    """ブログの公開フィード取得をモックする。

    Yields:
        MagicMock: requests.get のモック。
    """
    with patch(_FEED_PATCH_TARGET) as mock_get:
        mock_get.return_value.content = _FEED_XML
        yield mock_get


def _write_state(public_dir: str, entries: dict[str, str]) -> None:
    """2026年の状態ファイルを書き出す。"""
    year_dir = os.path.join(public_dir, _YEAR)
    os.makedirs(year_dir, exist_ok=True)
    with open(os.path.join(year_dir, ".hatena_entry_ids.json"), "w", encoding="utf-8") as f:
        json.dump({"entries": entries, "images": {}}, f)


@pytest.fixture
def dirs(tmp_path: pytest.TempPathFactory) -> tuple[str, str]:
    """public・templates ディレクトリを用意する。"""
    public_dir = str(tmp_path / "public")  # type: ignore[operator]
    templates_dir = str(tmp_path / "templates")  # type: ignore[operator]
    os.makedirs(templates_dir)
    with open(os.path.join(templates_dir, "TEMPLATE_RESULT.md"), "w", encoding="utf-8") as f:
        f.write(
            "# 【{RaceName}{Year}】回顧\n\n"
            "## 結果\n\n"
            "## 関連記事\n\n"
            "## 総評\n\n"
            "## 回顧\n"
        )
    return public_dir, templates_dir


def _run(
    mock_di: MagicMock,
    public_dir: str,
    templates_dir: str,
    marks: dict[int, str] | None = None,
    comments: dict[int, str] | None = None,
    race_code: str = _RACE_CODE,
    dynamics: tuple[MagicMock | None, Figure | None] = (None, None),
) -> MagicMock:
    """generate_result を実行し、展開評価のモックを返す。"""
    if marks is None:
        marks = {}
    if comments is None:
        comments = {}

    with (
        patch("scripts.gen_result.DataInterface", return_value=mock_di),
        patch("scripts.gen_result._PUBLIC_DIR", public_dir),
        patch("scripts.gen_result._TEMPLATES_DIR", templates_dir),
        patch(
            "scripts.gen_result.evaluate_race_dynamics_with_plot", return_value=dynamics
        ) as mock_evaluate,
        patch("scripts.gen_result.read_marks", return_value=marks),
        patch("scripts.gen_result.read_kek_comments", return_value=comments),
        patch.dict("os.environ", {"TFJV_DATA_DIR": "/tmp/fake_tfjv"}),
    ):
        generate_result(race_code)
    return mock_evaluate


def _read_md(public_dir: str, race_code: str, race_name: str, year: str) -> str:
    path = os.path.join(public_dir, year, f"{race_code}_{race_name}", "回顧.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


# 正常系
def test_gen_result_related_articles_with_predict_link(dirs: tuple[str, str]) -> None:
    """関連記事に予想記事のリンクと自作AIの結果を出力し、結果と総評の間に置く。"""
    public_dir, templates_dir = dirs
    _write_state(public_dir, {f"{_YEAR}/{_RACE_CODE}_{_RACE_NAME}/予想.md": "1"})
    _run(_make_mock_di([_normal_row(1, 5, "ホースA")]), public_dir, templates_dir)
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert (
        "| 1着 |  | 5 | ホースA | 1 | 1 (逃) | 35.0秒 (1位) |\n\n"
        "## 関連記事\n\n"
        "- [予想タイトル](https://example.com/1)\n"
        "- [自作AIの結果]()\n\n"
        "## 総評"
    ) in content


def test_gen_result_related_articles_without_predict_link(dirs: tuple[str, str]) -> None:
    """予想記事のリンクが無い場合は自作AIの結果だけを出力する。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_di([_normal_row(1, 5, "ホースA")]), public_dir, templates_dir)
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert "## 関連記事\n\n- [自作AIの結果]()\n\n## 総評" in content


# 準正常系
def test_gen_result_raises_when_feed_fetch_fails(
    dirs: tuple[str, str], mock_feed: MagicMock
) -> None:
    """フィードの取得に失敗した場合は例外になる。"""
    public_dir, templates_dir = dirs
    mock_feed.side_effect = requests.ConnectionError("down")
    with pytest.raises(requests.ConnectionError):
        _run(_make_mock_di([_normal_row(1, 5, "ホースA")]), public_dir, templates_dir)


# 正常系
def test_gen_result_creates_file_in_race_subdir(dirs: tuple[str, str]) -> None:
    """回顧.md が {race_code}_{race_name}/回顧.md に作成される。"""
    public_dir, templates_dir = dirs
    mock_di = _make_mock_di([_normal_row(1, 5, "ホースA")])
    _run(mock_di, public_dir, templates_dir)
    assert os.path.exists(
        os.path.join(public_dir, _YEAR, f"{_RACE_CODE}_{_RACE_NAME}", "回顧.md")
    )


def test_gen_result_title_format(dirs: tuple[str, str]) -> None:
    """生成ファイルのタイトルが # 【{race_name}{year}】回顧 になる。"""
    public_dir, templates_dir = dirs
    mock_di = _make_mock_di([_normal_row(1, 5, "ホースA")])
    _run(mock_di, public_dir, templates_dir)
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert content.startswith(f"# 【{_RACE_NAME}{_YEAR}】回顧")


def test_gen_result_has_sohyo_section(dirs: tuple[str, str]) -> None:
    """総評セクションが出力される。"""
    public_dir, templates_dir = dirs
    mock_di = _make_mock_di([_normal_row(1, 5, "ホースA")])
    _run(mock_di, public_dir, templates_dir)
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert "## 総評" in content


def test_gen_result_result_section_table_values(dirs: tuple[str, str]) -> None:
    """結果セクションに1〜3着の表が出力され、4着以降は出力されない。"""
    public_dir, templates_dir = dirs
    mock_di = _make_mock_di([
        _normal_row(1, 11, "ホースA", ninki=9, corner4=1, halon=35.8, kyakushitsu="1"),
        _normal_row(2, 3, "ホースB", ninki=2, corner4=5, halon=34.5, kyakushitsu="3"),
        _normal_row(3, 8, "ホースC", ninki=1, corner4=7, halon=36.0, kyakushitsu="4"),
        _normal_row(4, 1, "ホースD", ninki=3, corner4=2, halon=35.0, kyakushitsu="2"),
    ])
    _run(mock_di, public_dir, templates_dir, marks={11: "◎", 8: "▲"})
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    result_section = content[content.index("## 結果") : content.index("## 関連記事")]
    assert result_section == (
        "## 結果\n\n"
        "| 着順 | 印 | 馬番 | 馬名 | 人気 | 4角通過 | 後3F |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        "| 1着 | ◎ | 11 | ホースA | 9 | 1 (逃) | 35.8秒 (3位) |\n"
        "| 2着 |  | 3 | ホースB | 2 | 5 (差) | 34.5秒 (1位) |\n"
        "| 3着 | ▲ | 8 | ホースC | 1 | 7 (追) | 36.0秒 (4位) |\n\n"
    )


def test_gen_result_result_section_without_values(dirs: tuple[str, str]) -> None:
    """人気・4角通過・後3Fが無い馬は「-」、脚質判定が無い馬は4角通過に括弧を付けない。"""
    public_dir, templates_dir = dirs
    nan = float("nan")
    mock_di = _make_mock_di([
        _normal_row(1, 5, "ホースA", ninki=nan, corner4=nan, halon=nan, kyakushitsu=None),
        _normal_row(2, 3, "ホースB", corner4=4, kyakushitsu=None),
    ])
    _run(mock_di, public_dir, templates_dir)
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert "| 1着 |  | 5 | ホースA | - | - | - |\n" in content
    assert "| 2着 |  | 3 | ホースB | 1 | 4 | 35.0秒 (1位) |\n" in content


def test_gen_result_result_section_dynamics_table_and_image(dirs: tuple[str, str]) -> None:
    """展開評価がある場合は有利度の表・標準化散布図・総合評価の表を載せ、画像を保存する。"""
    public_dir, templates_dir = dirs
    cor_df = pd.DataFrame(
        {"差し有利度": [-0.79], "外枠有利度": [-0.15], "外有利度": [float("nan")]}
    )
    eval_df = pd.DataFrame({"馬番": [5, 3], "総合評価": [-0.2, 0.31]})
    dynamics = MagicMock(cor_df=cor_df, eval_df=eval_df)
    figure = MagicMock(spec=Figure)
    mock_evaluate = _run(
        _make_mock_di([_normal_row(1, 5, "ホースA"), _normal_row(2, 3, "ホースB")]),
        public_dir,
        templates_dir,
        dynamics=(dynamics, figure),
    )
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert (
        "\n\n| 差し有利度 | 外枠有利度 | 外有利度 |\n"
        "| --- | --- | --- |\n"
        "| -79% | -15% | - |\n\n"
        f"![標準化散布図](img/race_result/{_RACE_CODE}.png)\n\n"
        "| 着順 | 馬番 | 馬名 | 評価値 |\n"
        "| --- | --- | --- | --- |\n"
        "| 2着 | 3 | ホースB | +0.31 |\n"
        "| 1着 | 5 | ホースA | -0.20 |\n\n"
        "※ 評価値は、展開（4角の位置・馬番・コーナーでの内外）の有利不利で"
        "走破タイムを補正した値。大きいほど展開の不利をはね返して好走した馬。\n\n"
        "## 関連記事"
    ) in content
    expected_path = os.path.join(
        public_dir, _YEAR, f"{_RACE_CODE}_{_RACE_NAME}", "img", "race_result", f"{_RACE_CODE}.png"
    )
    figure.savefig.assert_called_once_with(expected_path, bbox_inches="tight")
    assert mock_evaluate.call_args.args[2] == date(2026, 5, 25)


def test_gen_result_result_section_without_dynamics(dirs: tuple[str, str]) -> None:
    """展開評価の対象外レースは有利度の表と散布図を載せず、画像を作らない。"""
    public_dir, templates_dir = dirs
    _run(_make_mock_di([_normal_row(1, 5, "ホースA")]), public_dir, templates_dir)
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert "差し有利度" not in content
    assert "標準化散布図" not in content
    assert not os.path.exists(
        os.path.join(public_dir, _YEAR, f"{_RACE_CODE}_{_RACE_NAME}", "img")
    )


def test_gen_result_review_section_all_horses_ordered(dirs: tuple[str, str]) -> None:
    """回顧セクションに全頭が着順順で出力される。"""
    public_dir, templates_dir = dirs
    mock_di = _make_mock_di([
        _normal_row(1, 5, "ホースA"),
        _normal_row(2, 3, "ホースB"),
        _normal_row(3, 8, "ホースC"),
        _normal_row(4, 1, "ホースD"),
    ])
    comments = {
        5: "[優駿牝馬] 好走。",
        3: "[優駿牝馬] 差し届く。",
        8: "[優駿牝馬] 外回し。",
        1: "[優駿牝馬] 凡走。",
    }
    _run(mock_di, public_dir, templates_dir, comments=comments)
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    review = content[content.index("## 回顧"):]
    pos = [review.index(f"### {n}着") for n in range(1, 5)]
    assert pos == sorted(pos)


def test_gen_result_review_section_comment_body_extracted(dirs: tuple[str, str]) -> None:
    """[レース名] プレフィックスを除いたコメント本文が回顧内容として出力される。"""
    public_dir, templates_dir = dirs
    mock_di = _make_mock_di([_normal_row(1, 5, "ホースA")])
    _run(mock_di, public_dir, templates_dir, comments={5: "[優駿牝馬] 好内容。"})
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert "好内容。" in content
    assert "[優駿牝馬]" not in content


def test_gen_result_review_section_empty_comment_skipped(dirs: tuple[str, str]) -> None:
    """回顧内容が空の馬はスキップされる。"""
    public_dir, templates_dir = dirs
    mock_di = _make_mock_di([
        _normal_row(1, 5, "ホースA"),
        _normal_row(2, 3, "ホースB"),
    ])
    _run(mock_di, public_dir, templates_dir, comments={5: "[優駿牝馬] 好走。"})
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    review = content[content.index("## 回顧"):]
    assert "ホースA" in review
    assert "ホースB" not in review


def test_gen_result_review_section_mark_shown(dirs: tuple[str, str]) -> None:
    """回顧セクションに印が出力される。"""
    public_dir, templates_dir = dirs
    mock_di = _make_mock_di([_normal_row(1, 5, "ホースA")])
    _run(mock_di, public_dir, templates_dir, marks={5: "◎"}, comments={5: "[優駿牝馬] 内容。"})
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert "### 1着 ◎5ホースA" in content


def test_gen_result_review_abnormal_label(dirs: tuple[str, str]) -> None:
    """異常区分馬のh3見出しにコード名称が使われる。"""
    public_dir, templates_dir = dirs
    mock_di = _make_mock_di([
        _normal_row(1, 5, "ホースA"),
        _abnormal_row(3, "ホースB", "4"),
    ])
    _run(mock_di, public_dir, templates_dir, comments={
        5: "[優駿牝馬] 好走。",
        3: "[優駿牝馬] 競走中止。",
    })
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert "### 競走中止 3ホースB" in content
    assert "### 1着 5ホースA" in content


@pytest.mark.parametrize(
    "ijo_code, expected_label",
    [
        ("1", "出走取消"),
        ("2", "発走除外"),
        ("3", "競走除外"),
        ("4", "競走中止"),
    ],
)
def test_gen_result_review_abnormal_all_codes(
    dirs: tuple[str, str],
    ijo_code: str,
    expected_label: str,
) -> None:
    """異常区分コード1〜4でそれぞれ正しいラベルが使われる。"""
    public_dir, templates_dir = dirs
    mock_di = _make_mock_di([
        _normal_row(1, 5, "ホースA"),
        _abnormal_row(3, "ホースB", ijo_code),
    ])
    _run(mock_di, public_dir, templates_dir, comments={
        5: "[優駿牝馬] 好走。",
        3: f"[優駿牝馬] {expected_label}。",
    })
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert f"### {expected_label} 3ホースB" in content


def test_gen_result_review_abnormal_order_by_code_desc_then_umaban_asc(
    dirs: tuple[str, str],
) -> None:
    """異常区分コード大→小、同コードは馬番昇順で出力される。"""
    public_dir, templates_dir = dirs
    mock_di = _make_mock_di([
        _normal_row(1, 1, "ホースA"),
        _abnormal_row(5, "ホースB", "4"),  # 競走中止
        _abnormal_row(3, "ホースC", "3"),  # 競走除外
        _abnormal_row(2, "ホースD", "4"),  # 競走中止（コード同じ、馬番小）
    ])
    comments = {
        1: "[優駿牝馬] 好走。",
        5: "[優駿牝馬] 競走中止。",
        3: "[優駿牝馬] 競走除外。",
        2: "[優駿牝馬] 競走中止。",
    }
    _run(mock_di, public_dir, templates_dir, comments=comments)
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    review = content[content.index("## 回顧"):]
    pos_2 = review.index("2ホースD")
    pos_5 = review.index("5ホースB")
    pos_3 = review.index("3ホースC")
    assert pos_2 < pos_5 < pos_3


def test_gen_result_review_comment_has_trailing_spaces(dirs: tuple[str, str]) -> None:
    """回顧セクションの「。」の後に半角スペース2つが出力される。"""
    public_dir, templates_dir = dirs
    mock_di = _make_mock_di([_normal_row(1, 5, "ホースA")])
    _run(mock_di, public_dir, templates_dir, comments={5: "[優駿牝馬] 好走。"})
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert "好走。  " in content


# _format_comment_body
def test_format_comment_body_single_sentence() -> None:
    """1文の末尾に半角スペース2つが付与される。"""
    assert _format_comment_body("好走。") == "好走。  "


def test_format_comment_body_multiple_sentences() -> None:
    """複数文の各「。」の後にスペース2つ+改行が挿入される。"""
    result = _format_comment_body("好走。内容良好。")
    assert result == "好走。  \n内容良好。  "


def test_format_comment_body_no_kuten() -> None:
    """「。」を含まない場合は変換なし。"""
    assert _format_comment_body("テキスト") == "テキスト"
