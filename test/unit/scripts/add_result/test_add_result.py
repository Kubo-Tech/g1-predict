"""add_result の単体テスト。"""
import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scripts.add_result import _format_comment_body, add_result

_RACE_CODE = "2026052405021011"
_RACE_NAME = "優駿牝馬"
_YEAR = "2026"


def _make_result_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _make_mock_di(result_rows: list[dict]) -> MagicMock:
    mock = MagicMock()
    mock.get_result.return_value = _make_result_df(result_rows)
    return mock


def _normal_row(chakusa: int, umaban: int, horse_name: str) -> dict:
    return {
        "確定着順": chakusa,
        "馬番": umaban,
        "馬名": horse_name,
        "異常区分コード": "0",
    }


def _abnormal_row(umaban: int, horse_name: str, ijo_code: str) -> dict:
    return {
        "確定着順": float("nan"),
        "馬番": umaban,
        "馬名": horse_name,
        "異常区分コード": ijo_code,
    }


def _run(
    mock_di: MagicMock,
    public_dir: str,
    marks: dict[int, str] | None = None,
    comments: dict[int, str] | None = None,
    race_code: str = _RACE_CODE,
) -> None:
    if marks is None:
        marks = {}
    if comments is None:
        comments = {}

    with (
        patch("scripts.add_result.DataInterface", return_value=mock_di),
        patch("scripts.add_result._PUBLIC_DIR", public_dir),
        patch("scripts.add_result.read_marks", return_value=marks),
        patch("scripts.add_result.read_kek_comments", return_value=comments),
        patch.dict("os.environ", {"TFJV_DATA_DIR": "/tmp/fake_tfjv"}),
    ):
        add_result(race_code)


def _make_md(public_dir: str, race_code: str, race_name: str, year: str) -> str:
    year_dir = os.path.join(public_dir, year)
    os.makedirs(year_dir, exist_ok=True)
    path = os.path.join(year_dir, f"{race_code}_{race_name}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            f"# {race_name}{year}\n\n"
            "## 買い目\n\n"
            "## 結果\n\n"
            "## 回顧\n\n"
        )
    return path


def _read_md(public_dir: str, race_code: str, race_name: str, year: str) -> str:
    with open(os.path.join(public_dir, year, f"{race_code}_{race_name}.md"), encoding="utf-8") as f:
        return f.read()


# 正常系
def test_add_result_result_section_shows_top3(tmp_path: pytest.TempPathFactory) -> None:
    """結果セクションに1〜3着が出力される。"""
    public_dir = str(tmp_path)
    _make_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    mock_di = _make_mock_di([
        _normal_row(1, 5, "ホースA"),
        _normal_row(2, 3, "ホースB"),
        _normal_row(3, 8, "ホースC"),
        _normal_row(4, 1, "ホースD"),
    ])
    _run(mock_di, public_dir)
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    result_section = content[content.index("## 結果") : content.index("## 回顧")]
    assert "1着 5ホースA" in result_section
    assert "2着 3ホースB" in result_section
    assert "3着 8ホースC" in result_section
    assert "4着" not in result_section


def test_add_result_result_section_trailing_spaces(tmp_path: pytest.TempPathFactory) -> None:
    """1着・2着行末尾に半角スペース2つ、3着は末尾スペースなし。"""
    public_dir = str(tmp_path)
    _make_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    mock_di = _make_mock_di([
        _normal_row(1, 5, "ホースA"),
        _normal_row(2, 3, "ホースB"),
        _normal_row(3, 8, "ホースC"),
    ])
    _run(mock_di, public_dir)
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert "1着 5ホースA  " in content
    assert "2着 3ホースB  " in content
    assert "3着 8ホースC  " not in content


def test_add_result_result_section_with_mark(tmp_path: pytest.TempPathFactory) -> None:
    """印がある馬は印付きで出力される。"""
    public_dir = str(tmp_path)
    _make_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    mock_di = _make_mock_di([
        _normal_row(1, 5, "ホースA"),
        _normal_row(2, 3, "ホースB"),
        _normal_row(3, 8, "ホースC"),
    ])
    _run(mock_di, public_dir, marks={5: "◎", 8: "▲"})
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    result_section = content[content.index("## 結果") : content.index("## 回顧")]
    assert "1着 ◎5ホースA" in result_section
    assert "2着 3ホースB" in result_section
    assert "3着 ▲8ホースC" in result_section


def test_add_result_review_section_all_horses_ordered(tmp_path: pytest.TempPathFactory) -> None:
    """回顧セクションに全頭が着順順で出力される。"""
    public_dir = str(tmp_path)
    _make_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
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
    _run(mock_di, public_dir, comments=comments)
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    review = content[content.index("## 回顧"):]
    pos = [review.index(f"### {n}着") for n in range(1, 5)]
    assert pos == sorted(pos)


def test_add_result_review_section_comment_body_extracted(tmp_path: pytest.TempPathFactory) -> None:
    """[レース名] プレフィックスを除いたコメント本文が回顧内容として出力される。"""
    public_dir = str(tmp_path)
    _make_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    mock_di = _make_mock_di([_normal_row(1, 5, "ホースA")])
    _run(mock_di, public_dir, comments={5: "[優駿牝馬] 好内容。"})
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert "好内容。" in content
    assert "[優駿牝馬]" not in content


def test_add_result_review_section_empty_comment_skipped(tmp_path: pytest.TempPathFactory) -> None:
    """回顧内容が空の馬はスキップされる。"""
    public_dir = str(tmp_path)
    _make_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    mock_di = _make_mock_di([
        _normal_row(1, 5, "ホースA"),
        _normal_row(2, 3, "ホースB"),
    ])
    _run(mock_di, public_dir, comments={5: "[優駿牝馬] 好走。"})
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    review = content[content.index("## 回顧"):]
    assert "ホースA" in review
    assert "ホースB" not in review


def test_add_result_review_section_mark_shown(tmp_path: pytest.TempPathFactory) -> None:
    """回顧セクションに印が出力される。"""
    public_dir = str(tmp_path)
    _make_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    mock_di = _make_mock_di([_normal_row(1, 5, "ホースA")])
    _run(mock_di, public_dir, marks={5: "◎"}, comments={5: "[優駿牝馬] 内容。"})
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert "### 1着 ◎5ホースA" in content


def test_add_result_review_abnormal_label(tmp_path: pytest.TempPathFactory) -> None:
    """異常区分馬のh3見出しにコード名称が使われる。"""
    public_dir = str(tmp_path)
    _make_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    mock_di = _make_mock_di([
        _normal_row(1, 5, "ホースA"),
        _abnormal_row(3, "ホースB", "4"),
    ])
    _run(mock_di, public_dir, comments={
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
def test_add_result_review_abnormal_all_codes(
    tmp_path: pytest.TempPathFactory,
    ijo_code: str,
    expected_label: str,
) -> None:
    """異常区分コード1〜4でそれぞれ正しいラベルが使われる。"""
    public_dir = str(tmp_path)
    _make_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    mock_di = _make_mock_di([
        _normal_row(1, 5, "ホースA"),
        _abnormal_row(3, "ホースB", ijo_code),
    ])
    _run(mock_di, public_dir, comments={
        5: "[優駿牝馬] 好走。",
        3: f"[優駿牝馬] {expected_label}。",
    })
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert f"### {expected_label} 3ホースB" in content


def test_add_result_review_abnormal_order_by_code_desc_then_umaban_asc(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """異常区分コード大→小、同コードは馬番昇順で出力される。"""
    public_dir = str(tmp_path)
    _make_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
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
    _run(mock_di, public_dir, comments=comments)
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    review = content[content.index("## 回顧"):]
    # code=4の馬番2が先、code=4の馬番5が次、code=3の馬番3が最後
    pos_2 = review.index("2ホースD")
    pos_5 = review.index("5ホースB")
    pos_3 = review.index("3ホースC")
    assert pos_2 < pos_5 < pos_3


def test_add_result_md_file_updated(tmp_path: pytest.TempPathFactory) -> None:
    """mdファイルが正しく上書き更新される。"""
    public_dir = str(tmp_path)
    _make_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    mock_di = _make_mock_di([_normal_row(1, 5, "ホースA")])
    _run(mock_di, public_dir, comments={5: "[優駿牝馬] 好走。"})
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert "1着 5ホースA" in content
    assert "好走。" in content


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


def test_add_result_review_comment_has_trailing_spaces(tmp_path: pytest.TempPathFactory) -> None:
    """回顧セクションの「。」の後に半角スペース2つが出力される。"""
    public_dir = str(tmp_path)
    _make_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    mock_di = _make_mock_di([_normal_row(1, 5, "ホースA")])
    _run(mock_di, public_dir, comments={5: "[優駿牝馬] 好走。"})
    content = _read_md(public_dir, _RACE_CODE, _RACE_NAME, _YEAR)
    assert "好走。  " in content


# 異常系
def test_add_result_raises_when_md_not_found(tmp_path: pytest.TempPathFactory) -> None:
    """対応する md ファイルがない場合 FileNotFoundError が発生する。"""
    public_dir = str(tmp_path)
    mock_di = _make_mock_di([_normal_row(1, 5, "ホースA")])
    with pytest.raises(FileNotFoundError):
        _run(mock_di, public_dir)
