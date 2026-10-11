"""今回の出走馬が、各項目の表のどの行に当たるかを求めるモジュール。"""

import pandas as pd
from mykeibadb.analytics import get_race_entry_groups
from mykeibadb.connection import ConnectionManager
from mykeibadb.exceptions import MykeibaDBError

from ._trend_catalog import TrendItem
from ._trend_loader import TrendContext
from ._trend_stats import build_item_grouping

# 出走取消・発走除外・競走除外の異常区分コード
_EXCLUDED_IJO_KUBUN_CODES = ("1", "2", "3")


def fetch_entry_horses(manager: ConnectionManager, race_code: str) -> pd.DataFrame:
    """今回の出走馬の枠番・馬番・馬名を馬番順に返す。

    出走取消・発走除外・競走除外の馬は含めない。

    Args:
        manager (ConnectionManager): DB接続マネージャ。
        race_code (str): 16桁のレースコード。

    Returns:
        pd.DataFrame: 馬番順の出走馬。waku（枠番）・umaban（馬番）・bamei（馬名）の列を持つ。

    Raises:
        MykeibaDBError: 出走馬が DB に無い場合。
    """
    sql = """
        SELECT TRIM(u.wakuban)::INTEGER AS waku,
               TRIM(u.umaban)::INTEGER AS umaban,
               TRIM(u.bamei) AS bamei
        FROM umagoto_race_joho u
        WHERE u.race_code = %s AND NOT (u.ijo_kubun_code = ANY(%s))
        ORDER BY umaban
    """
    horses = manager.fetch_dataframe(sql, params=(race_code, list(_EXCLUDED_IJO_KUBUN_CODES)))
    if horses.empty:
        raise MykeibaDBError(f"出走馬が見つかりません: race_code={race_code}")
    return horses


def find_entry_rows(
    item: TrendItem,
    context: TrendContext,
    race_code: str,
) -> dict[int, list[str]]:
    """今回の出走馬が、項目の集計と同じ割り当てでどの行に当たるかを返す。

    集計と同じ GroupBy で出走馬のグループの値を求め、集計と同じ割り当てで行に変換する。
    項目に注入された開催条件は集計対象を絞るためのものなので、判定には使わない。
    今走の結果で値が決まる項目は、レース前に値が無いため空を返す。

    Args:
        item (TrendItem): 判定する項目。
        context (TrendContext): 対象レースと集計対象の情報。
        race_code (str): 今回のレースの16桁のレースコード。

    Returns:
        dict[int, list[str]]: 馬番 -> 当たる行のラベル。値が求まらない馬は含まない。
            dynamic の項目では、表に出ない行のラベルも含む。

    Raises:
        MykeibaDBError: 出走馬が DB に無い場合。
    """
    if item.uses_race_result:
        return {}
    grouping = build_item_grouping(
        item.config, context.manager, context.condition, lambda: [race_code]
    )
    groups = get_race_entry_groups(context.manager, race_code, grouping.group_by)
    return {
        horse_num: grouping.assign_rows(group)
        for horse_num, group in groups.items()
        if group is not None
    }
