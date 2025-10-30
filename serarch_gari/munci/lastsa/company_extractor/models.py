from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class CompanyInfo:
    """개별 기업 상세 정보"""
    name: str
    stock_code: Optional[str] = None
    corp_code: Optional[str] = None
    sector: Optional[str] = None
    market: Optional[str] = None


@dataclass
class ExtractionResult:
    companies: List[str]
    confidence_scores: Dict[str, float]
    extraction_methods: Dict[str, List[str]]
    validation_status: Dict[str, str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 추가: 기업별 상세 정보
    company_details: Dict[str, CompanyInfo] = field(default_factory=dict)


@dataclass
class ValidationResult:
    is_valid: bool
    confidence: float
    validation_methods: List[str]
    suggestions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
