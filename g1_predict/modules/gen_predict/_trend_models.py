"""傾向セクション生成に使うデータモデルと共有ユーティリティ。"""

from dataclasses import dataclass
from typing import Any

import pandas as pd

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
        tansho_total (int): 1着馬の単勝払戻金合計（円）。
        fukusho_total (int): 1〜3着馬の複勝払戻金合計（円）。
        total (int): 対象馬の総頭数。
    """

    first: int = 0
    second: int = 0
    third: int = 0
    fourth_plus: int = 0
    tansho_total: int = 0
    fukusho_total: int = 0
    total: int = 0


@dataclass
class Db:
    """傾向計算に必要なデータをまとめて保持するデータクラス。

    Attributes:
        past_race_codes (list[str]): 過去レースコードのリスト（昇順）。
        results (dict[str, pd.DataFrame]): レースコード -> 結果DataFrameのdict。
        payoffs (dict[str, pd.Series | None]): レースコード -> 払戻情報Seriesのdict。
        history (pd.DataFrame): 全出走馬の全履歴DataFrame（UMAGOTO、convert_codes=False）。
        shosai (dict[str, dict[str, str]]): レースコード -> レース詳細情報のdict。
        kyosoba (dict[str, pd.Series]): 血統登録番号 -> KYOSOBA_MASTER2のSeriesのdict。
        sire_finisher_sets (dict[tuple[Any, ...], set[str]]): キー -> 条件着順以内の馬名セットのdict。
        matched_years (int): コース条件に一致した年数。
    """

    past_race_codes: list[str]
    results: dict[str, pd.DataFrame]
    payoffs: dict[str, pd.Series | None]
    history: pd.DataFrame
    shosai: dict[str, dict[str, str]]
    kyosoba: dict[str, pd.Series]
    sire_finisher_sets: dict[tuple[Any, ...], set[str]]
    matched_years: int


def sire_cache_key(source: dict[str, Any]) -> tuple[Any, ...]:
    """source dict からハッシュ可能なキーを生成する。

    type キーを除いた各パラメータをソート済みのタプルに変換する。
    list 型の値は tuple に変換して hashable にする。

    Args:
        source (dict[str, Any]): sire_race_condition_finisher の source 設定dict。

    Returns:
        tuple[Any, ...]: ハッシュ可能なキー。
    """
    parts: list[Any] = []
    for k in sorted(k for k in source if k != "type"):
        v = source[k]
        parts.append(k)
        parts.append(tuple(v) if isinstance(v, list) else v)
    return tuple(parts)
