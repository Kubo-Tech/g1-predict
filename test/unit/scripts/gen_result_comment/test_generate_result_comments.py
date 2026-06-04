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


def _make_mock_race_getter(race_name: str, result_rows: list[dict]) -> MagicMock:
    """RaceGetter のモックを生成する。"""
    mock = MagicMock()
    mock.get_race_shosai.return_value = pd.DataFrame({"kyosomei_ryakusho_6": [race_name]})
    mock.get_umagoto_race_joho.return_value = pd.DataFrame(result_rows)
    return mock


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
    mock_rg = _make_mock_race_getter(
        "クロッカスステークス",
        [
            {"kakutei_chakujun": 1, "time_sa": 0.0, "chakusa_code1": float("nan"),
             "umaban": 2, "ijo_kubun_code": "0"},
            {"kakutei_chakujun": 2, "time_sa": time_diff, "chakusa_code1": margin_code,
             "umaban": 1, "ijo_kubun_code": "0"},
        ],
    )
    with patch("scripts.gen_result_comment.RaceGetter", return_value=mock_rg):
        generate_result_comments("2026013105010110", base_dir)

    lines = _read_kek_com(base_dir, "05", "26", "11")
    assert len(lines) == 2
    assert f'[クロッカスステークス] {expected_gap}1着。"' in lines[0]


def test_generate_result_comments_no_suffix_daisa(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """大差は「差」サフィックスなしで生成される。"""
    base_dir = _make_kek_com(tmp_path, "05", "26", "11")
    mock_rg = _make_mock_race_getter(
        "クロッカスステークス",
        [
            {"kakutei_chakujun": 1, "time_sa": 0.0, "chakusa_code1": float("nan"),
             "umaban": 2, "ijo_kubun_code": "0"},
            {"kakutei_chakujun": 2, "time_sa": 0.0, "chakusa_code1": "T__",
             "umaban": 1, "ijo_kubun_code": "0"},
        ],
    )
    with patch("scripts.gen_result_comment.RaceGetter", return_value=mock_rg):
        generate_result_comments("2026013105010110", base_dir)

    lines = _read_kek_com(base_dir, "05", "26", "11")
    assert '大差1着。"' in lines[0]
    assert "大差差" not in lines[0]


def test_generate_result_comments_no_suffix_dochaku(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """同着は「差」サフィックスなしで生成される。"""
    base_dir = _make_kek_com(tmp_path, "05", "26", "11")
    mock_rg = _make_mock_race_getter(
        "クロッカスステークス",
        [
            {"kakutei_chakujun": 1, "time_sa": 0.0, "chakusa_code1": float("nan"),
             "umaban": 2, "ijo_kubun_code": "0"},
            {"kakutei_chakujun": 2, "time_sa": 0.0, "chakusa_code1": "D__",
             "umaban": 1, "ijo_kubun_code": "0"},
        ],
    )
    with patch("scripts.gen_result_comment.RaceGetter", return_value=mock_rg):
        generate_result_comments("2026013105010110", base_dir)

    lines = _read_kek_com(base_dir, "05", "26", "11")
    assert '同着1着。"' in lines[0]
    assert "同着差" not in lines[0]


def test_generate_result_comments_writes_all_horses(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """全馬分のコメントが書き込まれる。"""
    base_dir = _make_kek_com(tmp_path, "05", "26", "11")
    mock_rg = _make_mock_race_getter(
        "クロッカスステークス",
        [
            {"kakutei_chakujun": 1, "time_sa": -0.1, "chakusa_code1": float("nan"),
             "umaban": 2, "ijo_kubun_code": "0"},
            {"kakutei_chakujun": 2, "time_sa": 0.1, "chakusa_code1": "_34",
             "umaban": 1, "ijo_kubun_code": "0"},
            {"kakutei_chakujun": 3, "time_sa": 0.5, "chakusa_code1": "_34",
             "umaban": 3, "ijo_kubun_code": "0"},
        ],
    )
    with patch("scripts.gen_result_comment.RaceGetter", return_value=mock_rg):
        generate_result_comments("2026013105010110", base_dir)

    lines = _read_kek_com(base_dir, "05", "26", "11")
    assert len(lines) == 3
    assert "1着" in lines[0]
    assert "2着" in lines[1]
    assert "3着" in lines[2]


@pytest.mark.parametrize(
    "ijo_code, expected_name",
    [
        ("1", "出走取消"),
        ("2", "発走除外"),
        ("3", "競走除外"),
        ("4", "競走中止"),
    ],
)
def test_generate_result_comments_abnormal_code(
    tmp_path: pytest.TempPathFactory,
    ijo_code: str,
    expected_name: str,
) -> None:
    """異常区分コード1〜4の馬はコード名称のみのコメントが生成される。"""
    base_dir = _make_kek_com(tmp_path, "05", "26", "11")
    mock_rg = _make_mock_race_getter(
        "天皇賞春",
        [
            {"kakutei_chakujun": 1, "time_sa": 0.0, "chakusa_code1": float("nan"),
             "umaban": 1, "ijo_kubun_code": "0"},
            {"kakutei_chakujun": 2, "time_sa": 0.1, "chakusa_code1": "_34",
             "umaban": 2, "ijo_kubun_code": "0"},
            {
                "kakutei_chakujun": float("nan"),
                "time_sa": float("nan"),
                "chakusa_code1": float("nan"),
                "umaban": 3,
                "ijo_kubun_code": ijo_code,
            },
        ],
    )
    with patch("scripts.gen_result_comment.RaceGetter", return_value=mock_rg):
        generate_result_comments("2026013105010110", base_dir)

    lines = _read_kek_com(base_dir, "05", "26", "11")
    assert len(lines) == 3
    assert any(f'[天皇賞春] {expected_name}"' in line for line in lines)
    assert not any(
        f'[天皇賞春] {expected_name}' in line and "着。" in line for line in lines
    )


def test_generate_result_comments_normal_horses_unaffected_by_abnormal(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """異常区分馬が混在しても正常馬には着順コメントが生成される。"""
    base_dir = _make_kek_com(tmp_path, "05", "26", "11")
    mock_rg = _make_mock_race_getter(
        "天皇賞春",
        [
            {"kakutei_chakujun": 1, "time_sa": 0.1, "chakusa_code1": "_34",
             "umaban": 1, "ijo_kubun_code": "0"},
            {"kakutei_chakujun": 2, "time_sa": 0.1, "chakusa_code1": "_34",
             "umaban": 2, "ijo_kubun_code": "0"},
            {
                "kakutei_chakujun": float("nan"),
                "time_sa": float("nan"),
                "chakusa_code1": float("nan"),
                "umaban": 3,
                "ijo_kubun_code": "4",
            },
        ],
    )
    with patch("scripts.gen_result_comment.RaceGetter", return_value=mock_rg):
        generate_result_comments("2026013105010110", base_dir)

    lines = _read_kek_com(base_dir, "05", "26", "11")
    assert len(lines) == 3
    assert any("1着。" in line for line in lines)
    assert any("2着。" in line for line in lines)
    assert any("競走中止" in line for line in lines)


def test_generate_result_comments_missing_ijo_column(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """異常区分コード列が存在しない場合は正常馬として処理される。"""
    base_dir = _make_kek_com(tmp_path, "05", "26", "11")
    mock_rg = _make_mock_race_getter(
        "クロッカスステークス",
        [
            {"kakutei_chakujun": 1, "time_sa": 0.0, "chakusa_code1": float("nan"), "umaban": 1},
            {"kakutei_chakujun": 2, "time_sa": 0.1, "chakusa_code1": "_34", "umaban": 2},
        ],
    )
    with patch("scripts.gen_result_comment.RaceGetter", return_value=mock_rg):
        generate_result_comments("2026013105010110", base_dir)

    lines = _read_kek_com(base_dir, "05", "26", "11")
    assert len(lines) == 2
    assert any("1着。" in line for line in lines)
    assert any("2着。" in line for line in lines)


def test_generate_result_comments_numeric_ijo_code(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """数値型（float）の異常区分コードでも正しく異常馬として処理される。"""
    base_dir = _make_kek_com(tmp_path, "05", "26", "11")
    mock_rg = _make_mock_race_getter(
        "クロッカスステークス",
        [
            {"kakutei_chakujun": 1, "time_sa": 0.0, "chakusa_code1": float("nan"),
             "umaban": 1, "ijo_kubun_code": "0"},
            {"kakutei_chakujun": 2, "time_sa": 0.1, "chakusa_code1": "_34",
             "umaban": 2, "ijo_kubun_code": "0"},
            {
                "kakutei_chakujun": float("nan"),
                "time_sa": float("nan"),
                "chakusa_code1": float("nan"),
                "umaban": 3,
                "ijo_kubun_code": 4.0,
            },
        ],
    )
    with patch("scripts.gen_result_comment.RaceGetter", return_value=mock_rg):
        generate_result_comments("2026013105010110", base_dir)

    lines = _read_kek_com(base_dir, "05", "26", "11")
    assert len(lines) == 3
    assert any('競走中止"' in line for line in lines)
    assert not any("着。" in line and "競走中止" in line for line in lines)
