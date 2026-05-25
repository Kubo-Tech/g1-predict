"""generate_result_comments の単体テスト。"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scripts.gen_result_comment import generate_result_comments


def _make_kek_com(tmp_path: pytest.TempPathFactory, venue: str, year2: str, tfjv_code: str) -> str:
    """空の KEK_COM ファイルを作成し base_dir を返す。"""
    dirpath = tmp_path / "KEK_COM" / f"20{year2}"  # type: ignore[operator]
    dirpath.mkdir(parents=True)
    (dirpath / f"KC{venue}{year2}{tfjv_code}.DAT").write_bytes(b"")  # type: ignore[operator]
    return str(tmp_path)


def _make_mock_di(race_name: str, result_rows: list[dict]) -> MagicMock:
    """DataInterface のモックを生成する。"""
    mock_di = MagicMock()
    mock_di.get_race_basic_info.return_value = pd.DataFrame({"競走名略称6文字": [race_name]})
    mock_di.get_result.return_value = pd.DataFrame(result_rows)
    return mock_di


def _read_kek_com(base_dir: str, venue: str, year2: str, tfjv_code: str) -> list[str]:
    """KEK_COM ファイルの行一覧を返す。"""
    fpath = f"{base_dir}/KEK_COM/20{year2}/KC{venue}{year2}{tfjv_code}.DAT"
    with open(fpath, "rb") as f:
        return f.read().decode("shift_jis").splitlines()


# 正常系
@pytest.mark.parametrize(
    "time_diff, margin_code, expected_gap",
    [
        (-0.1, float("nan"), "0.1秒差"),
        (0.1, "_34", "0.1秒差"),
        (0.0, "K__", "クビ差"),
        (0.0, "H__", "ハナ差"),
        (0.0, "A__", "アタマ差"),
    ],
)
def test_generate_result_comments_gap_format(
    tmp_path: pytest.TempPathFactory,
    time_diff: float,
    margin_code: object,
    expected_gap: str,
) -> None:
    """様々なタイム差・着差コードで正しい着差文字列が生成される。"""
    base_dir = _make_kek_com(tmp_path, "05", "26", "11")
    mock_di = _make_mock_di(
        "クロッカスステークス",
        [
            {"確定着順": 1, "タイム差": 0.0, "着差コード1": float("nan"), "馬番": 2},
            {"確定着順": 2, "タイム差": time_diff, "着差コード1": margin_code, "馬番": 1},
        ],
    )
    with patch("scripts.gen_result_comment.DataInterface", return_value=mock_di):
        generate_result_comments("2026013105010110", base_dir)

    lines = _read_kek_com(base_dir, "05", "26", "11")
    assert len(lines) == 2
    assert f'[クロッカスステークス] {expected_gap}1着。"' in lines[0]


def test_generate_result_comments_no_suffix_daisa(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """大差は「差」サフィックスなしで生成される。"""
    base_dir = _make_kek_com(tmp_path, "05", "26", "11")
    mock_di = _make_mock_di(
        "クロッカスステークス",
        [
            {"確定着順": 1, "タイム差": 0.0, "着差コード1": float("nan"), "馬番": 2},
            {"確定着順": 2, "タイム差": 0.0, "着差コード1": "T__", "馬番": 1},
        ],
    )
    with patch("scripts.gen_result_comment.DataInterface", return_value=mock_di):
        generate_result_comments("2026013105010110", base_dir)

    lines = _read_kek_com(base_dir, "05", "26", "11")
    assert '大差1着。"' in lines[0]
    assert "大差差" not in lines[0]


def test_generate_result_comments_no_suffix_dochaku(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """同着は「差」サフィックスなしで生成される。"""
    base_dir = _make_kek_com(tmp_path, "05", "26", "11")
    mock_di = _make_mock_di(
        "クロッカスステークス",
        [
            {"確定着順": 1, "タイム差": 0.0, "着差コード1": float("nan"), "馬番": 2},
            {"確定着順": 2, "タイム差": 0.0, "着差コード1": "D__", "馬番": 1},
        ],
    )
    with patch("scripts.gen_result_comment.DataInterface", return_value=mock_di):
        generate_result_comments("2026013105010110", base_dir)

    lines = _read_kek_com(base_dir, "05", "26", "11")
    assert '同着1着。"' in lines[0]
    assert "同着差" not in lines[0]


def test_generate_result_comments_writes_all_horses(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """全馬分のコメントが書き込まれる。"""
    base_dir = _make_kek_com(tmp_path, "05", "26", "11")
    mock_di = _make_mock_di(
        "クロッカスステークス",
        [
            {"確定着順": 1, "タイム差": -0.1, "着差コード1": float("nan"), "馬番": 2},
            {"確定着順": 2, "タイム差": 0.1, "着差コード1": "_34", "馬番": 1},
            {"確定着順": 3, "タイム差": 0.5, "着差コード1": "_34", "馬番": 3},
        ],
    )
    with patch("scripts.gen_result_comment.DataInterface", return_value=mock_di):
        generate_result_comments("2026013105010110", base_dir)

    lines = _read_kek_com(base_dir, "05", "26", "11")
    assert len(lines) == 3
    assert "1着" in lines[0]
    assert "2着" in lines[1]
    assert "3着" in lines[2]
