"""build_past_race_dynamics_body の単体テスト。"""

import re
from collections.abc import Iterator
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from matplotlib.colors import to_hex

from g1_predict.modules.gen_past_race_dynamics.past_race_dynamics import (
    PastRaceDynamicsBody,
    build_past_race_dynamics_body,
)

_MODULE = "g1_predict.modules.gen_past_race_dynamics.past_race_dynamics"
_TARGET = "2026092706040911"
_G2 = "2026090609040211"
_STRAIGHT = "2026080104020407"
_CONDITION = "2026070506010101"
_CANCELLED = "2026062005010101"
_STEEPLE = "2026061505010101"
_LOCAL = "2026060530010101"
_NOT_HELD = "2026052405010101"
_OLD = "2026040505010101"

# 馬番 -> (血統登録番号, 馬名)
_HORSES = {1: ("0000000001", "ホースA"), 2: ("0000000002", "ホースB"), 3: ("0000000003", "ホースC")}


def _entry_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "馬番": list(_HORSES),
            "枠番": list(_HORSES),
            "血統登録番号": [horse_id for horse_id, _ in _HORSES.values()],
            "馬名": [name for _, name in _HORSES.values()],
        }
    )


def _pp_row(race_code: str, rank: object = 1, ijo: str = "0") -> dict[str, object]:
    return {
        "レースコード": race_code,
        "競馬場コード": race_code[8:10],
        "確定着順": rank,
        "異常区分コード": ijo,
    }


def _basic_info_row(
    race_code: str,
    hondai: object = None,
    grade: str = "_",
    shubetsu: str = "平地",
    condition_code: str = "703",
) -> dict[str, object]:
    return {
        "レースコード": race_code,
        "競走名本題": hondai,
        "競走条件名称": "",
        "競走条件コード": condition_code,
        "グレードコード": grade,
        "レース種別": shubetsu,
    }


def _result_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "馬番": [1, 2, 3, 4],
            "枠番": [1, 2, 3, 4],
            "確定着順": [3, 1, 2, 4],
            "馬名": ["ホースA", "ホースB", "ホースX", "ホースY"],
            "血統登録番号": ["0000000001", "0000000002", "0000000009", "0000000008"],
        }
    )


def _dynamics() -> SimpleNamespace:
    return SimpleNamespace(
        cor_df=pd.DataFrame({"差し有利度": [0.1], "外枠有利度": [-0.2], "外有利度": [0.3]}),
        eval_df=pd.DataFrame({"馬番": [1, 2, 3, 4], "総合評価": [0.4, 0.3, 0.2, 0.1]}),
    )


class _FakeRaceData:
    """過去成績と過去走の基本情報を持つRaceDataの代役。"""

    def __init__(self, past_performances: dict[int, pd.DataFrame]) -> None:
        self.reference_date = date(2026, 9, 27)
        self.entry_df = _entry_df()
        self.valid_horse_num = [1, 2, 3]
        self.past_performances_dict = past_performances
        self.past_race_basic_info_df = pd.DataFrame(
            [
                _basic_info_row(_G2, "産経賞セントウルステークス", "B"),
                _basic_info_row(_STRAIGHT, "アイビスサマーダッシュ", "C"),
                _basic_info_row(_CONDITION, None, "_", condition_code="010"),
                _basic_info_row(_CANCELLED),
                _basic_info_row(_STEEPLE, shubetsu="障害"),
                _basic_info_row(_LOCAL),
                _basic_info_row(_NOT_HELD),
                _basic_info_row(_OLD, "旧重賞", "A"),
            ]
        )
        self.fetched: list[str] = []

    def fetch_past_performances(self) -> None:
        self.fetched.append("past_performances")

    def fetch_past_race_basic_info(self) -> None:
        self.fetched.append("past_race_basic_info")


def _horse_a_past_performances() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _pp_row(_OLD),
            _pp_row(_NOT_HELD, rank=pd.NA),
            _pp_row(_LOCAL),
            _pp_row(_STEEPLE),
            _pp_row(_CANCELLED, rank=pd.NA, ijo="1"),
            _pp_row(_CONDITION),
            _pp_row(_STRAIGHT),
            _pp_row(_G2),
        ]
    )


@pytest.fixture
def evaluate_mock() -> Iterator[MagicMock]:
    """展開評価をモックし、直線レースだけ対象外にする。

    Yields:
        MagicMock: 展開評価関数のモック。
    """

    def evaluate(race_code: str, di: MagicMock, reference_date: date) -> tuple[object, object]:
        if race_code == _STRAIGHT:
            return None, None
        return _dynamics(), MagicMock(name=f"Figure{race_code}")

    with patch(f"{_MODULE}.evaluate_race_dynamics_with_plot", side_effect=evaluate) as mock:
        yield mock


def _build(
    num_past_races: int = 5,
    horse_b: pd.DataFrame | None = None,
    horse_c: pd.DataFrame | None = None,
) -> tuple[PastRaceDynamicsBody, _FakeRaceData]:
    empty = pd.DataFrame(columns=["レースコード", "競馬場コード", "確定着順", "異常区分コード"])
    fake = _FakeRaceData(
        {
            1: _horse_a_past_performances(),
            2: pd.DataFrame([_pp_row(_G2)]) if horse_b is None else horse_b,
            3: empty if horse_c is None else horse_c,
        }
    )
    di = MagicMock()
    di.get_result.side_effect = lambda race_code: _result_df()
    display_names = {
        _G2: "産経賞セントウルステークス",
        _STRAIGHT: "アイビスサマーダッシュ",
        _OLD: "新名ステークス",
    }
    with (
        patch(f"{_MODULE}.DataInterface", return_value=di),
        patch(f"{_MODULE}.RaceData", return_value=fake) as race_data_cls,
        patch(f"{_MODULE}.RaceGetter"),
        patch(f"{_MODULE}.get_race_display_names", return_value=display_names),
    ):
        body = build_past_race_dynamics_body(_TARGET, num_past_races)
    race_data_cls.assert_called_once_with(_TARGET, di, reference_date=date(2026, 9, 27))
    return body, fake


def _horse_section(text: str, horse: str) -> str:
    start = text.index(f"## {horse}\n")
    return text[start : text.index("</details>", start)]


# 正常系
@pytest.mark.usefixtures("evaluate_mock")
def test_details_wrap_each_horse_with_blank_lines_in_umaban_order() -> None:
    """馬名をh2見出しにし、過去走を details で囲んで開始タグの後と終了タグの前に空行を入れる。"""
    body, _ = _build()
    headings = re.findall(r"^## (.*)$", body.text, flags=re.MULTILINE)
    assert headings == ["展開評価値の合計値", "1. ホースA", "2. ホースB", "3. ホースC"]
    summaries = re.findall(r"<details><summary>(.*?)</summary>", body.text)
    assert summaries == ["過去走の展開評価を開く"] * 3
    assert "## 1. ホースA\n\n<details><summary>過去走の展開評価を開く</summary>\n\n" in body.text
    lines = body.text.split("\n")
    for index, line in enumerate(lines):
        if line.startswith("<details>"):
            assert lines[index + 1] == ""
        if line == "</details>":
            assert lines[index - 1] == ""
    assert body.text.count("</details>") == 3


@pytest.mark.usefixtures("evaluate_mock")
def test_body_starts_with_descriptions() -> None:
    """本文の冒頭に展開評価の説明を2つ載せる。"""
    body, _ = _build()
    assert body.text.startswith("差し有利度・外枠有利度・外有利度は、")
    assert "\n\n展開評価値は、" in body.text
    assert not body.text.startswith("#")


@pytest.mark.usefixtures("evaluate_mock")
def test_average_section_before_horses() -> None:
    """説明の後、1頭目の前に、展開評価値の平均値のセクションを載せる。"""
    body, _ = _build(num_past_races=4)
    assert (
        "好走した馬。\n\n"
        "## 展開評価値の合計値\n\n"
        "過去4走の展開評価値の平均値のランキング\n\n"
        "![展開評価値の平均値](img/past_dynamics/average.png)\n\n"
        "## 1. ホースA\n"
    ) in body.text


@pytest.mark.usefixtures("evaluate_mock")
def test_average_chart_excludes_straight_race_and_horse_without_past_race() -> None:
    """平均値は展開評価のある過去走で求め、平均値が無い馬はグラフに載せない。"""
    horse_b = pd.DataFrame([_pp_row(_G2), _pp_row(_STRAIGHT)])
    body, _ = _build(horse_b=horse_b)
    ax = body.images["img/past_dynamics/average.png"].axes[0]
    # ホースAはG2・条件戦・旧重賞で馬番1（0.4）、ホースBはG2で馬番2（0.3）
    assert [patch.get_width() for patch in ax.patches] == pytest.approx([0.4, 0.3])
    texts = [text.get_text() for text in ax.texts]
    assert "ホースC" not in texts
    assert {"ホースA", "ホースB", "+0.40", "+0.30"} <= set(texts)


@pytest.mark.usefixtures("evaluate_mock")
def test_past_races_exclude_not_started_steeplechase_local_and_not_held() -> None:
    """障害・地方は何走前には数えるが載せず、出走取消・開催されなかったレースは走数にも数えない。"""
    body, _ = _build()
    section = _horse_section(body.text, "1. ホースA")
    titles = re.findall(r"^### (\d+走前): (\d+年\d+月\d+日) ", section, flags=re.MULTILINE)
    assert titles == [
        ("1走前", "2026年9月6日"),
        ("2走前", "2026年8月1日"),
        ("3走前", "2026年7月5日"),
        ("6走前", "2026年4月5日"),
    ]


@pytest.mark.usefixtures("evaluate_mock")
def test_past_races_limited_to_num_past_races() -> None:
    """過去走は指定した数までで打ち切る。"""
    body, _ = _build(num_past_races=2)
    section = _horse_section(body.text, "1. ホースA")
    dates = re.findall(r"^### \d+走前: (\d+年\d+月\d+日) ", section, flags=re.MULTILINE)
    assert dates == ["2026年9月6日", "2026年8月1日"]


@pytest.mark.usefixtures("evaluate_mock")
def test_title_line_with_grade_and_url() -> None:
    """見出しに何走前・レース名・結果ページのURL・グレードを載せる。"""
    body, _ = _build()
    assert (
        "### 1走前: 2026年9月6日 [産経賞セントウルステークス]"
        "(https://race.netkeiba.com/race/result.html?race_id=202609040211) (G2)"
    ) in body.text


@pytest.mark.usefixtures("evaluate_mock")
def test_title_line_condition_race_has_condition_name_and_no_grade() -> None:
    """条件戦は条件名を使い、グレードが無ければ括弧を付けない。"""
    body, _ = _build()
    assert (
        "### 3走前: 2026年7月5日 [2勝クラス]"
        "(https://race.netkeiba.com/race/result.html?race_id=202606010101)\n"
    ) in body.text


@pytest.mark.usefixtures("evaluate_mock")
def test_title_line_uses_unified_race_name() -> None:
    """重賞は統一した競走名本題を使う。"""
    body, _ = _build()
    assert "### 6走前: 2026年4月5日 [新名ステークス]" in body.text


@pytest.mark.usefixtures("evaluate_mock")
def test_straight_race_has_note_instead_of_dynamics() -> None:
    """1000m直線コースは見出しの後に対象外の注記だけを載せる。"""
    body, _ = _build()
    section = _horse_section(body.text, "1. ホースA")
    assert (
        "### 2走前: 2026年8月1日 [アイビスサマーダッシュ]"
        "(https://race.netkeiba.com/race/result.html?race_id=202604020407) (G3)\n\n"
        "1000m直線コースのため展開評価の対象外。\n"
    ) in section
    assert f"img/past_dynamics/{_STRAIGHT}.png" not in body.images


@pytest.mark.usefixtures("evaluate_mock")
def test_horse_without_past_race_has_note() -> None:
    """過去走が無い馬は注記だけを載せる。"""
    body, _ = _build()
    assert _horse_section(body.text, "3. ホースC") == (
        "## 3. ホースC\n\n<details><summary>過去走の展開評価を開く</summary>\n\n"
        "中央の平地で出走した過去走なし。\n\n"
    )


@pytest.mark.usefixtures("evaluate_mock")
def test_highlight_own_bar_and_bold_other_runners_name() -> None:
    """その馬は棒を2色目にして左側の列と馬名を太字にし、今回の他の出走馬は棒を3色目にして馬名だけを太字にする。"""
    body, _ = _build()
    chart = body.images[f"img/past_dynamics/{_G2}_1.png"]
    ax = chart.axes[0]
    # 着順の順: 2(1着)・3(2着)・1(3着)・4(4着)
    assert [to_hex(patch.get_facecolor()).upper() for patch in ax.patches] == [
        "#EDB120",
        "#0072BD",
        "#D95319",
        "#0072BD",
    ]
    weights: dict[float, dict[str, str]] = {}
    for text in ax.texts:
        weights.setdefault(text.get_position()[1], {})[text.get_text()] = text.get_fontweight()
    assert set(weights[2].values()) == {"bold"}
    assert {text: weight for text, weight in weights[0].items() if weight == "bold"} == {
        "ホースB": "bold"
    }
    assert set(weights[1].values()) == {"normal"}


@pytest.mark.usefixtures("evaluate_mock")
def test_highlight_differs_by_horse() -> None:
    """同じ過去走でも、折りたたみの主の馬ごとに別の棒グラフを作り、強調する棒を変える。"""
    body, _ = _build()
    chart = body.images[f"img/past_dynamics/{_G2}_2.png"]
    colors = [to_hex(patch.get_facecolor()).upper() for patch in chart.axes[0].patches]
    assert colors == ["#D95319", "#0072BD", "#EDB120", "#0072BD"]


@pytest.mark.usefixtures("evaluate_mock")
def test_dynamics_table_scatter_and_chart_link() -> None:
    """有利度の表・標準化散布図・展開評価値の棒グラフを順に載せ、展開評価値の表は載せない。"""
    body, _ = _build()
    section = _horse_section(body.text, "2. ホースB")
    assert (
        "| 差し有利度 | 外枠有利度 | 外有利度 |\n| --- | --- | --- |\n| +10% | -20% | +30% |\n\n"
        f"![標準化散布図](img/past_dynamics/{_G2}.png)\n\n"
        f"![展開評価値](img/past_dynamics/{_G2}_2.png)\n"
    ) in section
    assert "展開評価値 |" not in body.text


def test_shared_past_race_is_evaluated_once_and_image_shared(evaluate_mock: MagicMock) -> None:
    """複数の出走馬が出ている過去走は、展開評価を1回だけ行い画像も1枚にする。"""
    body, _ = _build()
    evaluated = [call.args[0] for call in evaluate_mock.call_args_list]
    assert sorted(evaluated) == sorted([_G2, _STRAIGHT, _CONDITION, _OLD])
    assert all(call.args[2] == date(2026, 9, 27) for call in evaluate_mock.call_args_list)
    scatters = [f"img/past_dynamics/{code}.png" for code in (_G2, _CONDITION, _OLD)]
    charts = [f"img/past_dynamics/{_G2}_{umaban}.png" for umaban in (1, 2)]
    charts += [f"img/past_dynamics/{code}_1.png" for code in (_CONDITION, _OLD)]
    average = ["img/past_dynamics/average.png"]
    assert sorted(body.images) == sorted(scatters + charts + average)
    assert body.text.count(f"![標準化散布図](img/past_dynamics/{_G2}.png)") == 2


@pytest.mark.usefixtures("evaluate_mock")
def test_past_performances_fetched_before_basic_info() -> None:
    """過去成績を取得してから過去走の基本情報を取得する。"""
    _, fake = _build()
    assert fake.fetched == ["past_performances", "past_race_basic_info"]


# 準正常系
def test_dynamics_error_is_not_suppressed() -> None:
    """過去走の展開評価で例外が出た場合は、そのまま送出する。"""
    with (
        patch(f"{_MODULE}.evaluate_race_dynamics_with_plot", side_effect=ValueError("no corner")),
        pytest.raises(ValueError, match="no corner"),
    ):
        _build()
