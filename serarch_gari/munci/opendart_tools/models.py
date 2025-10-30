from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any

__all__ = [
    "DisclosureMeta",
    "DisclosureSignalType",
    "DisclosureSignal",
    "DARTVerificationResult",
    "RuleHit",
    "DARTVerdictResult",
]

@dataclass
class DisclosureMeta:
    rcept_no: str
    rcept_dt: str
    corp_code: str
    corp_name: str
    report_nm: str
    flr_nm: str = ""   # optional fields used by the verifier
    rm: str = ""
    pblntf_ty: str = ""  # 공시유형: A(정기), B(주요사항), I(거래소) 등
    counterparty: str = ""  # 계약 상대방 (거래처명)

class DisclosureSignalType(str, Enum):
    DECISION = "DECISION"   # official decision/contract: lowers rumor nature
    QUERY = "QUERY"         # price/rumor-related inquiry: raises rumor nature
    DENIAL = "DENIAL"       # official denial/clarification: rumor nature (exists) but not truth
    ANSWER = "ANSWER"       # official answer to an inquiry
    NEUTRAL = "NEUTRAL"

@dataclass
class DisclosureSignal:
    type: DisclosureSignalType
    keywords: List[str]
    weight: int
    description: str

@dataclass
class DARTVerificationResult:
    has_disclosure: bool
    total_found: int
    relevant_disclosures: List[DisclosureMeta]
    signals: List[DisclosureSignal]
    rumor_score_adjustment: int
    evidence_summary: str

@dataclass
class RuleHit:
    rule: str
    weight: int
    where: str
    matched: List[str]

@dataclass
class DARTVerdictResult:
    verdict: str               # "루머 가능성 높음" | "불확실" | "비루머(공식확인/부인)"
    score: int
    evidence: Dict[str, Any]
    disclosures: List[DisclosureMeta]
