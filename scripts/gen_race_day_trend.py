"""当日の傾向記事を生成するスクリプト。

コマンド:
cd path/to/g1-predict
python -m scripts.gen_race_day_trend --race-code <16桁 race_code>
"""

from g1_predict.modules.gen_day_trend.day_trend import RACE_DAY
from scripts.gen_day_trend import run_cli


def main() -> None:
    """エントリポイント。"""
    run_cli(RACE_DAY)


if __name__ == "__main__":
    main()
