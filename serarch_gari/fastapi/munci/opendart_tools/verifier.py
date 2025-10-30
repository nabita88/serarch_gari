from __future__ import annotations
import datetime as dt
from typing import List, Optional, Tuple, Dict, Any
import logging

from .models import (
    DisclosureMeta, DisclosureSignalType, DisclosureSignal, DARTVerificationResult
)
from .utils import match_keywords, to_yyyymmdd, clamp
from .rules import (
    DART_DECISION, DART_QUERY, DART_ANSWER, HEDGING, CONFIRM,
    PBLNTF_TY_RUMOR_SIGNAL
)
from .dart_client import DARTClient
from .contract_analyzer import ContractAnalyzer

try:
    from .db_client import DARTDBClient
except ImportError:
    DARTDBClient = None

logger = logging.getLogger(__name__)


class DisclosureAnalyzer:

    def __init__(self):
        self.contract_analyzer = ContractAnalyzer()

    def analyze_disclosure(self, disclosure: DisclosureMeta, rumor_companies: List[str] = None) -> List[
        DisclosureSignal]:
        signals: List[DisclosureSignal] = []
        report_nm = (disclosure.report_nm or "").lower()
        pblntf_ty = disclosure.pblntf_ty

        if rumor_companies and self.contract_analyzer.is_contract_disclosure(report_nm):
            contract_result = self.contract_analyzer.analyze_contract_signal(
                disclosure, rumor_companies
            )

            if contract_result['counterparty_matched']:
                matched = contract_result['matched_companies']
                signals.append(DisclosureSignal(
                    type=DisclosureSignalType.DECISION,
                    keywords=matched,
                    weight=-40,
                    description=f"루머 대상 기업과 계약 체결 확인: {', '.join(matched)}"
                ))
                return signals
            elif contract_result['has_counterparty']:
                signals.append(DisclosureSignal(
                    type=DisclosureSignalType.DECISION,
                    keywords=['계약체결'],
                    weight=-15,
                    description="계약 체결 (루머 대상 외 기업)"
                ))
                return signals

        if pblntf_ty in PBLNTF_TY_RUMOR_SIGNAL:
            matched_query = match_keywords(report_nm, DART_QUERY)
            if matched_query:
                signals.append(DisclosureSignal(
                    type=DisclosureSignalType.QUERY,
                    keywords=matched_query + [f"유형:I"],
                    weight=20,
                    description=f"조회공시/풍문 확인 요청 (거래소공시)",
                ))
                return signals

            matched_decision = match_keywords(report_nm, DART_DECISION)
            if matched_decision:
                signals.append(DisclosureSignal(
                    type=DisclosureSignalType.DECISION,
                    keywords=matched_decision + [f"유형:I"],
                    weight=-30,
                    description=f"공식 확정/체결 공시 (거래소공시)",
                ))
                return signals

        matched_decision = match_keywords(report_nm, DART_DECISION)
        if matched_decision:
            signals.append(DisclosureSignal(
                type=DisclosureSignalType.DECISION,
                keywords=matched_decision,
                weight=-30,
                description="공식 확정/체결 공시",
            ))

        matched_query = match_keywords(report_nm, DART_QUERY)
        if matched_query:
            signals.append(DisclosureSignal(
                type=DisclosureSignalType.QUERY,
                keywords=matched_query,
                weight=20,
                description="조회공시/풍문 확인 요청",
            ))

        matched_answer = match_keywords(report_nm, DART_ANSWER)
        if matched_answer:
            signals.append(DisclosureSignal(
                type=DisclosureSignalType.ANSWER,
                keywords=matched_answer,
                weight=-10,
                description="조회공시 답변",
            ))

        if not signals:
            signals.append(DisclosureSignal(
                type=DisclosureSignalType.NEUTRAL,
                keywords=[],
                weight=0,
                description="특별한 신호 없음",
            ))
        return signals

    def analyze_article(self, title: str, content: str) -> Tuple[int, List[str]]:
        text = f"{title}\n{content}".lower()
        score_adjustment = 0
        matched_keywords: List[str] = []

        hedging = match_keywords(text, HEDGING)
        if hedging:
            score_adjustment += 20
            matched_keywords.extend([f"헤징:{kw}" for kw in hedging])

        confirm = match_keywords(text, CONFIRM)
        if confirm:
            score_adjustment -= 15
            matched_keywords.extend([f"확정:{kw}" for kw in confirm])

        if "?" in (title or ""):
            score_adjustment += 10
            matched_keywords.append("제목:물음표")
        if "단독" in (title or ""):
            score_adjustment += 5
            matched_keywords.append("제목:단독")

        return score_adjustment, matched_keywords


class OpenDARTVerifier:
    def __init__(
            self,
            api_key: Optional[str] = None,
            db_config: Optional[dict] = None,
            db_cutoff_hour: int = 23
    ):
        import os
        self.api_key = api_key or os.getenv("DART_API_KEY")
        self.client = DARTClient(self.api_key) if self.api_key else None
        self.db_client = None
        if db_config and DARTDBClient:
            try:
                self.db_client = DARTDBClient(db_config)
                logger.info("DB 클라이언트 초기화 완료")
            except Exception as e:
                logger.warning(f"DB 클라이언트 초기화 실패: {e}")
        self.db_cutoff_hour = db_cutoff_hour
        self.analyzer = DisclosureAnalyzer()

    def _split_date_range(
            self,
            bgn_date: dt.date,
            end_date: dt.date,
            now: dt.datetime
    ) -> Tuple[Optional[Tuple[dt.date, dt.date]], Optional[Tuple[dt.date, dt.date]]]:
        today = now.date()

        if now.hour >= self.db_cutoff_hour:
            db_end = today
            api_start = today + dt.timedelta(days=1)
        else:
            db_end = today - dt.timedelta(days=1)
            api_start = today

        if bgn_date <= db_end and end_date >= bgn_date:
            db_range = (bgn_date, min(db_end, end_date))
        else:
            db_range = None

        if api_start <= end_date and end_date >= api_start:
            api_range = (max(api_start, bgn_date), end_date)
        else:
            api_range = None

        return db_range, api_range

    def verify(
            self,
            company_names: List[str],
            article_title: str,
            article_content: str,
            window_days: int = 3,
            article_date: Optional[dt.datetime] = None,
            company_details: Optional[Dict[str, Dict]] = None
    ) -> DARTVerificationResult:
        if not self.client and not self.db_client:
            return self._create_empty_result("DART API 및 DB 미연결")

        now = dt.datetime.now()
        base_date = (article_date or now).date()
        bgn_date = base_date - dt.timedelta(days=window_days)
        end_date = base_date + dt.timedelta(days=window_days)

        db_range, api_range = self._split_date_range(bgn_date, end_date, now)

        logger.info(f"검색 범위: {bgn_date} ~ {end_date}")
        if db_range:
            logger.info(f"  └─ DB: {db_range[0]} ~ {db_range[1]}")
        if api_range:
            logger.info(f"  └─ API: {api_range[0]} ~ {api_range[1]}")

        all_disclosures: List[DisclosureMeta] = []
        relevant_disclosures: List[DisclosureMeta] = []
        all_signals: List[DisclosureSignal] = []

        for company_name in company_names:
            corp_code = None
            if company_details and company_name in company_details:
                corp_code = company_details[company_name].get('corp_code')
                if corp_code:
                    logger.info(f"✓ {company_name}: corp_code={corp_code} (from company_details)")

            if not corp_code:
                logger.warning(f"'{company_name}'의 corp_code를 찾을 수 없습니다.")
                continue

            company_disclosures = []

            if self.db_client and db_range:
                try:
                    db_disclosures = self.db_client.list_disclosures(
                        corp_code=corp_code,
                        bgn_de=to_yyyymmdd(db_range[0]),
                        end_de=to_yyyymmdd(db_range[1]),
                        corp_name=company_name
                    )
                    company_disclosures.extend(db_disclosures)
                    logger.info(
                        f"✓ {company_name}: DB에서 {len(db_disclosures)}건 조회 "
                        f"({db_range[0]} ~ {db_range[1]})"
                    )
                except Exception as e:
                    logger.error(f"DB 조회 실패 ({company_name}): {e}")

            if self.client and api_range:
                try:
                    api_disclosures = self.client.list_disclosures(
                        corp_code=corp_code,
                        bgn_de=to_yyyymmdd(api_range[0]),
                        end_de=to_yyyymmdd(api_range[1]),
                        page_count=100,
                        max_pages=2,
                    )
                    company_disclosures.extend(api_disclosures)
                    logger.info(
                        f"✓ {company_name}: API에서 {len(api_disclosures)}건 조회 "
                        f"({api_range[0]} ~ {api_range[1]})"
                    )
                except Exception as e:
                    logger.error(f"API 조회 실패 ({company_name}): {e}")

            seen = set()
            unique_disclosures = []
            for d in company_disclosures:
                if d.rcept_no not in seen:
                    seen.add(d.rcept_no)
                    unique_disclosures.append(d)

            if len(company_disclosures) != len(unique_disclosures):
                logger.info(
                    f"✓ {company_name}: 중복 제거 "
                    f"{len(company_disclosures) - len(unique_disclosures)}건"
                )

            all_disclosures.extend(unique_disclosures)

            for disclosure in unique_disclosures:
                signals = self.analyzer.analyze_disclosure(
                    disclosure,
                    rumor_companies=company_names
                )
                if signals:
                    all_signals.extend(signals)
                    if any(s.weight != 0 for s in signals):
                        relevant_disclosures.append(disclosure)

        article_adjustment, _ = self.analyzer.analyze_article(article_title, article_content)
        total_adjustment = article_adjustment + sum(s.weight for s in all_signals)

        evidence_summary = self._generate_summary(
            len(all_disclosures), relevant_disclosures, all_signals, total_adjustment
        )

        return DARTVerificationResult(
            has_disclosure=len(all_disclosures) > 0,
            total_found=len(all_disclosures),
            relevant_disclosures=relevant_disclosures,
            signals=all_signals,
            rumor_score_adjustment=total_adjustment,
            evidence_summary=evidence_summary,
        )

    def _create_empty_result(self, reason: str) -> DARTVerificationResult:
        return DARTVerificationResult(
            has_disclosure=False,
            total_found=0,
            relevant_disclosures=[],
            signals=[],
            rumor_score_adjustment=0,
            evidence_summary=f"공시 검증 불가: {reason}",
        )

    def _generate_summary(
            self,
            total_found: int,
            relevant: List[DisclosureMeta],
            signals: List[DisclosureSignal],
            adjustment: int,
    ) -> str:
        if total_found == 0:
            return "관련 공시 없음"
        if adjustment <= -30:
            return f"공식 확정: {total_found}건의 공시 중 {len(relevant)}건이 공식 확정/체결 관련"
        elif adjustment >= 30:
            return f"루머 가능성 높음: 조회공시 또는 부인 공시 {len(relevant)}건 발견"
        else:
            return f"불확실: {total_found}건의 공시 발견, 추가 확인 필요"


def quick_verify(
        company_names: List[str],
        article_title: str,
        article_content: str,
        dart_api_key: Optional[str] = None,
        company_details: Optional[Dict[str, Dict]] = None
) -> Dict[str, Any]:
    verifier = OpenDARTVerifier(dart_api_key)
    result = verifier.verify(
        company_names,
        article_title,
        article_content,
        window_days=3,
        company_details=company_details
    )
    adjusted_score = clamp(50 + result.rumor_score_adjustment, 0, 100)
    rumor_probability = adjusted_score / 100.0

    if rumor_probability >= 0.7:
        recommendation = "높은 루머 가능성 - 공식 확인 필요"
    elif rumor_probability <= 0.3:
        recommendation = "낮은 루머 가능성 - 공식 확정 또는 신뢰할 만한 출처"
    else:
        recommendation = "불확실 - 추가 검증 필요"

    signals_payload = [
        {
            "type": s.type.value if hasattr(s.type, "value") else str(s.type),
            "keywords": s.keywords,
            "weight": s.weight,
            "description": s.description,
        }
        for s in result.signals[:5]
    ]

    return {
        "has_disclosure": result.has_disclosure,
        "rumor_probability": rumor_probability,
        "evidence": {
            "total_disclosures": result.total_found,
            "relevant_disclosures": [
                {
                    "rcept_no": d.rcept_no,
                    "date": d.rcept_dt,
                    "company": d.corp_name,
                    "title": d.report_nm,
                }
                for d in result.relevant_disclosures[:3]
            ],
            "signals": signals_payload,
            "summary": result.evidence_summary,
        },
        "recommendation": recommendation,
    }
