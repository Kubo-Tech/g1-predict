"""項目に注入する開催条件の検証と、集計対象の絞り込みを行うモジュール。"""

from dataclasses import replace
from typing import Any

from mykeibadb.analytics import EntryFilter, RaceColFilter, RaceCondition

from ._course_days import fetch_course_days
from ._trend_loader import TrendContext, fetch_past_races
from ._trend_models import TrendCondition

_CONDITION_KEYS = frozenset(
    {"keibajo_codes", "course_kubun", "course_days", "kaisai_nichime", "babajotai_codes"}
)
_COURSE_KUBUN_VALUES = frozenset({"A", "B", "C", "D", "E"})
_BABAJOTAI_VALUES = frozenset({"1", "2", "3", "4"})


def parse_trend_condition(raw: dict[str, Any], item_name: str) -> TrendCondition:
    """YAML の condition を検証して TrendCondition に変換する。

    Args:
        raw (dict[str, Any]): 項目に注入された condition。
        item_name (str): 項目名（エラーメッセージ用）。

    Returns:
        TrendCondition: 検証済みの開催条件。

    Raises:
        ValueError: condition が空、未知のキーを含む、または値の型・内容が不正な場合。
    """
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"{item_name}: condition にはキーを1つ以上指定してください: {raw!r}")
    unknown_keys = set(raw) - _CONDITION_KEYS
    if unknown_keys:
        raise ValueError(
            f"{item_name}: condition に未対応のキーがあります: {sorted(unknown_keys)}"
        )

    course_kubun = raw.get("course_kubun")
    if course_kubun is not None and course_kubun not in _COURSE_KUBUN_VALUES:
        raise ValueError(f"{item_name}: course_kubun は A〜E で指定してください: {course_kubun!r}")
    babajotai_codes = _parse_list(raw, "babajotai_codes", str, item_name)
    if babajotai_codes is not None:
        invalid = [code for code in babajotai_codes if code not in _BABAJOTAI_VALUES]
        if invalid:
            raise ValueError(f"{item_name}: babajotai_codes は 1〜4 で指定してください: {invalid}")
    course_days = _parse_list(raw, "course_days", int, item_name)
    if course_days is not None and any(day < 1 for day in course_days):
        raise ValueError(f"{item_name}: course_days は1以上の整数で指定してください: {course_days}")
    return TrendCondition(
        keibajo_codes=_parse_list(raw, "keibajo_codes", str, item_name),
        course_kubun=course_kubun,
        course_days=course_days,
        kaisai_nichime=_parse_list(raw, "kaisai_nichime", int, item_name),
        babajotai_codes=babajotai_codes,
    )


def apply_trend_condition(
    context: TrendContext,
    condition: TrendCondition,
) -> tuple[RaceCondition, list[EntryFilter]]:
    """既定の集計対象を開催条件でさらに絞り込む。

    keibajo_codes・kaisai_nichime・babajotai_codes は RaceCondition に反映する。
    course_kubun・course_days は、条件に合う過去の開催のレースコードを求めて
    RaceColFilter で絞り込む。

    Args:
        context (TrendContext): 対象レースと既定の集計対象。
        condition (TrendCondition): 項目に注入された開催条件。

    Returns:
        RaceCondition: 絞り込み後のレース絞り込み条件。
        list[EntryFilter]: 追加するエントリフィルタ。

    Raises:
        ValueError: 競馬場コードが既定の集計対象の競馬場を含まない場合、
            または条件に合う開催が無い場合。
    """
    race_condition = context.condition
    if condition.keibajo_codes is not None:
        base_codes = race_condition.keibajo_codes or []
        keibajo_codes = [code for code in condition.keibajo_codes if code in base_codes]
        if not keibajo_codes:
            raise ValueError(
                f"keibajo_codes が集計対象の競馬場を含みません: {list(condition.keibajo_codes)}"
            )
        race_condition = replace(race_condition, keibajo_codes=keibajo_codes)
    if condition.kaisai_nichime is not None:
        race_condition = replace(race_condition, kaisai_nichime=list(condition.kaisai_nichime))
    if condition.babajotai_codes is not None:
        race_condition = replace(race_condition, babajotai_codes=list(condition.babajotai_codes))

    filters: list[EntryFilter] = []
    if condition.course_kubun is not None or condition.course_days is not None:
        race_codes = _find_course_race_codes(context, race_condition, condition)
        filters.append(RaceColFilter(column="u.race_code", values=race_codes))
    return race_condition, filters


def _find_course_race_codes(
    context: TrendContext,
    race_condition: RaceCondition,
    condition: TrendCondition,
) -> list[str]:
    """コース区分・コース区分の何日目に合う過去の開催のレースコードを返す。

    Args:
        context (TrendContext): 対象レースと既定の集計対象。
        race_condition (RaceCondition): 競馬場などで絞り込み済みの条件。
        condition (TrendCondition): 項目に注入された開催条件。

    Returns:
        list[str]: 条件に合うレースのレースコード。

    Raises:
        ValueError: 条件に合う開催が無い場合。
    """
    past_races = fetch_past_races(context.manager, race_condition)
    if condition.course_kubun is not None:
        past_races = past_races[past_races["course_kubun"] == condition.course_kubun]

    course_days_cache: dict[tuple[str, str], dict[str, int]] = {}
    race_codes: list[str] = []
    for _, race in past_races.iterrows():
        if condition.course_days is not None:
            cache_key = (str(race["keibajo_code"]), str(race["kaisai_nen"]))
            if cache_key not in course_days_cache:
                course_days_cache[cache_key] = fetch_course_days(context.manager, *cache_key)
            # コース区分が登録されていない開催日（ダートのみの開催日など）は対象外にする
            course_day = course_days_cache[cache_key].get(str(race["kaisai_gappi"]))
            if course_day not in condition.course_days:
                continue
        race_codes.append(str(race["race_code"]))
    if not race_codes:
        raise ValueError(f"条件に合う開催がありません: {condition}")
    return race_codes


def _parse_list(
    raw: dict[str, Any],
    key: str,
    item_type: type,
    item_name: str,
) -> tuple[Any, ...] | None:
    """condition の1キーを、指定した型の要素を持つ空でないタプルに変換する。

    Args:
        raw (dict[str, Any]): 項目に注入された condition。
        key (str): 変換するキー。
        item_type (type): 要素の型（str または int）。
        item_name (str): 項目名（エラーメッセージ用）。

    Returns:
        tuple[Any, ...] | None: 変換後の値。キーが無い場合は None。

    Raises:
        ValueError: 値が空のリスト、リストでない、または要素の型が不正な場合。
    """
    if key not in raw:
        return None
    value = raw[key]
    if not isinstance(value, list) or not value:
        raise ValueError(f"{item_name}: {key} は空でないリストで指定してください: {value!r}")
    for element in value:
        if not isinstance(element, item_type) or isinstance(element, bool):
            raise ValueError(
                f"{item_name}: {key} の要素は {item_type.__name__} で指定してください: {element!r}"
            )
    return tuple(value)
