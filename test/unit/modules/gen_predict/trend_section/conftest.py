"""trend_section テスト共通設定。"""
import sys
from unittest.mock import MagicMock

# openpyxl が未インストールの環境でも import できるようにする
if "openpyxl" not in sys.modules:
    sys.modules["openpyxl"] = MagicMock()
    sys.modules["openpyxl.styles"] = MagicMock()
