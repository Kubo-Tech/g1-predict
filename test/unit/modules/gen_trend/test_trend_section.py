"""trend_section の単体テスト。"""

from unittest.mock import MagicMock, patch

import pandas as pd

from g1_predict.modules.gen_trend._trend_catalog import TrendCategory
from g1_predict.modules.gen_trend.trend_section import TrendSections, build_trend_sections

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
            side_effect=lambda category, _context: f"## {category.name}",
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
