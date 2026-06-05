"""TableContext クラス。"""

from typing import Any

import pandas as pd
from keiba_data_interface import DataInterface

from g1_predict.modules.gen_table.table_data_cache import TableDataCache
from g1_predict.modules.gen_table.table_stat import (
    kishu_continuity,
    kishu_course_stat,
    seisansha_race_stat,
    sire_course_stat,
    sire_race_chakujun,
    sire_race_stat,
    waku_stat,
)
from g1_predict.modules.gen_table.table_utils import filter_by_horse, filter_df, to_cell_value


class TableContext:
    """テーブル生成に必要なデータを保持するコンテキスト。

    Attributes:
        race_code (str): 16桁レースコード。
        race_year (int): レース開催年。
        race_name (str): レース名（例: "東京優駿"）。
        entry_df (pd.DataFrame): 出走表DataFrame。
    """

    def __init__(
        self,
        race_code: str,
        race_year: int,
        race_name: str,
        entry_df: pd.DataFrame,
        di: DataInterface,
    ) -> None:
        self.race_code = race_code
        self.race_year = race_year
        self.race_name = race_name
        self.entry_df = entry_df
        self._cache = TableDataCache(race_code, race_year, di)

    def get_value(self, horse: pd.Series, horse_id: str, source: dict[str, Any]) -> Any:
        """ソース設定に従い値を取得する。

        Args:
            horse (pd.Series): 出走馬の出走表データ（entry_dfの1行）。
            horse_id (str): 血統登録番号。
            source (dict[str, Any]): YAMLのsource設定（typeキーを持つ辞書）。

        Returns:
            Any: 取得した値。データがない場合はNone。

        Raises:
            ValueError: 不明なsource typeが指定された場合。
        """
        src_type = source["type"]

        if src_type == "entry_field":
            return to_cell_value(horse.get(source["field"]))

        if src_type == "past_count":
            filters = source.get("filters", [])
            past_df = self._cache.build_past_df(horse_id)
            if past_df.empty:
                return 0
            return len(filter_df(past_df, filters))

        if src_type == "past_field":
            filters = source.get("filters", [])
            field = source["field"]
            past_df = self._cache.build_past_df(horse_id)
            if past_df.empty:
                return None
            filtered = filter_df(past_df, filters) if filters else past_df
            idx = int(source.get("index", 0))
            if len(filtered) <= idx or field not in filtered.columns:
                return None
            return to_cell_value(filtered.iloc[idx][field])

        if src_type == "debut_field":
            filters = source.get("filters", [])
            field = source["field"]
            past_df = self._cache.build_past_df(horse_id)
            if past_df.empty:
                return None
            filtered = filter_df(past_df, filters) if filters else past_df
            if filtered.empty or field not in filtered.columns:
                return None
            return to_cell_value(filtered.iloc[-1][field])

        if src_type == "past_best":
            filters = source.get("filters", [])
            field = source["field"]
            agg = source.get("agg", "min")
            past_df = self._cache.build_past_df(horse_id)
            if past_df.empty:
                return None
            filtered = filter_df(past_df, filters) if filters else past_df
            if filtered.empty or field not in filtered.columns:
                return None
            series = pd.to_numeric(filtered[field], errors="coerce").dropna()
            if series.empty:
                return None
            return float(series.min() if agg == "min" else series.max())

        if src_type in ("kishu_venue_stat", "kishu_kyori_stat"):
            kishu_df = self._cache.get_kishu_df()
            if kishu_df.empty:
                return None
            rows = filter_by_horse(kishu_df, horse_id)
            if rows.empty:
                return None
            period = source.get("period", "")
            col = f"{source['field']}_{period}" if period else source["field"]
            if col not in rows.columns:
                return None
            return to_cell_value(rows.iloc[0][col])

        if src_type == "seisansha_stat":
            seisansha_df = self._cache.get_seisansha_df()
            if seisansha_df.empty:
                return None
            rows = filter_by_horse(seisansha_df, horse_id)
            if rows.empty:
                return None
            period = source.get("period", "")
            col = f"{source['field']}_{period}" if period else source["field"]
            if col not in rows.columns:
                return None
            return to_cell_value(rows.iloc[0][col])

        if src_type == "kyosoba_field":
            kyosoba_row = self._cache.get_kyosoba_row(horse_id)
            if kyosoba_row is None:
                return None
            field = source["field"]
            return to_cell_value(kyosoba_row.get(field))

        if src_type == "umagoto_field":
            umagoto_df = self._cache.get_umagoto_df()
            if umagoto_df.empty:
                return None
            rows = filter_by_horse(umagoto_df, horse_id)
            if rows.empty:
                return None
            field = source["field"]
            if field not in rows.columns:
                return None
            return to_cell_value(rows.iloc[0][field])

        if src_type == "recent_umagoto_field":
            df = self._cache.get_horse_umagoto_df(horse_id)
            if df.empty:
                return None
            field = source["field"]
            if field not in df.columns:
                return None
            series = df[field].dropna()
            if series.empty:
                return None
            return to_cell_value(series.iloc[0])

        if src_type == "kishu_continuity":
            return kishu_continuity(horse_id, self._cache)

        if src_type == "sire_race_chakujun":
            return sire_race_chakujun(horse_id, source, self.race_name, self._cache)

        if src_type == "waku_stat":
            return waku_stat(horse_id, source, self._cache)

        if src_type == "kishu_course_stat":
            return kishu_course_stat(horse_id, source, self._cache)

        if src_type == "seisansha_race_stat":
            return seisansha_race_stat(horse_id, source, self.race_name, self._cache)

        if src_type == "sire_race_stat":
            return sire_race_stat(horse_id, source, self.race_name, self._cache)

        if src_type == "sire_course_stat":
            return sire_course_stat(horse_id, source, self._cache)

        raise ValueError(f"不明なsource type: {src_type}")
