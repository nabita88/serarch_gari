from __future__ import annotations
import datetime as dt
from typing import Iterable, List

__all__ = ["to_yyyymmdd", "match_keywords", "clamp", "normalize_company_name"]

def to_yyyymmdd(d: dt.date | dt.datetime | str) -> str:
    if isinstance(d, str):
        s = d.replace("-", "")
        if len(s) == 8 and s.isdigit():
            return s
        raise ValueError(f"Unsupported date format: {d!r}")
    if isinstance(d, dt.datetime):
        d = d.date()
    return d.strftime("%Y%m%d")

def match_keywords(text: str, keywords: Iterable[str]) -> List[str]:
    t = (text or "").lower()
    found = []
    for kw in keywords:
        if kw.lower() in t:
            found.append(kw)
    return found

def clamp(x: int | float, lo: int | float, hi: int | float) -> int | float:
    return max(lo, min(hi, x))

def normalize_company_name(name: str) -> str:
    if not name:
        return name
    n = name.replace("(주)", "").replace("주식회사", "").strip()
    return n
