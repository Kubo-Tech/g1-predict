"""前日・当日の傾向記事の本文を生成するモジュール。"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd
from evaluation.params import WAKU_TO_COLOR_DICT
from keiba_data_interface import DataInterface
from keiba_domain import keibajo_from_code
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import MaxNLocator, PercentFormatter
from mykeibadb import RaceGetter

from g1_predict.modules.constants import GRADE_CODE_DISPLAY, TRACK_CODE_TO_SHIBA_DA
from g1_predict.modules.utils.race_dynamics import (
    DYNAMICS_COLUMNS,
    build_dynamics_table_lines,
    evaluate_race_dynamics_with_plot,
)
from g1_predict.modules.utils.race_result import (
    KYAKUSHITSU_DISPLAY,
    format_corner4,
    format_halon,
    halon_rank,
    kyakushitsu_display,
)

_KYOSO_JOKEN_CODE_DISPLAY: dict[str, str] = {
    "701": "新馬",
    "703": "未勝利",
    "005": "1勝クラス",
    "010": "2勝クラス",
    "016": "3勝クラス",
    "999": "オープン",
}

# MATLABの標準色（線・棒の既定の色順）
_MATLAB_COLORS: tuple[str, ...] = (
    "#0072BD", "#D95319", "#EDB120", "#7E2F8E", "#77AC30", "#4DBEEE", "#A2142F",
)
_KYAKUSHITSU_URL = "http://next5.jra-van.jp/appli/kyakushitsu3.html"
_JAPANESE_FONT = FontProperties(family="Noto Sans CJK JP")
# 展開評価に必要なコーナー通過順が揃っている結果区分。
# RACE_SHOSAIのDATA_KUBUNのうち、"6"は速報成績（全馬着順＋コーナー通過順）、"7"は成績。
_RESULT_CONFIRMED_DATA_KUBUN: frozenset[str] = frozenset({"6", "7"})


@dataclass(frozen=True)
class DayTrendKind:
    """傾向記事の種類（前日・当日）ごとの違い。

    Attributes:
        label (str): 記事の見出しや説明文に使う表示語（"前日" / "当日"）。
        day_offset (int): 集計日の対象レースの開催日からの日数（前日は-1、当日は0）。
        image_dir (str): 記事ディレクトリ直下の画像ディレクトリ名。
        confirmed_only (bool): 結果が出ているレースだけを集計する場合はTrue。
    """

    label: str
    day_offset: int
    image_dir: str
    confirmed_only: bool


PREV_DAY = DayTrendKind(label="前日", day_offset=-1, image_dir="prev_day", confirmed_only=False)
RACE_DAY = DayTrendKind(label="当日", day_offset=0, image_dir="race_day", confirmed_only=True)


@dataclass(frozen=True)
class DayTrendBody:
    """傾向記事の本文と画像。

    Attributes:
        text (str): 記事本文（Markdown）。対象レースが1件もない場合は空文字列。
        images (dict[str, Figure]): 記事ディレクトリからの相対パス
            （例: "img/prev_day/xxx.png"）から画像へのマッピング。出目の棒グラフ、
            展開グラフ（dynamics.png）と、展開評価の対象レースごとの
            標準化散布図を持つ。対象レースが1件もない場合は空辞書。
    """

    text: str
    images: dict[str, Figure]


@dataclass(frozen=True)
class _MatchedRace:
    """集計対象の1レース分のデータ。

    Attributes:
        race_code (str): 集計対象レースのrace_code。
        race_info (pd.DataFrame): 集計対象レースの基本情報DataFrame（日本語カラム名）。
        result_df (pd.DataFrame): 集計対象レースの結果DataFrame（日本語カラム名）。
        cor_df (pd.DataFrame | None): 展開評価の相関係数DataFrame（1行）。
            展開評価の対象外レースはNone。
        figure (Figure | None): 展開評価の標準化散布図。展開評価の対象外レースはNone。
    """

    race_code: str
    race_info: pd.DataFrame
    result_df: pd.DataFrame
    cor_df: pd.DataFrame | None
    figure: Figure | None


def build_day_trend_body(
    race_code: str,
    race_info: pd.DataFrame,
    race_label: str,
    kind: DayTrendKind,
) -> DayTrendBody:
    """傾向記事の本文を生成する。

    対象レースの前日または当日に、同競馬場・同芝ダで行われたレースの上位3頭を列挙する。
    本文は `## {前日|当日}の出目` `## 展開有利度の傾向` `## 各レースの結果` の3セクションから
    構成され、H1見出しは含まない。画像は出目の棒グラフ、展開グラフ、展開評価の標準化散布図で、
    標準化散布図は対象外レース（1000m直線コース）には生成しない。

    Args:
        race_code (str): 16桁レースコード。
        race_info (pd.DataFrame): 対象レースの基本情報DataFrame（raw英語カラム名）。
        race_label (str): 対象レースの表記名（例: "スプリンターズS"）。出目の説明文に使う。
        kind (DayTrendKind): 傾向記事の種類（PREV_DAY / RACE_DAY）。

    Returns:
        DayTrendBody: 傾向記事の本文と画像。集計対象のレースが1件もない場合は
            本文が空文字列、画像は空辞書。
    """
    di = DataInterface("mykeibadb")
    keibajo_code = str(race_info["keibajo_code"].iloc[0])
    track_code = str(race_info["track_code"].iloc[0]).strip()
    target_shiba_da = TRACK_CODE_TO_SHIBA_DA.get(track_code, "")

    year = int(race_code[0:4])
    mmdd = race_code[4:8]
    race_date = datetime.strptime(f"{year}{mmdd}", "%Y%m%d").date()
    trend_date = race_date + timedelta(days=kind.day_offset)

    # 対象レースと同じ日を集計するときは、対象レース以降のレースを含めない
    before_race_bango = int(race_code[14:16]) if trend_date == race_date else None
    matched = _get_matched_races(
        trend_date, keibajo_code, target_shiba_da, kind, before_race_bango
    )
    if matched.empty:
        return DayTrendBody(text="", images={})

    venue_name = keibajo_from_code(keibajo_code)

    matched_races: list[_MatchedRace] = []
    for _, raw_row in matched.iterrows():
        matched_race_code = str(raw_row["race_code"])
        matched_race_info = di.get_race_basic_info(matched_race_code)
        result_df = di.get_result(matched_race_code)
        cor_df, figure = evaluate_race_dynamics_with_plot(
            matched_race_code, di, trend_date + timedelta(days=1)
        )
        matched_races.append(
            _MatchedRace(matched_race_code, matched_race_info, result_df, cor_df, figure)
        )

    top3_entries: list[tuple[pd.Series, pd.DataFrame]] = []
    for race in matched_races:
        result_df = race.result_df
        top3 = result_df[result_df["確定着順"].isin([1, 2, 3])].sort_values("確定着順")
        for _, horse_row in top3.iterrows():
            top3_entries.append((horse_row, result_df))

    dememe_text, dememe_images = _build_dememe_section(top3_entries, race_label, kind)
    blocks: list[str] = [
        dememe_text,
        "",
        _build_dynamics_section(kind),
        "",
        "## 各レースの結果",
        "",
    ]

    for race in matched_races:
        blocks.append(_format_race_block(race, venue_name, kind))
        blocks.append("")

    images: dict[str, Figure] = {
        **dememe_images,
        _dynamics_chart_path(kind): _make_dynamics_chart(matched_races),
    }
    for race in matched_races:
        if race.figure is not None:
            images[f"img/{kind.image_dir}/{race.race_code}.png"] = race.figure

    return DayTrendBody(text="\n".join(blocks), images=images)


def _get_matched_races(
    trend_date: date,
    keibajo_code: str,
    shiba_da: str,
    kind: DayTrendKind,
    before_race_bango: int | None,
) -> pd.DataFrame:
    """集計日の同競馬場・同芝ダのレース一覧を返す。

    Args:
        trend_date (date): 集計日。
        keibajo_code (str): 競馬場コード（例: "05"）。
        shiba_da (str): 芝ダ区分（"芝" または "ダ"）。
        kind (DayTrendKind): 傾向記事の種類。confirmed_onlyの場合は結果が出ているレースに絞る。
        before_race_bango (int | None): 指定した場合、このレース番号より前のレースに絞る。

    Returns:
        pd.DataFrame: 条件一致したレースのraw RACE_SHOSAI DataFrame（race_bango昇順）。
    """
    rg = RaceGetter()
    raw = rg.get_race_shosai(start_date=trend_date, end_date=trend_date, convert_codes=False)

    if raw.empty:
        return raw

    if kind.confirmed_only:
        raw = raw[raw["data_kubun"].astype(str).str.strip().isin(_RESULT_CONFIRMED_DATA_KUBUN)]
        if raw.empty:
            return raw

    keibajo_mask = raw["keibajo_code"].astype(str).str.strip() == keibajo_code
    raw = raw[keibajo_mask]

    if raw.empty:
        return raw

    # 障害コード（51-59）を除外し、平地の芝ダのみ対象とする
    barrier_codes = {str(code) for code in range(51, 60)}
    not_barrier = ~raw["track_code"].apply(lambda tc: str(tc).strip() in barrier_codes)
    raw = raw[not_barrier]

    shiba_da_series = raw["track_code"].apply(
        lambda tc: TRACK_CODE_TO_SHIBA_DA.get(str(tc).strip(), "")
    )
    raw = raw[shiba_da_series == shiba_da]

    if before_race_bango is not None:
        raw = raw[pd.to_numeric(raw["race_bango"]) < before_race_bango]

    return raw.sort_values("race_bango").reset_index(drop=True)


def _race_label(race_info: pd.DataFrame, venue_name: str, race_no: int) -> str:
    """レースラベル（{競馬場}{R}R {条件}(グレード)）を生成する。

    Args:
        race_info (pd.DataFrame): レース基本情報DataFrame。
        venue_name (str): 競馬場表示名。
        race_no (int): レース番号。

    Returns:
        str: レースラベル文字列。
    """
    condition = _race_condition(race_info)
    grade_code = str(race_info["グレードコード"].iloc[0])
    grade_display = GRADE_CODE_DISPLAY.get(grade_code, "")

    if grade_display:
        return f"{venue_name}{race_no}R {condition}({grade_display})"
    return f"{venue_name}{race_no}R {condition}"


def _race_condition(race_info: pd.DataFrame) -> str:
    """競走条件の表示名を返す。

    競走条件名称があればそれを使い、無ければ競走条件コードから表示名を引く。

    Args:
        race_info (pd.DataFrame): レース基本情報DataFrame。

    Returns:
        str: 競走条件の表示名。
    """
    cond_raw = race_info["競走条件名称"].iloc[0]
    if pd.notna(cond_raw) and str(cond_raw).strip():
        return str(cond_raw).strip()
    joken_code_raw = race_info["競走条件コード"].iloc[0]
    joken_code = str(joken_code_raw) if pd.notna(joken_code_raw) else ""
    return _KYOSO_JOKEN_CODE_DISPLAY.get(joken_code, "")


def _dynamics_chart_path(kind: DayTrendKind) -> str:
    """展開グラフの記事ディレクトリからの相対パスを返す。

    Args:
        kind (DayTrendKind): 傾向記事の種類。

    Returns:
        str: 展開グラフの相対パス。
    """
    return f"img/{kind.image_dir}/dynamics.png"


def _build_dynamics_section(kind: DayTrendKind) -> str:
    """展開セクションを生成する。

    Args:
        kind (DayTrendKind): 傾向記事の種類。

    Returns:
        str: 展開セクション文字列（## 展開有利度の傾向から始まる）。
    """
    lines: list[str] = [
        "## 展開有利度の傾向",
        "",
        "差し有利度・外枠有利度・外有利度は、それぞれ4角通過位置・馬番・コーナーでの"
        "内外の位置と走破タイムの相関係数を100倍したもの。正なら差し・外枠・外を回した馬が有利。",
        "",
        f"![展開]({_dynamics_chart_path(kind)})",
    ]
    return "\n".join(lines)


def _make_dynamics_chart(matched_races: list[_MatchedRace]) -> Figure:
    """各レースの差し有利度・外枠有利度・外有利度の折れ線グラフを生成する。

    横軸はレースを等間隔に並べてレース番号を目盛りにし、縦軸は相関係数を100倍した
    -100%から100%とする。
    展開評価の対象外レースや値が無いレースは線を途切れさせる。

    Args:
        matched_races (list[_MatchedRace]): 集計対象レースのリスト。

    Returns:
        Figure: 展開グラフ。
    """
    figure = Figure(figsize=(8, 4))
    ax = figure.subplots()
    positions = list(range(len(matched_races)))
    for column, color in zip(DYNAMICS_COLUMNS, _MATLAB_COLORS, strict=False):
        values = [
            float(race.cor_df[column].iloc[0]) * 100 if race.cor_df is not None else float("nan")
            for race in matched_races
        ]
        ax.plot(positions, values, color=color, marker="o", label=column)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylim(-100, 100)
    ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.set_xticks(positions)
    ax.set_xticklabels([f"{int(race.race_info['レース番号'].iloc[0])}R" for race in matched_races])
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(prop=_JAPANESE_FONT)
    figure.tight_layout()
    return figure


def _format_race_block(race: _MatchedRace, venue_name: str, kind: DayTrendKind) -> str:
    """1レース分のトレンドブロックを生成する。

    Args:
        race (_MatchedRace): 集計対象の1レース分のデータ。
        venue_name (str): 競馬場表示名（例: "東京"）。
        kind (DayTrendKind): 傾向記事の種類。

    Returns:
        str: フォーマットされたレースブロック文字列。
    """
    race_no = int(race.race_info["レース番号"].iloc[0])
    label = _race_label(race.race_info, venue_name, race_no)
    distance = int(race.race_info["距離"].iloc[0])
    runners = len(race.result_df)
    heading = f"### {label} {distance}m {runners}頭"

    top3 = race.result_df[race.result_df["確定着順"].isin([1, 2, 3])].sort_values("確定着順")

    lines: list[str] = [
        heading,
        "",
        "| 着順 | 枠番 | 人気 | 4角通過 | 後3F |",
        "| --- | --- | --- | --- | --- |",
    ]
    for _, horse_row in top3.iterrows():
        place = int(horse_row["確定着順"])
        gate = horse_row["枠番"]
        horse_no = horse_row["馬番"]
        if pd.notna(gate) and pd.notna(horse_no):
            gate_horse_str = f"{int(gate)}枠 {int(horse_no)}番"
        else:
            gate_horse_str = "-"
        ninki = int(horse_row["単勝人気順"]) if pd.notna(horse_row["単勝人気順"]) else "-"

        cols = [
            f"{place}着",
            gate_horse_str,
            f"{ninki}人気",
            format_corner4(horse_row, "番手"),
            format_halon(horse_row, race.result_df),
        ]
        lines.append("| " + " | ".join(cols) + " |")

    if race.cor_df is not None:
        lines.extend(["", *build_dynamics_table_lines(race.cor_df)])
    if race.figure is not None:
        image_path = f"img/{kind.image_dir}/{race.race_code}.png"
        lines.append("")
        lines.append(f"![{venue_name}{race_no}R 標準化散布図]({image_path})")

    return "\n".join(lines)


def _build_dememe_section(
    top3_entries: list[tuple[pd.Series, pd.DataFrame]],
    race_label: str,
    kind: DayTrendKind,
) -> tuple[str, dict[str, Figure]]:
    """集計対象全レースの出目集計セクションを生成する。

    人気・枠番・脚質・上がり順位ごとに、3着以内に入った頭数の棒グラフを載せる。

    Args:
        top3_entries (list[tuple[pd.Series, pd.DataFrame]]): (horse_row, result_df) のリスト。
        race_label (str): 対象レースの表記名。
        kind (DayTrendKind): 傾向記事の種類。

    Returns:
        str: 出目セクション文字列（## {前日|当日}の出目から始まる）。
        dict[str, Figure]: 記事ディレクトリからの相対パスから棒グラフへのマッピング。
    """
    rows = [row for row, _ in top3_entries]
    waku_counts = _count_waku(rows)
    kyaku_counts = _count_kyakushitsu(rows)
    ninki_labels = ["1人気", "2人気", "3人気", "4-6人気", "7-9人気", "10人気以下"]
    agari_labels = ["1位", "2位", "3位", "4-6位", "7-9位", "10位以下"]
    kyaku_labels = list(KYAKUSHITSU_DISPLAY.values())
    # 枠番以外の棒はMATLABの標準色の1色目で揃える
    base_color = _MATLAB_COLORS[0]

    # (項目名, 見出しのリンク先, 画像ファイル名, 目盛りラベル, 頭数, 棒の色)
    charts: list[tuple[str, str | None, str, list[str], list[int], list[str]]] = [
        (
            "人気",
            None,
            "dememe_ninki",
            ninki_labels,
            _count_ninki(rows),
            [base_color] * len(ninki_labels),
        ),
        (
            "枠番",
            None,
            "dememe_waku",
            [f"{waku}枠" for waku in range(1, 9)],
            [waku_counts[waku] for waku in range(1, 9)],
            [WAKU_TO_COLOR_DICT[waku] for waku in range(1, 9)],
        ),
        (
            "脚質",
            _KYAKUSHITSU_URL,
            "dememe_kyakushitsu",
            kyaku_labels,
            [kyaku_counts[name] for name in kyaku_labels],
            [base_color] * len(kyaku_labels),
        ),
        (
            "上がり順位",
            None,
            "dememe_agari",
            agari_labels,
            _count_agari_rank(top3_entries),
            [base_color] * len(agari_labels),
        ),
    ]

    lines: list[str] = [
        f"## {kind.label}の出目",
        "",
        f"各要素において、{kind.label}のレースのうち{race_label}と同じ競馬場、芝ダのレースで"
        "3着以内に入った頭数を集計。",
    ]
    images: dict[str, Figure] = {}
    for name, url, file_name, labels, counts, colors in charts:
        image_path = f"img/{kind.image_dir}/{file_name}.png"
        heading = f"[{name}]({url})" if url is not None else name
        lines.extend(["", f"**{heading}**", "", f"![{name}]({image_path})"])
        images[image_path] = _make_bar_chart(labels, counts, colors)
    return "\n".join(lines), images


def _make_bar_chart(labels: list[str], counts: list[int], colors: list[str]) -> Figure:
    """頭数の棒グラフを生成する。

    棒の上に頭数を表示し、縦軸の目盛りは整数にする。

    Args:
        labels (list[str]): 横軸の目盛りラベル。
        counts (list[int]): 各ラベルの頭数。
        colors (list[str]): 各棒の色（labels と同じ長さ）。

    Returns:
        Figure: 棒グラフ。
    """
    figure = Figure(figsize=(6, 3))
    ax = figure.subplots()
    positions = list(range(len(labels)))
    bars = ax.bar(
        positions,
        counts,
        color=colors,
        edgecolor="black",
        linewidth=0.8,
    )
    ax.bar_label(bars)
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, fontproperties=_JAPANESE_FONT)
    ax.set_ylim(0, max([*counts, 1]) + 1)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(True, axis="y", linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    figure.tight_layout()
    return figure


def _count_ninki(rows: list[pd.Series]) -> list[int]:
    """人気グループ[1人気,2人気,3人気,4-6,7-9,10以下]の頭数を返す。

    Args:
        rows (list[pd.Series]): 馬毎レース結果の行リスト。

    Returns:
        list[int]: 各グループの頭数リスト（6要素）。
    """
    counts = [0, 0, 0, 0, 0, 0]
    for row in rows:
        ninki = row["単勝人気順"]
        if pd.isna(ninki):
            continue
        ninki = int(ninki)
        if ninki == 1:
            counts[0] += 1
        elif ninki == 2:
            counts[1] += 1
        elif ninki == 3:
            counts[2] += 1
        elif 4 <= ninki <= 6:
            counts[3] += 1
        elif 7 <= ninki <= 9:
            counts[4] += 1
        else:
            counts[5] += 1
    return counts


def _count_waku(rows: list[pd.Series]) -> dict[int, int]:
    """枠番ごとの頭数を返す。

    Args:
        rows (list[pd.Series]): 馬毎レース結果の行リスト。

    Returns:
        dict[int, int]: 枠番（1-8）をキーとした頭数辞書。
    """
    counts: dict[int, int] = {i: 0 for i in range(1, 9)}
    for row in rows:
        waku = row["枠番"]
        if pd.isna(waku):
            continue
        waku_int = int(waku)
        if waku_int in counts:
            counts[waku_int] += 1
    return counts


def _count_kyakushitsu(rows: list[pd.Series]) -> dict[str, int]:
    """脚質（逃げ/先行/差し/追込）ごとの頭数を返す。

    Args:
        rows (list[pd.Series]): 馬毎レース結果の行リスト。

    Returns:
        dict[str, int]: 脚質の表示名をキーとした頭数辞書。
    """
    counts: dict[str, int] = {name: 0 for name in KYAKUSHITSU_DISPLAY.values()}
    for row in rows:
        display = kyakushitsu_display(row)
        if display:
            counts[display] += 1
    return counts


def _count_agari_rank(
    top3_entries: list[tuple[pd.Series, pd.DataFrame]],
) -> list[int]:
    """上がり順位グループ[1位,2位,3位,4-6,7-9,10以下]の頭数を返す。

    Args:
        top3_entries (list[tuple[pd.Series, pd.DataFrame]]): (horse_row, result_df) のリスト。

    Returns:
        list[int]: 各グループの頭数リスト（6要素）。
    """
    counts = [0, 0, 0, 0, 0, 0]
    for horse_row, result_df in top3_entries:
        halon = horse_row["後3ハロン"]
        if pd.isna(halon):
            continue
        rank = halon_rank(horse_row, result_df)
        if rank == 1:
            counts[0] += 1
        elif rank == 2:
            counts[1] += 1
        elif rank == 3:
            counts[2] += 1
        elif 4 <= rank <= 6:
            counts[3] += 1
        elif 7 <= rank <= 9:
            counts[4] += 1
        else:
            counts[5] += 1
    return counts
