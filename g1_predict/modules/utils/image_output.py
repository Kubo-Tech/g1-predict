"""記事に貼る画像を記事ディレクトリへ保存するユーティリティ。"""

import os

from matplotlib import pyplot as plt
from matplotlib.figure import Figure


def save_images(race_dir: str, images: dict[str, Figure]) -> None:
    """画像を記事ディレクトリへ保存する。

    保存後にFigureをcloseし、メモリを解放する。

    Args:
        race_dir (str): レース単位の出力ディレクトリのパス。
        images (dict[str, Figure]): 記事ディレクトリからの相対パス → Figure。
    """
    for relative_path, figure in images.items():
        image_path = os.path.join(race_dir, relative_path)
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        # タイトル・軸ラベルが画像の外に切れないよう余白を内容に合わせる
        figure.savefig(image_path, bbox_inches="tight")
        plt.close(figure)
