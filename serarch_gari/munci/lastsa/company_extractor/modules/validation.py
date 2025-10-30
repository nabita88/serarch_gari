from __future__ import annotations
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from ..models import ValidationResult

def _validate_candidates(extractor, ensemble_result: Dict[str, Any],
                         text: str, context: Optional[Dict] = None) -> Dict[str, Any]:

    validated_companies = []
    validation_details = {}

    # 높은 신뢰도 후보 검증
    for company in ensemble_result['high_confidence']:
        vr = _validate_company(extractor, company, text, context, strict=False)
        if vr.is_valid:
            validated_companies.append(company)
            validation_details[company] = {
                'status': 'validated',
                'confidence': vr.confidence,
                'methods': vr.validation_methods
            }
        else:
            validation_details[company] = {
                'status': 'high_confidence_but_failed_validation',
                'confidence': vr.confidence,
                'warnings': vr.warnings
            }

    # 중간 신뢰도 후보 검증
    for company in ensemble_result['medium_confidence']:
        vr = _validate_company(extractor, company, text, context, strict=False)
        if vr.is_valid and vr.confidence > 0.6:
            validated_companies.append(company)
            validation_details[company] = {
                'status': 'medium_validated',
                'confidence': vr.confidence,
                'methods': vr.validation_methods
            }

    # 낮은 신뢰도 복원 가능 후보
    recoverable = []
    for company in ensemble_result['low_confidence_recoverable']:
        if _is_recoverable_candidate(extractor, company, text, ensemble_result):
            recoverable.append(company)
            validation_details[company] = {
                'status': 'recovered_candidate',
                'confidence': 0.7,
                'methods': ['recovery_validation']
            }

    ensemble_result.update({
        'validated_companies': validated_companies,
        'recoverable_candidates': recoverable,
        'validation_details': validation_details
    })
    return ensemble_result

def _validate_company(extractor, company: str, text: str,
                      context: Optional[Dict] = None,
                      strict: bool = False) -> ValidationResult:
    """개별 회사명 검증"""
    methods = []
    scores = []
    warnings = []
    suggestions: List[str] = []

    # 마스터 DB 검증
    if company in extractor.company_master:
        methods.append('master_db')
        scores.append(0.9)
    else:
        official = extractor._normalize_to_official_name(company)
        if official != company and official in extractor.company_master:
            methods.append('alias_to_official')
            scores.append(0.85)
        elif not strict:
            similar = extractor._find_similar_companies(company, threshold=0.8)
            if similar:
                suggestions.extend(similar[:2])
                scores.append(0.6)

    # 문맥 검증
    ctx_score = _validate_contextual_relevance(extractor, company, text, context)
    methods.append('contextual')
    scores.append(ctx_score)

    # 패턴 검증
    pv = _validate_pattern_match(extractor, company, text)
    if pv['valid']:
        methods.append('pattern')
        scores.append(pv['confidence'])

    # 의미 검증
    if not _is_obviously_invalid(company):
        methods.append('semantic')
        scores.append(0.7)
    else:
        warnings.append(f"의미적으로 부적절한 가능성: {company}")
        scores.append(0.3)

    avg = sum(scores) / len(scores) if scores else 0
    min_conf = 0.7 if strict else 0.5
    is_valid = avg >= min_conf and len(methods) >= 1

    return ValidationResult(
        is_valid=is_valid,
        confidence=avg,
        validation_methods=methods,
        suggestions=suggestions,
        warnings=warnings
    )

def _validate_contextual_relevance(extractor, company: str, text: str,
                                   context: Optional[Dict] = None) -> float:
    """문맥 관련성 검증"""
    conf = 0.5
    if context and context.get('title') and company in context['title']:
        conf += 0.4
    mentions = len(re.findall(rf'(?<![가-힣A-Za-z]){re.escape(company)}(?![가-힣A-Za-z])', text))
    if mentions > 0:
        conf += min(mentions * 0.1, 0.3)
    for kw in _get_company_related_keywords(extractor, company):
        if kw in text:
            conf += 0.05
            break
    return min(conf, 1.0)

def _get_company_related_keywords(extractor, company: str) -> List[str]:
    """회사 관련 키워드 가져오기"""
    if company not in extractor.company_master:
        return []
    sector = extractor.company_master[company].get('sector', '')
    sector_keywords = {
        '전자': ['반도체', '디스플레이', '가전', '스마트폰'],
        '자동차': ['전기차', '내연기관', '모빌리티', '자율주행'],
        '화학': ['석유화학', '소재', '배터리'],
        '조선': ['선박', '해양플랜트', '조선업'],
        '건설': ['부동산', '아파트', '건축'],
        'IT': ['플랫폼', '소프트웨어', '인공지능'],
        '금융': ['은행', '증권', '보험', '핀테크']
    }
    return sector_keywords.get(sector, [])

def _validate_pattern_match(extractor, company: str, text: str) -> Dict[str, Any]:
    """패턴 매칭 검증"""
    for pat, p_company, p_conf in extractor.company_patterns:
        if p_company == company:
            matches = list(pat.finditer(text))
            if matches:
                return {'valid': True, 'confidence': min(p_conf + 0.1, 1.0), 'match_count': len(matches)}
    return {'valid': False, 'confidence': 0.3}

def _is_obviously_invalid(company: str) -> bool:
    """명백하게 유효하지 않은 회사명인지 확인"""
    if len(company) < 2 or len(company) > 20:
        return True
    bad = {'회사', '기업', '업체', '업계', '그룹사', '계열사',
           '모두', '전체', '각각', '또한', '그리고', '하지만',
           '이번', '올해', '내년', '최근', '새로운'}
    if company in bad:
        return True
    if re.match(r'^\d+$', company):
        return True
    return False

def _is_recoverable_candidate(extractor, company: str, text: str,
                              ensemble_result: Dict[str, Any]) -> bool:
    """복원 가능한 후보인지 확인"""
    if company not in extractor.company_master:
        return False
    found = False
    for alias in extractor.company_aliases.get(company, [company]):
        pattern = rf'(?<![가-힣A-Za-z0-9]){re.escape(alias)}(?=\s|[,.!?;:]|$|[^가-힣A-Za-z0-9])'
        if re.search(pattern, text, re.IGNORECASE):
            found = True
            break
    if not found:
        return False
    extraction_methods = ensemble_result.get('extraction_methods', {})
    if company in extraction_methods and len(extraction_methods[company]) >= 1:
        return True
    return False
