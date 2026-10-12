"""generate_dynamics_history の単体テスト。"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from matplotlib.figure import Figure

from g1_predict.modules.gen_dynamics_history.dynamics_history import DynamicsHistoryBody
from scripts.gen_dynamics_history import generate_dynamics_history, main

_RACE_CODE = "2026101808040711"


# 正常系
def test_generate_dynamics_history_writes_article(tmp_path: Path) -> None:
    """記事が {race_code}_{race_name}/過去の展開.md に出力される。"""
    public_dir = str(tmp_path / "public")
    with (
        patch("scripts.gen_dynamics_history.load_race_info", return_value=_race_info()) as load,
        patch("scripts.gen_dynamics_history.build_dynamics_history", return_value=_body()),
        patch("scripts.gen_dynamics_history.save_images"),
        patch("scripts.gen_dynamics_history._PUBLIC_DIR", public_dir),
    ):
        generate_dynamics_history(_RACE_CODE, "0018")
    load.assert_called_once_with(_RACE_CODE, "0018")
    path = os.path.join(public_dir, "2026", f"{_RACE_CODE}_秋華賞", "過去の展開.md")
    with open(path, encoding="utf-8") as f:
        assert f.read() == "# 【秋華賞2026】過去10年の展開\n"


def test_generate_dynamics_history_saves_images_before_article(tmp_path: Path) -> None:
    """画像を保存してから記事を書き出す。"""
    public_dir = str(tmp_path / "public")
    race_dir = os.path.join(public_dir, "2026", f"{_RACE_CODE}_秋華賞")
    article = os.path.join(race_dir, "過去の展開.md")
    body = _body()
    article_existed: list[bool] = []

    def fake_save(directory: str, images: dict[str, Figure]) -> None:
        assert directory == race_dir
        assert images is body.images
        article_existed.append(os.path.exists(article))

    with (
        patch("scripts.gen_dynamics_history.load_race_info", return_value=_race_info()),
        patch("scripts.gen_dynamics_history.build_dynamics_history", return_value=body),
        patch("scripts.gen_dynamics_history.save_images", side_effect=fake_save),
        patch("scripts.gen_dynamics_history._PUBLIC_DIR", public_dir),
    ):
        generate_dynamics_history(_RACE_CODE)
    assert article_existed == [False]
    assert os.path.exists(article)


def test_generate_dynamics_history_no_article_when_save_fails(tmp_path: Path) -> None:
    """画像の保存に失敗したときは記事を書き出さない。"""
    public_dir = str(tmp_path / "public")
    with (
        patch("scripts.gen_dynamics_history.load_race_info", return_value=_race_info()),
        patch("scripts.gen_dynamics_history.build_dynamics_history", return_value=_body()),
        patch("scripts.gen_dynamics_history.save_images", side_effect=OSError("disk")),
        patch("scripts.gen_dynamics_history._PUBLIC_DIR", public_dir),
        pytest.raises(OSError),
    ):
        generate_dynamics_history(_RACE_CODE)
    assert not os.path.exists(
        os.path.join(public_dir, "2026", f"{_RACE_CODE}_秋華賞", "過去の展開.md")
    )


def test_main_passes_arguments() -> None:
    """--race-code と --tokubetsu-kyoso-bango が渡される。"""
    argv = ["prog", "--race-code", _RACE_CODE, "--tokubetsu-kyoso-bango", "0018"]
    with (
        patch.object(sys, "argv", argv),
        patch("scripts.gen_dynamics_history.generate_dynamics_history") as generate,
    ):
        main()
    generate.assert_called_once_with(_RACE_CODE, "0018")


def test_main_tokubetsu_kyoso_bango_is_optional() -> None:
    """--tokubetsu-kyoso-bango を省略すると None が渡される。"""
    with (
        patch.object(sys, "argv", ["prog", "--race-code", _RACE_CODE]),
        patch("scripts.gen_dynamics_history.generate_dynamics_history") as generate,
    ):
        main()
    generate.assert_called_once_with(_RACE_CODE, None)


# 異常系
def test_generate_dynamics_history_invalid_race_code_raises() -> None:
    """16桁の数字でない race_code は ValueError。"""
    with pytest.raises(ValueError):
        generate_dynamics_history("123")


def test_generate_dynamics_history_race_not_in_db_raises() -> None:
    """レースが DB に無い場合、load_race_info の ValueError がそのまま出る。"""
    with (
        patch(
            "scripts.gen_dynamics_history.load_race_info", side_effect=ValueError("DBにありません")
        ),
        patch("scripts.gen_dynamics_history.build_dynamics_history") as build,
        pytest.raises(ValueError, match="DBにありません"),
    ):
        generate_dynamics_history(_RACE_CODE)
    build.assert_not_called()


def test_main_requires_race_code() -> None:
    """--race-code が無いと終了する。"""
    with patch.object(sys, "argv", ["prog"]), pytest.raises(SystemExit):
        main()


def _race_info() -> pd.DataFrame:
    """秋華賞2026のレース基本情報を作る。

    Returns:
        pd.DataFrame: load_race_info() の戻り値の代わり。
    """
    return pd.DataFrame({"kyosomei_hondai": ["秋華賞"], "kaisai_nen": ["2026"]})


def _body() -> DynamicsHistoryBody:
    """画像を1枚持つ記事本文を作る。

    Returns:
        DynamicsHistoryBody: build_dynamics_history() の戻り値の代わり。
    """
    return DynamicsHistoryBody(
        content="# 【秋華賞2026】過去10年の展開\n", images={"img/dynamics_history/a.png": Figure()}
    )
