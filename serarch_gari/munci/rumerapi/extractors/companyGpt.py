
from __future__ import annotations
from typing import Optional, Dict, Any
import logging
import threading

logger = logging.getLogger(__name__)

_extractor: Optional[object] = None
_lock = threading.Lock()  # Thread-Safe 보장


def initialize_extractor():

    global _extractor

    # Double-Checked Locking Pattern
    if _extractor is None:
        with _lock:
            if _extractor is None:
                try:
                    from munci.lastsa.company_extractor.extractor import FinalCompanyExtractor
                    _extractor = FinalCompanyExtractor()
                    logger.info("FinalCompanyExtractor initialized")
                except Exception as e:
                    logger.error(f"FinalCompanyExtractor initialization failed: {e}")
                    _extractor = None

    return _extractor


def extract_companies(text: str) -> Dict[str, Any]:

    extractor = initialize_extractor()
    if extractor is None:
        logger.error("No company extractor available")
        return {'companies': [], 'company_details': {}}

    try:
        if hasattr(extractor, 'extract_companies'):
            result = extractor.extract_companies(text)

            if isinstance(result, list):
                return {'companies': result, 'company_details': {}}

            if hasattr(result, 'companies'):
                companies = result.companies or []

                company_details = {}
                if hasattr(result, 'company_details') and result.company_details:
                    for name, info in result.company_details.items():
                        company_details[name] = {
                            'name': info.name,
                            'stock_code': info.stock_code,
                            'corp_code': info.corp_code,
                            'sector': info.sector,
                            'market': info.market
                        }

                return {
                    'companies': companies,
                    'company_details': company_details
                }

            return {'companies': result or [], 'company_details': {}}

        return {'companies': [], 'company_details': {}}
    except Exception as e:
        logger.exception(f"Company extraction failed: {e}")
        return {'companies': [], 'company_details': {}}
