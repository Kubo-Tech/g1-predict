"""記事に貼る画像を記事ディレクトリへ保存するユーティリティ。"""

import io
import os

import numpy as np
import numpy.typing as npt
from matplotlib import pyplot as plt
from matplotlib.colors import to_rgba_array
from matplotlib.figure import Figure
from PIL import Image

# 減色後の色数（PNGのパレットの上限）
_PALETTE_SIZE = 256


def save_images(race_dir: str, images: dict[str, Figure]) -> None:
    """画像を256色に減色したPNGで記事ディレクトリへ保存する。

    Figureの描画に指定した不透明な色はパレットに必ず入れ、元の色のまま残す。
    パレットの残りは画素数の多い色で埋め、パレットに無い色（文字や線の縁の中間色など）は
    最も近いパレットの色に置き換える。
    保存後にFigureをcloseし、メモリを解放する。

    Args:
        race_dir (str): レース単位の出力ディレクトリのパス。
        images (dict[str, Figure]): 記事ディレクトリからの相対パス → Figure。

    Raises:
        ValueError: 画像に現れるFigureの指定色が256色を超える場合。
    """
    for relative_path, figure in images.items():
        image_path = os.path.join(race_dir, relative_path)
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        buffer = io.BytesIO()
        # タイトル・軸ラベルが画像の外に切れないよう余白を内容に合わせる
        figure.savefig(buffer, format="png", bbox_inches="tight")
        with Image.open(buffer) as image:
            pixels = np.asarray(image.convert("RGB"))
        _quantize(pixels, _figure_colors(figure)).save(image_path, optimize=True)
        plt.close(figure)


def _figure_colors(figure: Figure) -> npt.NDArray[np.int_]:
    """Figureの描画に指定した不透明な色を返す。

    半透明の色は背景と混ざって描画されるため含めない。

    Args:
        figure (Figure): 対象のFigure。

    Returns:
        np.ndarray: RGB（0〜255の整数）の配列。形状は (色数, 3)。
    """
    colors: list[npt.NDArray[np.float64]] = []
    for artist in figure.findobj():
        for getter in ("get_facecolor", "get_edgecolor", "get_color"):
            if not hasattr(artist, getter):
                continue
            value = getattr(artist, getter)()
            if isinstance(value, str) and value in ("none", "auto"):
                continue
            rgba = to_rgba_array(value)
            colors.append(rgba[rgba[:, 3] == 1, :3])
    rgb = np.round(np.concatenate(colors) * 255).astype(int)
    return np.unique(rgb, axis=0)


def _quantize(
    pixels: npt.NDArray[np.uint8], required_colors: npt.NDArray[np.int_]
) -> Image.Image:
    """画像を、指定した色を必ず含む256色以下のパレット画像にする。

    Args:
        pixels (np.ndarray): RGBの画素配列。形状は (高さ, 幅, 3)。
        required_colors (np.ndarray): 画像に現れればパレットに必ず入れる色。形状は (色数, 3)。

    Returns:
        Image.Image: パレット（Pモード）の画像。

    Raises:
        ValueError: 画像に現れる指定色が256色を超える場合。
    """
    # RGBを1つの整数にまとめてから数える（3列のままより速い）
    codes = pixels.reshape(-1, 3).astype(np.int64) @ np.array([1 << 16, 1 << 8, 1])
    unique_codes, inverse, counts = np.unique(codes, return_inverse=True, return_counts=True)
    colors = np.stack(
        [(unique_codes >> 16) & 0xFF, (unique_codes >> 8) & 0xFF, unique_codes & 0xFF], axis=1
    )
    # 画像に現れない指定色はパレットに入れる必要がない
    required_codes = required_colors.astype(np.int64) @ np.array([1 << 16, 1 << 8, 1])
    is_required = np.isin(unique_codes, required_codes)
    if is_required.sum() > _PALETTE_SIZE:
        raise ValueError(f"Figureに指定した色が{_PALETTE_SIZE}色を超えている: {is_required.sum()}")
    others = colors[~is_required][np.argsort(-counts[~is_required], kind="stable")]
    palette = np.concatenate([colors[is_required], others])[:_PALETTE_SIZE]
    distances = ((colors[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)
    indices = distances.argmin(axis=1)[inverse.ravel()].reshape(pixels.shape[:2])
    height, width = pixels.shape[:2]
    image = Image.frombytes("P", (width, height), indices.astype(np.uint8).tobytes())
    image.putpalette(palette.astype(np.uint8).flatten().tolist())
    return image
