"""傾向データから Markdown セクションを生成するモジュール。"""

from typing import Any

from keiba_domain import baba_from_code, keibajo_from_code
from mykeibadb.analytics import RaceCondition, Subject
from mykeibadb.connection import ConnectionManager

from ._trend_loader import build_metric_condition
from ._trend_models import OTHER_LABEL, TREND_YEARS, RowStats
from ._trend_stats import SUBJECT_MAP, compute_stats, get_juusho_race_names

_KM2_JOIN = "JOIN kyosoba_master2 km2 ON u.ketto_toroku_bango = km2.ketto_toroku_bango"

_SUBJECT_COLUMN_MAP: dict[Subject, tuple[str, str | None]] = {
    Subject.KISHU: ("u.kishumei_ryakusho", None),
    Subject.SIRE: ("km2.ketto1_bamei", _KM2_JOIN),
    Subject.SEISANSHA: ("km2.seisanshamei_hojinkaku_nashi", _KM2_JOIN),
}


def build_category_section(
    category_name: str,
    metrics: list[dict[str, Any]],
    manager: ConnectionManager,
    condition: RaceCondition,
    race_year: int,
    race_code: str = "",
) -> str:
    """1カテゴリ分の傾向セクション文字列を生成する。

    ## カテゴリ名 から始まり、各 metric の h3 テーブルと
    ## 比較表 プレースホルダーを含む文字列を返す。

    Args:
        category_name (str): カテゴリ名（例: "出走馬傾向"）。
        metrics (list[dict[str, Any]]): カテゴリ内の metric 設定リスト。
        manager (ConnectionManager): DB接続マネージャ。
        condition (RaceCondition): レース絞り込み条件。
        race_year (int): 対象レースの開催年。
        race_code (str): 16桁レースコード（all_entries 型で使用）。

    Returns:
        str: ## ヘッダーから始まる Markdown セクション文字列。
    """
    header = f"## {category_name}\n\n過去{TREND_YEARS}年{category_name}に関する傾向"

    metric_sections = [
        _build_metric_section(metric_cfg, manager, condition, race_year, race_code)
        for metric_cfg in metrics
    ]
    metric_sections.append("### 比較表\n")
    return header + "\n\n" + "\n\n".join(metric_sections)


def format_condition_note(condition_cfg: dict[str, Any] | None) -> str:
    """metric condition から開催条件の注記文字列を返す。

    `※過去{years}年{開催場名}{開催日目}{馬場状態}のみ` の形式で返す。
    condition_cfg が None の場合は空文字を返す。

    Args:
        condition_cfg (dict[str, Any] | None): metric の condition 設定dict。

    Returns:
        str: 注記文字列。condition_cfg が None の場合は空文字。
    """
    if condition_cfg is None:
        return ""

    years = condition_cfg.get("years", TREND_YEARS)
    parts = [f"過去{years}年"]

    keibajo_codes: list[str] | None = condition_cfg.get("keibajo_codes")
    if keibajo_codes:
        parts.append("・".join(keibajo_from_code(code) for code in keibajo_codes))

    kaisai_nichime: list[int] | None = condition_cfg.get("kaisai_nichime")
    if kaisai_nichime:
        nichime_str = "・".join(str(n) for n in kaisai_nichime)
        parts.append(f"{nichime_str}日目")

    babajotai_codes: list[str] | None = condition_cfg.get("babajotai_codes")
    if babajotai_codes:
        # baba_from_code はコード"0"（未設定）に対してNoneを返すため、その場合は
        # 注記に含めずスキップする。
        # Baba は "稍"/"不" と短縮した名称のため「馬場」は付けない（"稍馬場" は不自然）。
        baba_names = [
            baba for code in babajotai_codes if (baba := baba_from_code(code)) is not None
        ]
        if baba_names:
            parts.append("・".join(baba_names))

    parts.append("のみ")
    return "※" + "".join(parts)


def get_race_subject_entries(
    manager: ConnectionManager,
    race_code: str,
    subject: Subject,
) -> list[tuple[int, str]]:
    """指定レースの Subject 対象を (umaban, label) リストで返す。

    同一ラベルが複数馬に出る場合は最小馬番を採用し、重複を除いて返す。

    Args:
        manager (ConnectionManager): DB接続マネージャ。
        race_code (str): 16桁レースコード。
        subject (Subject): 集計対象。

    Returns:
        list[tuple[int, str]]: 馬番昇順の (umaban, label) タプルリスト。
    """
    column, join_sql = _SUBJECT_COLUMN_MAP[subject]
    join_clause = f"\n        {join_sql}" if join_sql else ""
    sql = f"""
        SELECT TRIM(u.umaban)::INTEGER AS umaban,
               TRIM({column}) AS label
        FROM umagoto_race_joho u{join_clause}
        WHERE u.race_code = %s
        ORDER BY TRIM(u.umaban)::INTEGER
    """
    df = manager.fetch_dataframe(sql, params=(race_code,))
    entries = list(zip(df["umaban"].astype(int).tolist(), df["label"].astype(str).tolist()))

    min_umaban: dict[str, int] = {}
    for umaban, label in entries:
        if label not in min_umaban or umaban < min_umaban[label]:
            min_umaban[label] = umaban

    return sorted(((umaban, label) for label, umaban in min_umaban.items()), key=lambda x: x[0])


def sort_entry_labels(
    stats_map: dict[str, RowStats],
    entries: list[tuple[int, str]],
) -> list[str]:
    """今回出走対象ラベルを着度数・着外数・馬番でソートして返す。

    ソート優先順位:
    1. 1着数 降順
    2. 2着数 降順
    3. 3着数 降順
    4. 着外数 昇順
    5. 馬番 昇順

    Args:
        stats_map (dict[str, RowStats]): ラベル -> RowStats。
        entries (list[tuple[int, str]]): (umaban, label) リスト。

    Returns:
        list[str]: ソート済みラベルリスト。
    """
    umaban_map = {label: umaban for umaban, label in entries}
    all_labels = [label for _, label in entries]

    def sort_key(label: str) -> tuple[int, int, int, int, int]:
        s = stats_map.get(label, RowStats())
        return (-s.first, -s.second, -s.third, s.fourth_plus, umaban_map.get(label, 99))

    return sorted(all_labels, key=sort_key)


def _build_metric_section(
    metric_cfg: dict[str, Any],
    manager: ConnectionManager,
    condition: RaceCondition,
    race_year: int,
    race_code: str = "",
) -> str:
    """1 metric 分の h3 テーブルセクション文字列を生成する。

    rows.type に応じてラベル一覧を決定し、各行の集計値から
    Markdown テーブルを生成する。dynamic 型は最後に「その他」行を追加する。
    metric_cfg に condition が指定されている場合は、開催条件を反映した
    RaceCondition で集計し、表の直下に開催条件の注記を出力する。

    Args:
        metric_cfg (dict[str, Any]): metric の YAML 設定dict。
        manager (ConnectionManager): DB接続マネージャ。
        condition (RaceCondition): レース絞り込み条件。
        race_year (int): 対象レースの開催年。
        race_code (str): 16桁レースコード（all_entries 型で使用）。

    Returns:
        str: ### ヘッダーから始まる Markdown テーブル文字列。

    Raises:
        ValueError: rows.type が all_entries で race_code が空、または
            source.type が SUBJECT_MAP に存在しない場合。
    """
    metric_name = metric_cfg["name"]
    rows_cfg = metric_cfg["rows"]
    condition_cfg = metric_cfg.get("condition")

    metric_condition = build_metric_condition(condition, race_year, condition_cfg)
    stats_map = compute_stats(metric_cfg, manager, metric_condition)

    source_cfg = metric_cfg.get("source", {})
    allowed_values: list[str] | None = source_cfg.get("allowed_values")

    add_other_row = False
    if rows_cfg["type"] == "all_entries":
        if not race_code:
            raise ValueError("rows.type: all_entries には race_code が必要です")
        src_type = source_cfg.get("type", "")
        if src_type not in SUBJECT_MAP:
            raise ValueError(f"all_entries で未対応の source.type です: {src_type}")
        entries = get_race_subject_entries(manager, race_code, SUBJECT_MAP[src_type])
        labels = sort_entry_labels(stats_map, entries)
    elif rows_cfg["type"] == "dynamic":
        top_n = rows_cfg.get("top_n")
        labels = _get_dynamic_labels(stats_map, top_n)
        if allowed_values is not None:
            allowed_set = set(str(v) for v in allowed_values)
            labels = [lb for lb in labels if lb in allowed_set]
        always_grades = rows_cfg.get("always_include_grades")
        if always_grades is not None:
            juusho_names = get_juusho_race_names(manager, always_grades)
            labels_set = set(labels)
            extra = [
                name for name in juusho_names
                if name in stats_map and name not in labels_set
            ]
            extra.sort(
                key=lambda n: stats_map[n].first + stats_map[n].second + stats_map[n].third,
                reverse=True,
            )
            labels = labels + extra
        has_top_n = rows_cfg.get("top_n") is not None
        has_allowed = allowed_values is not None
        add_other_row = has_top_n or has_allowed
    elif rows_cfg["type"] in ("fixed", "boolean_multi"):
        labels = [item["label"] for item in rows_cfg["items"]]
    else:
        labels = list(stats_map.keys())

    display_map: dict[str, str] = metric_cfg.get("display_map", {})

    lines = [
        f"### {metric_name}",
        "",
        f"| {metric_name} | 着度数 | 勝率 | 複率 | 単回 | 複回 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for label in labels:
        display_label = display_map.get(label, label)
        stats = stats_map.get(label, RowStats())
        lines.append(_format_table_row(display_label, stats))

    if add_other_row:
        other_stats = _aggregate_other_stats(stats_map, set(labels))
        lines.append(_format_table_row(OTHER_LABEL, other_stats))

    note = format_condition_note(condition_cfg)
    if note:
        lines.append("")
        lines.append(note)

    return "\n".join(lines)


def _get_dynamic_labels(
    stats_map: dict[str, RowStats],
    top_n: int | None,
) -> list[str]:
    """3着内数の多い順にラベルを返す。

    「その他」ラベルは集計対象から除外する。
    top_n が None の場合は全件返す。

    Args:
        stats_map (dict[str, RowStats]): 行ラベル -> RowStats。
        top_n (int | None): 返す上位件数。None の場合は全件。

    Returns:
        list[str]: 3着内数降順で並べたラベルのリスト。
    """
    items = [
        (label, s.first + s.second + s.third)
        for label, s in stats_map.items()
        if label != OTHER_LABEL
    ]
    items.sort(key=lambda x: x[1], reverse=True)
    if top_n is None or len(items) <= top_n:
        return [label for label, _ in items]
    threshold = items[top_n - 1][1]
    return [label for label, score in items if score >= threshold]


def _aggregate_other_stats(
    stats_map: dict[str, RowStats],
    top_labels: set[str],
) -> RowStats:
    """top_labels に含まれないラベルの集計値を加重平均で合算して返す。

    dynamic 型の「その他」行を生成するために使用する。

    Args:
        stats_map (dict[str, RowStats]): 行ラベル -> RowStats。
        top_labels (set[str]): 上位ラベルのセット（これらは除外して集計する）。

    Returns:
        RowStats: top_labels 以外の全ラベルを合算した集計値。
    """
    other = RowStats()
    tansho_sum = 0.0
    fukusho_sum = 0.0
    for label, s in stats_map.items():
        if label in top_labels:
            continue
        other.first += s.first
        other.second += s.second
        other.third += s.third
        other.fourth_plus += s.fourth_plus
        tansho_sum += s.tansho_kaishuu * s.total
        fukusho_sum += s.fukusho_kaishuu * s.total
        other.total += s.total
    if other.total > 0:
        other.tansho_kaishuu = tansho_sum / other.total
        other.fukusho_kaishuu = fukusho_sum / other.total
    return other


def _format_table_row(label: str, s: RowStats) -> str:
    """Markdown テーブルの1行文字列を生成する。

    Args:
        label (str): 行ラベル（1列目に表示する文字列）。
        s (RowStats): 行の集計値。

    Returns:
        str: | label | 着度数 | 勝率 | 複率 | 単回 | 複回 | 形式の文字列。
    """
    win_str = _format_percent(s.first, s.total)
    place_str = _format_percent(s.first + s.second + s.third, s.total)
    tansho_str = f"{round(s.tansho_kaishuu)}%" if s.total > 0 else "-"
    fukusho_str = f"{round(s.fukusho_kaishuu)}%" if s.total > 0 else "-"
    return (
        f"| {label} | {_format_chakudo(s)}"
        f" | {win_str} | {place_str} | {tansho_str} | {fukusho_str} |"
    )


def _format_chakudo(s: RowStats) -> str:
    """RowStats を「1着-2着-3着-着外」形式の着度数文字列に変換する。

    Args:
        s (RowStats): 行の集計値。

    Returns:
        str: "{first}-{second}-{third}-{fourth_plus}" 形式の文字列。
    """
    return f"{s.first}-{s.second}-{s.third}-{s.fourth_plus}"


def _format_percent(count: int, total: int) -> str:
    """頭数比率を百分率文字列に変換する。

    total が 0 の場合はデータなしを示す "-" を返す。
    計算式: round(count / total * 100) %

    Args:
        count (int): 対象頭数。
        total (int): 全体頭数。

    Returns:
        str: "N%" 形式の文字列。total が 0 の場合は "-"。
    """
    if total == 0:
        return "-"
    return f"{round(count / total * 100)}%"
