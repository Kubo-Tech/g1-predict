"""傾向データから Markdown セクションを生成するモジュール。"""

from dataclasses import dataclass

from keiba_domain import baba_from_code, keibajo_from_code
from mykeibadb.analytics import EntryFilter

from ._trend_catalog import TrendCategory, TrendItem
from ._trend_condition import apply_trend_condition
from ._trend_entries import find_entry_rows
from ._trend_loader import TrendContext
from ._trend_models import OTHER_LABEL, TREND_YEARS, RowStats, TrendCondition
from ._trend_stats import compute_stats, get_juusho_race_names


@dataclass(frozen=True)
class ItemTable:
    """1項目分の表の行と、今回の出走馬が当たる行。

    Attributes:
        item (TrendItem): 項目。
        rows (list[str]): 表に出す行のラベル（display_map 適用前）。dynamic の項目は
            最後に「その他」を含むことがある。
        stats (dict[str, RowStats]): 行のラベル -> 過去の集計値。
        entry_rows (dict[int, list[str]]): 馬番 -> 当たる行のラベル（表の行の順）。
            当たる行が無い馬は含まない。
    """

    item: TrendItem
    rows: list[str]
    stats: dict[str, RowStats]
    entry_rows: dict[int, list[str]]

    def display_name(self, label: str) -> str:
        """行のラベルの表示名を返す。

        Args:
            label (str): 行のラベル。

        Returns:
            str: display_map にあればその表示名、無ければラベルそのまま。
        """
        display_map: dict[str, str] = self.item.config.get("display_map", {})
        return display_map.get(label, label)

    def horse_nums(self, label: str) -> list[int]:
        """行に当たる出走馬の馬番を昇順で返す。

        Args:
            label (str): 行のラベル。

        Returns:
            list[int]: 馬番。当たる馬がいない場合は空。
        """
        return sorted(num for num, rows in self.entry_rows.items() if label in rows)


def build_item_table(
    item: TrendItem,
    context: TrendContext,
    entry_race_code: str | None = None,
) -> ItemTable | None:
    """1項目分の表の行と集計値を求める。

    rows.type に応じて行を決定し、各行の集計値を求める。dynamic 型は、top_n などで表に出ない値が
    ある場合と、表に出ていない値の出走馬がいる場合に、最後に「その他」行を追加する。
    項目に開催条件が注入されている場合は、開催条件で絞り込んで集計する。
    entry_race_code を指定した場合は、今回の出走馬が当たる行も求める。
    hide_empty の項目でも、今回の出走馬が当たる行は隠さない。
    hide_if_empty の項目は、集計対象にも今回の出走馬にも該当馬が1頭もいない場合は None を返す。

    Args:
        item (TrendItem): 対象の項目。
        context (TrendContext): 対象レースと集計対象の情報。
        entry_race_code (str | None): 今回のレースの16桁のレースコード。
            None の場合は出走馬の判定をしない。

    Returns:
        ItemTable | None: 表の行と集計値。隠す指定により表を出さない場合は None。
    """
    metric_cfg = item.config
    rows_cfg = metric_cfg["rows"]

    filters: list[EntryFilter] = []
    metric_condition = context.condition
    if item.condition is not None:
        metric_condition, filters = apply_trend_condition(context, item.condition)
    stats_map = compute_stats(metric_cfg, context.manager, metric_condition, filters)
    entry_groups: dict[int, list[str]] = {}
    if entry_race_code is not None:
        entry_groups = find_entry_rows(item, context, entry_race_code)

    source_cfg = metric_cfg.get("source", {})
    allowed_values: list[str] | None = source_cfg.get("allowed_values")

    add_other_row = False
    if rows_cfg["type"] == "dynamic":
        top_n = rows_cfg.get("top_n")
        labels = _get_dynamic_labels(stats_map, top_n, bool(rows_cfg.get("exclude_no_top3")))
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

    entry_rows = _assign_entry_rows(entry_groups, labels, rows_cfg["type"] == "dynamic")
    entry_labels = {label for rows in entry_rows.values() for label in rows}
    # 表に出ていない値の出走馬がいれば、top_n などの指定が無い項目でも「その他」行を出す
    add_other_row = add_other_row or OTHER_LABEL in entry_labels
    if (
        metric_cfg.get("hide_if_empty")
        and all(s.total == 0 for s in stats_map.values())
        and not entry_labels
    ):
        return None

    if rows_cfg.get("hide_empty"):
        labels = [
            label
            for label in labels
            if stats_map.get(label, RowStats()).total > 0 or label in entry_labels
        ]

    stats = {label: stats_map.get(label, RowStats()) for label in labels}
    rows = list(labels)
    if add_other_row:
        stats[OTHER_LABEL] = _aggregate_other_stats(stats_map, set(labels))
        rows.append(OTHER_LABEL)
    return ItemTable(item=item, rows=rows, stats=stats, entry_rows=entry_rows)


def build_category_section(
    category: TrendCategory,
    context: TrendContext,
    tables: list[ItemTable],
    with_entries: bool = False,
    comparison_image: str | None = None,
) -> str:
    """1カテゴリ分の傾向セクション文字列を生成する。

    ## カテゴリ名 とカテゴリの説明文から始まり、各項目の h3 テーブルを含む文字列を返す。
    with_entries が True の場合は、各テーブルの右端に今回の出走馬のうち行に当たる馬の馬番を
    書く「該当馬」列を付ける。comparison_image がある場合は、末尾に比較表の画像を載せる。

    Args:
        category (TrendCategory): 出力するカテゴリ。
        context (TrendContext): 対象レースと集計対象の情報。
        tables (list[ItemTable]): カテゴリの各項目の表（表を出さない項目は含めない）。
        with_entries (bool): 該当馬列を付けるか。
        comparison_image (str | None): 比較表の画像の、記事ディレクトリからの相対パス。

    Returns:
        str: ## ヘッダーから始まる Markdown セクション文字列。
    """
    description = category.description.replace("{years}", str(context.years))
    header = f"## {category.name}\n\n{description}"

    sections = [_format_item_section(table, with_entries) for table in tables]
    if comparison_image is not None:
        sections.append(f"### 比較表\n\n![{category.name}の比較表]({comparison_image})")
    return header + "\n\n" + "\n\n".join(sections)


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


def _assign_entry_rows(
    entry_groups: dict[int, list[str]],
    labels: list[str],
    is_dynamic: bool,
) -> dict[int, list[str]]:
    """出走馬が当たる行のラベルを、表に出す行に絞り込む。

    dynamic の項目で、表に出ている行のどれにも当たらない行のラベルは「その他」に置き換える。

    Args:
        entry_groups (dict[int, list[str]]): 馬番 -> 集計の割り当てで当たる行のラベル。
        labels (list[str]): 表に出す行のラベル（「その他」を除く）。
        is_dynamic (bool): rows.type が dynamic か。

    Returns:
        dict[int, list[str]]: 馬番 -> 当たる行のラベル（表の行の順）。当たる行が無い馬は含まない。
    """
    label_set = set(labels)
    entry_rows: dict[int, list[str]] = {}
    for horse_num, assigned in entry_groups.items():
        hits: set[str] = set()
        for label in assigned:
            if label in label_set:
                hits.add(label)
            elif is_dynamic:
                hits.add(OTHER_LABEL)
        rows = [label for label in [*labels, OTHER_LABEL] if label in hits]
        if rows:
            entry_rows[horse_num] = rows
    return entry_rows


def _format_item_section(table: ItemTable, with_entries: bool) -> str:
    """1項目分の h3 テーブルセクション文字列を生成する。

    各行の集計値から Markdown テーブルを生成する。
    項目に開催条件が注入されている場合は、表の直下に開催条件の注記を出力する。
    項目に note がある場合は、その直下に出力する。

    Args:
        table (ItemTable): 出力する項目の表。
        with_entries (bool): 該当馬列を付けるか。

    Returns:
        str: ### ヘッダーから始まる Markdown テーブル文字列。
    """
    item = table.item
    header_cells = [item.name, "着度数", "勝率", "複率", "単回", "複回"]
    if with_entries:
        header_cells.append("該当馬")
    lines = [
        f"### {item.name}",
        "",
        "| " + " | ".join(header_cells) + " |",
        "| " + " | ".join(["---"] * len(header_cells)) + " |",
    ]
    for label in table.rows:
        horses: str | None = None
        if with_entries:
            horses = ", ".join(str(num) for num in table.horse_nums(label))
        lines.append(_format_table_row(table.display_name(label), table.stats[label], horses))

    notes = [format_condition_note(item.condition), item.config.get("note", "")]
    for note in notes:
        if note:
            lines.append("")
            lines.append(note)

    return "\n".join(lines)


def _get_dynamic_labels(
    stats_map: dict[str, RowStats],
    top_n: int | None,
    exclude_no_top3: bool = False,
) -> list[str]:
    """3着内数の多い順にラベルを返す。

    「その他」ラベルは集計対象から除外する。
    top_n が None の場合は全件返す。
    exclude_no_top3 が True の場合は、3着内数が0のラベルを上位に入れない。

    Args:
        stats_map (dict[str, RowStats]): 行ラベル -> RowStats。
        top_n (int | None): 返す上位件数。None の場合は全件。
        exclude_no_top3 (bool): 3着内数が0のラベルを除くか。

    Returns:
        list[str]: 3着内数降順で並べたラベルのリスト。
    """
    items = [
        (label, s.first + s.second + s.third)
        for label, s in stats_map.items()
        if label != OTHER_LABEL
    ]
    if exclude_no_top3:
        items = [(label, score) for label, score in items if score > 0]
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


def _format_table_row(label: str, s: RowStats, horses: str | None = None) -> str:
    """Markdown テーブルの1行文字列を生成する。

    Args:
        label (str): 行ラベル（1列目に表示する文字列）。
        s (RowStats): 行の集計値。
        horses (str | None): 該当馬列に書く馬番。None の場合は該当馬列を付けない。

    Returns:
        str: | label | 着度数 | 勝率 | 複率 | 単回 | 複回 | 形式の文字列。
            horses がある場合は末尾に該当馬の列が付く。
    """
    win_str = _format_percent(s.first, s.total)
    place_str = _format_percent(s.first + s.second + s.third, s.total)
    tansho_str = f"{round(s.tansho_kaishuu)}%" if s.total > 0 else "-"
    fukusho_str = f"{round(s.fukusho_kaishuu)}%" if s.total > 0 else "-"
    cells = [label, _format_chakudo(s), win_str, place_str, tansho_str, fukusho_str]
    if horses is not None:
        cells.append(horses)
    return "| " + " | ".join(cells) + " |"


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
