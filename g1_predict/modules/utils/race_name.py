"""競走名本題から記事・ファイルで使うレース名を導出するモジュール。"""

import re

RACE_NAME_ABBREVIATIONS: dict[str, str] = {
    "スプリンターズステークス": "スプリンターズS",
}

# 表に書くときに短くする競走名本題 -> 短い表記。スポンサー名などを除き、netkeiba の表記に合わせる。
# ここに無いレースは、末尾の語の略記と全角英数字の半角化だけを行う。
SHORT_RACE_NAMES: dict[str, str] = {
    "朝日杯フューチュリティステークス": "朝日杯FS",
    "阪神ジュベナイルフィリーズ": "阪神JF",
    "マイルチャンピオンシップ": "マイルCS",
    "アメリカジョッキークラブカップ": "AJCC",
    "京王杯スプリングカップ": "京王杯SC",
    "サンケイスポーツ賞フローラステークス": "フローラS",
    "読売マイラーズカップ": "マイラーズC",
    "ＭＢＳ賞スワンステークス": "スワンS",
    "報知杯フィリーズレビュー": "フィリーズレビュー",
    "関西テレビ放送賞ローズステークス": "ローズS",
    "デイリー杯２歳ステークス": "デイリー杯2歳S",
    "日刊スポーツ賞中山金杯": "中山金杯",
    "ローレル競馬場賞中山牝馬ステークス": "中山牝馬S",
    "ダービー卿チャレンジトロフィー": "ダービー卿CT",
    "スポーツニッポン賞ステイヤーズステークス": "ステイヤーズS",
    "スポーツニッポン賞京都金杯": "京都金杯",
    "サンケイスポーツ杯阪神牝馬ステークス": "阪神牝馬S",
    "産経賞セントウルステークス": "セントウルS",
    "テレビ西日本賞北九州記念": "北九州記念",
    "農林水産省賞典　函館記念": "函館記念",
    "農林水産省賞典　新潟記念": "新潟記念",
    "農林水産省賞典　小倉記念": "小倉記念",
    "デイリー杯クイーンカップ": "クイーンC",
    "報知杯弥生賞ディープインパクト記念": "弥生賞",
    "北海道新聞杯クイーンステークス": "クイーンS",
    "朝日杯セントライト記念": "セントライト記念",
    "日刊スポーツ賞シンザン記念": "シンザン記念",
    "中日スポーツ賞ファルコンステークス": "ファルコンS",
    "東京スポーツ杯２歳ステークス": "東スポ杯2歳S",
    "ＫＢＳ京都賞ファンタジーステークス": "ファンタジーS",
    "京成杯オータムハンデキャップ": "京成杯AH",
    "アイビスサマーダッシュ": "アイビスSD",
    "サウジアラビアロイヤルカップ": "サウジアラビアRC",
    "ラジオＮＩＫＫＥＩ杯京都２歳ステークス": "京都2歳S",
}
# 地方との交流重賞の競走名に付く「（中央交流）」と、末尾の格付け（例: 「　Ｊｐｎ３」「　Ｇ１」）
_EXCHANGE_RACE_MARKS = re.compile(r"（中央交流）|　(?:Ｊｐｎ|Ｇ)[１２３]$")
# 競走名の末尾の語 -> 略記
_SUFFIX_ABBREVIATIONS: tuple[tuple[str, str], ...] = (
    ("ステークス", "S"),
    ("カップ", "C"),
    ("トロフィー", "T"),
)
# 全角英数字 -> 半角英数字
_FULLWIDTH_ALNUM = str.maketrans(
    "０１２３４５６７８９"
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
)


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


def to_short_race_name(kyosomei_hondai: str) -> str:
    """競走名本題を、横幅の狭い表に書くための短い表記に変換する。

    `SHORT_RACE_NAMES` に登録されているレースはその表記にする。登録されていないレースは、
    地方との交流重賞の「（中央交流）」と末尾の格付けを除き、末尾の「ステークス」「カップ」
    「トロフィー」を「S」「C」「T」にし、全角英数字を半角にする。

    Args:
        kyosomei_hondai (str): 競走名本題。

    Returns:
        str: 短い表記のレース名（例: 関西テレビ放送賞ローズステークス -> ローズS）。
    """
    if kyosomei_hondai in SHORT_RACE_NAMES:
        return SHORT_RACE_NAMES[kyosomei_hondai]
    name = _EXCHANGE_RACE_MARKS.sub("", kyosomei_hondai)
    for suffix, abbreviation in _SUFFIX_ABBREVIATIONS:
        if name.endswith(suffix):
            name = name[: -len(suffix)] + abbreviation
            break
    return name.translate(_FULLWIDTH_ALNUM)
