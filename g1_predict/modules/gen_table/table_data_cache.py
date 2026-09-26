"""TableDataCache クラス。"""

from typing import Any

import pandas as pd
from keiba_data_interface import DataInterface
from keiba_data_interface.providers.mykeibadb_converters.convert_race_basic_info import (
    RACE_INFO_RENAME,
)
from keiba_data_interface.schema.columns import RACE_BASIC_INFO_COLUMNS
from mykeibadb import MasterGetter, RaceGetter, ShussobetsuGetter
from mykeibadb.analytics import ChokyoCondition, get_chokyo_match_days, get_race_display_names

from g1_predict.modules.gen_table.table_utils import DIRT_TRACK_CODES, SHIBA_TRACK_CODES, year_range


class TableDataCache:
    """レース・馬データの取得とキャッシュを管理する。

    Attributes:
        race_code (str): 16桁レースコード。
        race_year (int): レース開催年。
    """

    def __init__(self, race_code: str, race_year: int, di: DataInterface) -> None:
        self.race_code = race_code
        self.race_year = race_year
        self._di = di

        self._race_getter = RaceGetter()
        self._master_getter = MasterGetter()
        self._shussobetsu_getter = ShussobetsuGetter()

        self._kishu_df: pd.DataFrame | None = None
        self._seisansha_df: pd.DataFrame | None = None
        self._umagoto_df: pd.DataFrame | None = None
        self._past_perfs: dict[str, pd.DataFrame] = {}
        self._merged_past_perfs: dict[str, pd.DataFrame] = {}
        self._race_shosai_cache: dict[str, pd.Series | None] = {}
        self._kyosoba_cache: dict[str, pd.Series | None] = {}
        self._course_umagoto_cache: dict[
            tuple[str, str, int, int, str | None, int | None, str | None], pd.DataFrame
        ] = {}
        self._course_kyosoba_cache: dict[
            tuple[str, str, int, int, str | None], pd.DataFrame
        ] = {}
        self._past_race_codes_cache: dict[tuple[str, int], list[str]] = {}
        self._past_umagoto_cache: dict[tuple[str, int], pd.DataFrame] = {}
        self._past_kyosoba_cache: dict[tuple[str, int], pd.DataFrame] = {}
        self._horse_umagoto_cache: dict[str, pd.DataFrame] = {}
        self._race_field_cache: dict[str, pd.DataFrame] = {}
        self._race_display_name_cache: dict[str, str | None] = {}
        self._chokyo_match_days_cache: dict[
            tuple[Any, ...], dict[str, list[tuple[int, bool]]]
        ] = {}

    def get_kishu_df(self) -> pd.DataFrame:
        """現在レースの出走別騎手データを取得する（遅延初期化）。

        Returns:
            pd.DataFrame: SHUSSOBETSU_KISHUデータ。
        """
        if self._kishu_df is None:
            self._kishu_df = self._shussobetsu_getter.get_shussobetsu_kishu(
                race_code=self.race_code, convert_codes=False
            )
        return self._kishu_df

    def get_seisansha_df(self) -> pd.DataFrame:
        """現在レースの出走別生産者データを取得する（遅延初期化）。

        Returns:
            pd.DataFrame: SHUSSOBETSU_SEISANSHA2データ。
        """
        if self._seisansha_df is None:
            self._seisansha_df = self._shussobetsu_getter.get_shussobetsu_seisansha2(
                race_code=self.race_code, convert_codes=False
            )
        return self._seisansha_df

    def get_umagoto_df(self) -> pd.DataFrame:
        """現在レースの馬ごとデータを取得する（遅延初期化）。

        Returns:
            pd.DataFrame: UMAGOTO_RACE_JOHOデータ（convert_codes=True）。
        """
        if self._umagoto_df is None:
            self._umagoto_df = self._race_getter.get_umagoto_race_joho(
                race_code=self.race_code, convert_codes=True
            )
        return self._umagoto_df

    def get_kyosoba_row(self, horse_id: str) -> pd.Series | None:
        """馬の競走馬マスタ2レコードを取得する（キャッシュあり）。

        Args:
            horse_id (str): 血統登録番号。

        Returns:
            pd.Series | None: KYOSOBA_MASTER2の1行。データがない場合はNone。
        """
        if horse_id not in self._kyosoba_cache:
            df = self._master_getter.get_kyosoba_master2(
                ketto_toroku_bango=horse_id, convert_codes=False
            )
            self._kyosoba_cache[horse_id] = df.iloc[0] if not df.empty else None
        return self._kyosoba_cache[horse_id]

    def get_horse_umagoto_df(self, horse_id: str) -> pd.DataFrame:
        """馬の全出走記録を取得する（現レース除く・race_code降順・キャッシュあり）。

        Args:
            horse_id (str): 血統登録番号。

        Returns:
            pd.DataFrame: UMAGOTO_RACE_JOHOデータ（現レース除外・降順）。
        """
        if horse_id not in self._horse_umagoto_cache:
            df = self._race_getter.get_umagoto_race_joho(
                ketto_toroku_bango=horse_id, convert_codes=True
            )
            if not df.empty:
                df = df[df["race_code"].astype(str).str.strip() != self.race_code]
                df = df.sort_values("race_code", ascending=False).reset_index(drop=True)
            self._horse_umagoto_cache[horse_id] = df
        return self._horse_umagoto_cache[horse_id]

    def get_race_field_df(self, race_code: str) -> pd.DataFrame:
        """指定レースの全頭分の馬ごとデータを取得する（キャッシュあり）。

        Args:
            race_code (str): 16桁レースコード。

        Returns:
            pd.DataFrame: UMAGOTO_RACE_JOHOデータ（convert_codes=False）。
        """
        if race_code not in self._race_field_cache:
            self._race_field_cache[race_code] = self._race_getter.get_umagoto_race_joho(
                race_code=race_code, convert_codes=False
            )
        return self._race_field_cache[race_code]

    def get_race_display_name(self, race_code: str) -> str | None:
        """指定レースの表示用レース名を取得する（キャッシュあり）。

        重賞（JRA開催）は特別競走番号ごとに、開催日が最も新しいレースの
        競走名本題へ統一した名称を返す（mykeibadb.analytics.get_race_display_names）。

        Args:
            race_code (str): 16桁レースコード。

        Returns:
            str | None: 表示用レース名。race_shosaiに存在しない場合はNone。
        """
        if race_code not in self._race_display_name_cache:
            names = get_race_display_names(self._race_getter.connection_manager, [race_code])
            self._race_display_name_cache[race_code] = names.get(race_code)
        return self._race_display_name_cache[race_code]

    def get_chokyo_match_days(
        self,
        chokyo_condition: ChokyoCondition,
        days_from: int,
        days_to: int,
    ) -> dict[str, list[tuple[int, bool]]]:
        """現在レースの出走馬について、期間内の調教ごとの(何日前, 該当か)を取得する.

        chokyo_condition・days_from・days_toの組み合わせごとに1レース分を
        1回だけ問い合わせてキャッシュする（mykeibadb.analytics.get_chokyo_match_days）。

        Args:
            chokyo_condition (ChokyoCondition): 調教閾値条件リスト。
            days_from (int): 対象レース日から遡る日数の下限。
            days_to (int): 対象レース日から遡る日数の上限。

        Returns:
            dict[str, list[tuple[int, bool]]]: 血統登録番号 -> [(何日前, 該当か), ...]。
                調教記録なしの馬は空リスト。
        """
        cache_key = (
            tuple(
                (t.course, t.metric, t.furlong, t.max_value, t.min_value, t.tracen_kubun)
                for t in chokyo_condition
            ),
            days_from,
            days_to,
        )
        if cache_key not in self._chokyo_match_days_cache:
            self._chokyo_match_days_cache[cache_key] = get_chokyo_match_days(
                self._race_getter.connection_manager,
                self.race_code,
                chokyo_condition,
                days_from,
                days_to,
            )
        return self._chokyo_match_days_cache[cache_key]

    def build_past_df(self, horse_id: str) -> pd.DataFrame:
        """過去成績にRACE_BASIC_INFOをマージしたDataFrameを返す（キャッシュあり）。

        Args:
            horse_id (str): 血統登録番号。

        Returns:
            pd.DataFrame: 過去成績とRACE_BASIC_INFOをleft joinしたDataFrame（現レース除外）。
        """
        if horse_id in self._merged_past_perfs:
            return self._merged_past_perfs[horse_id]

        past_df = self._get_past_perfs(horse_id)
        if past_df.empty:
            self._merged_past_perfs[horse_id] = past_df
            return past_df

        race_codes = past_df["レースコード"].dropna().unique().tolist()
        missing = [rc for rc in race_codes if rc not in self._race_shosai_cache]
        if missing:
            self._load_race_shosai_batch(missing)

        valid_rows = [
            self._race_shosai_cache[rc]
            for rc in race_codes
            if self._race_shosai_cache.get(rc) is not None
        ]

        if valid_rows:
            rbi_df = pd.DataFrame(valid_rows)
            key = "レースコード"
            extra_cols = [
                c
                for c in RACE_BASIC_INFO_COLUMNS
                if c in rbi_df.columns and c != key and c not in past_df.columns
            ]
            if extra_cols:
                past_df = past_df.merge(rbi_df[[key] + extra_cols], on=key, how="left")

        past_df = past_df[past_df["レースコード"] != self.race_code].reset_index(drop=True)
        self._merged_past_perfs[horse_id] = past_df
        return past_df

    def get_course_umagoto_df(
        self,
        keibajo_code: str,
        track: str,
        kyori: int,
        years: int,
        course_kubun: str | None = None,
        week: int | None = None,
        track_condition: str | None = None,
    ) -> pd.DataFrame:
        """条件を指定してコース別の馬ごとデータを取得する（キャッシュあり）。

        Args:
            keibajo_code (str): 競馬場コード（例: "05"＝東京）。
            track (str): 馬場種別。"shiba"または"dirt"。
            kyori (int): 距離（メートル）。
            years (int): 遡る年数。
            course_kubun (str | None): コース区分（"A"〜"E"）。Noneの場合は絞り込まない。
            week (int | None): 各開催のコース区分内で絞り込む週（1始まり、1週=2日間）。
                Noneの場合は絞り込まない。
            track_condition (str | None): 馬場状態コード（例: "1"＝良）。Noneの場合は絞り込まない。

        Returns:
            pd.DataFrame: 条件に合致するUMAGOTO_RACE_JOHOデータ。
        """
        cache_key = (keibajo_code, track, kyori, years, course_kubun, week, track_condition)
        if cache_key in self._course_umagoto_cache:
            return self._course_umagoto_cache[cache_key]

        start_dt, end_dt = year_range(self.race_year, years)

        raw_shosai = self._race_getter.get_race_shosai(
            start_date=start_dt, end_date=end_dt, convert_codes=False
        )

        if raw_shosai.empty:
            self._course_umagoto_cache[cache_key] = pd.DataFrame()
            return pd.DataFrame()

        track_codes = SHIBA_TRACK_CODES if track == "shiba" else DIRT_TRACK_CODES
        mask = (
            raw_shosai["keibajo_code"].astype(str).str.strip() == str(keibajo_code)
        ) & (
            raw_shosai["track_code"].astype(str).str.strip().isin(track_codes)
        ) & (
            pd.to_numeric(raw_shosai["kyori"], errors="coerce") == kyori
        )
        filtered = raw_shosai.loc[mask].copy()

        if track_condition is not None and "babajotai_code" in filtered.columns:
            filtered = filtered[
                filtered["babajotai_code"].astype(str).str.strip() == track_condition
            ]

        if week is not None and not filtered.empty:
            filtered = self._filter_by_week_in_course(filtered, raw_shosai, keibajo_code, week)

        if course_kubun is not None and "course_kubun" in filtered.columns:
            filtered = filtered[
                filtered["course_kubun"].astype(str).str.strip() == course_kubun
            ]

        filtered_codes = filtered["race_code"].tolist()

        if not filtered_codes:
            self._course_umagoto_cache[cache_key] = pd.DataFrame()
            return pd.DataFrame()

        umagoto_df = self._race_getter.get_umagoto_race_joho(
            race_code=filtered_codes, convert_codes=False
        )
        self._course_umagoto_cache[cache_key] = umagoto_df
        return umagoto_df

    def get_past_umagoto_df(self, race_name_for_history: str, years: int) -> pd.DataFrame:
        """指定レース名の過去出走馬データを取得する（キャッシュあり）。

        Args:
            race_name_for_history (str): 集計対象のレース名（例: "東京優駿"）。
            years (int): 遡る年数。

        Returns:
            pd.DataFrame: 過去レースのUMAGOTO_RACE_JOHOデータ。
        """
        cache_key = (race_name_for_history, years)
        if cache_key in self._past_umagoto_cache:
            return self._past_umagoto_cache[cache_key]

        past_codes = self._get_past_race_codes(race_name_for_history, years)
        if not past_codes:
            self._past_umagoto_cache[cache_key] = pd.DataFrame()
            return pd.DataFrame()

        df = self._race_getter.get_umagoto_race_joho(
            race_code=past_codes, convert_codes=False
        )
        self._past_umagoto_cache[cache_key] = df
        return df

    def get_past_kyosoba_df(self, race_name_for_history: str, years: int) -> pd.DataFrame:
        """指定レースの過去出走馬の競走馬マスタを取得する（キャッシュあり）。

        Args:
            race_name_for_history (str): 集計対象のレース名（例: "東京優駿"）。
            years (int): 遡る年数。

        Returns:
            pd.DataFrame: 過去出走馬のKYOSOBA_MASTER2データ。
        """
        cache_key = (race_name_for_history, years)
        if cache_key in self._past_kyosoba_cache:
            return self._past_kyosoba_cache[cache_key]

        past_umagoto = self.get_past_umagoto_df(race_name_for_history, years)
        if past_umagoto.empty:
            self._past_kyosoba_cache[cache_key] = pd.DataFrame()
            return pd.DataFrame()

        horse_ids = past_umagoto["ketto_toroku_bango"].dropna().unique().tolist()
        if not horse_ids:
            self._past_kyosoba_cache[cache_key] = pd.DataFrame()
            return pd.DataFrame()

        df = self._master_getter.get_kyosoba_master2(
            ketto_toroku_bango=horse_ids, convert_codes=False
        )
        self._past_kyosoba_cache[cache_key] = df
        return df

    def get_course_kyosoba_df(
        self,
        keibajo_code: str,
        track: str,
        kyori: int,
        years: int,
        track_condition: str | None = None,
    ) -> pd.DataFrame:
        """コース出走馬の競走馬マスタを一括取得する（キャッシュあり）。

        Args:
            keibajo_code (str): 競馬場コード。
            track (str): 馬場種別。"shiba"または"dirt"。
            kyori (int): 距離（メートル）。
            years (int): 遡る年数。
            track_condition (str | None): 馬場状態コード。Noneの場合は絞り込まない。

        Returns:
            pd.DataFrame: コース出走馬のKYOSOBA_MASTER2データ。
        """
        cache_key = (keibajo_code, track, kyori, years, track_condition)
        if cache_key in self._course_kyosoba_cache:
            return self._course_kyosoba_cache[cache_key]

        umagoto_df = self.get_course_umagoto_df(
            keibajo_code, track, kyori, years, track_condition=track_condition
        )
        if umagoto_df.empty:
            self._course_kyosoba_cache[cache_key] = pd.DataFrame()
            return pd.DataFrame()

        horse_ids = umagoto_df["ketto_toroku_bango"].dropna().unique().tolist()
        if not horse_ids:
            self._course_kyosoba_cache[cache_key] = pd.DataFrame()
            return pd.DataFrame()

        df = self._master_getter.get_kyosoba_master2(
            ketto_toroku_bango=horse_ids, convert_codes=False
        )
        self._course_kyosoba_cache[cache_key] = df
        return df

    def _get_past_perfs(self, horse_id: str) -> pd.DataFrame:
        """馬の過去成績DataFrameを取得する（キャッシュあり）。

        Args:
            horse_id (str): 血統登録番号。

        Returns:
            pd.DataFrame: DataInterfaceの過去成績データ。
        """
        if horse_id not in self._past_perfs:
            self._past_perfs[horse_id] = self._di.get_past_performances(horse_id)
        return self._past_perfs[horse_id]

    def _get_past_race_codes(self, race_name_for_history: str, years: int) -> list[str]:
        """指定レース名の過去レースコード一覧を取得する（キャッシュあり）。

        Args:
            race_name_for_history (str): 集計対象のレース名（例: "東京優駿"）。
            years (int): 遡る年数。

        Returns:
            list[str]: 過去レースコードのリスト。現レースは除外済み。
        """
        cache_key = (race_name_for_history, years)
        if cache_key in self._past_race_codes_cache:
            return self._past_race_codes_cache[cache_key]

        start_dt, end_dt = year_range(self.race_year, years)

        raw_shosai = self._race_getter.get_race_shosai(
            start_date=start_dt, end_date=end_dt, convert_codes=False
        )

        if raw_shosai.empty:
            self._past_race_codes_cache[cache_key] = []
            return []

        mask = (
            raw_shosai["kyosomei_hondai"].astype(str).str.strip() == race_name_for_history
        ) & (
            raw_shosai["race_code"].astype(str).str.strip() != self.race_code
        )
        past_codes = raw_shosai.loc[mask, "race_code"].tolist()
        self._past_race_codes_cache[cache_key] = past_codes
        return past_codes

    def _filter_by_week_in_course(
        self,
        filtered: pd.DataFrame,
        raw_shosai: pd.DataFrame,
        keibajo_code: str,
        week: int,
    ) -> pd.DataFrame:
        """開催回・コース区分ごとの週番号でfilteredを絞り込む。

        週番号は「その開催回で、そのレースのコース区分が使われ始めた日から数えた暦週」
        （(開催日 − 同一開催回・同一コース区分の最初の開催日).days // 7 + 1）とする。
        course_kubunを絞り込んでいない場合も、レースごとに自身のコース区分を基準に
        週番号を計算するため、コース区分をまたいで正しく絞り込める。

        Args:
            filtered (pd.DataFrame): keibajo_code・track・kyori等で絞り込み済みのデータ。
            raw_shosai (pd.DataFrame): 期間内のRACE_SHOSAI生データ（convert_codes=False）。
            keibajo_code (str): 競馬場コード。
            week (int): 絞り込む週番号（1始まり）。

        Returns:
            pd.DataFrame: 週番号が一致する行のみのDataFrame。
        """
        week_df = self._build_week_in_course_df(raw_shosai, keibajo_code)
        merge_keys = ["keibajo_code", "kaisai_nen", "kaisai_kai", "kaisai_nichime"]
        filtered = filtered.copy()
        for col in merge_keys:
            filtered[col] = filtered[col].astype(str).str.strip()
        merged = filtered.merge(week_df, on=merge_keys, how="left")
        merged = merged[merged["week_in_course"] == week]
        return merged.drop(columns=["week_in_course"])

    def _build_week_in_course_df(
        self, raw_shosai: pd.DataFrame, keibajo_code: str
    ) -> pd.DataFrame:
        """競馬場ごとの開催日単位で週番号（暦週）を計算する。

        Args:
            raw_shosai (pd.DataFrame): 期間内のRACE_SHOSAI生データ（convert_codes=False）。
            keibajo_code (str): 競馬場コード。

        Returns:
            pd.DataFrame: keibajo_code・kaisai_nen・kaisai_kai・kaisai_nichime・
                week_in_courseの開催日単位DataFrame。
        """
        key_cols = [
            "keibajo_code",
            "kaisai_nen",
            "kaisai_kai",
            "kaisai_nichime",
            "kaisai_gappi",
            "course_kubun",
        ]
        day_df = raw_shosai[key_cols].astype(str)
        for col in key_cols:
            day_df[col] = day_df[col].str.strip()
        day_df = day_df[
            (day_df["keibajo_code"] == str(keibajo_code)) & (day_df["course_kubun"] != "")
        ]
        day_df = day_df.drop_duplicates(
            subset=["keibajo_code", "kaisai_nen", "kaisai_kai", "kaisai_nichime"]
        )
        day_df["race_date"] = pd.to_datetime(
            day_df["kaisai_nen"] + day_df["kaisai_gappi"], format="%Y%m%d"
        )
        day_df["first_date"] = day_df.groupby(
            ["keibajo_code", "kaisai_nen", "kaisai_kai", "course_kubun"]
        )["race_date"].transform("min")
        day_df["week_in_course"] = (
            (day_df["race_date"] - day_df["first_date"]).dt.days // 7
        ) + 1
        return day_df[
            ["keibajo_code", "kaisai_nen", "kaisai_kai", "kaisai_nichime", "week_in_course"]
        ]

    def _load_race_shosai_batch(self, race_codes: list[str]) -> None:
        """レースコード一覧を一括でRACE_SHOSAIから取得してキャッシュに格納する。

        Args:
            race_codes (list[str]): 取得対象のレースコードリスト。
        """
        if not race_codes:
            return
        raw_df = self._race_getter.get_race_shosai(race_code=race_codes, convert_codes=False)
        if raw_df.empty:
            for rc in race_codes:
                self._race_shosai_cache[rc] = None
            return
        df = raw_df.rename(columns=RACE_INFO_RENAME)
        found: set[str] = set()
        for _, row in df.iterrows():
            rc = str(row.get("レースコード", "")).strip()
            if rc:
                self._race_shosai_cache[rc] = row
                found.add(rc)
        for rc in race_codes:
            if rc not in found:
                self._race_shosai_cache[rc] = None
