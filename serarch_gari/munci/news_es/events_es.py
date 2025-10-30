
from __future__ import annotations
import os
from typing import Dict, List, Tuple

_EVENT_ALIAS2CODE = None
_EVENT_CODE2LABEL = {
    "liquidity_crunch": "자금부족",
    "rights_issue": "유상증자",
    "cb_issue": "전환사채",
    "workout": "워크아웃",
    "asset_sale": "자산 매각",
}

def load_event_alias_index(path: str = "config/event_synonyms.txt") -> Dict[str, str]:
    global _EVENT_ALIAS2CODE
    if _EVENT_ALIAS2CODE is None:
        alias2code: Dict[str, str] = {}
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=>" not in line:
                            continue
                        lhs, rhs = line.split("=>", 1)
                        code = rhs.strip()
                        for alias in [a.strip().lower() for a in lhs.split(",")]:
                            if alias:
                                alias2code[alias] = code
            else:
                print(f"[경고] event synonyms not found: {path}")
        except Exception as e:
            print(f"[경고] load_event_alias_index 실패: {e}")
        _EVENT_ALIAS2CODE = alias2code
    return _EVENT_ALIAS2CODE

def resolve_event_from_query(q: str) -> Tuple[List[str], List[str]]:
    idx = load_event_alias_index()
    lq = (q or "").lower()
    codes, matched = set(), []
    for alias, code in idx.items():
        if alias and alias in lq:
            codes.add(code); matched.append(alias)
    return sorted(codes), matched

def _extract_event_keywords_from_query(q: str) -> List[str]:
    idx = load_event_alias_index()
    lq = (q or "").lower()
    keywords: List[str] = []

    for alias in idx.keys():
        if alias and alias in lq:
            keywords.append(alias)

    specific_event_terms = [
        "자금난", "유동성 위기", "유동성 경색", "증자", "유상증자",
        "전환사채", "워크아웃", "채권단", "구조조정", "자산 매각",
        "인수합병", "M&A", "부도", "회생", "파산", "감자", "CB", "BW",
        "차환", "디폴트", "채무불이행"
    ]
    for term in specific_event_terms:
        if term in q and term not in keywords:
            keywords.append(term)

    return keywords[:10]

def extract_events(text: str):
    idx = load_event_alias_index()
    lt = (text or "").lower()

    event_codes: List[str] = []
    confidence_map = {}

    for alias, code in idx.items():
        if alias and alias in lt:
            if code not in event_codes:
                event_codes.append(code)
                confidence = min(0.9, 0.5 + len(alias) * 0.05)
                confidence_map[code] = max(confidence_map.get(code, 0), confidence)

    if "워크아웃" in lt and "개시" in lt:
        if "workout" in event_codes:
            confidence_map["workout"] = 0.95

    if "유동성" in lt and ("위기" in lt or "경색" in lt):
        if "liquidity_crunch" in event_codes:
            confidence_map["liquidity_crunch"] = 0.9

    if "전환사채" in lt and "발행" in lt:
        if "cb_issue" in event_codes:
            confidence_map["cb_issue"] = 0.85

    return event_codes, confidence_map

EVENT_CODE2LABEL = _EVENT_CODE2LABEL
