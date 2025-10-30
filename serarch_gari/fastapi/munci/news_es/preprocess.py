from __future__ import annotations
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from .config import KST
from .utils import (
    split_companies, canonicalize_naver_news, normalize_title, generate_keyphrases,
    simhash64, iso_to_mysql_dt, normalize_publisher
)
from .companies import normalize_company
from .events_es import extract_events, EVENT_CODE2LABEL
from .embedding import embed_title

try:
    from munci.lastsa.event_with_translate import classify_event

    RUMERAPI_AVAILABLE = True
except ImportError:
    RUMERAPI_AVAILABLE = False
    logging.warning("event_with_translate not available, using fallback event extraction")

logger = logging.getLogger(__name__)


class NewsPreprocessor:

    def __init__(
            self,
            use_embedding: bool = False,
            model_name: str = "",
            use_ai_events: bool = False
    ):
        self.use_embedding = use_embedding
        self.model_name = model_name
        self.use_ai_events = use_ai_events

        logger.info(
            f"전처리기 초기화 완료 "
            f"(임베딩={'활성화' if use_embedding else '비활성화'}, "
            f"AI 이벤트={'활성화' if use_ai_events else '비활성화'})"
        )

    def preprocess_row(
            self,
            row: Dict[str, str],
            cols: Dict[str, str]
    ) -> Dict[str, Any]:
        try:
            input_data = self._extract_input_data(row, cols)

            url_data = self._process_url(input_data['url'])

            date_data = self._process_date(input_data['date'])

            title_data = self._process_title(input_data['title'])

            publisher_data = self._process_publisher(input_data['publisher'])

            company_data = self._process_companies(input_data['companies'])

            event_data = self._extract_events(title_data['normalized'])

            embedding = self._generate_embedding(title_data['normalized'])

            doc_id = self._generate_doc_id(
                url_data['oid'],
                url_data['aid'],
                url_data['canonical'],
                input_data['url'],
                title_data['normalized'],
                date_data['iso']
            )

            return self._build_document(
                doc_id=doc_id,
                url_data=url_data,
                date_data=date_data,
                title_data=title_data,
                publisher_data=publisher_data,
                company_data=company_data,
                event_data=event_data,
                category=input_data['category'],
                embedding=embedding
            )

        except Exception as e:
            logger.error(f"행 전처리 실패: {e}", exc_info=True)
            logger.debug(f"문제 발생 행 데이터: {row}")
            raise

    def _extract_input_data(self, row: Dict[str, str], cols: Dict[str, str]) -> Dict[str, str]:
        try:
            return {
                'date': (row.get(cols["date"], "") or "").strip(),
                'category': (row.get(cols["category"], "") or "").strip(),
                'title': (row.get(cols["title"], "") or "").strip(),
                'publisher': (row.get(cols["publisher"], "") or "").strip(),
                'url': (row.get(cols["url"], "") or "").strip(),
                'companies': row.get(cols["companies"], "")
            }
        except KeyError as e:
            logger.error(f"설정에 필수 컬럼 누락: {e}")
            raise
        except Exception as e:
            logger.error(f"입력 데이터 추출 실패: {e}")
            raise

    def _process_url(self, url: str) -> Dict[str, Optional[str]]:
        try:
            canonical_url, oid, aid = canonicalize_naver_news(url)
            return {
                'original': url,
                'canonical': canonical_url or url,
                'oid': oid,
                'aid': aid
            }
        except Exception as e:
            logger.warning(f"URL 정규화 실패 '{url}': {e}")
            return {
                'original': url,
                'canonical': url,
                'oid': None,
                'aid': None
            }

    def _process_date(self, date_str: str) -> Dict[str, Optional[str]]:
        try:
            date_iso = self._parse_date_to_iso(date_str)
            mysql_date = iso_to_mysql_dt(date_iso) if date_iso else None

            if not date_iso:
                logger.warning(f"날짜 파싱 실패: '{date_str}'")

            return {
                'original': date_str,
                'iso': date_iso,
                'mysql': mysql_date
            }
        except Exception as e:
            logger.error(f"날짜 처리 오류 '{date_str}': {e}")
            return {
                'original': date_str,
                'iso': None,
                'mysql': None
            }

    def _parse_date_to_iso(self, date_str: str) -> Optional[str]:
        if not date_str:
            return None

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y.%m.%d",
            "%Y/%m/%d"
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt).replace(tzinfo=KST)
                return dt.isoformat()
            except ValueError:
                continue

        logger.debug(f"날짜 '{date_str}'가 알려진 형식과 일치하지 않음")
        return None

    def _process_title(self, title_raw: str) -> Dict[str, Any]:
        try:
            normalized = normalize_title(title_raw)
            keyphrases = generate_keyphrases(normalized)
            title_hash = simhash64(normalized)

            return {
                'raw': title_raw,
                'normalized': normalized,
                'keyphrases': keyphrases,
                'simhash': title_hash
            }
        except Exception as e:
            logger.error(f"제목 처리 오류 '{title_raw[:50]}...': {e}")
            return {
                'raw': title_raw,
                'normalized': title_raw,
                'keyphrases': [],
                'simhash': ""
            }

    def _process_publisher(self, publisher: str) -> Dict[str, Any]:
        try:
            normalized, tier = normalize_publisher(publisher)
            return {
                'name': normalized,
                'tier': tier
            }
        except Exception as e:
            logger.warning(f"언론사 처리 오류 '{publisher}': {e}")
            return {
                'name': publisher,
                'tier': 0.5  # 기본 가중치
            }

    def _process_companies(self, companies_str: str) -> Dict[str, List[str]]:
        try:
            raw_names = split_companies(companies_str)

            companies = []
            tickers = []

            for name in raw_names:
                try:
                    ticker, canonical = normalize_company(name)
                    if canonical:
                        companies.append(canonical)
                    if ticker:
                        tickers.append(ticker)
                except Exception as e:
                    logger.warning(f"기업 정규화 실패 '{name}': {e}")
                    companies.append(name)

            companies_unique = self._remove_duplicates(companies)
            tickers_unique = self._remove_duplicates(tickers)

            companies_kw = [c.lower() for c in companies_unique]

            return {
                'raw': raw_names,
                'canonical': companies_unique,
                'keywords': companies_kw,
                'tickers': tickers_unique
            }
        except Exception as e:
            logger.error(f"기업 처리 오류 '{companies_str}': {e}")
            return {
                'raw': [],
                'canonical': [],
                'keywords': [],
                'tickers': []
            }

    def _remove_duplicates(self, items: List[str]) -> List[str]:
        seen = set()
        result = []
        for item in items:
            item_stripped = item.strip()
            if item_stripped and item_stripped not in seen:
                seen.add(item_stripped)
                result.append(item_stripped)
        return result

    def _extract_events(self, title: str) -> Dict[str, Any]:

        if self.use_ai_events:
            if not RUMERAPI_AVAILABLE:
                    logger.warning("AI 이벤트 요청되었으나 rumerapi 사용 불가, fallback 사용")
            else:
                try:
                    result = classify_event(title)

                    event_codes = result.labels if result.labels else []
                    event_labels = result.event_phrases if result.event_phrases else event_codes
                    confidence = result.confidence if result.confidence else 0.0

                    logger.debug(
                        f"AI 이벤트 추출: codes={event_codes}, "
                        f"phrases={event_labels}, conf={confidence:.2f}"
                    )

                    return {
                        'codes': event_codes,
                        'labels': event_labels,
                        'confidence': confidence,
                        'confidence_map': {},
                        'source': 'ai'
                    }

                except Exception as e:
                    logger.error(f"AI 이벤트 추출 실패: {e}, fallback 사용")

        try:
            event_codes, confidence_map = extract_events(title)
            event_labels = [EVENT_CODE2LABEL.get(code, code) for code in event_codes]
            max_confidence = max(confidence_map.values()) if confidence_map else None

            if event_codes:
                logger.debug(f"규칙 기반 이벤트: {event_codes} from '{title[:50]}...'")

            return {
                'codes': event_codes,
                'labels': event_labels,
                'confidence': max_confidence,
                'confidence_map': confidence_map,
                'source': 'rules'
            }
        except Exception as e:
            logger.error(f"이벤트 추출 오류 '{title[:50]}...': {e}")
            return {
                'codes': [],
                'labels': [],
                'confidence': None,
                'confidence_map': {},
                'source': 'error'
            }

    def _generate_embedding(self, title: str) -> Optional[List[float]]:
        if not self.use_embedding:
            return None

        try:
            embedding = embed_title(title, self.model_name)
            if embedding:
                logger.debug(f"임베딩 생성 완료 (차원={len(embedding)})")
            else:
                logger.warning("임베딩 생성 실패")
            return embedding
        except Exception as e:
            logger.error(f"임베딩 생성 오류 '{title[:50]}...': {e}")
            return None

    def _generate_doc_id(
            self,
            oid: Optional[str],
            aid: Optional[str],
            canonical_url: str,
            url: str,
            title: str,
            date_iso: Optional[str]
    ) -> str:
        try:
            if oid and aid:
                base_id = f"{oid}:{aid}"
            else:
                base_id = canonical_url or url or title

            base_id += "|" + (date_iso or "")
            doc_id = hashlib.blake2b(base_id.encode("utf-8"), digest_size=8).hexdigest()

            logger.debug(f"doc_id 생성: {doc_id}, 기준: {base_id[:50]}...")
            return doc_id
        except Exception as e:
            logger.error(f"문서 ID 생성 오류: {e}")
            fallback_id = hashlib.blake2b(
                f"{title}_{datetime.now().timestamp()}".encode("utf-8"),
                digest_size=8
            ).hexdigest()
            logger.warning(f"대체 문서 ID 사용: {fallback_id}")
            return fallback_id

    def _build_document(
            self,
            doc_id: str,
            url_data: Dict[str, Any],
            date_data: Dict[str, Any],
            title_data: Dict[str, Any],
            publisher_data: Dict[str, Any],
            company_data: Dict[str, Any],
            event_data: Dict[str, Any],
            category: str,
            embedding: Optional[List[float]]
    ) -> Dict[str, Any]:
        try:
            document = {
                "id": doc_id,
                "oid": url_data['oid'],
                "aid": url_data['aid'],
                "title": title_data['normalized'],
                "keyphrases": title_data['keyphrases'],
                "title_simhash": title_data['simhash'],
                "published_at": date_data['iso'],
                "published_at_mysql": date_data['mysql'],
                "publisher": publisher_data['name'],
                "publisher_tier": publisher_data['tier'],
                "category": category,
                "url": url_data['original'],
                "canonical_url": url_data['canonical'],
                "companies": company_data['canonical'],
                "companies_kw": company_data['keywords'],
                "companies_raw": company_data['raw'],
                "tickers": company_data['tickers'],
                "events": event_data['labels'],
                "event_codes": event_data['codes'],
            }

            if event_data['confidence'] is not None:
                document['event_conf'] = float(event_data['confidence'])

            if self.use_embedding and embedding is not None:
                document['embedding'] = embedding

            return document
        except Exception as e:
            logger.error(f"문서 빌드 오류: {e}")
            raise


class DocumentGenerator:

    def __init__(
            self,
            cols: Dict[str, str],
            use_embedding: bool,
            model_name: str,
            index: str,
            use_ai_events: bool = False
    ):
        self.cols = cols
        self.index = index
        self.preprocessor = NewsPreprocessor(use_embedding, model_name, use_ai_events)
        logger.info(f"문서 생성기 초기화: {index}")

    def generate(self, df):
        total_rows = len(df)
        success_count = 0
        error_count = 0

        for idx, row in df.fillna("").iterrows():
            try:
                doc = self.preprocessor.preprocess_row(row.to_dict(), self.cols)
                success_count += 1

                yield {
                    "_op_type": "index",
                    "_index": self.index,
                    "_id": doc["id"],
                    **doc
                }
            except Exception as e:
                error_count += 1
                logger.error(f"행 처리 실패 {idx}: {e}")
                logger.debug(f"행 데이터: {row.to_dict()}")
                continue

        logger.info(
            f"문서 생성 완료: "
            f"{success_count}/{total_rows} 성공, "
            f"{error_count} 오류"
        )


def preprocess_row(
        row: Dict[str, str],
        cols: Dict[str, str],
        use_embedding: bool,
        model_name: str,
        use_ai_events: bool = False
) -> Dict[str, Any]:
    try:
        preprocessor = NewsPreprocessor(use_embedding, model_name, use_ai_events)
        return preprocessor.preprocess_row(row, cols)
    except Exception as e:
        logger.error(f"preprocess_row wrapper 실패: {e}")
        raise


def docs_generator(
        df,
        cols: Dict[str, str],
        use_embedding: bool,
        model_name: str,
        index: str,
        use_ai_events: bool = False
):
    try:
        generator = DocumentGenerator(cols, use_embedding, model_name, index, use_ai_events)
        return generator.generate(df)
    except Exception as e:
        logger.error(f"docs_generator wrapper 실패: {e}")
        raise
