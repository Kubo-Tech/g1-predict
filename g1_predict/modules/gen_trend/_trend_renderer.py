"""傾向データから Markdown セクションを生成するモジュール。"""

from keiba_domain import baba_from_code, keibajo_from_code
from mykeibadb.analytics import EntryFilter

from ._trend_catalog import TrendCategory, TrendItem
from ._trend_condition import apply_trend_condition
from ._trend_loader import TrendContext
from ._trend_models import OTHER_LABEL, TREND_YEARS, RowStats, TrendCondition
from ._trend_stats import compute_stats, get_juusho_race_names


def build_category_section(category: TrendCategory, context: TrendContext) -> str:
    """1カテゴリ分の傾向セクション文字列を生成する。

    ## カテゴリ名 とカテゴリの説明文から始まり、各項目の h3 テーブルと
    ### 比較表 プレースホルダーを含む文字列を返す。
    hide_if_empty の項目で該当馬が1頭もいないものは出力しない。

    Args:
        category (TrendCategory): 出力するカテゴリ。
        context (TrendContext): 対象レースと集計対象の情報。

    Returns:
        str: ## ヘッダーから始まる Markdown セクション文字列。
    """
    description = category.description.replace("{years}", str(context.years))
    header = f"## {category.name}\n\n{description}"

    metric_sections = [
        section
        for item in category.items
        if (section := _build_metric_section(item, context)) is not None
    ]
    metric_sections.append("### 比較表\n")
    return header + "\n\n" + "\n\n".join(metric_sections)


def format_scope_note(context: TrendContext, race_label: str) -> str:
    """集計対象を説明する注記を返す。

    集計年数が既定の TREND_YEARS 年に満たない場合は、G1になった年から集計したことを示す。

    Args:
        context (TrendContext): 対象レースと集計対象の情報。
        race_label (str): 記事に出力するレース名。

    Returns:
        str: `※集計対象は、...` の形式の注記。
    """
    last_year = context.race_year - 1
    span = f"{context.first_year}〜{last_year}年"
    if context.years == TREND_YEARS:
        period = f"過去{context.years}年（{span}）"
    else:
        period = f"G1になった{context.first_year}年から前年まで（{span}）"
    course = f"{keibajo_from_code(context.keibajo_code)}{context.shiba_da}{context.kyori}m"
    return f"※集計対象は、{period}に{course}で行われた{race_label}（{context.race_count}回）。"


def format_condition_note(condition: TrendCondition | None) -> str:
    """項目に注入された開催条件から注記文字列を返す。

    `※{開催場名}・{開催日目}・{コース区分}コース{何日目}・{馬場状態}のみ` の形式で返す。
    condition が None の場合は空文字を返す。

    Args:
        condition (TrendCondition | None): 項目に注入された開催条件。

    Returns:
        str: 注記文字列。condition が None の場合は空文字。
    """
    if condition is None:
        return ""

    parts: list[str] = []
    if condition.keibajo_codes:
        parts.append("・".join(keibajo_from_code(code) for code in condition.keibajo_codes))
    if condition.kaisai_nichime:
        nichime_str = "・".join(str(n) for n in condition.kaisai_nichime)
        parts.append(f"{nichime_str}日目")
    if condition.course_kubun or condition.course_days:
        course_part = f"{condition.course_kubun or ''}コース"
        if condition.course_days:
            course_part += "・".join(str(day) for day in condition.course_days) + "日目"
        parts.append(course_part)
    if condition.babajotai_codes:
        # baba_from_code はコード"0"（未設定）に対してNoneを返すため、その場合は
        # 注記に含めずスキップする。
        baba_names = [
            baba for code in condition.babajotai_codes if (baba := baba_from_code(code)) is not None
        ]
        if baba_names:
            parts.append("・".join(baba_names))

    return "※" + "・".join(parts) + "のみ"


def _build_metric_section(item: TrendItem, context: TrendContext) -> str | None:
    """1項目分の h3 テーブルセクション文字列を生成する。

    rows.type に応じてラベル一覧を決定し、各行の集計値から
    Markdown テーブルを生成する。dynamic 型は最後に「その他」行を追加する。
    項目に開催条件が注入されている場合は、開催条件で絞り込んで集計し、
    表の直下に開催条件の注記を出力する。
    項目に note がある場合は、その直下に出力する。
    項目に hide_if_empty が指定されていて、集計対象に該当馬が1頭もいない場合は None を返す。

    Args:
        item (TrendItem): 出力する項目。
        context (TrendContext): 対象レースと集計対象の情報。

    Returns:
        str | None: ### ヘッダーから始まる Markdown テーブル文字列。
            hide_if_empty の項目で該当馬がいない場合は None。
    """
    metric_cfg = item.config
    rows_cfg = metric_cfg["rows"]

    filters: list[EntryFilter] = []
    metric_condition = context.condition
    if item.condition is not None:
        metric_condition, filters = apply_trend_condition(context, item.condition)
    stats_map = compute_stats(metric_cfg, context.manager, metric_condition, filters)
    if metric_cfg.get("hide_if_empty") and all(s.total == 0 for s in stats_map.values()):
        return None

    source_cfg = metric_cfg.get("source", {})
    allowed_values: list[str] | None = source_cfg.get("allowed_values")

    add_other_row = False
    if rows_cfg["type"] == "dynamic":
        top_n = rows_cfg.get("top_n")
        labels = _get_dynamic_labels(stats_map, top_n)
        if allowed_values is not None:
            allowed_set = set(str(v) for v in allowed_values)
            labels = [lb for lb in labels if lb in allowed_set]
        always_grades = rows_cfg.get("always_include_grades")
        if always_grades is not None:
            juusho_names = get_juusho_race_names(context.manager, always_grades)
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
        labels = [row_item["label"] for row_item in rows_cfg["items"]]
    else:
        labels = list(stats_map.keys())

    if rows_cfg.get("hide_empty"):
        labels = [label for label in labels if stats_map.get(label, RowStats()).total > 0]

    display_map: dict[str, str] = metric_cfg.get("display_map", {})

    lines = [
        f"### {item.name}",
        "",
        f"| {item.name} | 着度数 | 勝率 | 複率 | 単回 | 複回 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for label in labels:
        display_label = display_map.get(label, label)
        stats = stats_map.get(label, RowStats())
        lines.append(_format_table_row(display_label, stats))

    if add_other_row:
        other_stats = _aggregate_other_stats(stats_map, set(labels))
        lines.append(_format_table_row(OTHER_LABEL, other_stats))

    notes = [format_condition_note(item.condition), metric_cfg.get("note", "")]
    for note in notes:
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
