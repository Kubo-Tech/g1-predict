"""save_images の単体テスト。"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from matplotlib.figure import Figure

from g1_predict.modules.utils.image_output import save_images


# 正常系
def test_save_images_saves_with_tight_bbox_and_closes(tmp_path: Path) -> None:
    """記事ディレクトリ配下へbbox_inches="tight"で保存し、保存後にcloseする。"""
    figure = MagicMock(spec=Figure)
    with patch("g1_predict.modules.utils.image_output.plt.close") as mock_close:
        save_images(str(tmp_path), {"img/race_result/x.png": figure})
    expected = os.path.join(str(tmp_path), "img/race_result/x.png")
    figure.savefig.assert_called_once_with(expected, bbox_inches="tight")
    mock_close.assert_called_once_with(figure)
    assert (tmp_path / "img" / "race_result").is_dir()


def test_save_images_empty(tmp_path: Path) -> None:
    """画像が無い場合は何も作らない。"""
    save_images(str(tmp_path), {})
    assert list(tmp_path.iterdir()) == []
