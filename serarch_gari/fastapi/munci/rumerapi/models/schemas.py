from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class TrustLevelEnum(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class EvidenceType(str, Enum):
    DISCLOSURE = "DISCLOSURE"
    NEWS = "NEWS"
    WEB = "WEB"

class RumorVerifyRequest(BaseModel):
    query_text: str = Field(..., min_length=10, max_length=2000)
    source_url: Optional[str] = None

class Evidence(BaseModel):
    type: EvidenceType
    title: str
    url: str
    published_at: Optional[datetime] = None

class RumorVerifyResponse(BaseModel):
    id: str
    level: TrustLevelEnum
    score: float = Field(..., ge=0.0, le=1.0)
    summary: str
    top_evidence: List[Evidence] = Field(default_factory=list)
    checked_at: datetime


# ===== 유사사례 패턴 분석 =====

class PatternAnalysisRequest(BaseModel):
    query_text: str = Field(..., min_length=10, max_length=2000)
    lookback_days: int = Field(default=365, ge=30, le=1825)
    min_similarity: float = Field(default=0.6, ge=0.0, le=1.0)

class SimilarCase(BaseModel):
    title: str
    companies: List[str] = Field(default_factory=list)
    event_labels: List[str] = Field(default_factory=list)
    similarity_score: float
    published_at: Optional[datetime] = None
    url: Optional[str] = None
    trust_outcome: Optional[str] = None

class PatternInsight(BaseModel):
    pattern_type: str
    description: str
    frequency: int
    confidence: float

class PatternAnalysisResponse(BaseModel):
    id: str
    query: str
    total_similar_cases: int
    similar_cases: List[SimilarCase] = Field(default_factory=list)
    patterns: List[PatternInsight] = Field(default_factory=list)
    summary: str
    analyzed_at: datetime
