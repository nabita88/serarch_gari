from __future__ import annotations
import datetime as dt
from typing import List, Optional, Dict, Any
import logging

from .models import (
    DisclosureMeta, DisclosureSignalType, DisclosureSignal, DARTVerificationResult
)
from .verifier import OpenDARTVerifier

logger = logging.getLogger(__name__)

EVENT_DISCLOSURE_MAP = {
    "company.earnings_result": [
        "잠정실적", "연결재무제표", "별도재무제표", "분기보고서",
        "반기보고서", "사업보고서", "실적발표", "매출액또는손익구조",
        "영업이익", "당기순이익", "매출현황"
    ],
    "company.earnings_forecast": [
        "실적예상", "실적전망", "공정공시", "영업실적예고", "실적가이던스"
    ],

    "company.mna_acquisition": [
        "주식양수", "영업양수", "자산양수", "지분취득", "인수합병",
        "합병결정", "합병계약", "주요사항보고서(회사합병)", "타법인주식및출자증권취득결정"
    ],
    "company.mna_divestiture": [
        "주식양도", "영업양도", "자산양도", "지분매각", "매각결정",
        "타법인주식및출자증권처분결정"
    ],
    "company.mna_letter_of_intent": [
        "양해각서", "MOU", "LOI", "인수의향서", "매각의향서", "조회공시"
    ],

    "company.financing_equity": [
        "유상증자", "무상증자", "주식발행", "신주발행", "증자결정",
        "제3자배정", "주주배정", "일반공모", "전환사채", "신주인수권부사채"
    ],
    "company.financing_debt": [
        "사채발행", "차입금", "대출", "회사채", "CB발행", "BW발행", "EB발행"
    ],

    "company.capex_expansion": [
        "시설투자", "설비투자", "공장건설", "생산능력확대", "증설",
        "신규사업", "사업확장", "투자계획"
    ],

    "company.contract_win": [
        "공급계약", "수주", "계약체결", "판매계약", "용역계약", "건설계약", "계약", "체결", "수주", "공급", "판매", "구매", "양수", "양도", "인수", "매각", "투자"

    ],
    "company.contract_termination": [
        "계약해지", "계약취소", "계약파기", "계약종료"
    ],

    "company.restructuring_workout": [
        "워크아웃", "기업개선작업", "채무재조정", "자율협약", "경영정상화"
    ],
    "company.restructuring_bankruptcy": [
        "회생절차", "법정관리", "파산", "청산", "상장폐지"
    ],

    "company.regulatory_approval": [
        "인허가", "승인", "허가취득", "임상승인", "품목허가"
    ],
    "company.regulatory_penalty": [
        "제재", "과징금", "영업정지", "시정명령", "벌금", "징계"
    ],
    "company.dividend": [
        "배당", "현금배당", "주식배당", "중간배당", "배당결정"
    ],
    "company.stock_buyback": [
        "자기주식", "자사주", "주식취득", "주식소각", "자기주식처분"
    ]
}

try:
    from .keyword_database import (
        get_all_keywords_by_category,
        get_rumor_signal_keywords,
        EARNINGS_KEYWORDS, MNA_KEYWORDS, INVESTMENT_KEYWORDS,
        FINANCING_KEYWORDS, CONTRACT_KEYWORDS, REGULATORY_KEYWORDS,
        RESTRUCTURING_KEYWORDS, SCANDAL_KEYWORDS, TECHNOLOGY_KEYWORDS,
        MARKET_KEYWORDS, GOVERNANCE_KEYWORDS
    )
except ImportError:
    EARNINGS_KEYWORDS = {"metrics": ["영업이익", "매출", "실적"]}
    MNA_KEYWORDS = {"actions": ["인수", "매각", "합병"]}
    INVESTMENT_KEYWORDS = {"actions": ["투자", "증설", "확대"]}
    FINANCING_KEYWORDS = {"equity": ["증자"], "debt": ["사채"]}


    def get_all_keywords_by_category(cat):
        return []


    def get_rumor_signal_keywords():
        return {}


def extract_keywords_from_rumor(text: str) -> List[tuple]:
    keywords = []
    text_lower = text.lower()

    category_configs = [
        ("earnings", EARNINGS_KEYWORDS),
        ("mna", MNA_KEYWORDS),
        ("investment", INVESTMENT_KEYWORDS),
        ("financing", FINANCING_KEYWORDS),
        ("contract", CONTRACT_KEYWORDS),
        ("regulatory", REGULATORY_KEYWORDS),
        ("restructuring", RESTRUCTURING_KEYWORDS),
        ("scandal", SCANDAL_KEYWORDS),
        ("technology", TECHNOLOGY_KEYWORDS),
        ("market", MARKET_KEYWORDS),
        ("governance", GOVERNANCE_KEYWORDS)
    ]

    for category, keyword_dict in category_configs:
        if isinstance(keyword_dict, dict):
            for subcategory, keyword_list in keyword_dict.items():
                if isinstance(keyword_list, list):
                    for kw in keyword_list:
                        if kw.lower() in text_lower:
                            keywords.append((category, kw, subcategory))
        elif isinstance(keyword_dict, list):
            for kw in keyword_dict:
                if kw.lower() in text_lower:
                    keywords.append((category, kw, "general"))

    rumor_signals = get_rumor_signal_keywords()
    for signal_type, signal_keywords in rumor_signals.items():
        for kw in signal_keywords:
            if kw.lower() in text_lower:
                keywords.append(("signal", kw, signal_type))

    return keywords


def calculate_relevance_score(
        report_nm: str,
        event_labels: List[str],
        rumor_text: str = None,
        event_phrases: List[str] = None
) -> tuple[float, str]:
    if not event_labels or not report_nm:
        return 0.0, "no_labels_or_report"

    report_nm_lower = report_nm.lower()
    max_score = 0.0
    best_reason = "no_match"

    for label in event_labels:
        if label in EVENT_DISCLOSURE_MAP:
            keywords = EVENT_DISCLOSURE_MAP[label]
            match_count = 0
            matched_keywords = []

            for keyword in keywords:
                if keyword.lower() in report_nm_lower:
                    match_count += 1
                    matched_keywords.append(keyword)

            if keywords and match_count > 0:
                score = match_count / len(keywords)
                if score > max_score:
                    max_score = score
                    best_reason = f"label_match:{label}:{','.join(matched_keywords)}"

    if rumor_text:
        rumor_keywords = extract_keywords_from_rumor(rumor_text)

        category_matches = {}
        for category, keyword, subcategory in rumor_keywords:
            if keyword.lower() in report_nm_lower:
                if category not in category_matches:
                    category_matches[category] = []
                category_matches[category].append((keyword, subcategory))

        if category_matches:
            if "earnings" in category_matches:
                earnings_disclosure_keywords = [
                    "잠정실적", "연결재무제표", "별도재무제표", "분기보고서",
                    "반기보고서", "사업보고서", "영업실적", "매출액또는손익구조",
                    "공정공시", "실적공시", "어닝", "매출현황", "손익계산서"
                ]
                if any(kw in report_nm_lower for kw in earnings_disclosure_keywords):
                    matched_kws = [kw for kw, _ in category_matches['earnings']]
                    if max_score < 0.9:
                        max_score = 0.9
                        best_reason = f"strong_match:earnings:{','.join(matched_kws[:3])}"

            if "mna" in category_matches:
                mna_disclosure_keywords = [
                    "주식양수", "주식양도", "영업양수", "영업양도", "합병",
                    "인수", "매각", "지분취득", "지분매각", "MOU", "LOI",
                    "타법인주식", "출자증권", "경영권", "지배력"
                ]
                if any(kw in report_nm_lower for kw in mna_disclosure_keywords):
                    matched_kws = [kw for kw, _ in category_matches['mna']]
                    if max_score < 0.85:
                        max_score = 0.85
                        best_reason = f"strong_match:mna:{','.join(matched_kws[:3])}"

            if "investment" in category_matches:
                investment_disclosure_keywords = [
                    "시설투자", "설비투자", "공장", "생산능력", "증설",
                    "신규사업", "capex", "투자결정", "착공", "준공"
                ]
                if any(kw in report_nm_lower for kw in investment_disclosure_keywords):
                    matched_kws = [kw for kw, _ in category_matches['investment']]
                    if max_score < 0.8:
                        max_score = 0.8
                        best_reason = f"strong_match:investment:{','.join(matched_kws[:3])}"

            if "financing" in category_matches:
                financing_disclosure_keywords = [
                    "유상증자", "무상증자", "사채발행", "전환사채", "신주인수권",
                    "CB", "BW", "EB", "자금조달", "차입", "회사채"
                ]
                if any(kw in report_nm_lower for kw in financing_disclosure_keywords):
                    matched_kws = [kw for kw, _ in category_matches['financing']]
                    if max_score < 0.8:
                        max_score = 0.8
                        best_reason = f"strong_match:financing:{','.join(matched_kws[:3])}"

            if "signal" in category_matches:
                for kw, signal_type in category_matches['signal']:
                    if signal_type == "rumor" and "조회공시" in report_nm_lower:
                        if max_score < 0.3:
                            max_score = 0.3
                            best_reason = f"rumor_signal:조회공시:{kw}"

    if event_phrases:
        for phrase in event_phrases:
            if phrase and len(phrase) > 2:
                phrase_lower = phrase.lower()

                if phrase_lower in report_nm_lower:
                    if max_score < 0.95:
                        max_score = 0.95
                        best_reason = f"exact_phrase_match:{phrase}"
                else:
                    important_words = [w for w in phrase_lower.split() if len(w) > 2]
                    if important_words:
                        match_count = sum(1 for word in important_words if word in report_nm_lower)
                        phrase_score = match_count / len(important_words)

                        if phrase_score > 0.6 and phrase_score > max_score:
                            max_score = phrase_score
                            best_reason = f"partial_phrase_match:{phrase}:{match_count}/{len(important_words)}"

    irrelevant_keywords = [
        "자기주식", "자사주", "주주총회", "임원", "이사회",
        "감사보고서", "사외이사", "정정", "단순", "안내",
        "주주명부", "결산", "회계", "감사", "정기", "임시"
    ]

    if event_labels:
        if "company.earnings_result" in event_labels:
            if any(kw in report_nm_lower for kw in ["자기주식", "자사주", "배당", "주주환원"]):
                max_score = max_score * 0.1
                best_reason = "penalty:unrelated_to_earnings"

        if any("mna" in label for label in event_labels):
            if "단일판매" in report_nm_lower or "공급계약" in report_nm_lower:
                max_score = max_score * 0.3
                best_reason = "penalty:simple_contract_not_mna"

        if "company.capex_expansion" in event_labels:
            if any(kw in report_nm_lower for kw in ["증자", "사채", "차입"]):
                max_score = max_score * 0.5
                best_reason = "penalty:financing_not_investment"

    if rumor_text:
        denial_keywords = get_rumor_signal_keywords().get('denial', [])
        denial_found = []

        for denial_kw in denial_keywords:
            if denial_kw.lower() in report_nm_lower:
                denial_found.append(denial_kw)

        if denial_found:
            if "조회공시" in report_nm_lower and "답변" in report_nm_lower:
                if max_score < 0.6:
                    max_score = 0.6
                    best_reason = f"denial_in_inquiry:{','.join(denial_found[:3])}"
            elif any(kw in report_nm_lower for kw in ["해명", "설명", "반박"]):
                if max_score < 0.5:
                    max_score = 0.5
                    best_reason = f"denial_disclosure:{','.join(denial_found[:3])}"

            rumor_text_lower = rumor_text.lower()
            if any(denial_kw.lower() in rumor_text_lower for denial_kw in denial_found):
                max_score = max_score * 0.5
                best_reason = f"denial_in_both_rumor_and_disclosure"

    if rumor_text:
        undecided_keywords = get_rumor_signal_keywords().get('undecided', [])
        undecided_found = []

        for undecided_kw in undecided_keywords:
            if undecided_kw.lower() in report_nm_lower:
                undecided_found.append(undecided_kw)

        if undecided_found:
            if "조회공시" in report_nm_lower:
                if max_score < 0.5:
                    max_score = 0.5
                    best_reason = f"undecided_in_inquiry:{','.join(undecided_found[:3])}"
            else:
                if max_score < 0.4:
                    max_score = 0.4
                    best_reason = f"undecided_status:{','.join(undecided_found[:3])}"

            high_uncertainty = ["검토 중", "협의 중", "논의 중", "TBD", "미정", "미확정"]
            if any(kw in undecided_found for kw in high_uncertainty):
                if max_score < 0.6:
                    max_score = 0.6
                    best_reason = f"high_uncertainty:{','.join([kw for kw in undecided_found if kw in high_uncertainty][:2])}"

    if "조회공시" in report_nm_lower:
        if "요구" in report_nm_lower or "요청" in report_nm_lower:
            if max_score < 0.4:
                max_score = 0.4
                best_reason = "inquiry_request:rumor_exists"

        elif "답변" in report_nm_lower or "회신" in report_nm_lower:
            if any(kw in report_nm_lower for kw in ["사실", "확인", "맞다", "진행"]):
                if max_score < 0.7:
                    max_score = 0.7
                    best_reason = "inquiry_answer:confirmed"
            elif any(kw in report_nm_lower for kw in denial_keywords[:20]):
                if max_score < 0.3:
                    max_score = 0.3
                    best_reason = "inquiry_answer:denied"
            else:
                if max_score < 0.5:
                    max_score = 0.5
                    best_reason = "inquiry_answer:ambiguous"

    return max_score, best_reason


class EnhancedDARTVerifier(OpenDARTVerifier):

    def __init__(
            self,
            api_key: Optional[str] = None,
            db_config: Optional[dict] = None,
            db_cutoff_hour: int = 23
    ):
        super().__init__(api_key, db_config, db_cutoff_hour)

    def verify_with_event(
            self,
            company_names: List[str],
            article_title: str,
            article_content: str,
            event_labels: List[str] = None,
            event_phrases: List[str] = None,
            window_days: int = 7,
            article_date: Optional[dt.datetime] = None
    ) -> DARTVerificationResult:

        result = super().verify(
            company_names=company_names,
            article_title=article_title,
            article_content=article_content,
            window_days=window_days,
            article_date=article_date
        )

        if not event_labels:
            logger.info("No event_extractor labels provided, using base verification")
            return result

        rumor_text = f"{article_title} {article_content}"

        highly_relevant = []
        moderately_relevant = []
        irrelevant = []

        for disclosure in result.relevant_disclosures:
            relevance_score, reason = calculate_relevance_score(
                disclosure.report_nm,
                event_labels,
                rumor_text=rumor_text,
                event_phrases=event_phrases
            )

            logger.info(f"Disclosure: {disclosure.report_nm}")
            logger.info(f"  Relevance: {relevance_score:.2f}, Reason: {reason}")

            if relevance_score >= 0.5:
                highly_relevant.append((disclosure, relevance_score, reason))
            elif relevance_score >= 0.2:
                moderately_relevant.append((disclosure, relevance_score, reason))
            else:
                irrelevant.append((disclosure, relevance_score, reason))

        adjusted_score = 0
        new_signals = []
        final_relevant_disclosures = []

        if highly_relevant:
            best_match = max(highly_relevant, key=lambda x: x[1])
            adjusted_score = -30

            reason_parts = best_match[2].split(":")
            if reason_parts[0] == "keyword_match":
                desc = f"키워드 매칭: {reason_parts[2]}"
            elif reason_parts[0] == "label_match":
                desc = f"라벨 매칭: {reason_parts[2]}"
            else:
                desc = f"{len(highly_relevant)}건의 직접 관련 공시 확인"

            new_signals.append(DisclosureSignal(
                type=DisclosureSignalType.DECISION,
                keywords=[d[0].report_nm for d in highly_relevant[:3]],
                weight=-30,
                description=desc
            ))
            logger.info(f"Found {len(highly_relevant)} highly relevant disclosures")

            final_relevant_disclosures = [d[0] for d in sorted(highly_relevant, key=lambda x: x[1], reverse=True)]

        elif moderately_relevant:
            adjusted_score = -10
            new_signals.append(DisclosureSignal(
                type=DisclosureSignalType.ANSWER,
                keywords=[d[0].report_nm for d in moderately_relevant[:2]],
                weight=-10,
                description=f"{len(moderately_relevant)}건의 간접 관련 공시"
            ))
            logger.info(f"Found {len(moderately_relevant)} moderately relevant disclosures")
            final_relevant_disclosures = [d[0] for d in moderately_relevant]

        else:
            if irrelevant:
                adjusted_score = 0
                new_signals.append(DisclosureSignal(
                    type=DisclosureSignalType.NEUTRAL,
                    keywords=["무관한 공시"],
                    weight=0,
                    description=f"이벤트와 무관한 공시 {len(irrelevant)}건"
                ))
                logger.info(f"Found {len(irrelevant)} unrelated disclosures")
                final_relevant_disclosures = []

        has_query_disclosure = False
        query_disclosures = []

        for disclosure in result.relevant_disclosures:
            if "조회공시" in disclosure.report_nm and "요구" in disclosure.report_nm:
                has_query_disclosure = True
                query_disclosures.append(disclosure)

        if has_query_disclosure:
            new_signals.append(DisclosureSignal(
                type=DisclosureSignalType.QUERY,
                keywords=["조회공시"],
                weight=20,
                description="조회공시 요청 - 루머 확인 중"
            ))
            adjusted_score += 20
            logger.info(f"Found {len(query_disclosures)} inquiry disclosure(s)")

            for qd in query_disclosures:
                if qd not in final_relevant_disclosures:
                    final_relevant_disclosures.append(qd)

        if new_signals:
            result.signals = new_signals
            result.rumor_score_adjustment = adjusted_score
            result.relevant_disclosures = final_relevant_disclosures

            if highly_relevant and has_query_disclosure:
                result.evidence_summary = f"혼재 신호: 확정 공시 + 조회공시 발견 (조정값: {adjusted_score})"
            elif highly_relevant:
                result.evidence_summary = f"공식 확인: {len(highly_relevant)}건의 직접 관련 공시"
            elif moderately_relevant and has_query_disclosure:
                result.evidence_summary = f"불확실: 간접 공시 + 조회공시 (조정값: {adjusted_score})"
            elif moderately_relevant:
                result.evidence_summary = f"부분 확인: {len(moderately_relevant)}건의 간접 관련 공시"
            elif has_query_disclosure:
                result.evidence_summary = "조회공시 발견 - 루머 확인 중"
            elif irrelevant:
                result.evidence_summary = "이벤트와 무관한 공시만 발견"
            else:
                result.evidence_summary = "관련 공시 없음"

        return result


def verify_with_event_context(
        company_names: List[str],
        article_title: str,
        article_content: str,
        event_labels: List[str] = None,
        event_phrases: List[str] = None,
        dart_api_key: Optional[str] = None
) -> Dict[str, Any]:
    verifier = EnhancedDARTVerifier(dart_api_key)
    result = verifier.verify_with_event(
        company_names=company_names,
        article_title=article_title,
        article_content=article_content,
        event_labels=event_labels,
        event_phrases=event_phrases,
        window_days=7
    )

    from .utils import clamp
    adjusted_score = clamp(50 + result.rumor_score_adjustment, 0, 100)
    rumor_probability = adjusted_score / 100.0

    if rumor_probability >= 0.7:
        recommendation = "높은 루머 가능성 - 공식 확인 필요"
    elif rumor_probability <= 0.3:
        recommendation = "낮은 루머 가능성 - 공식 확정 또는 신뢰할 만한 출처"
    else:
        recommendation = "불확실 - 추가 검증 필요"

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
            "signals": [
                {
                    "type": s.type.value if hasattr(s.type, "value") else str(s.type),
                    "keywords": s.keywords,
                    "weight": s.weight,
                    "description": s.description,
                }
                for s in result.signals[:5]
            ],
            "summary": result.evidence_summary,
        },
        "recommendation": recommendation,
    }
