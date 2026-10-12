"""dynamics_history の単体テスト。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from evaluation import CornerDataError
from matplotlib.figure import Figure

from g1_predict.modules.gen_dynamics_history.dynamics_history import (
    DynamicsHistoryBody,
    _fetch_laps,
    _fetch_win_times,
    build_dynamics_history,
    build_section_heading,
    calc_passage_1000m,
    format_race_time,
    parse_soha_time,
)

_MODULE = "g1_predict.modules.gen_dynamics_history.dynamics_history"
_CODE_2025 = "2025101908030711"
_CODE_2024 = "2024102008030711"
_CODE_2023 = "2023102208030711"
# lap 2000m: 12.0 x 10 の 1000m 通過 = 60.0
_LAPS = [120] * 10


# 正常系
def test_calc_passage_1000m_on_lap_boundary() -> None:
    """1000m地点がラップの区切りに当たる場合は、そこまでのラップの合計になる。"""
    laps = [120, 110, 118, 122, 121, 126]
    assert calc_passage_1000m(2000, laps) == 591


def test_calc_passage_1000m_prorates_lap() -> None:
    """区切りが無い場合は、1000m地点を含むラップを距離で案分して足す（2025年有馬記念）。"""
    laps = [69, 110, 118, 122, 121, 126, 125]
    assert calc_passage_1000m(2500, laps) == 603


def test_calc_passage_1000m_rounds_half_up() -> None:
    """案分した値は0.1秒単位に四捨五入する。"""
    # 最初のラップ 100m、次のラップ 200m（101）の半分 = 50.5 -> 51
    laps = [60, 100, 100, 100, 100, 101]
    assert calc_passage_1000m(2500, laps) == 60 + 100 + 100 + 100 + 100 + 51


def test_calc_passage_1000m_over_one_minute() -> None:
    """通過タイムが1分以上でも0.1秒単位の整数で返る。"""
    assert calc_passage_1000m(2000, [130] * 10) == 650


# 異常系
def test_calc_passage_1000m_short_laps_raises() -> None:
    """ラップが1000m地点に届かない場合は ValueError。"""
    with pytest.raises(ValueError, match="届きません"):
        calc_passage_1000m(2000, [120, 120])


def test_calc_passage_1000m_missing_lap_raises() -> None:
    """1000m地点までに記録されていないラップがある場合は ValueError。"""
    with pytest.raises(ValueError, match="記録されていません"):
        calc_passage_1000m(2000, [120, 110, 0, 122, 121, 126])


# 正常系
@pytest.mark.parametrize(
    ("tenths", "expected"),
    [(1183, "1:58.3"), (599, "59.9"), (600, "1:00.0"), (2013, "3:21.3"), (87, "8.7")],
)
def test_format_race_time(tenths: int, expected: str) -> None:
    """1分以上は M:SS.S、未満は S.S の形式になる。"""
    assert format_race_time(tenths) == expected


def test_parse_soha_time() -> None:
    """MSSS 形式の走破タイムを0.1秒単位にする。"""
    assert parse_soha_time("1583") == 1183
    assert parse_soha_time(" 599 ") == 599


# 異常系
@pytest.mark.parametrize("value", ["", "12", "12345", "1a83"])
def test_parse_soha_time_invalid_raises(value: str) -> None:
    """3〜4桁の数字でない走破タイムは ValueError。"""
    with pytest.raises(ValueError, match="走破タイム"):
        parse_soha_time(value)


# 正常系
def test_build_section_heading_with_course_kubun() -> None:
    """コース区分・何日目・馬場状態が入り、netkeiba の結果ページへリンクする。"""
    assert build_section_heading(_CODE_2025, "A", 7, "1") == (
        "## [25年 Aコース7日目 (良)](https://race.netkeiba.com/race/result.html?race_id=202508030711)"
    )


def test_build_section_heading_without_course_kubun() -> None:
    """コース区分が空の場合は年と馬場状態だけになる。"""
    assert build_section_heading("2009102505040811", "", None, "2") == (
        "## [09年 (稍重)](https://race.netkeiba.com/race/result.html?race_id=200905040811)"
    )


@pytest.mark.parametrize(("code", "name"), [("3", "重"), ("4", "不良")])
def test_build_section_heading_baba_names(code: str, name: str) -> None:
    """馬場状態コードが名称に変換される。"""
    assert build_section_heading(_CODE_2023, "", None, code).startswith(f"## [23年 ({name})]")


# 異常系
def test_build_section_heading_invalid_baba_raises() -> None:
    """馬場状態コードが不正なら ValueError。"""
    with pytest.raises(ValueError, match="馬場状態コード"):
        build_section_heading(_CODE_2023, "A", 1, "0")


def test_build_section_heading_missing_course_day_raises() -> None:
    """コース区分があるのに何日目が無いなら ValueError。"""
    with pytest.raises(ValueError, match="何日目"):
        build_section_heading(_CODE_2023, "A", None, "1")


# 正常系
def test_build_dynamics_history_orders_years_newest_first() -> None:
    """年ごとの節が新しい年から順に並び、冒頭と推移の節がある。"""
    body = _run([_race(_CODE_2023), _race(_CODE_2024), _race(_CODE_2025)])
    content = body.content
    assert content.startswith("# 【秋華賞2026】過去3年の展開\n")
    assert "過去3年（2023年〜2025年）の秋華賞の展開をまとめる。" in content
    assert "集計対象は京都芝2000mで行われた3年分。" in content
    assert "## 過去3年の推移" in content
    assert content.index("## [25年") < content.index("## [24年") < content.index("## [23年")
    url = "https://race.netkeiba.com/race/result.html?race_id=202508030711"
    assert f"## [25年 Aコース7日目 (良)]({url})" in content
    assert "勝ちタイム: 1:58.3  \n1000m通過: 1:00.0" in content
    assert "| +12% | -5% | +30% |" in content


def test_build_dynamics_history_descriptions_appear_once() -> None:
    """有利度の説明は推移の節に1回だけ書き、展開評価値の説明は書かない。"""
    from g1_predict.modules.utils.race_dynamics import (
        DYNAMICS_DESCRIPTION,
        TOTAL_EVALUATION_DESCRIPTION,
    )

    body = _run([_race(_CODE_2024), _race(_CODE_2025)], _context(2024, 2))
    assert body.content.count(DYNAMICS_DESCRIPTION) == 1
    assert TOTAL_EVALUATION_DESCRIPTION not in body.content


def test_build_dynamics_history_breaks_lines_after_intro_and_description() -> None:
    """冒頭の1文目と有利度の説明の末尾に半角スペース2つを付けて改行表示にする。"""
    from g1_predict.modules.utils.race_dynamics import DYNAMICS_DESCRIPTION

    body = _run([_race(_CODE_2024), _race(_CODE_2025)], _context(2024, 2))
    assert "の秋華賞の展開をまとめる。  \n集計対象は" in body.content
    assert f"{DYNAMICS_DESCRIPTION}  \nグラフの点は" in body.content


def test_build_dynamics_history_explains_track_marks_before_years() -> None:
    """推移の節に、点の塗りつぶしと白抜きが馬場状態を表すことを書く。"""
    body = _run([_race(_CODE_2024), _race(_CODE_2025)], _context(2024, 2))
    sentence = "グラフの点は、塗りつぶし（●）が良馬場、白抜き（○）が稍重・重・不良で行われた年。"
    assert body.content.count(sentence) == 1
    assert body.content.index(sentence) < body.content.index("## [25年")


def test_build_dynamics_history_skips_years_with_other_course() -> None:
    """条件に合わない年は節を出さず、{M}年分は条件に合うレースの数になる。"""
    body = _run([_race(_CODE_2023), _race(_CODE_2025)], _context(2023, 2))
    assert "集計対象は京都芝2000mで行われた2年分。" in body.content
    assert "## [24年" not in body.content
    assert "## [25年" in body.content
    assert "## [23年" in body.content


def test_build_dynamics_history_image_keys() -> None:
    """推移グラフ1枚と、年ごとの標準化散布図・展開評価値の2枚が画像になる。"""
    body = _run([_race(_CODE_2024), _race(_CODE_2025)], _context(2024, 2))
    assert set(body.images) == {
        "img/dynamics_history/dynamics.png",
        f"img/dynamics_history/{_CODE_2025}.png",
        f"img/dynamics_history/{_CODE_2025}_evaluation.png",
        f"img/dynamics_history/{_CODE_2024}.png",
        f"img/dynamics_history/{_CODE_2024}_evaluation.png",
    }
    assert all(isinstance(figure, Figure) for figure in body.images.values())
    assert "![過去2年の推移](img/dynamics_history/dynamics.png)" in body.content


def test_build_dynamics_history_without_course_kubun_heading() -> None:
    """コース区分が空の年は見出しに コース区分と何日目を出さない。"""
    body = _run([_race(_CODE_2025, kubun="", baba="2")], _context(2025, 1))
    assert "## [25年 (稍重)]" in body.content


def test_build_dynamics_history_uses_day_after_race_as_reference_date() -> None:
    """展開評価の基準日は開催日の翌日。"""
    captured: list[date] = []

    def evaluate(race_code: str, di: object, reference: date) -> tuple[object, Figure]:
        captured.append(reference)
        return SimpleNamespace(cor_df=_cor_df(0.1, 0.1, 0.1), eval_df=pd.DataFrame()), Figure()

    context = _context(2025, 1)
    with (
        patch(f"{_MODULE}.build_race_context", return_value=context),
        patch(f"{_MODULE}.fetch_past_races", return_value=pd.DataFrame([_race(_CODE_2025)])),
        patch(f"{_MODULE}.DataInterface"),
        patch(f"{_MODULE}._fetch_win_times", return_value={_CODE_2025: 1183}),
        patch(f"{_MODULE}._fetch_laps", return_value={_CODE_2025: _LAPS}),
        patch(f"{_MODULE}.fetch_course_days", return_value={"1019": 7}),
        patch(f"{_MODULE}.evaluate_race_dynamics_with_plot", side_effect=evaluate),
        patch(f"{_MODULE}.make_total_evaluation_chart", return_value=Figure()),
    ):
        build_dynamics_history(pd.DataFrame({"kaisai_nen": ["2026"]}), "秋華賞")
    assert captured == [date(2025, 10, 20)]


# 異常系
def test_build_dynamics_history_no_races_raises() -> None:
    """集計対象のレースが0件なら ValueError。"""
    with pytest.raises(ValueError, match="集計対象のレースがありません"):
        _run([], _context(2023, 0))


def test_build_dynamics_history_straight_race_raises() -> None:
    """集計対象のレースが1000m直線コースなら ValueError。"""
    with pytest.raises(ValueError, match="直線"):
        _run([_race(_CODE_2025)], _context(2025, 1), {_CODE_2025: None})


def test_build_dynamics_history_missing_result_raises_corner_data_error() -> None:
    """結果情報が無いレースは、勝ちタイムが無くても CornerDataError をそのまま出す。"""
    with (
        patch(f"{_MODULE}.build_race_context", return_value=_context(2025, 1)),
        patch(f"{_MODULE}.fetch_past_races", return_value=pd.DataFrame([_race(_CODE_2025)])),
        patch(f"{_MODULE}.DataInterface"),
        patch(f"{_MODULE}._fetch_win_times", return_value={}),
        patch(f"{_MODULE}._fetch_laps", return_value={}),
        patch(f"{_MODULE}.fetch_course_days", return_value={"1019": 7}),
        patch(
            f"{_MODULE}.evaluate_race_dynamics_with_plot",
            side_effect=CornerDataError("結果情報がありません"),
        ),
        pytest.raises(CornerDataError),
    ):
        build_dynamics_history(pd.DataFrame({"kaisai_nen": ["2026"]}), "秋華賞")


# 正常系
def test_fetch_win_times_parses_soha_time() -> None:
    """1着馬の走破タイムを0.1秒単位にして返す。同着は速い方。"""
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame(
        {"race_code": [_CODE_2025, _CODE_2024, _CODE_2024], "soha_time": ["1583", "1590", "1585"]}
    )
    result = _fetch_win_times(manager, [_CODE_2025, _CODE_2024])
    assert result == {_CODE_2025: 1183, _CODE_2024: 1185}


def test_fetch_laps_drops_trailing_empty_columns() -> None:
    """末尾の空の列は含めず、0.1秒単位の整数で返す。"""
    row = {"race_code": _CODE_2025} | {f"lap_time{i}": "" for i in range(1, 26)}
    row["lap_time1"] = "120"
    row["lap_time2"] = " 115"
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame([row])
    assert _fetch_laps(manager, [_CODE_2025]) == {_CODE_2025: [120, 115]}


def test_fetch_laps_keeps_position_of_missing_lap() -> None:
    """途中の空の列は詰めずに 0 として残す。"""
    row = {"race_code": _CODE_2025} | {f"lap_time{i}": "" for i in range(1, 26)}
    row["lap_time1"] = "120"
    row["lap_time3"] = "115"
    manager = MagicMock()
    manager.fetch_dataframe.return_value = pd.DataFrame([row])
    assert _fetch_laps(manager, [_CODE_2025]) == {_CODE_2025: [120, 0, 115]}


def _cor_df(sashi: float, waku: float, soto: float) -> pd.DataFrame:
    """有利度の表（相関係数）を作る。

    Args:
        sashi (float): 差し有利度の相関係数。
        waku (float): 外枠有利度の相関係数。
        soto (float): 外有利度の相関係数。

    Returns:
        pd.DataFrame: RaceDynamicsResult.cor_df と同じ列の1行の表。
    """
    return pd.DataFrame({"差し有利度": [sashi], "外枠有利度": [waku], "外有利度": [soto]})


def _context(first_year: int = 2023, race_count: int = 3) -> SimpleNamespace:
    """2026年の京都芝2000mのレースの TrendContext の代わりを作る。

    Args:
        first_year (int): 集計期間の初年。
        race_count (int): 集計対象のレースの数。

    Returns:
        SimpleNamespace: TrendContext と同じ属性を持つオブジェクト。
    """
    return SimpleNamespace(
        manager=MagicMock(),
        condition=MagicMock(),
        race_year=2026,
        keibajo_code="08",
        kyori=2000,
        shiba_da="芝",
        first_year=first_year,
        years=2026 - first_year,
        race_count=race_count,
    )


def _race(race_code: str, kubun: str = "A", baba: str = "1") -> dict[str, str]:
    """fetch_past_races() の1行を作る。

    Args:
        race_code (str): レースコード。
        kubun (str): コース区分。
        baba (str): 馬場状態コード。

    Returns:
        dict[str, str]: fetch_past_races() の戻り値の1行。
    """
    return {
        "race_code": race_code,
        "kaisai_nen": race_code[0:4],
        "kaisai_gappi": race_code[4:8],
        "keibajo_code": "08",
        "grade_code": "A",
        "course_kubun": kubun,
        "babajotai_code": baba,
    }


def _run(
    races: list[dict[str, str]],
    context: SimpleNamespace | None = None,
    dynamics_by_code: dict[str, object] | None = None,
) -> DynamicsHistoryBody:
    """build_dynamics_history を DB 部分をモックして実行する。

    Args:
        races (list[dict[str, str]]): fetch_past_races() が返す行。
        context (SimpleNamespace | None): build_race_context() が返す値。None なら _context()。
        dynamics_by_code (dict[str, object] | None): レースコード -> 展開評価の結果。
            None を値にしたレースは1000m直線コースとして扱う。

    Returns:
        DynamicsHistoryBody: 記事全文と画像。
    """
    context = context or _context()
    codes = [race["race_code"] for race in races]
    default = SimpleNamespace(cor_df=_cor_df(0.12, -0.05, 0.3), eval_df=pd.DataFrame())
    dynamics_by_code = dynamics_by_code or {}

    def evaluate(race_code: str, di: object, reference: date) -> tuple[object, Figure | None]:
        dynamics = dynamics_by_code.get(race_code, default)
        return dynamics, None if dynamics is None else Figure()

    with (
        patch(f"{_MODULE}.build_race_context", return_value=context),
        patch(f"{_MODULE}.fetch_past_races", return_value=pd.DataFrame(races)),
        patch(f"{_MODULE}.DataInterface"),
        patch(f"{_MODULE}._fetch_win_times", return_value={c: 1183 for c in codes}),
        patch(f"{_MODULE}._fetch_laps", return_value={c: _LAPS for c in codes}),
        patch(
            f"{_MODULE}.fetch_course_days",
            return_value={"1019": 7, "1020": 4, "1022": 2},
        ),
        patch(f"{_MODULE}.evaluate_race_dynamics_with_plot", side_effect=evaluate),
        patch(f"{_MODULE}.make_total_evaluation_chart", side_effect=lambda *_: Figure()),
    ):
        return build_dynamics_history(pd.DataFrame({"kaisai_nen": ["2026"]}), "秋華賞")
