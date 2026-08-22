"""出力パスの検証ユーティリティ。

race_code / year / race_name のような外部由来の値から出力パスを組み立てる際に、
パストラバーサル等で public ディレクトリの外へ書き込まれることを防ぐための
共通バリデーション関数を提供する。
"""

import os
import re
from pathlib import Path

# $ は文字列末尾の改行直前にもマッチするため、アンカーではなく fullmatch で判定する。
_RACE_CODE_PATTERN = re.compile(r"[0-9]{16}")
_YEAR_PATTERN = re.compile(r"[0-9]{4}")


def validate_race_code(race_code: str) -> None:
    """race_code が16桁の数字であることを検証する。

    Args:
        race_code (str): 検証対象の race_code。

    Raises:
        ValueError: 16桁の数字でない場合。
    """
    if not _RACE_CODE_PATTERN.fullmatch(race_code):
        raise ValueError(f"race_code は16桁の数字である必要があります: {race_code!r}")


def build_race_dir(public_dir: str, year: str, race_code: str, race_name: str) -> str:
    """レース単位の出力ディレクトリのパスを検証して返す。

    Args:
        public_dir (str): 出力先の public ディレクトリのパス。
        year (str): 開催年（4桁の数字）。
        race_code (str): 16桁 JRA-VAN 形式の race_code。
        race_name (str): レース名。

    Returns:
        str: 検証済みのレース単位出力ディレクトリのパス
            （`{public_dir}/{year}/{race_code}_{race_name}`）。

    Raises:
        ValueError: race_code / year / race_name が不正な場合、
            または組み立てたパスが public_dir の外を指す場合。
    """
    validate_race_code(race_code)
    if not _YEAR_PATTERN.fullmatch(year):
        raise ValueError(f"year は4桁の数字である必要があります: {year!r}")
    _validate_race_name(race_name)

    race_dir = os.path.join(public_dir, year, f"{race_code}_{race_name}")

    public_root = Path(public_dir).resolve()
    resolved_race_dir = Path(race_dir).resolve()
    if not resolved_race_dir.is_relative_to(public_root):
        raise ValueError(f"出力先パスが public_dir の外を指しています: {race_dir!r}")

    return race_dir


def _validate_race_name(race_name: str) -> None:
    r"""race_name にパス区切り文字や不正な値が含まれないことを検証する。

    Args:
        race_name (str): 検証対象のレース名。

    Raises:
        ValueError: race_name が空文字、`.`・`..`、
            またはパス区切り文字（`/`・`\`）を含む場合。
    """
    if race_name in ("", ".", "..") or "\\" in race_name:
        raise ValueError(f"race_name が不正です: {race_name!r}")
    if Path(race_name).name != race_name:
        raise ValueError(f"race_name が不正です: {race_name!r}")
