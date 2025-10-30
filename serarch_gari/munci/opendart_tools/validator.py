from __future__ import annotations
from typing import List, Dict, Any, Optional
import datetime as dt

from .models import (
    DisclosureMeta, RuleHit, DARTVerdictResult
)
from .rules import (
    HEDGING, CONFIRM, DENIAL, DART_DECISION, DART_QUERY, DART_ANSWER, TITLE_HINTS
)
from .utils import match_keywords
from .dart_client import DARTClient


def compute_verdict_from_disclosures(
        text: str,
        disclosures: List[DisclosureMeta],
        title: Optional[str] = None,
) -> DARTVerdictResult:
    base = 50
    hits: List[RuleHit] = []
    full_text = f"{title or ''}\n{text}"

    m = match_keywords(full_text, HEDGING)
    if m:
        base += 20
        hits.append(RuleHit("모호/추측 표현", +20, "text", m))

    m = match_keywords(full_text, DENIAL)
    if m:
        base -= 30
        hits.append(RuleHit("공식 부인", -30, "text", m))

    m = match_keywords(full_text, CONFIRM)
    if m and "조회공시" not in full_text:
        base -= 15
        hits.append(RuleHit("공식 확정", -15, "text", m))

    if title and any(h in title for h in TITLE_HINTS):
        base += 10
        hits.append(RuleHit("제목 과장/의문", +10, "title", TITLE_HINTS))

    dart_evidence: List[Dict[str, Any]] = []
    for d in disclosures:
        report = d.report_nm or ""
        signals = []

        m1 = match_keywords(report, DART_DECISION)
        if m1:
            base -= 25
            hits.append(RuleHit("DART: 의사결정/체결", -25, "dart", m1))
            signals.extend(m1)

        m2 = match_keywords(report, DART_QUERY)
        if m2:
            base += 10
            hits.append(RuleHit("DART: 조회공시/풍문", +10, "dart", m2))
            signals.extend(m2)

        m3 = match_keywords(report, DART_ANSWER)
        if m3:
            base -= 10
            hits.append(RuleHit("DART: 공식답변", -10, "dart", m3))
            signals.extend(m3)

        if signals:
            dart_evidence.append({
                "rcept_no": d.rcept_no,
                "rcept_dt": d.rcept_dt,
                "corp_name": d.corp_name,
                "report_nm": d.report_nm,
                "signals": list(set(signals)),
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={d.rcept_no}",
            })

    score = max(0, min(100, base))

    if score >= 70:
        verdict = "루머 가능성 높음"
    elif score <= 35:
        verdict = "비루머(공식확인/부인)"
    else:
        verdict = "불확실"

    evidence = {
        "disclosures": dart_evidence,
        "rule_hits": [h.__dict__ for h in hits],
        "base_score": base,
        "final_score": score,
    }

    return DARTVerdictResult(
        verdict=verdict,
        score=score,
        evidence=evidence,
        disclosures=disclosures,
    )


class OpenDARTValidator:
    def __init__(self, api_key: str | None = None):
        import os
        self.api_key = api_key or os.getenv("DART_API_KEY", "")
        self.dart_client = DARTClient(self.api_key) if self.api_key else None

    def verify(
            self,
            text: str,
            company_names: List[str],
            title: Optional[str] = None,
            window_days: int = 3,
            company_details: Optional[Dict[str, Dict]] = None
    ) -> Optional[DARTVerdictResult]:
        if not self.dart_client:
            return None

        all_disclosures: List[DisclosureMeta] = []
        today = dt.date.today()
        bgn = today - dt.timedelta(days=window_days)
        end = today

        for company in company_names:
            corp_code = None
            if company_details and company in company_details:
                corp_code = company_details[company].get('corp_code')

            if not corp_code:
                print(f"⚠️ {company}의 corp_code를 찾을 수 없음")
                continue

            try:
                disclosures = self.dart_client.list_disclosures(
                    corp_code=corp_code,
                    bgn_de=bgn,
                    end_de=end,
                    page_count=50,
                    max_pages=2,
                )
                all_disclosures.extend(disclosures)
            except Exception as e:
                print(f"⚠️ {company} 공시 조회 실패: {e}")
                continue

        if not all_disclosures:
            return None

        return compute_verdict_from_disclosures(text=text, disclosures=all_disclosures, title=title)
