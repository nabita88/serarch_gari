"""계약 공시 분석기 - 계약 상대방 정보 추출 및 검증"""
from __future__ import annotations
from typing import List, Optional, Tuple
import re
import logging

from .models import DisclosureMeta

logger = logging.getLogger(__name__)

# 계약 관련 키워드 (supls_verifier의 company.contract_win과 동기화 필요)
CONTRACT_KEYWORDS = [
    "공급계약", "수주", "계약체결", "판매계약", "용역계약", "건설계약"
]


class ContractAnalyzer:
    """계약 공시에서 상대방 정보를 추출하고 루머와 비교"""

    def is_contract_disclosure(self, report_nm: str) -> bool:
        """계약 관련 공시인지 판단"""
        report_lower = report_nm.lower()
        return any(kw in report_lower for kw in CONTRACT_KEYWORDS)

    def extract_counterparty_from_text(self, text: str) -> List[str]:
        """
        텍스트에서 계약 상대방 추출

        패턴:
        - "~와 계약", "~과 계약"
        - "매수인: ~", "매도인: ~"
        - "거래처: ~", "공급처: ~"
        """
        counterparties = []
        text = text.replace('\n', ' ')

        # 패턴 1: ~와/과 계약
        pattern1 = r'([가-힣A-Za-z0-9\s]+)(?:와|과)\s*계약'
        matches = re.findall(pattern1, text)
        counterparties.extend([m.strip() for m in matches if len(m.strip()) > 2])

        # 패턴 2: 매수인/매도인/거래처 등
        pattern2 = r'(?:매수인|매도인|거래처|공급처|수요처|계약상대방|상대방)\s*[:\s]\s*([가-힣A-Za-z0-9\s]+)'
        matches = re.findall(pattern2, text)
        counterparties.extend([m.strip() for m in matches if len(m.strip()) > 2])

        # 패턴 3: 주식회사, (주) 형태
        pattern3 = r'(?:주식회사|㈜|\(주\))\s*([가-힣A-Za-z0-9]+)'
        matches = re.findall(pattern3, text)
        counterparties.extend([f"(주){m.strip()}" for m in matches if len(m.strip()) > 1])

        # 중복 제거 및 정리
        unique = []
        seen = set()
        for cp in counterparties:
            cp_clean = cp.strip()
            if cp_clean and cp_clean not in seen and len(cp_clean) <= 50:
                seen.add(cp_clean)
                unique.append(cp_clean)

        return unique[:5]  # 최대 5개만

    def match_counterparty_with_rumor(
            self,
            disclosure: DisclosureMeta,
            rumor_companies: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        공시의 계약 상대방이 루머에 언급된 기업인지 확인

        Returns:
            (매칭여부, 매칭된_기업명들)
        """
        if not self.is_contract_disclosure(disclosure.report_nm):
            return False, []

        # counterparty 필드 사용
        counterparty = disclosure.counterparty
        if not counterparty:
            # summary나 rm에서 추출 시도
            text = f"{disclosure.report_nm} {disclosure.rm}"
            extracted = self.extract_counterparty_from_text(text)
        else:
            extracted = [counterparty]

        if not extracted:
            return False, []

        # 루머에 언급된 기업과 비교
        matched = []
        for rumor_company in rumor_companies:
            rumor_clean = self._normalize_company_name(rumor_company)

            for cp in extracted:
                cp_clean = self._normalize_company_name(cp)

                # 부분 매칭 (예: "삼성" in "삼성전자")
                if rumor_clean in cp_clean or cp_clean in rumor_clean:
                    matched.append(cp)
                    logger.info(f"계약 상대방 매칭: {cp} ↔ {rumor_company}")

        return len(matched) > 0, matched

    def _normalize_company_name(self, name: str) -> str:
        """기업명 정규화"""
        # 괄호, 주식회사 등 제거
        name = re.sub(r'\(주\)|㈜|주식회사|\s+', '', name)
        return name.lower().strip()

    def analyze_contract_signal(
            self,
            disclosure: DisclosureMeta,
            rumor_companies: List[str]
    ) -> dict:

        is_contract = self.is_contract_disclosure(disclosure.report_nm)

        if not is_contract:
            return {
                'is_contract': False,
                'has_counterparty': False,
                'counterparty_matched': False,
                'matched_companies': [],
                'weight_adjustment': 0
            }

        matched, companies = self.match_counterparty_with_rumor(
            disclosure, rumor_companies
        )

        # 가중치 조정
        weight = 0
        if matched:
            # 루머에 언급된 기업과 계약 → 신뢰도 상승
            weight = -40
        elif disclosure.counterparty:
            # 계약 상대방은 있지만 루머와 무관 → 약간 감소
            weight = -15

        return {
            'is_contract': True,
            'has_counterparty': bool(disclosure.counterparty or companies),
            'counterparty_matched': matched,
            'matched_companies': companies,
            'weight_adjustment': weight
        }


# 편의 함수
def analyze_contract_disclosures(
        disclosures: List[DisclosureMeta],
        rumor_companies: List[str]
) -> List[dict]:
    """여러 공시를 한번에 분석"""
    analyzer = ContractAnalyzer()
    results = []

    for disclosure in disclosures:
        result = analyzer.analyze_contract_signal(disclosure, rumor_companies)
        if result['is_contract']:
            results.append({
                'disclosure': disclosure,
                **result
            })

    return results
