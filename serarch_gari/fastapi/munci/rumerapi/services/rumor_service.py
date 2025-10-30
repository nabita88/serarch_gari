from __future__ import annotations
import logging, uuid
from typing import Any, Dict, List
from datetime import datetime

from munci.rumerapi.models.schemas import (
    RumorVerifyRequest, RumorVerifyResponse, Evidence, EvidenceType, TrustLevelEnum
)
from munci.rumerapi.extractors.companyGpt import extract_companies, initialize_extractor
from munci.lastsa.event_with_translate import classify_event, initialize_event_classifier
from munci.main_utils.date_context import extract_date_context
from munci.main_utils.optional_imports import try_import_trust_evaluator, try_import_dart_verifier
from munci.rumerapi.core.config import settings
from munci.news_es.search import search_with_api_params
from munci.news_es.es_client import create_es_client

# optional modules
TrustEvaluator = try_import_trust_evaluator()
OpenDARTVerifier = try_import_dart_verifier()

logger = logging.getLogger(__name__)


def _clip_adj(value: float) -> float:
    """DART 조정값 클리핑 - 더 넓은 범위 허용"""
    return max(-0.5, min(0.5, value))


class RumorVerificationServiceES:
    def __init__(self):
        self.es = create_es_client()
        self.index = settings.es_index
        self.evaluator = TrustEvaluator() if TrustEvaluator else None

        # DB 설정 구성
        db_config = None
        if all([settings.db_host, settings.db_username, settings.db_password, settings.db_database]):
            db_config = {
                'host': settings.db_host,
                'username': settings.db_username,
                'password': settings.db_password,
                'database': settings.db_database,
                'port': settings.db_port
            }
            logger.info("DB 설정 완료 - 하이브리드 모드 (DB + API)")
        else:
            logger.info("DB 설정 없음 - API 전용 모드")

        # DART Verifier 초기화 (DB 설정 전달)
        if OpenDARTVerifier and settings.dart_api_key:
            self.dart_verifier = OpenDARTVerifier(
                api_key=settings.dart_api_key,
                db_config=db_config
            )
        else:
            self.dart_verifier = None

    def _extract_evidence_from_results(self, results: List[Dict[str, Any]], max_items: int = 3) -> List[Evidence]:
        evs: List[Evidence] = []
        for r in results[:max_items]:
            title = r.get("title", "제목 없음")
            url = r.get("url", "")
            dt_str = r.get("published_at")
            dt_obj = None
            if isinstance(dt_str, str):
                try:
                    dt_obj = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                except Exception:
                    dt_obj = None
            evs.append(Evidence(type=EvidenceType.NEWS, title=title[:200], url=url, published_at=dt_obj))
        return evs

    def _evaluate_trust(self, search_result: Dict[str, Any], exact_matches: List, partial_matches: List) -> float:
        """신뢰도 평가 - 중복 제거된 독립 출처 기반"""
        results = search_result.get("results", [])
        total_hits = search_result.get("total_hits", 0)

        logger.info(
            f"Evaluating trust - total_hits: {total_hits}, exact: {len(exact_matches)}, partial: {len(partial_matches)}")

        base_score = 0.0
        source_diversity_bonus = 0.0
        relevance_bonus = 0.0

        if exact_matches:
            num_sources = len(exact_matches)

            if num_sources == 1:
                base_score = 0.5
            elif num_sources == 2:
                base_score = 0.65
            elif num_sources >= 3 and num_sources < 5:
                base_score = 0.75
            elif num_sources >= 5 and num_sources < 10:
                base_score = 0.85
            else:
                base_score = 0.9

            unique_sources = set()
            for match in exact_matches[:10]:
                source = match.get("publisher", "")
                if source:
                    unique_sources.add(source)

            if len(unique_sources) >= 5:
                source_diversity_bonus = 0.05
                logger.info(f"Source diversity bonus: {len(unique_sources)} unique sources")

            top_scores = [r.get("score", 0) for r in exact_matches[:5]]
            if top_scores:
                avg_score = sum(top_scores) / len(top_scores)
                if avg_score > 30:
                    relevance_bonus = 0.05
                elif avg_score > 20:
                    relevance_bonus = 0.03
                elif avg_score > 10:
                    relevance_bonus = 0.02
                logger.info(f"Relevance bonus: {relevance_bonus} (avg ES score: {avg_score:.2f})")

            logger.info(f"Exact matches: {num_sources} sources, base_score: {base_score}")

        elif partial_matches:
            num_sources = len(partial_matches)

            if num_sources == 1:
                base_score = 0.25
            elif num_sources == 2:
                base_score = 0.35
            elif num_sources >= 3 and num_sources < 5:
                base_score = 0.45
            else:
                base_score = 0.5

            top_scores = [r.get("score", 0) for r in partial_matches[:3]]
            if top_scores:
                avg_score = sum(top_scores) / len(top_scores)
                if avg_score > 20:
                    relevance_bonus = 0.03
                elif avg_score > 10:
                    relevance_bonus = 0.02

            logger.info(f"Partial matches: {num_sources} sources, base_score: {base_score}")

        elif results:
            top_score = results[0].get("score", 0)
            if top_score > 20:
                base_score = 0.15
            elif top_score > 10:
                base_score = 0.1
            else:
                base_score = 0.05
            logger.info(f"Only general results (top score: {top_score}), base_score: {base_score}")

        else:
            logger.info("No search results at all")
            return 0.0

        final_score = min(1.0, base_score + source_diversity_bonus + relevance_bonus)

        logger.info(f"Score breakdown - base: {base_score:.2f}, diversity: {source_diversity_bonus:.2f}, "
                    f"relevance: {relevance_bonus:.2f}, final: {final_score:.2f}")

        return final_score

    def _detect_contradictions(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        contradiction_keywords = [
            "부인", "사실무근", "해명", "아니다", "없다", "틀렸다",
            "조회공시", "해당사항없음", "검토한바없", "추진사실없",
            "계획없", "근거없", "사실과다름", "허위", "오보"
        ]

        contradictions = []

        for result in results[:20]:
            title = (result.get('title') or '').lower()
            body = (result.get('body') or '').lower()
            full_text = title + " " + body

            for keyword in contradiction_keywords:
                if keyword in full_text:
                    contradictions.append({
                        "title": result.get('title'),
                        "publisher": result.get('publisher'),
                        "keyword": keyword,
                        "url": result.get('url')
                    })
                    break

        if contradictions:
            logger.warning(f"Found {len(contradictions)} contradictions")

        return contradictions

    def _verify_key_claims(self, query_text: str, companies: List[str], results: List[Dict[str, Any]]) -> float:

        import re

        # 핵심 주장 추출
        claims = []

        # 1. 회사명
        claims.extend(companies)

        # 2. 금액/수치
        amounts = re.findall(r'\d+[\.,]?\d*\s*(?:조|억|만|천|백|달러|원|%)', query_text)
        claims.extend(amounts)

        # 3. 핵심 동사/명사
        key_terms = [
            "인수", "매각", "투자", "확대", "발표", "체결", "결정",
            "합병", "계약", "수주", "증자", "감자", "상장", "폐쇄"
        ]
        found_terms = [term for term in key_terms if term in query_text]
        claims.extend(found_terms)

        if not claims:
            return 0.5  # 주장을 추출 못하면 중립

        # 기사에서 주장 확인
        supported_claims = set()

        for result in results[:10]:
            article_text = f"{result.get('title', '')} {result.get('body', '')}".lower()

            for claim in claims:
                if claim.lower() in article_text:
                    supported_claims.add(claim)

        support_ratio = len(supported_claims) / len(claims)

        logger.info(f"Claim verification: {len(supported_claims)}/{len(claims)} claims supported = {support_ratio:.2f}")

        return support_ratio

    def _verify_temporal_consistency(
            self,
            query_text: str,
            date_range: tuple,
            results: List[Dict[str, Any]]
    ) -> float:

        from datetime import datetime, timezone

        if not results:
            return 0.5  # 기사가 없으면 중립

        # 날짜 범위 추출
        if date_range and date_range[0] and date_range[1]:
            start_date = date_range[0]
            end_date = date_range[1]
        else:
            # 날짜 언급이 없으면 최근 3개월로 간주
            end_date = datetime.now(timezone.utc)
            from datetime import timedelta
            start_date = end_date - timedelta(days=90)

        logger.info(f"Temporal range: {start_date.date()} ~ {end_date.date()}")

        # 범위 내 기사 카운트
        articles_in_range = 0
        total_articles = 0

        for result in results[:20]:
            published_at_str = result.get('published_at')
            if not published_at_str:
                continue

            total_articles += 1

            try:
                # ISO 형식 파싱
                if isinstance(published_at_str, str):
                    article_date = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                else:
                    continue

                # 범위 내 확인
                if start_date <= article_date <= end_date:
                    articles_in_range += 1

            except Exception as e:
                logger.debug(f"Date parsing error: {published_at_str} - {e}")
                continue

        if total_articles == 0:
            return 0.5  # 날짜 정보 없으면 중립

        # 시간적 일치도 계산
        temporal_score = articles_in_range / total_articles

        logger.info(
            f"Temporal consistency: {articles_in_range}/{total_articles} articles in range = {temporal_score:.2f}"
        )

        return temporal_score

    def verify(self, req: RumorVerifyRequest) -> RumorVerifyResponse:
        initialize_extractor()
        initialize_event_classifier()

        extraction_result = extract_companies(req.query_text)
        companies = extraction_result.get('companies', [])
        company_details = extraction_result.get('company_details', {})

        event_result = classify_event(req.query_text)
        date_range = extract_date_context(req.query_text)

        logger.info(f"Extracted companies: {companies}")
        if company_details:
            logger.info(f"Company details: {company_details}")
        logger.info(f"Event result: {event_result.labels}, phrases: {event_result.event_phrases}")
        logger.info(f"Date range: {date_range}")

        search_result = search_with_api_params(
            es=self.es,
            index=self.index,
            query=req.query_text,
            companies=companies,
            event_phrases=event_result.event_phrases,
            event_labels=event_result.labels,
            date_range=date_range,
            use_flexible_matching=True
        )

        logger.info(f"Search result - total_hits: {search_result.get('total_hits', 0)}")
        logger.info(f"Search result - results count: {len(search_result.get('results', []))}")
        if search_result.get('results'):
            logger.info(f"First result score: {search_result['results'][0].get('score', 0)}")

        results = search_result.get("results", [])

        exact_matches = []
        partial_matches = []

        for r in results:
            doc_companies = r.get("companies", [])
            doc_event_codes = r.get("event_codes", [])

            company_match = any(c in doc_companies for c in companies) if companies else False
            event_match = False

            if event_result.labels and event_result.labels != ["other"]:
                event_match = any(label in doc_event_codes for label in event_result.labels)

            if not event_match and event_result.event_phrases:
                title_lower = (r.get("title") or "").lower()
                for phrase in event_result.event_phrases:
                    if phrase and phrase.lower() in title_lower:
                        event_match = True
                        break

            if company_match and event_match:
                exact_matches.append(r)
            elif company_match or event_match:
                partial_matches.append(r)

        base_score_01 = self._evaluate_trust(search_result, exact_matches, partial_matches)



        # 1. 모순 탐지 (가장 중요!)
        contradictions = self._detect_contradictions(results)
        contradiction_penalty = 0.0

        if contradictions:
            # 모순되는 기사가 있으면 대폭 감점
            contradiction_penalty = -0.5
            logger.warning(f"Contradiction detected: {len(contradictions)} articles deny the rumor")

        # 2. 핵심 주장 검증
        claim_support = self._verify_key_claims(req.query_text, companies, results)
        claim_penalty = 0.0

        if claim_support < 0.3:
            # 주장의 30% 미만만 지지되면 감점
            claim_penalty = -0.2
            logger.warning(f"Low claim support: {claim_support:.2f}")
        elif claim_support < 0.5:
            # 50% 미만이면 약간 감점
            claim_penalty = -0.1
            logger.warning(f"Moderate claim support: {claim_support:.2f}")

        # 3. 시간적 일치도 검증
        temporal_score = self._verify_temporal_consistency(req.query_text, date_range, results)
        temporal_penalty = 0.0

        if temporal_score < 0.2:
            # 20% 미만만 시간적으로 일치하면 감점
            temporal_penalty = -0.15
            logger.warning(f"Low temporal consistency: {temporal_score:.2f}")
        elif temporal_score < 0.4:
            # 40% 미만이면 약간 감점
            temporal_penalty = -0.05
            logger.warning(f"Moderate temporal consistency: {temporal_score:.2f}")

        # 기본 점수에 페널티 적용
        base_score_01 = max(0.0, base_score_01 + contradiction_penalty + claim_penalty + temporal_penalty)

        logger.info(
            f"Truth verification - "
            f"contradictions: {len(contradictions)}, "
            f"claim_support: {claim_support:.2f}, "
            f"temporal_score: {temporal_score:.2f}, "
            f"penalties: contradiction={contradiction_penalty:.2f}, "
            f"claim={claim_penalty:.2f}, temporal={temporal_penalty:.2f}"
        )

        dart_adj = 0.0
        dart_evidence: List[Evidence] = []
        if companies and self.dart_verifier:
            try:
                logger.info(f"Checking DART for companies: {companies}")
                logger.info(f"Event labels: {event_result.labels}")
                logger.info(f"Event phrases: {event_result.event_phrases}")

                if company_details:
                    companies_with_codes = {
                        name: details
                        for name, details in company_details.items()
                        if details.get('corp_code')
                    }

                    if companies_with_codes:
                        logger.info(f"Using corp_codes from company_details: {list(companies_with_codes.keys())}")

                if hasattr(self.dart_verifier, 'verify_with_event'):
                    dart_res = self.dart_verifier.verify_with_event(
                        company_names=companies,
                        article_title=req.query_text[:100],
                        article_content=req.query_text,
                        event_labels=event_result.labels,
                        event_phrases=event_result.event_phrases,
                        window_days=7,
                        company_details=company_details
                    )
                else:
                    dart_res = self.dart_verifier.verify(
                        company_names=companies,
                        article_title=req.query_text[:100],
                        article_content=req.query_text,
                        window_days=7,
                        company_details=company_details
                    )

                if dart_res.rumor_score_adjustment is not None:
                    raw_adj = -1 * (dart_res.rumor_score_adjustment / 100.0)
                    dart_adj = _clip_adj(raw_adj)
                    logger.info(f"DART adjustment: rumor_adj={dart_res.rumor_score_adjustment}, trust_adj={dart_adj}")

                if dart_res.relevant_disclosures:
                    logger.info(f"Found {len(dart_res.relevant_disclosures)} relevant disclosures")
                    for disc in dart_res.relevant_disclosures[:3]:
                        dart_evidence.append(Evidence(
                            type=EvidenceType.DISCLOSURE,
                            title=f"[공시] {disc.corp_name}: {disc.report_nm[:120]}",
                            url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={disc.rcept_no}",
                            published_at=datetime.strptime(disc.rcept_dt, "%Y%m%d") if disc.rcept_dt else None,
                        ))
            except Exception as e:
                logger.exception(f"OpenDART verification failed: {e}")

        final_score = max(0.0, min(1.0, base_score_01 + dart_adj))

        logger.info(
            f"Score calculation - base: {base_score_01:.2f}, dart_adj: {dart_adj:.2f}, final: {final_score:.2f}")

        if final_score >= 0.7:
            level = TrustLevelEnum.HIGH
        elif final_score >= 0.4:
            level = TrustLevelEnum.MEDIUM
        else:
            level = TrustLevelEnum.LOW

        news_evs = self._extract_evidence_from_results(exact_matches or results)
        top_ev = (dart_evidence + news_evs)[:5]

        summary = f"신뢰도 {level.value} ({final_score:.2f})"

        # 우선순위: 모순 > DART > 시간 > 주장 검증 > 매칭
        if contradictions:
            summary += f" - {len(contradictions)}건의 부인/해명 기사 발견"
        elif dart_adj >= 0.2 and dart_evidence:
            summary += " - 공시로 공식 확인"
        elif dart_adj <= -0.2 and dart_evidence:
            summary += " - 조회공시/답변 신호 감지"
        elif temporal_score < 0.3:
            summary += f" - 시간적 불일치 (일치도 {temporal_score:.0%})"
        elif claim_support < 0.5 and exact_matches:
            summary += f" - 핵심 주장 지지 부족 ({claim_support:.0%})"
        elif exact_matches:
            summary += f" - {len(exact_matches)}건의 정확 매칭 기사"
        elif partial_matches:
            summary += f" - {len(partial_matches)}건의 부분 매칭 기사"
        else:
            summary += " - 관련 정보 부족"

        return RumorVerifyResponse(
            id=str(uuid.uuid4()),
            level=level,
            score=round(final_score, 2),
            summary=summary,
            top_evidence=top_ev,
            checked_at=datetime.now(),
        )
