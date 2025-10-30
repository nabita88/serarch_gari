
from __future__ import annotations
import re
from datetime import timezone, timedelta

CSV_FILE = "sample_3000.csv"  # 기본 입력 파일명
INDEX_NAME = "news_251015"  # 기본 ES 인덱스명

KST = timezone(timedelta(hours=9))

SPACE = re.compile(r"\s+")
PUNCT = re.compile(r"[\\[\\]\\(\\)<>…·,\\.\\!\\?:;\\\"'`]+")

PUBLISHER_TIER = {
    "연합뉴스": 0.8,
    "매일경제": 0.8,
    "한국경제": 0.8,
    "파이낸셜뉴스": 0.8,
    "서울경제": 0.65,
    "중앙일보": 0.65,
    "아시아경제": 0.65,
    "이데일리": 0.65,
    "헤럴드경제": 0.65,
    "연합뉴스TV": 0.5,
    "한국경제TV": 0.5,
    "MBN": 0.5,
    "뉴스1": 0.5,
    "일간스포츠": 0.5,
}
