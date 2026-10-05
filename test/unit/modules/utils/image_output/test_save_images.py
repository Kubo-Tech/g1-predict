"""save_images の単体テスト。"""

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from PIL import Image

from g1_predict.modules.utils.image_output import save_images

_MODULE = "g1_predict.modules.utils.image_output"


def _bar_figure() -> Figure:
    """面積の大きい棒と、面積の小さい棒を持つFigure。"""
    figure = Figure(figsize=(4, 3))
    ax = figure.subplots()
    ax.bar([0, 1], [1.0, 0.01], color=["#0072BD", "#D95319"])
    ax.set_title("title")
    return figure


def _rgb_set(image: Image.Image) -> set[tuple[int, int, int]]:
    pixels = np.asarray(image.convert("RGB")).reshape(-1, 3)
    return {tuple(int(v) for v in color) for color in np.unique(pixels, axis=0)}


# 正常系
def test_save_images_saves_palette_png_and_closes(tmp_path: Path) -> None:
    """記事ディレクトリ配下へ256色以下のパレットのPNGで保存し、保存後にcloseする。"""
    figure = _bar_figure()
    with patch(f"{_MODULE}.plt.close") as mock_close:
        save_images(str(tmp_path), {"img/race_result/x.png": figure})
    with Image.open(tmp_path / "img" / "race_result" / "x.png") as image:
        assert image.format == "PNG"
        assert image.mode == "P"
        assert len(_rgb_set(image)) <= 256
    mock_close.assert_called_once_with(figure)


def test_save_images_keeps_specified_colors(tmp_path: Path) -> None:
    """Figureに指定した色は、面積が小さくても元の色のまま残す。"""
    save_images(str(tmp_path), {"x.png": _bar_figure()})
    with Image.open(tmp_path / "x.png") as image:
        colors = _rgb_set(image)
    assert {(0x00, 0x72, 0xBD), (0xD9, 0x53, 0x19), (255, 255, 255), (0, 0, 0)} <= colors


def test_save_images_tight_bbox(tmp_path: Path) -> None:
    """余白を内容に合わせて切り詰めて保存する。"""
    figure = _bar_figure()
    width, height = figure.canvas.get_width_height()
    save_images(str(tmp_path), {"x.png": figure})
    with Image.open(tmp_path / "x.png") as image:
        assert image.size != (width, height)


def test_save_images_empty(tmp_path: Path) -> None:
    """画像が無い場合は何も作らない。"""
    save_images(str(tmp_path), {})
    assert list(tmp_path.iterdir()) == []


# 異常系
def test_save_images_too_many_specified_colors(tmp_path: Path) -> None:
    """画像に現れる指定色が256色を超える場合は例外を送出する。"""
    figure = Figure(figsize=(6, 6))
    ax = figure.subplots()
    ax.axis("off")
    ax.set_position((0, 0, 1, 1))
    for i in range(300):
        color = (i // 256 / 255, i % 256 / 255, 0.5)
        ax.add_patch(
            Rectangle(((i % 20) / 20, (i // 20) / 20), 0.05, 0.05, color=color, linewidth=0)
        )
    with pytest.raises(ValueError, match="256色を超えている"):
        save_images(str(tmp_path), {"x.png": figure})
