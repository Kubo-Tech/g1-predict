"""trend_section の単体テスト。"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from matplotlib.figure import Figure
from mykeibadb.exceptions import MykeibaDBError

from g1_predict.modules.gen_trend._trend_catalog import TrendCategory, TrendItem
from g1_predict.modules.gen_trend._trend_table_config import TableColumn
from g1_predict.modules.gen_trend.trend_section import (
    EntrySettings,
    TrendSections,
    build_trend_sections,
)

_SECTION = "g1_predict.modules.gen_trend.trend_section"


def test_build_trend_sections_returns_scope_note_and_sections_in_race_config_order() -> None:
    """集計対象の注記と、カテゴリ名 -> セクションを trends.yml の並び順で返す。"""
    context = MagicMock(race_name="東京優駿", kyori=2400)
    categories = [
        TrendCategory(name="基本項目", description="d1", items=[]),
        TrendCategory(name="前走", description="d2", items=[]),
    ]
    with (
        patch(f"{_SECTION}.load_trend_catalog", return_value={}) as mock_catalog,
        patch(f"{_SECTION}.build_race_context", return_value=context),
        patch(f"{_SECTION}.build_trend_categories", return_value=categories) as mock_build,
        patch(f"{_SECTION}.format_scope_note", return_value="※注記") as mock_note,
        patch(
            f"{_SECTION}.build_category_section",
            side_effect=lambda category, *_args, **_kwargs: f"## {category.name}",
        ),
    ):
        race_config = {"基本項目": ["人気"], "前走": ["前走着順"]}
        result = build_trend_sections(pd.DataFrame(), "東京優駿", race_config, "configs/trends")

    assert result == TrendSections(
        scope_note="※注記", sections={"基本項目": "## 基本項目", "前走": "## 前走"}
    )
    assert list(result.sections) == ["基本項目", "前走"]
    mock_catalog.assert_called_once_with("configs/trends")
    assert mock_build.call_args[0][2:] == ("東京優駿", 2400)
    assert mock_note.call_args[0] == (context, "東京優駿")


def _make_categories() -> list[TrendCategory]:
    """テスト用のカテゴリ（基本項目: 枠順、同年/前年レース実績: 同年高松宮記念着順）。"""
    return [
        TrendCategory(
            name="基本項目", description="d1", items=[TrendItem("枠順", {}, None)]
        ),
        TrendCategory(
            name="同年/前年レース実績",
            description="d2",
            items=[TrendItem("同年高松宮記念着順", {}, None)],
        ),
    ]


def _build_with_entries(
    table_config: dict[str, object],
    informative: bool = True,
) -> tuple[TrendSections, MagicMock, MagicMock]:
    """出走馬の確定後の設定で build_trend_sections を実行する。

    Args:
        table_config (dict[str, object]): table.yml の内容。
        informative (bool): 各項目の表を記事に載せる判定にするか。

    Returns:
        TrendSections: 生成結果。
        MagicMock: build_category_section のモック。
        MagicMock: make_comparison_table のモック。
    """
    context = MagicMock(race_name="スプリンターズステークス", kyori=1200)
    horses = pd.DataFrame({"waku": [1], "umaban": [1], "bamei": ["A"]})
    with (
        patch(f"{_SECTION}.load_trend_catalog", return_value={}),
        patch(f"{_SECTION}.build_race_context", return_value=context),
        patch(f"{_SECTION}.build_trend_categories", return_value=_make_categories()),
        patch(f"{_SECTION}.format_scope_note", return_value="※注記"),
        patch(f"{_SECTION}.fetch_entry_horses", return_value=horses),
        patch(
            f"{_SECTION}.build_item_table",
            side_effect=lambda item, *_args: MagicMock(item=item),
        ),
        patch(f"{_SECTION}.is_entry_table_informative", return_value=informative),
        patch(
            f"{_SECTION}.build_category_section",
            side_effect=lambda category, *_args, **_kwargs: f"## {category.name}",
        ) as mock_section,
        patch(f"{_SECTION}.make_comparison_table", return_value=Figure()) as mock_table,
    ):
        result = build_trend_sections(
            pd.DataFrame(),
            "スプリンターズS",
            {"基本項目": ["枠順"]},
            "configs/trends",
            EntrySettings(race_code="2026092706040911", table_config=table_config),
        )
    return result, mock_section, mock_table


def test_build_trend_sections_without_entries_has_no_images_and_no_entry_columns() -> None:
    """出走馬の設定が無い場合は、該当馬列も比較表も無い。"""
    context = MagicMock(race_name="東京優駿", kyori=2400)
    with (
        patch(f"{_SECTION}.load_trend_catalog", return_value={}),
        patch(f"{_SECTION}.build_race_context", return_value=context),
        patch(f"{_SECTION}.build_trend_categories", return_value=_make_categories()),
        patch(f"{_SECTION}.format_scope_note", return_value="※注記"),
        patch(f"{_SECTION}.build_item_table", return_value=MagicMock()) as mock_item,
        patch(f"{_SECTION}.build_category_section", return_value="## s") as mock_section,
        patch(f"{_SECTION}.fetch_entry_horses") as mock_horses,
    ):
        result = build_trend_sections(pd.DataFrame(), "東京優駿", {}, "configs/trends")

    assert result.images == {}
    assert list(result.sections) == ["基本項目", "同年/前年レース実績"]
    assert mock_item.call_args[0][2] is None
    assert mock_section.call_args[0][3] is False
    mock_horses.assert_not_called()


def test_build_trend_sections_with_entries_adds_comparison_section_at_end() -> None:
    """出走馬の設定がある場合は、table.yml の全カテゴリの項目を並べた比較表を最後に載せる。"""
    table_config = {"同年/前年レース実績": ["同年高松宮記念着順"], "基本項目": ["枠順"]}
    result, mock_section, mock_table = _build_with_entries(table_config)

    assert list(result.sections) == ["基本項目", "同年/前年レース実績", "比較表"]
    assert result.sections["比較表"] == (
        "## 比較表\n\n複勝率に差が出る項目を並べて比較した表。\n"
        "黄色はプラスデータ、灰色はマイナスデータ。\n"
        "「好データ」はプラスデータの該当数を数えたもの。\n\n"
        "![比較表](img/trend_table/比較表.png)"
    )
    assert list(result.images) == ["img/trend_table/比較表.png"]
    assert mock_section.call_args_list[0][0][3] is True
    assert mock_section.call_args_list[0][1] == {"horse_count": 1}
    # 列は table.yml の順に並ぶ
    shown = mock_table.call_args[0][1]
    assert [(column, [t.item.name for t in tables]) for column, tables in shown] == [
        (TableColumn("同年高松宮記念着順", ()), ["同年高松宮記念着順"]),
        (TableColumn("枠順", ()), ["枠順"]),
    ]


def test_build_trend_sections_without_shown_tables_has_no_comparison_section() -> None:
    """比較表に載せる項目の表が1つも無い場合は、比較表のセクションも画像も付けない。"""
    result, _, mock_table = _build_with_entries({"基本項目": ["枠順"]}, informative=False)
    assert result.images == {}
    assert "比較表" not in result.sections
    mock_table.assert_not_called()


def test_build_trend_sections_with_entries_drops_uninformative_tables() -> None:
    """出走馬の当たり方から載せないと判定した表は、記事にも比較表にも載せない。"""
    context = MagicMock(race_name="スプリンターズステークス", kyori=1200)
    horses = pd.DataFrame({"waku": [1], "umaban": [1], "bamei": ["A"]})
    tables = {
        "枠順": MagicMock(item=TrendItem("枠順", {}, None)),
        "同年高松宮記念着順": MagicMock(item=TrendItem("同年高松宮記念着順", {}, None)),
    }
    kept = tables["枠順"]
    with (
        patch(f"{_SECTION}.load_trend_catalog", return_value={}),
        patch(f"{_SECTION}.build_race_context", return_value=context),
        patch(f"{_SECTION}.build_trend_categories", return_value=_make_categories()),
        patch(f"{_SECTION}.format_scope_note", return_value="※注記"),
        patch(f"{_SECTION}.fetch_entry_horses", return_value=horses),
        patch(
            f"{_SECTION}.build_item_table",
            side_effect=lambda item, *_args: tables[item.name],
        ),
        patch(
            f"{_SECTION}.is_entry_table_informative",
            side_effect=lambda table, horse_count: table is kept and horse_count == 1,
        ),
        patch(f"{_SECTION}.build_category_section", return_value="## s") as mock_section,
        patch(f"{_SECTION}.make_comparison_table", return_value=Figure()) as mock_table,
    ):
        build_trend_sections(
            pd.DataFrame(),
            "スプリンターズS",
            {"基本項目": ["枠順"]},
            "configs/trends",
            EntrySettings(
                race_code="2026092706040911",
                table_config={"基本項目": ["枠順"], "同年/前年レース実績": ["同年高松宮記念着順"]},
            ),
        )
    assert mock_section.call_args_list[0][0][2] == [kept]
    assert mock_section.call_args_list[1][0][2] == []
    assert [tables for _, tables in mock_table.call_args[0][1]] == [[kept]]


# 準正常系
def test_build_trend_sections_with_invalid_table_config_raises() -> None:
    """table.yml に trends.yml に無いカテゴリがある場合は ValueError になる。"""
    with pytest.raises(ValueError):
        _build_with_entries({"存在しないカテゴリ": ["枠順"]})


def test_build_trend_sections_with_entries_propagates_missing_entries_error() -> None:
    """出馬表が DB に無い場合は、取得元の例外をそのまま送出する。"""
    context = MagicMock(race_name="スプリンターズステークス", kyori=1200)
    with (
        patch(f"{_SECTION}.load_trend_catalog", return_value={}),
        patch(f"{_SECTION}.build_race_context", return_value=context),
        patch(f"{_SECTION}.build_trend_categories", return_value=_make_categories()),
        patch(f"{_SECTION}.fetch_entry_horses", side_effect=MykeibaDBError("出走馬なし")),
        pytest.raises(MykeibaDBError),
    ):
        build_trend_sections(
            pd.DataFrame(),
            "スプリンターズS",
            {},
            "configs/trends",
            EntrySettings("2026092706040911", {"基本項目": ["枠順"]}),
        )
