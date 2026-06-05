"""傾向セクション生成に使うデータモデル。"""

from dataclasses import dataclass

TREND_YEARS = 10
SIRE_YEARS = 30
OTHER_LABEL = "その他"


@dataclass
class RowStats:
    """1行分の集計値。

    Attributes:
        first (int): 1着頭数。
        second (int): 2着頭数。
        third (int): 3着頭数。
        fourth_plus (int): 着外頭数。
        tansho_kaishuu (float): 単勝回収率（%）。
        fukusho_kaishuu (float): 複勝回収率（%）。
        total (int): 対象馬の総頭数。
    """

    first: int = 0
    second: int = 0
    third: int = 0
    fourth_plus: int = 0
    tansho_kaishuu: float = 0.0
    fukusho_kaishuu: float = 0.0
    total: int = 0
