from __future__ import annotations
import re
from datetime import datetime, timedelta
from typing import Tuple
from dateutil import parser
from dateutil.relativedelta import relativedelta

def extract_date_context(text: str) -> Tuple[datetime, datetime]:
    now = datetime.now()
    lower_text = (text or "").lower()

    relative_patterns = {
        "어제": (now - timedelta(days=1), now - timedelta(days=1)),
        "그제": (now - timedelta(days=2), now - timedelta(days=2)),
        "오늘": (now.replace(hour=0, minute=0, second=0, microsecond=0), now),  # refined
        "이번주": (now - timedelta(days=now.weekday()), now),
        "지난주": (now - timedelta(days=now.weekday() + 7), now - timedelta(days=now.weekday() + 1)),
        "이번달": (now.replace(day=1), now),
        "지난달": ((now.replace(day=1) - timedelta(days=1)).replace(day=1), now.replace(day=1) - timedelta(days=1)),
        "올해": (datetime(now.year, 1, 1), now),
        "작년": (datetime(now.year - 1, 1, 1), datetime(now.year - 1, 12, 31)),
        "재작년": (datetime(now.year - 2, 1, 1), datetime(now.year - 2, 12, 31)),
        "최근": (now - timedelta(days=7), now),
        "요즘": (now - timedelta(days=14), now),
        "근래": (now - timedelta(days=30), now),
        "최근 일주일": (now - timedelta(days=7), now),
        "최근 한달": (now - timedelta(days=30), now),
        "최근 3개월": (now - relativedelta(months=3), now),
        "최근 6개월": (now - relativedelta(months=6), now),
    }
    for pattern, date_range in relative_patterns.items():
        if pattern in lower_text:
            return date_range

    days_ago = re.search(r"(\d+)\s*일\s*전", lower_text)
    if days_ago:
        days = int(days_ago.group(1))
        target_date = now - timedelta(days=days)
        return (target_date - timedelta(days=1), target_date + timedelta(days=1))

    weeks_ago = re.search(r"(\d+)\s*주\s*전", lower_text)
    if weeks_ago:
        weeks = int(weeks_ago.group(1))
        target_date = now - timedelta(weeks=weeks)
        return (target_date - timedelta(days=3), target_date + timedelta(days=3))

    months_ago = re.search(r"(\d+)\s*개월\s*전", lower_text)
    if months_ago:
        months = int(months_ago.group(1))
        target_date = now - relativedelta(months=months)
        start = target_date.replace(day=1)
        end = (start + relativedelta(months=1)) - timedelta(days=1)
        return (start, end)

    quarter_patterns = {
        "1분기": (1, 3),
        "2분기": (4, 6),
        "3분기": (7, 9),
        "4분기": (10, 12),
        "상반기": (1, 6),
        "하반기": (7, 12),
    }
    year_quarter = re.search(r"(\d{4})[년]?\s*(1|2|3|4)\s*분기", lower_text)
    if year_quarter:
        year = int(year_quarter.group(1)); quarter = int(year_quarter.group(2))
        start_month = (quarter - 1) * 3 + 1; end_month = quarter * 3
        start = datetime(year, start_month, 1)
        end = datetime(year, end_month, 1) + relativedelta(months=1) - timedelta(days=1)
        return (start - timedelta(days=3), min(end + timedelta(days=3), now))

    for quarter_name, (start_month, end_month) in quarter_patterns.items():
        if quarter_name in lower_text:
            if "올해" in lower_text or "이번" in lower_text:
                year = now.year
            elif "작년" in lower_text or "지난해" in lower_text:
                year = now.year - 1
            elif "재작년" in lower_text:
                year = now.year - 2
            else:
                year_match = re.search(r"(\d{4})", lower_text)
                year = int(year_match.group(1)) if year_match else now.year
            start = datetime(year, start_month, 1)
            end = datetime(year, end_month, 1) + relativedelta(months=1) - timedelta(days=1)
            return (start - timedelta(days=3), min(end + timedelta(days=3), now))

    date_patterns = [
        r"(\d{4})[년\.\-/]\s*(\d{1,2})[월\.\-/]\s*(\d{1,2})[일]?",
        r"(\d{4})[년\.\-/]\s*(\d{1,2})[월]?",
        r"(\d{2,4})[년]\s*(\d{1,2})[월]",
    ]
    for pattern in date_patterns:
        m = re.search(pattern, text or "")
        if m:
            groups = m.groups()
            y = int(groups[0]); y = 2000 + y if y < 100 and y < 50 else (1900 + y if y < 100 else y)
            mm = int(groups[1])
            if len(groups) == 3 and groups[2]:
                dd = int(groups[2]); target_date = datetime(y, mm, dd)
                return (target_date - timedelta(days=1), target_date + timedelta(days=1))
            start = datetime(y, mm, 1)
            end = (datetime(y + 1, 1, 1) - timedelta(days=1)) if mm == 12 else (datetime(y, mm + 1, 1) - timedelta(days=1))
            return (start - timedelta(days=3), min(end + timedelta(days=3), now))

    year_only = re.search(r"(\d{4})[년]", text or "")
    if year_only:
        y = int(year_only.group(1))
        if y == now.year:
            return (now - timedelta(days=120)), now
        return (datetime(y, 1, 1), min(datetime(y, 12, 31), now))

    try:
        parsed_date = parser.parse(text, fuzzy=True, default=now)
        return (parsed_date - timedelta(days=7), min(parsed_date + timedelta(days=7), now))
    except Exception:
        pass

    event_dates = {
        "코로나": (datetime(2020, 1, 1), datetime(2023, 5, 11)),
        "러우전쟁": (datetime(2022, 2, 24), now),
        "금융위기": (datetime(2008, 9, 1), datetime(2009, 6, 30)),
    }
    for event, date_range in event_dates.items():
        if event in lower_text:
            return date_range

    return (now - timedelta(days=30), now)

def extract_date_context_legacy(text: str):
    now = datetime.now()
    m = re.search(r"(\d{4})[년\.\-/]?\s*(\d{1,2})[월\.\-/]?", text or "")
    if m:
        y, mm = int(m.group(1)), int(m.group(2))
        start = datetime(y, mm, 1)
        end = (datetime(y + 1, 1, 1) - timedelta(days=1)) if mm == 12 else (datetime(y, mm + 1, 1) - timedelta(days=1))
        return start - timedelta(days=3), min(end + timedelta(days=3), now)
    m = re.search(r"(\d{4})년", text or "")
    if m:
        y = int(m.group(1))
        if y == now.year:
            return now - timedelta(days=120), now
        return (datetime(y, 1, 1), min(datetime(y, 12, 31), now))
    return now - timedelta(days=30), now
