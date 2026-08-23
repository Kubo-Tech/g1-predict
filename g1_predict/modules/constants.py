"""複数の機能から参照する共通定数。"""

TRACK_CODE_TO_SHIBA_DA: dict[str, str] = {
    **{str(code): "芝" for code in range(10, 23)},
    **{str(code): "ダ" for code in range(23, 30)},
    **{str(code): "芝" for code in range(51, 60)},
}

GRADE_CODE_DISPLAY: dict[str, str] = {
    "A": "G1",
    "B": "G2",
    "C": "G3",
    "D": "重賞",
    "E": "特別",
    "F": "J・G1",
    "G": "J・G2",
    "H": "J・G3",
    "L": "L",
}
