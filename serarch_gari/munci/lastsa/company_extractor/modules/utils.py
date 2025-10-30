from __future__ import annotations
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import re
import hashlib

def setup_logging(DATA_PATH: str) -> logging.Logger:

    parent = Path(DATA_PATH).parent
    log_dir = parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'finalextractorComany.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('finalextractorComany')

def _generate_cache_key(text: str, context: Optional[Dict[str, Any]] = None) -> str:

    content = (text or '')[:500]
    if context:
        content += str(context.get('title', ''))
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def _calculate_string_similarity(s1: str, s2: str) -> float:

    if not s1 or not s2:
        return 0.0
    set1, set2 = set(s1.lower()), set(s2.lower())
    inter = len(set1 & set2)
    union = len(set1 | set2)
    jaccard = inter / union if union > 0 else 0.0
    length_similarity = 1.0 - abs(len(s1) - len(s2)) / max(len(s1), len(s2))
    return jaccard * 0.7 + length_similarity * 0.3

def _is_analyst_report(text: str, context: Optional[Dict[str, Any]] = None) -> bool:

    securities = [
        "미래에셋증권", "삼성증권", "KB증권", "한국투자증권", "NH투자증권",
        "신한투자증권", "하나증권", "메리츠증권", "키움증권", "대신증권",
        "유안타증권", "SK증권", "한화투자증권", "교보증권", "IBK투자증권",
        "현대차증권", "유진투자증권", "이베스트투자증권", "하이투자증권",
        "케이프투자증권", "DB금융투자", "토스증권", "한양증권",
        "JP모간", "골드만삭스", "모건스탠리", "UBS", "크레디트스위스",
        "HSBC", "씨티그룹", "도이치", "BNP파리바", "노무라", "CLSA", "맥쿼리"
    ]
    keywords = [
        "목표가", "목표주가", "투자의견", "상향", "하향", "유지",
        "매수", "매도", "중립", "보유", "Buy", "Sell", "Hold",
        "컨센서스", "TP", "애널리스트", "리서치", "리포트",
        "실적 전망", "실적 예상", "밸류에이션", "레이팅", "커버리지"
    ]
    low = text.lower()
    for sec in securities:
        if sec in text[:100]:
            for kw in keywords:
                if kw.lower() in low:
                    return True
    return False
