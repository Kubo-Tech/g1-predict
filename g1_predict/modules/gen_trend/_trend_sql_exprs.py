"""傾向表の集計項目に使う SQL 式を組み立てるモジュール。

ここで組み立てる式は `GroupBy(kind="race_col", column=<式>)` に渡す。
式は `umagoto_race_joho u`（集計対象レースへの出走）と `race_shosai r`（そのレース）を参照できる。
馬の過去走が必要な式は、集計対象レースに出走した全馬の過去走を1回だけ集計して
`{集計対象レースのコード}{血統登録番号}` をキーとする jsonb に畳み込み、出走ごとに引く。
馬ごとの相関サブクエリにすると、血統登録番号のインデックスが無いため全件走査が出走ごとに走る。
"""

# 4角通過順位。数字でない値と0は対象外にする
CORNER4_JUNI_EXPR = (
    "(CASE WHEN TRIM(u.corner4_juni) ~ '^[0-9]+$' "
    "THEN NULLIF(TRIM(u.corner4_juni)::INTEGER, 0) END)"
)

# 馬体重（kg）。0（計量前）と999（計量不能）は対象外にする
HORSE_WEIGHT_EXPR = (
    "(CASE WHEN TRIM(u.bataiju) ~ '^[0-9]+$' "
    "AND TRIM(u.bataiju)::INTEGER BETWEEN 1 AND 998 "
    "THEN TRIM(u.bataiju)::INTEGER END)"
)

# 誕生月
BIRTH_MONTH_EXPR = (
    "(SELECT NULLIF(SUBSTRING(km.seinengappi FROM 5 FOR 2)::INTEGER, 0) "
    "FROM kyosoba_master2 km WHERE km.ketto_toroku_bango = u.ketto_toroku_bango)"
)

# 過去走として有効な着順（数字2桁で00でない）
_VALID_RUN_SQL = "kakutei_chakujun ~ '^[0-9]{2}$' AND kakutei_chakujun != '00'"
# 実際に出走した過去走（出走取消・発走除外・競走除外を除く。競走中止などは含む）
_STARTED_RUN_SQL = "TRIM(ijo_kubun) NOT IN ('1', '2', '3')"

# 競走条件コード（年齢別の5列の最大値）
_JOKEN_SQL = (
    "GREATEST("
    "NULLIF(TRIM(r2.kyoso_joken_code_2sai), '')::INTEGER, "
    "NULLIF(TRIM(r2.kyoso_joken_code_3sai), '')::INTEGER, "
    "NULLIF(TRIM(r2.kyoso_joken_code_4sai), '')::INTEGER, "
    "NULLIF(TRIM(r2.kyoso_joken_code_5sai_ijo), '')::INTEGER, "
    "NULLIF(TRIM(r2.kyoso_joken_code_saijakunen), '')::INTEGER)"
)

# 過去走のクラス。history CTE の列を参照する
_RACE_CLASS_SQL = (
    "CASE WHEN grade_code = 'A' THEN 'G1' "
    "WHEN grade_code = 'B' THEN 'G2' "
    "WHEN grade_code = 'C' THEN 'G3' "
    "WHEN grade_code = 'L' THEN 'リステッド' "
    "WHEN grade_code = 'D' THEN 'オープン' "
    "WHEN joken = 999 THEN 'オープン' "
    "WHEN joken = 16 THEN '3勝クラス' "
    "WHEN joken = 10 THEN '2勝クラス' "
    "WHEN joken = 5 THEN '1勝クラス' "
    "WHEN joken = 703 THEN '未勝利' "
    "WHEN joken = 701 THEN '新馬' "
    "WHEN keibajo_code ~ '^[0-9]+$' AND keibajo_code BETWEEN '30' AND '61' THEN '地方' "
    "WHEN keibajo_code ~ '[A-Za-z]' THEN '海外' END"
)

# 美浦所属で中山・東京、栗東所属で阪神・京都・中京のレースは輸送なし
_NO_TRANSPORT_SQL = (
    "((TRIM({tozai}) = '1' AND {keibajo} IN ('05', '06')) "
    "OR (TRIM({tozai}) = '2' AND {keibajo} IN ('07', '08', '09')))"
)

# 過去走の馬場状態コード。芝のレースは芝、ダートのレースはダートの馬場状態を使う
_BABA_SQL = (
    "CASE WHEN TRIM(r2.track_code) BETWEEN '23' AND '29' "
    "THEN NULLIF(NULLIF(TRIM(r2.dirt_babajotai_code), ''), '0') "
    "ELSE NULLIF(NULLIF(TRIM(r2.shiba_babajotai_code), ''), '0') END"
)

_RACE_CODE_LENGTH = 16
_GOOD_BABA_CODES = ("1",)
_SOFT_BABA_CODES = ("2", "3", "4")


def build_prev_corner4_juni_expr(race_codes: list[str]) -> str:
    """前走の4角通過順位を返す式を組み立てる。

    Args:
        race_codes (list[str]): 集計対象レースのレースコード。

    Returns:
        str: 前走の4角通過順位（数字でない値と0は NULL）を返す SQL 式。
    """
    select_sql = (
        "SELECT DISTINCT ON (ketto, rc) rc || ketto AS k, "
        "CASE WHEN TRIM(corner4_juni) ~ '^[0-9]+$' "
        "THEN NULLIF(TRIM(corner4_juni)::INTEGER, 0) END AS v "
        f"FROM hist WHERE {_VALID_RUN_SQL} "
        "ORDER BY ketto, rc, d2 DESC"
    )
    return _history_lookup_expr(race_codes, select_sql)


def build_prev_distance_diff_expr(race_codes: list[str]) -> str:
    """前走の距離から集計対象レースの距離を引いた差を返す式を組み立てる。

    Args:
        race_codes (list[str]): 集計対象レースのレースコード。

    Returns:
        str: 前走距離 - 集計対象レースの距離（m）を返す SQL 式。
    """
    select_sql = (
        "SELECT DISTINCT ON (ketto, rc) rc || ketto AS k, kyori2 - kyori3 AS v "
        f"FROM hist WHERE {_VALID_RUN_SQL} "
        "ORDER BY ketto, rc, d2 DESC"
    )
    return _history_lookup_expr(race_codes, select_sql)


def build_prev_race_class_expr(race_codes: list[str]) -> str:
    """前走のクラスを返す式を組み立てる。

    Args:
        race_codes (list[str]): 集計対象レースのレースコード。

    Returns:
        str: 前走のクラス（G1・G2・G3・リステッド・オープン・3勝クラス・2勝クラス・
            1勝クラス・未勝利・新馬・地方・海外）を返す SQL 式。
            該当しない前走は NULL。
    """
    select_sql = (
        f"SELECT DISTINCT ON (ketto, rc) rc || ketto AS k, {_RACE_CLASS_SQL} AS v "
        f"FROM hist WHERE {_VALID_RUN_SQL} "
        "ORDER BY ketto, rc, d2 DESC"
    )
    return _history_lookup_expr(race_codes, select_sql)


def build_prev_race_finish_by_class_expr(race_codes: list[str], race_class: str) -> str:
    """前走が指定クラスだった場合の前走の着順を返す式を組み立てる。

    Args:
        race_codes (list[str]): 集計対象レースのレースコード。
        race_class (str): 前走のクラス。`build_prev_race_class_expr` が返すクラス名。

    Returns:
        str: 前走が race_class だった場合は前走の着順、それ以外は NULL を返す SQL 式。

    Raises:
        ValueError: race_class に SQL の文字列リテラルへ埋め込めない文字が含まれる場合。
    """
    if "'" in race_class:
        raise ValueError(f"race_class に使えない文字が含まれています: {race_class!r}")
    select_sql = (
        "SELECT DISTINCT ON (ketto, rc) rc || ketto AS k, "
        f"CASE WHEN ({_RACE_CLASS_SQL}) = '{race_class}' "
        "THEN CAST(kakutei_chakujun AS INTEGER) END AS v "
        f"FROM hist WHERE {_VALID_RUN_SQL} "
        "ORDER BY ketto, rc, d2 DESC"
    )
    return _history_lookup_expr(race_codes, select_sql)


def build_transport_expr(race_codes: list[str]) -> str:
    """輸送の有無を返す式を組み立てる。

    Args:
        race_codes (list[str]): 集計対象レースのレースコード。

    Returns:
        str: 輸送なし・輸送あり・初輸送のいずれかを返す SQL 式。
            過去のレースの輸送の有無は、そのレース時点の所属とそのレースの競馬場で判定する。
    """
    no_transport_now = _NO_TRANSPORT_SQL.format(
        tozai="u.tozai_shozoku_code", keibajo="r.keibajo_code"
    )
    no_transport_hist = _NO_TRANSPORT_SQL.format(tozai="tozai", keibajo="keibajo_code")
    select_sql = (
        "SELECT rc || ketto AS k, "
        f"BOOL_OR(NOT {no_transport_hist}) AS v "
        f"FROM hist WHERE {_STARTED_RUN_SQL} "
        "GROUP BY ketto, rc"
    )
    lookup = _history_lookup_expr(race_codes, select_sql)
    return (
        f"(CASE WHEN {no_transport_now} THEN '輸送なし' "
        f"WHEN COALESCE(({lookup})::BOOLEAN, FALSE) THEN '輸送あり' "
        "ELSE '初輸送' END)"
    )


def build_good_baba_top3_count_expr(race_codes: list[str]) -> str:
    """良馬場での3着以内の回数を返す式を組み立てる。

    Args:
        race_codes (list[str]): 集計対象レースのレースコード。

    Returns:
        str: 集計対象レースより前に、良馬場で3着以内に入った回数を返す SQL 式。
    """
    return _build_baba_top3_count_expr(race_codes, _GOOD_BABA_CODES)


def build_soft_baba_top3_count_expr(race_codes: list[str]) -> str:
    """稍重以上の馬場での3着以内の回数を返す式を組み立てる。

    Args:
        race_codes (list[str]): 集計対象レースのレースコード。

    Returns:
        str: 集計対象レースより前に、稍重・重・不良の馬場で3着以内に入った回数を返す SQL 式。
    """
    return _build_baba_top3_count_expr(race_codes, _SOFT_BABA_CODES)


def build_debut_month_expr(race_codes: list[str]) -> str:
    """デビュー月を返す式を組み立てる。

    Args:
        race_codes (list[str]): 集計対象レースのレースコード。

    Returns:
        str: その馬が最初に出走したレース（出走取消・発走除外・競走除外を除き、
            競走中止などは含む）の月を返す SQL 式。
    """
    select_sql = (
        "SELECT DISTINCT ON (ketto, rc) rc || ketto AS k, "
        "SUBSTRING(d2 FROM 5 FOR 2)::INTEGER AS v "
        f"FROM hist WHERE {_STARTED_RUN_SQL} "
        "ORDER BY ketto, rc, d2 ASC"
    )
    return _history_lookup_expr(race_codes, select_sql)


def _build_baba_top3_count_expr(race_codes: list[str], baba_codes: tuple[str, ...]) -> str:
    """指定した馬場状態での3着以内の回数を返す式を組み立てる。

    Args:
        race_codes (list[str]): 集計対象レースのレースコード。
        baba_codes (tuple[str, ...]): 馬場状態コード。

    Returns:
        str: 集計対象レースより前に、baba_codes の馬場で3着以内に入った回数を返す SQL 式。
    """
    baba_list = ", ".join(f"'{code}'" for code in baba_codes)
    select_sql = (
        "SELECT rc || ketto AS k, COUNT(*) AS v "
        f"FROM hist WHERE {_VALID_RUN_SQL} "
        "AND CAST(kakutei_chakujun AS INTEGER) BETWEEN 1 AND 3 "
        f"AND baba IN ({baba_list}) "
        "GROUP BY ketto, rc"
    )
    lookup = _history_lookup_expr(race_codes, select_sql)
    return f"COALESCE(({lookup})::INTEGER, 0)"


def _history_lookup_expr(race_codes: list[str], select_sql: str) -> str:
    """集計対象レースの出走馬の過去走から値を引く式を組み立てる。

    Args:
        race_codes (list[str]): 集計対象レースのレースコード。
        select_sql (str): CTE `hist` から `k`（キー）と `v`（値）を選ぶ SELECT 文。
            `hist` は集計対象レースの出走ごとに、その出走より前の過去走を1行ずつ持つ。

    Returns:
        str: 出走ごとに `v` を文字列で返す SQL 式。過去走が無い出走は NULL。

    Raises:
        ValueError: race_codes が空、または16桁の数字でないレースコードを含む場合。
    """
    if not race_codes:
        raise ValueError("race_codes が空です。")
    for race_code in race_codes:
        if len(race_code) != _RACE_CODE_LENGTH or not race_code.isdigit():
            raise ValueError(f"race_code が16桁の数字ではありません: {race_code!r}")
    code_list = ", ".join(f"'{code}'" for code in race_codes)
    tgt_cte = (
        "tgt AS ("
        "SELECT u3.ketto_toroku_bango AS ketto, u3.race_code AS rc, "
        "r3.kaisai_nen || r3.kaisai_gappi AS d3, "
        "NULLIF(TRIM(r3.kyori), '')::INTEGER AS kyori3 "
        "FROM umagoto_race_joho u3 JOIN race_shosai r3 ON u3.race_code = r3.race_code "
        f"WHERE u3.race_code IN ({code_list}))"
    )
    hist_cte = (
        "hist AS ("
        "SELECT t.ketto, t.rc, t.kyori3, r2.kaisai_nen || r2.kaisai_gappi AS d2, "
        "r2.keibajo_code, r2.grade_code, "
        f"{_JOKEN_SQL} AS joken, "
        "NULLIF(TRIM(r2.kyori), '')::INTEGER AS kyori2, "
        f"{_BABA_SQL} AS baba, "
        "u2.kakutei_chakujun, u2.corner4_juni, "
        "u2.tozai_shozoku_code AS tozai, u2.ijo_kubun_code AS ijo_kubun "
        "FROM tgt t "
        "JOIN umagoto_race_joho u2 ON u2.ketto_toroku_bango = t.ketto "
        "JOIN race_shosai r2 ON u2.race_code = r2.race_code "
        "WHERE r2.kaisai_nen || r2.kaisai_gappi < t.d3)"
    )
    return (
        f"((WITH {tgt_cte}, {hist_cte} "
        f"SELECT jsonb_object_agg(k, v) FROM ({select_sql}) m) "
        "->> (u.race_code || u.ketto_toroku_bango))"
    )
