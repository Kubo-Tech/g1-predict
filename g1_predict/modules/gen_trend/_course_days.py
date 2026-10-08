"""開催日がコース区分の何日目かを求めるモジュール。"""

from datetime import date

from mykeibadb.connection import ConnectionManager

# 前の開催日からこの日数以上空いた開催日は、同じコース区分でも1日目に戻す
COURSE_RESET_GAP_DAYS = 14


def fetch_course_days(
    manager: ConnectionManager,
    keibajo_code: str,
    kaisai_nen: str,
) -> dict[str, int]:
    """同じ競馬場・同じ年の開催日ごとに、コース区分の何日目かを返す。

    Args:
        manager (ConnectionManager): DB接続マネージャ。
        keibajo_code (str): 競馬場コード。
        kaisai_nen (str): 開催年（YYYY）。

    Returns:
        dict[str, int]: 開催月日（MMDD）-> コース区分の何日目か。

    Raises:
        ValueError: 同じ開催日に複数のコース区分が登録されている場合。
    """
    sql = """
        SELECT DISTINCT r.kaisai_gappi, TRIM(r.course_kubun) AS course_kubun
        FROM race_shosai r
        WHERE r.keibajo_code = %s
          AND r.kaisai_nen = %s
          AND TRIM(r.course_kubun) != ''
        ORDER BY r.kaisai_gappi
    """
    df = manager.fetch_dataframe(sql, params=(keibajo_code, kaisai_nen))
    gappi_list = [str(v).strip() for v in df["kaisai_gappi"]]
    if len(set(gappi_list)) != len(gappi_list):
        raise ValueError(
            f"同じ開催日に複数のコース区分があります: keibajo_code={keibajo_code}, "
            f"kaisai_nen={kaisai_nen}"
        )
    kubun_list = [str(v).strip() for v in df["course_kubun"]]
    year = int(kaisai_nen)
    dates = [date(year, int(gappi[:2]), int(gappi[2:])) for gappi in gappi_list]
    days = assign_course_days(dates, kubun_list)
    return dict(zip(gappi_list, days))


def assign_course_days(dates: list[date], course_kubun_list: list[str]) -> list[int]:
    """開催日ごとに、コース区分の何日目かを数える。

    コース区分が前の開催日から変わった日、または前の開催日から
    COURSE_RESET_GAP_DAYS 日以上空いた日を1日目とする。

    Args:
        dates (list[date]): 同じ競馬場・同じ年の開催日（昇順）。
        course_kubun_list (list[str]): dates と同じ順のコース区分。

    Returns:
        list[int]: dates と同じ順の、コース区分の何日目か。

    Raises:
        ValueError: dates と course_kubun_list の長さが異なる場合。
    """
    if len(dates) != len(course_kubun_list):
        raise ValueError("dates と course_kubun_list の長さが異なります。")
    days: list[int] = []
    for i, (kaisai_date, kubun) in enumerate(zip(dates, course_kubun_list)):
        if i == 0:
            days.append(1)
            continue
        gap_days = (kaisai_date - dates[i - 1]).days
        if kubun != course_kubun_list[i - 1] or gap_days >= COURSE_RESET_GAP_DAYS:
            days.append(1)
        else:
            days.append(days[-1] + 1)
    return days
