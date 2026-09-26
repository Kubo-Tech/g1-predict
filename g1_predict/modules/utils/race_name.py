"""競走名本題から記事・ファイルで使うレース名を導出するモジュール。"""

RACE_NAME_ABBREVIATIONS: dict[str, str] = {
    "スプリンターズステークス": "スプリンターズS",
}


def to_race_label(kyosomei_hondai: str) -> str:
    """競走名本題を記事・ファイルで使うレース名に変換する。

    `RACE_NAME_ABBREVIATIONS` に登録されているレースだけ略称に変換し、
    登録されていないレースは引数をそのまま返す。DB検索には使えないため、
    競走名本題でのDB照合が必要な箇所には変換前の値を渡すこと。

    Args:
        kyosomei_hondai (str): DBの競走名本題（`kyosomei_hondai`）。

    Returns:
        str: 記事タイトル・configファイル名・出力先ディレクトリ名に使うレース名。
    """
    return RACE_NAME_ABBREVIATIONS.get(kyosomei_hondai, kyosomei_hondai)
