"""generate_past_race_dynamics の単体テスト。"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from matplotlib.figure import Figure

from g1_predict.modules.gen_past_race_dynamics.past_race_dynamics import PastRaceDynamicsBody
from scripts.gen_past_race_dynamics import generate_past_race_dynamics

_RACE_CODE = "2026092706040911"


@pytest.fixture
def public_dir(tmp_path: Path) -> str:
    """public ディレクトリを用意する。"""
    return str(tmp_path / "public")


def _run(public_dir: str, body: PastRaceDynamicsBody) -> None:
    race_getter = MagicMock()
    race_getter.get_race_shosai.return_value = pd.DataFrame(
        {"kyosomei_hondai": ["スプリンターズステークス"], "kaisai_nen": ["2026"]}
    )
    with (
        patch("scripts.gen_past_race_dynamics.RaceGetter", return_value=race_getter),
        patch("scripts.gen_past_race_dynamics._PUBLIC_DIR", public_dir),
        patch("scripts.gen_past_race_dynamics.build_past_race_dynamics_body", return_value=body),
    ):
        generate_past_race_dynamics(_RACE_CODE)


# 正常系
def test_generate_writes_article_with_title_and_body(public_dir: str) -> None:
    """タイトルに略称のレース名と年を使い、本文を続けて書き出す。"""
    _run(public_dir, PastRaceDynamicsBody(text="本文\n", images={}))
    path = os.path.join(
        public_dir, "2026", f"{_RACE_CODE}_スプリンターズS", "出走馬の過去走の展開評価.md"
    )
    with open(path, encoding="utf-8") as f:
        assert f.read() == "# 【スプリンターズS2026】出走馬の過去走の展開評価\n\n本文\n"


def test_generate_saves_images_under_article_dir(public_dir: str) -> None:
    """画像は記事ディレクトリからの相対パスで保存する。"""
    figure = Figure()
    figure.subplots()
    images = {"img/past_dynamics/2026090609040211.png": figure}
    body = PastRaceDynamicsBody(text="本文\n", images=images)
    _run(public_dir, body)
    image = os.path.join(
        public_dir,
        "2026",
        f"{_RACE_CODE}_スプリンターズS",
        "img",
        "past_dynamics",
        "2026090609040211.png",
    )
    assert os.path.exists(image)


# 準正常系
def test_generate_rejects_invalid_race_code(public_dir: str) -> None:
    """16桁の数字でないrace_codeはValueErrorになる。"""
    with pytest.raises(ValueError):
        generate_past_race_dynamics("abc")


def test_generate_does_not_write_article_when_saving_images_fails(public_dir: str) -> None:
    """画像の保存に失敗した場合は、記事を書き出さずに例外を送出する。"""
    body = PastRaceDynamicsBody(text="本文\n", images={"img/past_dynamics/x.png": Figure()})
    with (
        patch(
            "scripts.gen_past_race_dynamics.save_images", side_effect=ValueError("too many colors")
        ),
        pytest.raises(ValueError, match="too many colors"),
    ):
        _run(public_dir, body)
    path = os.path.join(
        public_dir, "2026", f"{_RACE_CODE}_スプリンターズS", "出走馬の過去走の展開評価.md"
    )
    assert not os.path.exists(path)
