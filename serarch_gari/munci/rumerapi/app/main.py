from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Optional, List

from munci.rumerapi.models.schemas import (
    RumorVerifyRequest, RumorVerifyResponse,
    PatternAnalysisRequest, PatternAnalysisResponse
)
from munci.rumerapi.models.gap_schemas import (
    GapVerifyRequest, GapVerifyResponse,
    GapScanRequest
)
from munci.rumerapi.services.rumor_service import RumorVerificationServiceES
from munci.rumerapi.services.pattern_service import PatternAnalysisService
from munci.rumerapi.services.gap_verification_service import GapVerificationService
from munci.rumerapi.services.build_news_history import NewsGapScanner
from munci.rumerapi.services.gap_checker import NewsGapChecker
from munci.rumerapi.extractors.companyGpt import initialize_extractor
from munci.lastsa.event_with_translate import initialize_event_classifier, classify_event
from munci.rumerapi.core.config import settings
from munci.rumerapi.core.logging import setup_logging

setup_logging()

services = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print(" 서비스 초기화 중...")
    print("=" * 60)

    try:
        services["rumor"] = RumorVerificationServiceES()
        print(" RumorVerificationServiceES 초기화 완료")
    except Exception as e:
        print(f" RumorVerificationServiceES 초기화 실패: {e}")
        services["rumor"] = None

    try:
        services["pattern"] = PatternAnalysisService()
        print(" PatternAnalysisService 초기화 완료")
    except Exception as e:
        print(f" PatternAnalysisService 초기화 실패: {e}")
        services["pattern"] = None

    try:
        services["extractor"] = initialize_extractor()
        print(" CompanyExtractor 초기화 완료")
    except Exception as e:
        print(f" CompanyExtractor 초기화 실패: {e}")
        services["extractor"] = None

    try:
        services["classifier"] = initialize_event_classifier()
        print(" EventClassifier 초기화 완료")
    except Exception as e:
        print(f" EventClassifier 초기화 실패: {e}")
        services["classifier"] = None

    try:
        services["gap_verification"] = GapVerificationService()
        print(" GapVerificationService 초기화 완료")
    except Exception as e:
        print(f" GapVerificationService 초기화 실패: {e}")
        services["gap_verification"] = None

    try:
        services["gap_scanner"] = NewsGapScanner()
        print(" NewsGapScanner 초기화 완료")
    except Exception as e:
        print(f"NewsGapScanner 초기화 실패: {e}")
        services["gap_scanner"] = None

    try:
        services["gap_checker"] = NewsGapChecker()
        print(" NewsGapChecker 초기화 완료")
    except Exception as e:
        print(f" NewsGapChecker 초기화 실패: {e}")
        services["gap_checker"] = None

    print("=" * 60)
    print(" 모든 서비스 초기화 완료!")
    print("=" * 60)

    yield

    print("=" * 60)
    print(" 서비스 정리 중...")
    print("=" * 60)
    services.clear()
    print("모든 서비스 정리 완료")


app = FastAPI(
    title="루머 검증 + 괴리 분석 API",
    version="5.0.0",
    description="루머 검증 + 유사사례 패턴 분석 + 뉴스 괴리 분석 통합 API",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allow_origins.split(",")] if settings.allow_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ready",
        "timestamp": datetime.now().isoformat(),
        "es_index": settings.es_index,
        "services": {
            "rumor": services.get("rumor") is not None,
            "pattern": services.get("pattern") is not None,
            "extractor": services.get("extractor") is not None,
            "classifier": services.get("classifier") is not None,
            "gap_verification": services.get("gap_verification") is not None,
            "gap_scanner": services.get("gap_scanner") is not None,
            "gap_checker": services.get("gap_checker") is not None,
        }
    }


@app.post("/rumors/verify", response_model=RumorVerifyResponse)
def verify_rumor(req: RumorVerifyRequest):
    service = services.get("rumor")
    if service is None:
        raise HTTPException(status_code=503, detail="RumorService not initialized")

    try:
        return service.verify(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/patterns/analyze", response_model=PatternAnalysisResponse)
def analyze_pattern(req: PatternAnalysisRequest):
    service = services.get("pattern")
    if service is None:
        raise HTTPException(status_code=503, detail="PatternService not initialized")

    try:
        return service.analyze(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/gaps/verify", response_model=GapVerifyResponse)
def verify_with_gap(req: GapVerifyRequest):
    service = services.get("gap_verification")
    if service is None:
        raise HTTPException(status_code=503, detail="GapVerificationService not initialized")

    try:
        return service.verify(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/gaps/scan")
def scan_gaps(req: GapScanRequest):
    scanner = services.get("gap_scanner")
    if scanner is None:
        raise HTTPException(status_code=503, detail="GapScanner not initialized")

    try:
        gaps = scanner.scan_recent(hours=req.hours)
        return {
            "scanned_hours": req.hours,
            "gap_count": len(gaps),
            "gaps": gaps
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/gaps/check/{stock_code}")
def check_stock_gap(
        stock_code: str,
        days: int = Query(3, ge=1, le=30, description="조회 기간 (일)")
):
    checker = services.get("gap_checker")
    if checker is None:
        raise HTTPException(status_code=503, detail="GapChecker not initialized")

    try:
        result = checker.check(stock_code, days=days)
        return {
            "stock_code": stock_code,
            "days": days,
            "has_gap": result["has_gap"],
            "gap_count": len(result["gap_signals"]),
            "gap_signals": result["gap_signals"],
            "price_change": result["price_change"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def check_stock_gap(
        stock_code: str,
        days: int = Query(3, ge=1, le=30, description="조회 기간 (일)")
):
    checker = services.get("gap_checker")
    if checker is None:
        raise HTTPException(status_code=503, detail="GapChecker not initialized")

    try:
        result = checker.check(stock_code, days=days)
        return {
            "stock_code": stock_code,
            "days": days,
            "has_gap": result["has_gap"],
            "gap_count": len(result["gap_signals"]),
            "gap_signals": result["gap_signals"],
            "price_change": result["price_change"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/gaps/list")
def list_gaps(
        days: int = Query(7, ge=1, le=30, description="조회 기간 (일)"),
        direction: Optional[str] = Query(None, description="OVER | UNDER"),
        magnitude: Optional[str] = Query(None, description="EXTREME | HIGH | MODERATE"),
        min_z: float = Query(2.0, ge=0.0, description="최소 |Z-score|"),
        limit: int = Query(20, ge=1, le=100, description="최대 개수")
):
    checker = services.get("gap_checker")
    if checker is None:
        raise HTTPException(status_code=503, detail="GapChecker not initialized")

    try:
        gaps = checker.list_gaps(
            days=days,
            direction=direction,
            magnitude=magnitude,
            min_z=min_z,
            limit=limit
        )
        return {
            "total": len(gaps),
            "gaps": gaps,
            "filters": {
                "days": days,
                "direction": direction,
                "magnitude": magnitude,
                "min_z": min_z
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/gaps/stats")
def gap_stats(
        days: int = Query(7, ge=1, le=30, description="조회 기간 (일)")
):
    checker = services.get("gap_checker")
    if checker is None:
        raise HTTPException(status_code=503, detail="GapChecker not initialized")

    try:
        return checker.get_stats(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/test/extract-companies")
def test_extract_companies(text: str):
    extractor = services.get("extractor")
    if extractor is None:
        raise HTTPException(status_code=503, detail="Extractor not initialized")

    result = {
        "input": text,
        "companies": extractor.extract_companies(text),
        "methods_tried": []
    }

    if extractor.company_extractor:
        try:
            ce_result = extractor.extract_by_company_extractor(text)
            result["methods_tried"].append({"method": "company_extractor", "result": ce_result})
        except Exception as e:
            result["methods_tried"].append({"method": "company_extractor", "error": str(e)})

    if extractor.openai_client:
        try:
            gpt_result = extractor.extract_by_chatgpt(text)
            result["methods_tried"].append({"method": "chatgpt", "result": gpt_result})
        except Exception as e:
            result["methods_tried"].append({"method": "chatgpt", "error": str(e)})

    alias_result = extractor.extract_by_alias_dict(text)
    result["methods_tried"].append({"method": "alias_dict", "result": alias_result})

    return result


@app.get("/test/classify-event")
def test_classify_event(text: str):
    classifier = services.get("classifier")
    if classifier is None:
        raise HTTPException(status_code=503, detail="Classifier not initialized")

    unified_result = classify_event(text)

    return {
        "input": text,
        "unified_result": {
            "labels": unified_result.labels,
            "event_phrases": unified_result.event_phrases,
            "confidence": unified_result.confidence,
            "source": unified_result.source
        }
    }

