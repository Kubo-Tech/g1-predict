"""generate_day_trend の単体テスト。"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from g1_predict.modules.gen_day_trend.day_trend import PREV_DAY, RACE_DAY, DayTrendBody
from scripts.gen_day_trend import generate_day_trend


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
    body: str = "",
) -> None:
    """generate_day_trend をパッチ環境で実行する。

    Args:
        mock_race_getter (MagicMock): RaceGetter のモック。
        public_dir (str): public ディレクトリパス。
        race_code (str): 16桁 JRA-VAN 形式の race_code。
        body (str): 前日の傾向記事本文。
    """
    with (
        patch("scripts.gen_day_trend.RaceGetter", return_value=mock_race_getter),
        patch("scripts.gen_day_trend._PUBLIC_DIR", public_dir),
        patch(
            "scripts.gen_day_trend.build_day_trend_body",
            return_value=DayTrendBody(text=body, images={}),
        ),
    ):
        generate_day_trend(race_code, PREV_DAY)


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
    path = os.path.join(public_dir, year, f"{race_code}_{race_name}", "前日の傾向.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


# 正常系
def test_generate_day_trend_prev_day_title_format(public_dir: str) -> None:
    """生成ファイルのタイトルが # 【{race_name}{year}】前日の傾向 になる。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(
        _make_mock_race_getter(race_name="天皇賞春", year="2026"),
        public_dir,
        body="## 出目\n\n本文\n",
    )
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert content.startswith("# 【天皇賞春2026】前日の傾向")


def test_generate_day_trend_prev_day_creates_file_in_race_subdir(public_dir: str) -> None:
    """生成ファイルが {race_code}_{race_name}/前日の傾向.md に作成される。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(_make_mock_race_getter(), public_dir, body="## 出目\n\n本文\n")
    assert os.path.exists(
        os.path.join(public_dir, "2026", "2026013105010110_天皇賞春", "前日の傾向.md")
    )


def test_generate_day_trend_prev_day_contains_body(public_dir: str) -> None:
    """生成ファイルに本文が埋め込まれる。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(
        _make_mock_race_getter(),
        public_dir,
        body="## 出目\n\n出目本文\n\n## 各レース\n\n### 東京6R 未勝利 1800m 16頭\n",
    )
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert "## 出目" in content
    assert "## 各レース" in content
    assert "### 東京6R 未勝利 1800m 16頭" in content


def test_generate_day_trend_prev_day_title_only_when_body_empty(public_dir: str) -> None:
    """本文が空文字列の場合、タイトル行のみが出力される。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    _run(_make_mock_race_getter(race_name="天皇賞春", year="2026"), public_dir, body="")
    content = _read_output(public_dir, "2026", "2026013105010110", "天皇賞春")
    assert content == "# 【天皇賞春2026】前日の傾向\n"


def test_generate_day_trend_prev_day_saves_and_closes_image(public_dir: str) -> None:
    """画像がimg/prev_day配下に保存され、保存後にFigureがcloseされる。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    mock_figure = MagicMock()
    race_code = "2026013105010110"
    body = DayTrendBody(
        text="## 出目\n\n本文\n",
        images={"img/prev_day/2026013005010106.png": mock_figure},
    )

    with (
        patch(
            "scripts.gen_day_trend.RaceGetter",
            return_value=_make_mock_race_getter(),
        ),
        patch("scripts.gen_day_trend._PUBLIC_DIR", public_dir),
        patch("scripts.gen_day_trend.build_day_trend_body", return_value=body),
        patch("g1_predict.modules.utils.image_output.plt") as mock_plt,
    ):
        generate_day_trend(race_code, PREV_DAY)

    expected_path = os.path.join(
        public_dir, "2026", f"{race_code}_天皇賞春", "img", "prev_day", "2026013005010106.png"
    )
    mock_figure.savefig.assert_called_once_with(expected_path, bbox_inches="tight")
    mock_plt.close.assert_called_once_with(mock_figure)


def test_generate_day_trend_race_day_writes_race_day_article_and_images(public_dir: str) -> None:
    """当日の傾向では、タイトルが当日の傾向になり当日の傾向.mdと画像が出力される。

    Args:
        public_dir (str): public ディレクトリパス。
    """
    mock_figure = MagicMock()
    race_code = "2026013105010110"
    body = DayTrendBody(
        text="## 当日の出目\n\n本文\n",
        images={"img/race_day/dynamics.png": mock_figure},
    )

    with (
        patch("scripts.gen_day_trend.RaceGetter", return_value=_make_mock_race_getter()),
        patch("scripts.gen_day_trend._PUBLIC_DIR", public_dir),
        patch("scripts.gen_day_trend.build_day_trend_body", return_value=body) as mock_build,
        patch("g1_predict.modules.utils.image_output.plt") as mock_plt,
    ):
        generate_day_trend(race_code, RACE_DAY)

    race_dir = os.path.join(public_dir, "2026", f"{race_code}_天皇賞春")
    with open(os.path.join(race_dir, "当日の傾向.md"), encoding="utf-8") as f:
        assert f.read() == "# 【天皇賞春2026】当日の傾向\n\n## 当日の出目\n\n本文\n"
    assert not os.path.exists(os.path.join(race_dir, "前日の傾向.md"))
    mock_figure.savefig.assert_called_once_with(
        os.path.join(race_dir, "img", "race_day", "dynamics.png"), bbox_inches="tight"
    )
    mock_plt.close.assert_called_once_with(mock_figure)
    assert mock_build.call_args.args[2] == "天皇賞春"
    assert mock_build.call_args.args[3] is RACE_DAY
