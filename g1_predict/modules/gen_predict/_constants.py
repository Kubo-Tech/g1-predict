"""gen_predict モジュール共通定数。"""

TRACK_CODE_TO_SHIBA_DA: dict[str, str] = {
    **{str(code): "芝" for code in range(10, 23)},
    **{str(code): "ダ" for code in range(23, 30)},
    **{str(code): "芝" for code in range(51, 60)},
}
