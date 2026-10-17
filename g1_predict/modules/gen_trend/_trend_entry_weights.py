"""今回の出走馬の馬体重の項目の判定に使う馬体重を決めるモジュール。

当日の馬体重は発走前の計量まで DB に入らないため、手に入る値を次の順に使う。

1. 全出走馬の当日の馬体重が DB にあれば、当日の馬体重
2. 調教後馬体重が発表されていれば、調教後馬体重
3. どちらも無ければ、前走の馬体重。前走が海外などで馬体重が無い馬は、さかのぼって最新の馬体重
"""

from dataclasses import dataclass

import pandas as pd
from mykeibadb.connection import ConnectionManager

# 出走取消・発走除外・競走除外の異常区分コード
_EXCLUDED_IJO_KUBUN_CODES = ["1", "2", "3"]
# 有効な馬体重（kg）の範囲。0 は計量前、999 は計量不能
_MIN_WEIGHT = 1
_MAX_WEIGHT = 998

_CHOKYO_NOTE = "※該当馬は調教後馬体重"
_PREV_NOTE = "※該当馬は前走馬体重"
_PREV_WITH_OLDER_NOTE = "※該当馬は前走馬体重。前走海外の場合は最新の馬体重"


@dataclass(frozen=True)
class EntryWeights:
    """出走馬の判定に使う馬体重と、表の下に書く注記。

    Attributes:
        values (dict[int, str]): 馬番 -> 馬体重（kg）の文字列。馬体重が無い馬は含まない。
        note (str): 表の下に書く注記。当日の馬体重を使う場合は空文字列。
    """

    values: dict[int, str]
    note: str


def resolve_entry_weights(
    manager: ConnectionManager,
    race_code: str,
    horses: pd.DataFrame,
    chokyo_bataiju: dict[str, int] | None,
) -> EntryWeights:
    """出走馬の判定に使う馬体重を、当日・調教後・前走の順に手に入るものから決める。

    Args:
        manager (ConnectionManager): DB接続マネージャ。
        race_code (str): 今回のレースの16桁のレースコード。
        horses (pd.DataFrame): 今回の出走馬。umaban（馬番）・bamei（馬名）の列を持つ。
        chokyo_bataiju (dict[str, int] | None): 馬名 -> 調教後馬体重（kg）。
            発表前で手に入らない場合は None。

    Returns:
        EntryWeights: 判定に使う馬体重と注記。

    Raises:
        ValueError: 調教後馬体重に載っていない出走馬がいる場合。
    """
    umabans = [int(umaban) for umaban in horses["umaban"]]
    race_day = _fetch_race_day_weights(manager, race_code)
    if all(umaban in race_day for umaban in umabans):
        return EntryWeights({umaban: str(race_day[umaban]) for umaban in umabans}, "")
    if chokyo_bataiju is not None:
        return EntryWeights(_to_chokyo_values(horses, chokyo_bataiju), _CHOKYO_NOTE)
    return _resolve_previous_weights(_fetch_past_weights(manager, race_code), umabans)


def _to_chokyo_values(horses: pd.DataFrame, chokyo_bataiju: dict[str, int]) -> dict[int, str]:
    """馬名ごとの調教後馬体重を、馬番ごとの馬体重の文字列にする。

    Args:
        horses (pd.DataFrame): 今回の出走馬。umaban（馬番）・bamei（馬名）の列を持つ。
        chokyo_bataiju (dict[str, int]): 馬名 -> 調教後馬体重（kg）。

    Returns:
        dict[int, str]: 馬番 -> 調教後馬体重（kg）の文字列。

    Raises:
        ValueError: 調教後馬体重に載っていない出走馬がいる場合。
    """
    missing = [name for name in horses["bamei"] if name not in chokyo_bataiju]
    if missing:
        raise ValueError(f"調教後馬体重が見つからない出走馬がいます: {missing}")
    return {
        int(umaban): str(chokyo_bataiju[name])
        for umaban, name in zip(horses["umaban"], horses["bamei"], strict=True)
    }


def _resolve_previous_weights(
    past: dict[int, list[int | None]], umabans: list[int]
) -> EntryWeights:
    """過去走の馬体重から、前走（無ければ最新）の馬体重と注記を決める。

    Args:
        past (dict[int, list[int | None]]): 馬番 -> 過去走の馬体重（kg）を新しい順に並べたもの。
            馬体重が無い出走は None。過去走が無い馬は含まない。
        umabans (list[int]): 今回の出走馬の馬番。

    Returns:
        EntryWeights: 判定に使う馬体重と注記。過去走に馬体重が1つも無い馬は values に含めず、
            注記に馬番を書く。
    """
    values: dict[int, str] = {}
    uses_older = False
    no_weight: list[int] = []
    for umaban in umabans:
        weights = past.get(umaban, [])
        latest = next((weight for weight in weights if weight is not None), None)
        if latest is None:
            no_weight.append(umaban)
            continue
        values[umaban] = str(latest)
        uses_older = uses_older or weights[0] is None
    notes = [_PREV_WITH_OLDER_NOTE if uses_older else _PREV_NOTE]
    if no_weight:
        notes.append(f"※{', '.join(str(umaban) for umaban in no_weight)}は馬体重情報なし")
    return EntryWeights(values, "  \n".join(notes))


def _fetch_race_day_weights(manager: ConnectionManager, race_code: str) -> dict[int, int]:
    """今回のレースの当日の馬体重を DB から取得する。

    Args:
        manager (ConnectionManager): DB接続マネージャ。
        race_code (str): 今回のレースの16桁のレースコード。

    Returns:
        dict[int, int]: 馬番 -> 当日の馬体重（kg）。計量前などで馬体重が無い馬は含まない。
    """
    sql = """
        SELECT TRIM(u.umaban)::INTEGER AS umaban, TRIM(u.bataiju) AS bataiju
        FROM umagoto_race_joho u
        WHERE u.race_code = %s AND NOT (u.ijo_kubun_code = ANY(%s))
    """
    rows = manager.fetch_dataframe(sql, params=(race_code, _EXCLUDED_IJO_KUBUN_CODES))
    weights = {
        int(umaban): _parse_weight(bataiju)
        for umaban, bataiju in zip(rows["umaban"], rows["bataiju"], strict=True)
    }
    return {umaban: weight for umaban, weight in weights.items() if weight is not None}


def _fetch_past_weights(manager: ConnectionManager, race_code: str) -> dict[int, list[int | None]]:
    """今回の出走馬の、今回のレースより前の出走ごとの馬体重を DB から取得する。

    出走取消・発走除外・競走除外の出走は含めない。海外の競走などで馬体重が無い出走は
    None として含める。

    Args:
        manager (ConnectionManager): DB接続マネージャ。
        race_code (str): 今回のレースの16桁のレースコード。

    Returns:
        dict[int, list[int | None]]: 今回の馬番 -> 過去走の馬体重（kg）を新しい順に並べたもの。
            過去走が無い馬は含まない。
    """
    sql = """
        SELECT TRIM(e.umaban)::INTEGER AS umaban,
               r.kaisai_nen || r.kaisai_gappi AS race_date,
               TRIM(u.bataiju) AS bataiju
        FROM umagoto_race_joho e
        JOIN race_shosai cur ON cur.race_code = e.race_code
        JOIN umagoto_race_joho u ON u.ketto_toroku_bango = e.ketto_toroku_bango
        JOIN race_shosai r ON r.race_code = u.race_code
        WHERE e.race_code = %s
          AND NOT (e.ijo_kubun_code = ANY(%s))
          AND NOT (u.ijo_kubun_code = ANY(%s))
          AND (r.kaisai_nen || r.kaisai_gappi) < (cur.kaisai_nen || cur.kaisai_gappi)
        ORDER BY umaban, race_date DESC
    """
    rows = manager.fetch_dataframe(
        sql, params=(race_code, _EXCLUDED_IJO_KUBUN_CODES, _EXCLUDED_IJO_KUBUN_CODES)
    )
    past: dict[int, list[int | None]] = {}
    for umaban, bataiju in zip(rows["umaban"], rows["bataiju"], strict=True):
        past.setdefault(int(umaban), []).append(_parse_weight(bataiju))
    return past


def _parse_weight(text: str | None) -> int | None:
    """DB の馬体重の文字列を数値にする。

    Args:
        text (str | None): 馬体重の文字列。

    Returns:
        int | None: 馬体重（kg）。空・計量前（0）・計量不能（999）の場合は None。
    """
    if text is None or not text.isdecimal():
        return None
    weight = int(text)
    return weight if _MIN_WEIGHT <= weight <= _MAX_WEIGHT else None
