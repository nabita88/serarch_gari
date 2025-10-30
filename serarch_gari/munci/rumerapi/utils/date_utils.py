
from datetime import datetime, date
from typing import Union


def to_yyyymmdd(value: Union[str, date, datetime]) -> str:

    if isinstance(value, str):
        # 이미 YYYYMMDD 형식인 경우
        clean = value.replace("-", "").replace("/", "").strip()
        if len(clean) == 8 and clean.isdigit():
            return clean
        
        # YYYY-MM-DD 형식 파싱
        if len(value) == 10:
            return value.replace("-", "")
            
        raise ValueError(f"지원하지 않는 날짜 문자열 형식: {value}")
    
    elif isinstance(value, (date, datetime)):
        return value.strftime("%Y%m%d")
    
    else:
        raise TypeError(f"지원하지 않는 날짜 타입: {type(value)}")


def to_db_date(yyyymmdd: str) -> str:

    if len(yyyymmdd) != 8:
        raise ValueError(f"YYYYMMDD 형식이 아님: {yyyymmdd}")
    
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


def from_db_date(db_date: Union[str, date]) -> str:

    return to_yyyymmdd(db_date)
