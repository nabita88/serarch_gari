from __future__ import annotations
import logging
import uuid
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import Counter

from munci.rumerapi.models.schemas import (
    PatternAnalysisRequest, PatternAnalysisResponse,
    SimilarCase, PatternInsight
)
from munci.rumerapi.extractors.companyGpt import extract_companies
from munci.lastsa.event_with_translate import classify_event
from munci.rumerapi.core.config import settings
from munci.news_es.es_client import create_es_client

logger = logging.getLogger(__name__)


class PatternAnalysisService:
    def __init__(self):
        self.es = create_es_client()
        self.index = settings.es_index

    def _build_pattern_query(
            self,
            query_companies: List[str],  # 쿼리에서 추출된 회사
            filter_companies: List[str],  # 사용자가 지정한 필터 회사
            event_labels: List[str],
            lookback_days: int
    ) -> Dict[str, Any]:
        """유사 사례 검색 쿼리 생성"""
        now = datetime.now()
        start_date = now - timedelta(days=lookback_days)

        must_queries = []
        should_queries = []

        # 유사사례 패턴: 쿼리 회사와 필터 회사가 다르면 유사사례
        all_companies = list(set(query_companies + filter_companies))

        if all_companies:
            should_queries.append({
                "terms": {"companies.keyword": all_companies}
            })

        # 이벤트 레이블 매칭
        if event_labels and event_labels != ["other"]:
            should_queries.append({
                "terms": {"event_codes.keyword": event_labels}
            })

        # 날짜 범위
        must_queries.append({
            "range": {
                "published_at": {
                    "gte": start_date.isoformat(),
                    "lte": now.isoformat()
                }
            }
        })

        query = {
            "bool": {
                "must": must_queries,
                "should": should_queries,
                "minimum_should_match": 1
            }
        }

        return {
            "query": query,
            "size": 100,
            "sort": [
                {"_score": "desc"},
                {"published_at": "desc"}
            ]
        }

    def _calculate_similarity(
            self,
            doc: Dict[str, Any],
            query_companies: List[str],
            query_events: List[str]
    ) -> float:
        """문서와 쿼리의 유사도 계산"""
        doc_companies = doc.get("companies", [])
        doc_events = doc.get("event_codes", [])

        company_match = len(set(query_companies) & set(doc_companies))
        event_match = len(set(query_events) & set(doc_events))

        total_query_features = len(query_companies) + len(query_events)
        if total_query_features == 0:
            return 0.0

        matched_features = company_match + event_match
        similarity = matched_features / total_query_features

        # ES 스코어 반영
        es_score = doc.get("_score", 0)
        if es_score > 20:
            similarity = min(1.0, similarity + 0.1)
        elif es_score > 10:
            similarity = min(1.0, similarity + 0.05)

        return similarity

    def _extract_patterns(
            self,
            similar_cases: List[SimilarCase]
    ) -> List[PatternInsight]:
        """유사 사례에서 패턴 추출"""
        patterns = []

        if not similar_cases:
            return patterns

        # 1. 회사 빈도 분석
        all_companies = []
        for case in similar_cases:
            all_companies.extend(case.companies)

        company_freq = Counter(all_companies)
        most_common_companies = company_freq.most_common(3)

        if most_common_companies and most_common_companies[0][1] >= 3:
            top_company, count = most_common_companies[0]
            patterns.append(PatternInsight(
                pattern_type="frequent_company",
                description=f"'{top_company}'가 {count}건의 유사 사례에 등장",
                frequency=count,
                confidence=min(1.0, count / len(similar_cases))
            ))

        # 2. 이벤트 빈도 분석
        all_events = []
        for case in similar_cases:
            all_events.extend(case.event_labels)

        event_freq = Counter(all_events)
        most_common_events = event_freq.most_common(3)

        if most_common_events and most_common_events[0][1] >= 3:
            top_event, count = most_common_events[0]
            patterns.append(PatternInsight(
                pattern_type="frequent_event",
                description=f"'{top_event}' 이벤트가 {count}건 발생",
                frequency=count,
                confidence=min(1.0, count / len(similar_cases))
            ))

        # 3. 시간적 패턴 분석
        dates = [case.published_at for case in similar_cases if case.published_at]
        if len(dates) >= 5:
            dates.sort()

            # 최근 집중도 확인
            now = datetime.now()
            recent_30days = sum(1 for d in dates if (now - d).days <= 30)

            if recent_30days >= len(dates) * 0.5:
                patterns.append(PatternInsight(
                    pattern_type="recent_spike",
                    description=f"최근 30일 내 {recent_30days}건 집중 발생",
                    frequency=recent_30days,
                    confidence=recent_30days / len(dates)
                ))

            # 주기적 패턴 확인
            intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                if 80 <= avg_interval <= 100:  # 분기별
                    patterns.append(PatternInsight(
                        pattern_type="quarterly_pattern",
                        description=f"약 {int(avg_interval)}일 간격으로 반복 발생 (분기별 패턴)",
                        frequency=len(dates),
                        confidence=0.7
                    ))

        # 4. 신뢰도 패턴 분석
        if any(case.trust_outcome for case in similar_cases):
            trust_outcomes = [case.trust_outcome for case in similar_cases if case.trust_outcome]
            outcome_freq = Counter(trust_outcomes)

            if outcome_freq:
                most_common_outcome, count = outcome_freq.most_common(1)[0]
                patterns.append(PatternInsight(
                    pattern_type="trust_pattern",
                    description=f"과거 유사 사례의 {count}/{len(trust_outcomes)}건이 '{most_common_outcome}' 판정",
                    frequency=count,
                    confidence=count / len(trust_outcomes)
                ))

        return patterns

    def analyze(self, req: PatternAnalysisRequest) -> PatternAnalysisResponse:
        """유사 사례 패턴 분석"""

        # 1. 쿼리에서 회사명/이벤트 추출
        extraction_result = extract_companies(req.query_text)
        query_companies = extraction_result.get('companies', [])

        event_result = classify_event(req.query_text)
        event_labels = event_result.labels

        # 필터 회사 (사용자 지정)
        filter_companies = req.companies or []

        logger.info(
            f"Pattern analysis - query_companies: {query_companies}, filter_companies: {filter_companies}, events: {event_labels}")

        if not query_companies and not filter_companies and not event_labels:
            return PatternAnalysisResponse(
                id=str(uuid.uuid4()),
                query=req.query_text,
                total_similar_cases=0,
                similar_cases=[],
                patterns=[],
                summary="회사명 또는 이벤트를 추출할 수 없어 패턴 분석 불가",
                analyzed_at=datetime.now()
            )

        # 2. Elasticsearch 검색
        es_query = self._build_pattern_query(
            query_companies,
            filter_companies,
            event_labels,
            req.lookback_days
        )

        try:
            response = self.es.search(index=self.index, body=es_query)
            hits = response.get("hits", {}).get("hits", [])

            logger.info(f"Found {len(hits)} similar cases")
        except Exception as e:
            logger.exception(f"ES search failed: {e}")
            hits = []

        # 3. 유사도 계산 및 필터링
        similar_cases = []
        all_companies = list(set(query_companies + filter_companies))

        for hit in hits:
            source = hit.get("_source", {})

            similarity = self._calculate_similarity(
                {**source, "_score": hit.get("_score", 0)},
                all_companies,
                event_labels
            )

            if similarity < req.min_similarity:
                continue

            published_at = None
            if pub_str := source.get("published_at"):
                try:
                    published_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                except Exception:
                    pass

            similar_cases.append(SimilarCase(
                title=source.get("title", "제목 없음")[:200],
                companies=source.get("companies", []),
                event_labels=source.get("event_codes", []),
                similarity_score=round(similarity, 2),
                published_at=published_at,
                url=source.get("url"),
                trust_outcome=source.get("trust_outcome")
            ))

        # 유사도 순 정렬
        similar_cases.sort(key=lambda x: x.similarity_score, reverse=True)
        top_similar_cases = similar_cases[:20]

        # 4. 패턴 추출
        patterns = self._extract_patterns(similar_cases)

        # 5. 요약 생성
        summary = self._generate_summary(
            len(similar_cases),
            top_similar_cases,
            patterns,
            req.lookback_days
        )

        return PatternAnalysisResponse(
            id=str(uuid.uuid4()),
            query=req.query_text,
            total_similar_cases=len(similar_cases),
            similar_cases=top_similar_cases,
            patterns=patterns,
            summary=summary,
            analyzed_at=datetime.now()
        )

    def _generate_summary(
            self,
            total_cases: int,
            top_cases: List[SimilarCase],
            patterns: List[PatternInsight],
            lookback_days: int
    ) -> str:
        """분석 결과 요약 생성"""
        if total_cases == 0:
            return f"최근 {lookback_days}일간 유사 사례 없음"

        summary_parts = [f"최근 {lookback_days}일간 {total_cases}건의 유사 사례 발견"]

        if top_cases:
            avg_similarity = sum(c.similarity_score for c in top_cases) / len(top_cases)
            summary_parts.append(f"평균 유사도: {avg_similarity:.0%}")

        # 주요 패턴 1개 강조
        if patterns:
            main_pattern = max(patterns, key=lambda p: p.confidence)
            summary_parts.append(f"주요 패턴: {main_pattern.description}")

        return " - ".join(summary_parts)
