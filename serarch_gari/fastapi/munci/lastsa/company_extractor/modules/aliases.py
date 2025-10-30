from __future__ import annotations
from collections import defaultdict
from typing import Dict, List, Set, Optional
from . import utils, error_handler


def _merge_krx_aliases(extractor, path: str) -> None:


    krx_data = error_handler.safe_json_load(path)
    if not krx_data:
        return

    for official_name, aliases_list in krx_data.items():
        if not isinstance(aliases_list, list) or len(aliases_list) == 0:
            continue

        ticker, aliases = _parse_krx_aliases(aliases_list)

        _register_company(extractor, official_name, ticker, aliases)


def _parse_krx_aliases(aliases_list: List[str]) -> tuple[Optional[str], List[str]]:

    ticker = None
    aliases = []

    for item in aliases_list:
        if item.isdigit() and len(item) == 6:
            # 숫자 6자리 → 종목코드
            ticker = item
        else:
            # 나머지 → 별칭
            aliases.append(item)

    return ticker, aliases


def _register_company(extractor, official_name: str, ticker: Optional[str], aliases: List[str]) -> None:



    if official_name not in extractor.company_master:
        extractor.company_master[official_name] = {
            "code": ticker,  # "005930"
            "name": official_name,  # "삼성전자"
            "market": "KRX",
            "length": len(official_name),
            "type": "listed",
            "verified": True
        }



    existing_aliases: Set[str] = set(extractor.company_aliases.get(official_name, []))


    existing_aliases.update(aliases)


    existing_aliases.add(official_name)

    extractor.company_aliases[official_name] = list(existing_aliases)


    for alias in aliases:
        extractor.alias_to_official[alias] = official_name


def _build_enhanced_company_aliases(extractor) -> Dict[str, List[str]]:

    aliases = extractor.company_aliases if hasattr(extractor, 'company_aliases') else defaultdict(list)

    suffix_rules = {
        "전자": _create_electronics_aliases,  # "삼성전자" → ["삼성"]
        "자동차": _create_automotive_aliases,  # "현대자동차" → ["현대", "현대차"]
        "홀딩스": _create_holding_aliases,  # "삼성홀딩스" → ["삼성"]
    }


    for company_name in extractor.company_master.keys():



        if company_name not in aliases:
            aliases[company_name] = []
        if company_name not in aliases[company_name]:
            aliases[company_name].append(company_name)



        for suffix, rule_func in suffix_rules.items():
            if suffix in company_name:

                new_aliases = rule_func(company_name, suffix)


                _add_aliases(extractor, company_name, aliases, new_aliases)



    for company in aliases:
        aliases[company] = list(set(aliases[company]))

    print(f"[OK] Total {len(extractor.alias_to_official)} alias mappings built")

    return dict(aliases)


def _create_electronics_aliases(company_name: str, suffix: str) -> List[str]:

    base = company_name.replace(suffix, "")
    return [base] if len(base) > 1 else []


def _create_automotive_aliases(company_name: str, suffix: str) -> List[str]:

    base = company_name.replace(suffix, "")
    if len(base) <= 1:
        return []

    aliases = [base]  # ["현대"]
    base_with_cha = base + "차"  # "현대차"
    aliases.append(base_with_cha)  # ["현대", "현대차"]
    return aliases


def _create_holding_aliases(company_name: str, suffix: str) -> List[str]:

    base = company_name.replace(suffix, "")
    return [base] if len(base) > 1 else []


def _add_aliases(extractor, official_name: str, aliases_dict: Dict, new_aliases: List[str]) -> None:

    for alias in new_aliases:
        if alias not in aliases_dict[official_name]:
            # aliases_dict에 별칭 추가
            aliases_dict[official_name].append(alias)
            # aliases_dict["삼성전자"] = ["삼성전자", "삼성"]

            # 역매핑 저장
            extractor.alias_to_official[alias] = official_name
            # alias_to_official["삼성"] = "삼성전자"


def _normalize_to_official_name(extractor, company: str) -> str:

    # 1순위: alias_to_official에서 찾기
    if company in extractor.alias_to_official:
        return extractor.alias_to_official[company]
        # "삼성" → "삼성전자" 변환


    if company in extractor.company_master:
        return company
        # "삼성전자" → "삼성전자" (그대로)


    for official in extractor.company_master.keys():
        similarity = utils._calculate_string_similarity(company, official)
        if similarity > 0.9:
            return official



    return company


def _find_similar_companies(extractor, company: str, threshold: float = 0.8) -> List[str]:

    similar = []

    for master_company in extractor.company_master.keys():
        similarity = utils._calculate_string_similarity(company, master_company)
        if similarity >= threshold:
            similar.append(master_company)

    return similar[:3]
