from __future__ import annotations
import os
from typing import Dict
import pandas as pd
from . import error_handler


def _load_enhanced_company_master(extractor) -> Dict[str, Dict]:
    """향상된 회사 마스터 데이터 로드"""
    company_dict = {}

    stock_path = os.path.join(extractor.DATA_PATH, "stock_master.csv")
    df = None
    if os.path.exists(stock_path):
        for enc in ['cp949', 'utf-8', 'euc-kr', 'utf-8-sig']:
            try:
                df = pd.read_csv(stock_path, encoding=enc)
                print(f"  [OK] stock_master.csv 로드 성공 (encoding: {enc})")
                break
            except Exception:
                continue

        if df is not None:
            for _, row in df.iterrows():
                if len(row) > 1 and pd.notna(row.iloc[1]):
                    name = str(row.iloc[1]).strip()
                    if name and len(name) >= 2:
                        company_dict[name] = {
                            "code": str(row.iloc[0]) if pd.notna(row.iloc[0]) else None,
                            "name": name,
                            "sector": str(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else None,
                            "market": str(row.iloc[3]) if len(row) > 3 and pd.notna(row.iloc[3]) else None,
                            "length": len(name),
                            "type": "listed",
                            "verified": True
                        }
            print(f"  [OK] {len(company_dict)} companies loaded from stock_master.csv")
        else:
            print(f"  [WARNING] Failed to read stock_master.csv")
    else:
        print(f"  [WARNING] stock_master.csv not found: {stock_path}")

    additional = _get_comprehensive_additional_companies(extractor)

    for n, info in additional.items():
        if n not in company_dict:
            company_dict[n] = info

    print(f"[OK] Total {len(company_dict)} companies loaded in enhanced master")

    return company_dict if company_dict else _get_fallback_companies()


def _get_comprehensive_additional_companies(extractor) -> Dict[str, Dict]:
    """comprehensive_companies.json에서 추가 회사 정보 로드"""
    additional = {}

    path = os.path.join(extractor.DATA_PATH, "comprehensive_companies.json")
    comp = error_handler.safe_json_load(path)

    if not comp:
        return _get_fallback_additional_companies()

    try:
        for cat_name, cat_data in comp.get("categories", {}).items():
            for cname, cinfo in cat_data.get("companies", {}).items():
                if cname not in additional:
                    additional[cname] = {
                        "code": cinfo.get("code"),
                        "name": cname,
                        "sector": cinfo.get("sector"),
                        "market": "기타",
                        "length": len(cname),
                        "type": cinfo.get("type", "listed"),
                        "verified": True
                    }
                    if "old_name" in cinfo:
                        additional[cname]["old_name"] = cinfo["old_name"]
                    if "changed_to" in cinfo:
                        additional[cname]["changed_to"] = cinfo["changed_to"]

        print(f"[OK] {len(additional)} companies loaded from comprehensive_companies.json")

    except Exception as e:
        print(f"[WARNING] Failed to load comprehensive_companies.json: {e}")

    if not additional:
        additional = _get_fallback_additional_companies()

    return additional


def _get_fallback_additional_companies() -> Dict[str, Dict]:
    """폴백용 추가 회사 데이터"""
    companies = {
        "삼성전자": {"sector": "전자", "type": "listed"},
        "삼성바이오로직스": {"sector": "바이오", "type": "subsidiary"},
        "삼성SDI": {"sector": "배터리", "type": "subsidiary"},
        "LG전자": {"sector": "전자", "type": "listed"},
        "LG에너지솔루션": {"sector": "배터리", "type": "subsidiary"},
        "LG화학": {"sector": "화학", "type": "subsidiary"},
        "SK하이닉스": {"sector": "반도체", "type": "listed"},
        "SK텔레콤": {"sector": "통신", "type": "subsidiary"},
        "SK이노베이션": {"sector": "화학", "type": "subsidiary"},
        "현대자동차": {"sector": "자동차", "type": "listed"},
        "기아": {"sector": "자동차", "type": "subsidiary"},
        "현대모비스": {"sector": "자동차부품", "type": "subsidiary"},
        "네이버": {"sector": "IT", "type": "tech"},
        "카카오": {"sector": "IT", "type": "tech"},
        "쿠팡": {"sector": "이커머스", "type": "unicorn"},
        "POSCO홀딩스": {"sector": "철강", "type": "conglomerate"},
        "한국전력": {"sector": "전력", "type": "listed"},
        "KT": {"sector": "통신", "type": "listed"},
        "셀트리온": {"sector": "바이오", "type": "listed"},
    }

    additional = {}
    for name, info in companies.items():
        additional[name] = {
            "code": None,
            "name": name,
            "sector": info["sector"],
            "market": "기타",
            "length": len(name),
            "type": info["type"],
            "verified": True
        }

    return additional


def _get_fallback_companies() -> Dict[str, Dict]:
    """완전 폴백용 기본 회사 데이터"""
    return {
        "삼성전자": {"code": "005930", "name": "삼성전자", "sector": "전자", "length": 4, "verified": True},
        "SK하이닉스": {"code": "000660", "name": "SK하이닉스", "sector": "반도체", "length": 6, "verified": True},
        "LG전자": {"code": "066570", "name": "LG전자", "sector": "전자", "length": 4, "verified": True},
        "현대자동차": {"code": "005380", "name": "현대자동차", "sector": "자동차", "length": 5, "verified": True},
        "네이버": {"code": "035420", "name": "네이버", "sector": "IT", "length": 3, "verified": True},
    }
