from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from .schemas import Evidence  # 기존 Evidence 재활용


class GapVerifyRequest(BaseModel):
    """Gap 검증 요청"""
    query_text: str = Field(..., min_length=10, max_length=2000)
    days: int = Field(default=3, ge=1, le=30, description="괴리 신호 조회 기간 (일)")


class NewsValidation(BaseModel):
    """뉴스 검증 결과 (기존 Rumor 로직)"""
    trust_score: float = Field(ge=0.0, le=1.0, description="신뢰도 점수")
    news_found: int = Field(description="발견된 뉴스 수")
    exact_matches: int = Field(description="정확 매칭 뉴스 수")

    # 검증 지표
    has_contradictions: bool = Field(description="모순 기사 존재 여부")
    contradiction_count: int = Field(description="모순 기사 수")
    claim_support_ratio: float = Field(ge=0.0, le=1.0, description="주장 지지 비율")
    temporal_consistency: float = Field(ge=0.0, le=1.0, description="시간적 일치도")

    # DART 검증
    dart_confirmed: bool = Field(description="공시 확인 여부")
    dart_evidence_count: int = Field(description="관련 공시 수")

    # 종합 판단
    is_reliable: bool = Field(description="신뢰 가능 여부")
    reliability_level: str = Field(description="신뢰도 레벨: HIGH/MEDIUM/LOW")


class GapSignal(BaseModel):
    """괴리 신호"""
    stock_code: str = Field(description="회사명")
    stock_name: str = Field(description="종목명")
    news_title: str = Field(description="뉴스 제목")
    event_code: str = Field(description="이벤트 코드")
    news_date: str = Field(description="뉴스 날짜 YYYYMMDD")

    # 괴리 정보
    has_gap: bool = Field(description="괴리 존재 여부")
    direction: Optional[str] = Field(None, description="방향: OVER(과대반응) | UNDER(과소반응)")
    magnitude: Optional[str] = Field(None, description="강도: EXTREME | HIGH | MODERATE")
    z_score: Optional[float] = Field(None, description="Z-score")

    # 수익률 비교
    actual_return: float = Field(description="실제 수익률 (%)")
    expected_return: float = Field(description="예상 수익률 (%)")
    sample_count: int = Field(description="통계 샘플 수")

    # 해석
    interpretation: str = Field(description="괴리 해석")
    risk_level: str = Field(description="위험 레벨: HIGH/MEDIUM/LOW")


class GapVerifyResponse(BaseModel):
    """Gap 검증 응답"""
    id: str
    query: str

    # 추출 정보
    extracted: dict = Field(description="추출된 회사/회사명/이벤트")

    # 뉴스 검증 (기존 Rumor 로직)
    news_validation: NewsValidation

    # 괴리 신호
    gap_signals: List[GapSignal] = Field(default_factory=list, description="괴리 신호 목록")

    # 증거 자료
    evidence: List[Evidence] = Field(default_factory=list, description="증거 자료")

    # 최종 판단
    summary: str = Field(description="종합 요약")
    risk_alert: Optional[str] = Field(None, description="위험 경고")

    analyzed_at: datetime


class GapScanRequest(BaseModel):
    """괴리 스캔 요청"""
    hours: int = Field(default=48, ge=1, le=168, description="스캔 기간 (시간)")
    z_threshold: float = Field(default=2.0, ge=0.0, description="Z-score 임계값")


class GapCheckRequest(BaseModel):
    """종목 괴리 조회 요청"""
    stock_code: str = Field(description="회사명")
    days: int = Field(default=3, ge=1, le=30, description="조회 기간 (일)")


class GapListRequest(BaseModel):
    """괴리 목록 요청"""
    days: int = Field(default=7, ge=1, le=30, description="조회 기간")
    direction: Optional[str] = Field(None, description="OVER | UNDER")
    magnitude: Optional[str] = Field(None, description="EXTREME | HIGH | MODERATE")
    min_z: float = Field(default=2.0, ge=0.0, description="최소 |Z-score|")
    limit: int = Field(default=20, ge=1, le=100, description="최대 개수")
