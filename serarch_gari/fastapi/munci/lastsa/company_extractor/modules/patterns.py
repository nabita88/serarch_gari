from __future__ import annotations
import re
from typing import List, Tuple
from . import filters, error_handler


def _build_advanced_patterns(extractor) -> List[Tuple[re.Pattern, str, float]]:

    patterns = []
    companies_to_process = []

    # 처리할 회사 선정
    for company_name in extractor.company_master.keys():
        if len(companies_to_process) < extractor.MAX_PATTERN_COUNT:
            companies_to_process.append(company_name)

    # 각 회사의 패턴 생성
    for company_name in companies_to_process:
        info = error_handler.safe_dict_get(extractor.company_master, company_name)
        if not info:
            continue

        # 기본 가중치 계산
        base_weight = 0.7
        if info.get("verified"):
            base_weight += 0.1
        if info.get("type") == "listed":
            base_weight += 0.1
        if len(company_name) >= 4:
            base_weight += 0.05
        if info.get("sector") in ["전자", "자동차", "IT", "반도체"]:
            base_weight += 0.05

        # 사용할 별칭 목록 (본명 + 주요 별칭 2개)
        aliases_to_use = [company_name]
        if company_name in extractor.company_aliases:
            main_aliases = [a for a in extractor.company_aliases[company_name] if a != company_name]
            aliases_to_use.extend(main_aliases[:2])

        # 각 별칭에 대해 패턴 생성
        for alias in aliases_to_use:
            pattern = error_handler.safe_compile_pattern(alias)
            if pattern:
                weight = base_weight * (
                    1.0 if alias == company_name else
                    (0.95 if len(alias) >= len(company_name) else 0.85)
                )
                patterns.append((pattern, company_name, weight))

    # 가중치 순으로 정렬
    patterns.sort(key=lambda x: (-x[2], -len(x[1])))
    print(f"[OK] Total {len(patterns)} patterns generated")
    return patterns


def _extract_with_patterns(extractor, text: str) -> List[str]:

    found = []

    for pat, cname, conf in extractor.company_patterns:
        matches = error_handler.safe_pattern_finditer(pat, text)

        for m in matches:
            # 그룹명 단독 사용인지 체크
            if filters.should_exclude_group_mention(cname, text):
                continue

            found.append((m.start(), m.end(), cname, conf, m.group()))

    resolved = _resolve_overlapping_matches(extractor, found)
    return [m[2] for m in resolved]


def _resolve_overlapping_matches(extractor, matches):

    if not matches:
        return []

    sorted_matches = sorted(matches, key=lambda x: (x[0], -x[3], -len(x[2])))
    result = []

    for current in sorted_matches:
        cstart, cend, cname, cconf, calias = current
        overlapping = []

        for existing in result:
            estart, eend = existing[0], existing[1]
            if not (cend <= estart or cstart >= eend):
                overlapping.append(existing)

        if not overlapping:
            result.append(current)
        else:
            allc = overlapping + [current]
            best = max(allc, key=lambda x: (
                x[3],  # 신뢰도
                len(x[2]),  # 회사명 길이
                1.0 if x[4] == x[2] else 0.8  # 본명 여부
            ))

            for ov in overlapping:
                if ov in result:
                    result.remove(ov)
            result.append(best)

    return result
