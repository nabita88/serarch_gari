from __future__ import annotations
import re
from typing import Dict, List, Any
from datetime import datetime
from collections import defaultdict
from ..models import ExtractionResult
from . import filters


def _ensemble_integration(extractor, extraction_results: Dict[str, List[str]],
                          text: str, context: dict = None) -> Dict[str, Any]:
    """여러 추출 방법의 결과를 통합"""
    # 1단계: 투표 및 신뢰도 집계
    company_data = _collect_company_votes(extractor, extraction_results, text)

    # 2단계: 신뢰도 기반 분류
    classified = _classify_by_confidence(
        extractor,
        company_data['confidence'],
        company_data['votes']
    )

    # 3단계: 결과 반환
    return {
        'high_confidence': classified['high'],
        'medium_confidence': classified['medium'],
        'low_confidence_recoverable': classified['low'],
        'confidence_scores': company_data['confidence'],
        'extraction_methods': company_data['methods'],
        'voting_details': company_data['votes']
    }


def _collect_company_votes(extractor, extraction_results: Dict[str, List[str]],
                           text: str) -> Dict[str, Dict]:
    """각 추출 방법의 결과를 수집하고 투표"""
    votes = defaultdict(list)
    confidence = defaultdict(float)
    methods = defaultdict(list)

    for method, companies in extraction_results.items():
        method_weight = extractor.extraction_weights.get(method, 0.1)

        for company in companies:
            # 유효성 검사
            if not company or len(company.strip()) < 2:
                continue

            # 정규화
            normalized = extractor._normalize_to_official_name(company.strip())

            # 그룹명 단독 사용 필터링
            if filters.should_exclude_group_mention(normalized, text):
                continue

            # 투표 및 신뢰도 누적
            votes[normalized].append(method)
            confidence[normalized] += method_weight
            methods[normalized].append(method)

    return {
        'votes': dict(votes),
        'confidence': dict(confidence),
        'methods': dict(methods)
    }


def _classify_by_confidence(extractor, confidence_scores: Dict[str, float],
                            votes: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """신뢰도에 따라 후보를 분류"""
    high, medium, low = [], [], []

    for company, score in confidence_scores.items():
        voting_methods_count = len(set(votes.get(company, [])))

        if (score >= extractor.confidence_threshold and
                voting_methods_count >= extractor.min_consensus_methods):
            high.append((company, score))

        elif (score >= extractor.confidence_threshold * 0.7 and
              voting_methods_count >= 1):
            medium.append((company, score))

        elif score >= 0.3:
            low.append((company, score))

    # 신뢰도 순으로 정렬
    return {
        'high': [c for c, _ in sorted(high, key=lambda x: x[1], reverse=True)],
        'medium': [c for c, _ in sorted(medium, key=lambda x: x[1], reverse=True)],
        'low': [c for c, _ in sorted(low, key=lambda x: x[1], reverse=True)]
    }


def _candidate_recovery_and_refinement(extractor, validated_result: Dict[str, Any],
                                       text: str, context: dict = None,
                                       verbose: bool = True) -> ExtractionResult:
    """후보 복원 및 정제"""
    # 1단계: 후보 병합
    companies = _merge_candidates(extractor, validated_result, verbose)

    # 2단계: 중복 제거 및 정렬
    refined = _remove_duplicates(extractor, companies, text)
    sorted_companies = _sort_companies_by_relevance(
        extractor, refined, text,
        validated_result.get('confidence_scores', {})
    )

    # 3단계: 최종 신뢰도 계산
    final_data = _calculate_final_scores(
        sorted_companies,
        validated_result
    )

    # 4단계: 메타데이터 생성
    metadata = _build_metadata(extractor, validated_result, companies)

    return ExtractionResult(
        companies=sorted_companies,
        confidence_scores=final_data['confidence'],
        extraction_methods=final_data['methods'],
        validation_status=final_data['status'],
        metadata=metadata
    )


def _merge_candidates(extractor, validated_result: Dict[str, Any],
                      verbose: bool) -> List[str]:
    """검증된 회사와 복원 가능한 후보를 병합"""
    companies = validated_result.get('validated_companies', [])
    recoverable = validated_result.get('recoverable_candidates', [])

    if recoverable:
        extractor.extraction_stats['false_negative_recovery'] += len(recoverable)
        if verbose:
            print(f"    [RECOVERY] Candidate recovery: {len(recoverable)} items ({recoverable})")
        companies.extend(recoverable)

    return companies


def _calculate_final_scores(sorted_companies: List[str],
                            validated_result: Dict[str, Any]) -> Dict[str, Dict]:
    """최종 신뢰도, 상태, 추출방법 계산"""
    confidence_scores = validated_result.get('confidence_scores', {})
    extraction_methods = validated_result.get('extraction_methods', {})
    validation_details = validated_result.get('validation_details', {})

    final_conf = {}
    final_status = {}
    final_methods = {}

    for company in sorted_companies:
        base_conf = confidence_scores.get(company, 0.5)
        vinfo = validation_details.get(company, {})
        vconf = vinfo.get('confidence', 0.5)

        # 복원된 후보는 더 높은 신뢰도
        if vinfo.get('status') == 'recovered_candidate':
            final_conf[company] = max(0.65, (base_conf + vconf) / 2)
        else:
            final_conf[company] = base_conf * 0.6 + vconf * 0.4

        final_status[company] = vinfo.get('status', 'unknown')
        final_methods[company] = extraction_methods.get(company, [])

    return {
        'confidence': final_conf,
        'status': final_status,
        'methods': final_methods
    }


def _build_metadata(extractor, validated_result: Dict[str, Any],
                    companies: List[str]) -> Dict[str, Any]:
    """메타데이터 생성"""
    recoverable = validated_result.get('recoverable_candidates', [])
    extraction_methods = validated_result.get('extraction_methods', {})
    validation_details = validated_result.get('validation_details', {})

    return {
        'finished_at': datetime.now().isoformat(),
        'features_used': ['fixed_threshold', 'candidate_recovery', 'enhanced_aliases'],
        'confidence_threshold': extractor.confidence_threshold,
        'recovered_candidates_count': len(recoverable),
        'total_methods_used': len([m for methods in extraction_methods.values() for m in methods]),
        'validation_summary': {
            'total_candidates': len(companies) + len(recoverable),
            'validated': len([c for c, v in validation_details.items()
                              if 'validated' in v.get('status', '')]),
            'recovered': len(recoverable)
        }
    }


def _remove_duplicates(extractor, companies: List[str], text: str) -> List[str]:
    """중복된 회사명 제거 (별칭 고려)"""
    if len(companies) <= 1:
        return companies

    refined = []
    for company in companies:
        should_add = True

        for existing in refined:
            if _are_duplicate_companies(extractor, company, existing, text):
                # 더 나은 이름으로 교체
                if _is_better_company_name(extractor, company, existing):
                    refined.remove(existing)
                else:
                    should_add = False
                break

        if should_add:
            refined.append(company)

    return refined


def _are_duplicate_companies(extractor, c1: str, c2: str, text: str) -> bool:
    """두 회사명이 중복인지 확인 (별칭 고려)"""
    # 1. 완전 일치
    if c1 == c2:
        return True

    # 2. 서로의 별칭인 경우
    aliases1 = extractor.company_aliases.get(c1, [c1])
    aliases2 = extractor.company_aliases.get(c2, [c2])
    if c1 in aliases2 or c2 in aliases1:
        return True

    # 3. 정규화된 이름이 같은 경우
    official1 = extractor._normalize_to_official_name(c1)
    official2 = extractor._normalize_to_official_name(c2)
    return official1 == official2


def _is_better_company_name(extractor, c1: str, c2: str) -> bool:
    """두 회사명 중 더 나은 것 선택"""
    in_master1 = c1 in extractor.company_master
    in_master2 = c2 in extractor.company_master

    if in_master1 != in_master2:
        return in_master1

    if len(c1) != len(c2):
        return len(c1) > len(c2)

    return c1 < c2


def _sort_companies_by_relevance(extractor, companies: List[str], text: str,
                                 confidence_scores: Dict[str, float]) -> List[str]:
    """관련성 점수로 회사 정렬"""
    scored = []

    for company in companies:
        score = _calculate_relevance_score(
            extractor, company, text, confidence_scores
        )
        scored.append((company, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [company for company, _ in scored]


def _calculate_relevance_score(extractor, company: str, text: str,
                               confidence_scores: Dict[str, float]) -> float:
    """개별 회사의 관련성 점수 계산"""
    score = 0.0

    # 1. 기본 신뢰도 (40%)
    score += confidence_scores.get(company, 0.5) * 0.4

    # 2. 직접 언급 횟수 (20%)
    mention_count = len(re.findall(
        rf'(?<![가-힣A-Za-z]){re.escape(company)}(?![가-힣A-Za-z])',
        text
    ))
    score += min(mention_count / 3.0, 1.0) * 0.2

    # 3. 별칭 언급 횟수 (10%)
    alias_mentions = _count_alias_mentions(extractor, company, text)
    score += min(alias_mentions / 5.0, 1.0) * 0.1

    # 4. 첫 등장 위치 (15% - 앞쪽일수록 높음)
    first_pos = text.find(company)
    if first_pos >= 0:
        position_score = 1.0 - (first_pos / max(1, len(text)))
        score += position_score * 0.15

    # 5. 회사 속성 보너스 (15%)
    score += _calculate_company_bonus(extractor, company)

    return score


def _count_alias_mentions(extractor, company: str, text: str) -> int:
    """회사의 별칭이 텍스트에 언급된 횟수"""
    count = 0
    for alias in extractor.company_aliases.get(company, []):
        if alias != company:
            count += len(re.findall(
                rf'(?<![가-힣A-Za-z]){re.escape(alias)}(?![가-힣A-Za-z])',
                text
            ))
    return count


def _calculate_company_bonus(extractor, company: str) -> float:
    """회사 속성에 따른 보너스 점수"""
    bonus = 0.0

    if company in extractor.company_master:
        info = extractor.company_master[company]

        # 상장사 보너스
        if info.get('type') == 'listed':
            bonus += 0.075

        # 긴 이름 보너스 (구체적일수록 정확)
        if len(company) >= 4:
            bonus += 0.075

    return bonus
