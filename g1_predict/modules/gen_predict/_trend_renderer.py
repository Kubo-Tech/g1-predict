"""傾向データから Markdown セクションを生成するモジュール。"""

from typing import Any

from mykeibadb.analytics import RaceCondition
from mykeibadb.connection import ConnectionManager

from ._trend_models import OTHER_LABEL, TREND_YEARS, RowStats
from ._trend_stats import compute_stats


def build_category_section(
    category_name: str,
    metrics: list[dict[str, Any]],
    manager: ConnectionManager,
    condition: RaceCondition,
) -> str:
    """1カテゴリ分の傾向セクション文字列を生成する。

    ## カテゴリ名 から始まり、各 metric の h3 テーブルと
    ## 比較表 プレースホルダーを含む文字列を返す。

    Args:
        category_name (str): カテゴリ名（例: "出走馬傾向"）。
        metrics (list[dict[str, Any]]): カテゴリ内の metric 設定リスト。
        manager (ConnectionManager): DB接続マネージャ。
        condition (RaceCondition): レース絞り込み条件。

    Returns:
        str: ## ヘッダーから始まる Markdown セクション文字列。
    """
    header = f"## {category_name}\n\n過去{TREND_YEARS}年{category_name}に関する傾向"

    metric_sections = [
        _build_metric_section(metric_cfg, manager, condition) for metric_cfg in metrics
    ]
    metric_sections.append("### 比較表\n")
    return header + "\n\n" + "\n\n".join(metric_sections)


def _build_metric_section(
    metric_cfg: dict[str, Any],
    manager: ConnectionManager,
    condition: RaceCondition,
) -> str:
    """1 metric 分の h3 テーブルセクション文字列を生成する。

    rows.type に応じてラベル一覧を決定し、各行の集計値から
    Markdown テーブルを生成する。dynamic 型は最後に「その他」行を追加する。

    Args:
        metric_cfg (dict[str, Any]): metric の YAML 設定dict。
        manager (ConnectionManager): DB接続マネージャ。
        condition (RaceCondition): レース絞り込み条件。

    Returns:
        str: ### ヘッダーから始まる Markdown テーブル文字列。
    """
    metric_name = metric_cfg["name"]
    rows_cfg = metric_cfg["rows"]

    stats_map = compute_stats(metric_cfg, manager, condition)

    if rows_cfg["type"] == "dynamic":
        top_n = rows_cfg.get("top_n")
        labels = _get_dynamic_labels(stats_map, top_n)
    elif rows_cfg["type"] in ("fixed", "boolean_multi"):
        labels = [item["label"] for item in rows_cfg["items"]]
    else:
        labels = list(stats_map.keys())

    display_map: dict[str, str] = metric_cfg.get("display_map", {})

    lines = [
        f"### {metric_name}",
        "",
        f"| {metric_name} | 1着 | 2着 | 3着 | 着外 | 勝率 | 複率 | 単回 | 複回 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for label in labels:
        display_label = display_map.get(label, label)
        stats = stats_map.get(label, RowStats())
        lines.append(_format_table_row(display_label, stats))

    source_cfg = metric_cfg.get("source", {})
    has_top_n = rows_cfg.get("top_n") is not None
    has_allowed = source_cfg.get("allowed_values") is not None
    if rows_cfg["type"] == "dynamic" and (has_top_n or has_allowed):
        other_stats = _aggregate_other_stats(stats_map, set(labels))
        lines.append(_format_table_row(OTHER_LABEL, other_stats))

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
    return [label for label, _ in items] if top_n is None else [label for label, _ in items[:top_n]]


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
        str: | label | 1着 | 2着 | 3着 | 着外 | 勝率 | 複率 | 単回 | 複回 | 形式の文字列。
    """
    win_str = _format_percent(s.first, s.total)
    place_str = _format_percent(s.first + s.second + s.third, s.total)
    tansho_str = f"{round(s.tansho_kaishuu)}%" if s.total > 0 else "-"
    fukusho_str = f"{round(s.fukusho_kaishuu)}%" if s.total > 0 else "-"
    return (
        f"| {label} | {s.first}頭 | {s.second}頭 | {s.third}頭 | {s.fourth_plus}頭"
        f" | {win_str} | {place_str} | {tansho_str} | {fukusho_str} |"
    )


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
