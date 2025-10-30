
from __future__ import annotations
import pandas as pd
import logging
from typing import Dict, Any, Generator
from datetime import datetime
from elasticsearch import helpers

from .es_client import create_es_client
from .index_schema import create_index, recreate_index
from .embedding import embedding_dim

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PreprocessedCSVLoader:
    """전처리된 CSV → Elasticsearch 직접 적재"""

    def __init__(
            self,
            csv_path: str,
            index_name: str,
            use_embedding: bool = False,
            embed_model: str = "",
            column_mapping: Dict[str, str] = None
    ):

        self.csv_path = csv_path
        self.index_name = index_name
        self.use_embedding = use_embedding
        self.embed_model = embed_model
        self.es = create_es_client()

        # 기본 컬럼 매핑 (전처리된 CSV 형식)
        self.column_mapping = column_mapping or {
            'id': 'id',
            'title': 'title',
            'published_at': 'published_at',
            'publisher': 'publisher',
            'publisher_tier': 'publisher_tier',
            'category': 'category',
            'url': 'url',
            'canonical_url': 'canonical_url',
            'stock_name': 'companies',  # CSV: stock_name → ES: companies
            'companies_kw': 'companies_kw',
            'tickers': 'tickers',
            'event_code': 'event_codes',  # CSV: event_code → ES: event_codes
            'events': 'events',
            'event_conf': 'event_conf',
            'keyphrases': 'keyphrases',
            'title_simhash': 'title_simhash',
            'embedding': 'embedding',
            'body': 'body'
        }

        logger.info(f"전처리된 CSV 로더 초기화 - {csv_path} → {index_name}")

    def prepare_index(self, recreate: bool = False):
        """인덱스 생성/재생성"""
        emb_dim = embedding_dim(self.embed_model) if self.use_embedding else 0

        if recreate:
            recreate_index(self.es, self.index_name)
            logger.info(f"인덱스 재생성: {self.index_name}")

        create_index(self.es, self.index_name, self.use_embedding, emb_dim)
        logger.info(f"인덱스 준비 완료: {self.index_name}")

    def parse_list_field(self, value: Any) -> list:

        if pd.isna(value) or value == '' or value is None:
            return []

        value_str = str(value).strip()

        # 1. Python 리스트 형식
        if value_str.startswith('[') and value_str.endswith(']'):
            try:
                import ast
                parsed = ast.literal_eval(value_str)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if x]
            except Exception:
                # 파싱 실패시 쉼표 분리로 폴백
                value_str = value_str[1:-1]  # [] 제거

        # 2. 쉼표 구분
        if ',' in value_str:
            return [x.strip().strip("'\"") for x in value_str.split(',') if x.strip()]

        # 3. 단일 값
        return [value_str] if value_str else []

    def parse_float_field(self, value: Any, default: float = 0.0) -> float:
        """float 필드 파싱"""
        if pd.isna(value) or value == '' or value is None:
            return default
        try:
            return float(value)
        except Exception:
            return default

    def parse_embedding_field(self, value: Any) -> list:
        """임베딩 벡터 파싱"""
        if not self.use_embedding:
            return None

        if pd.isna(value) or value == '' or value is None:
            return None

        try:
            import ast
            parsed = ast.literal_eval(str(value))
            if isinstance(parsed, list):
                return [float(x) for x in parsed]
        except Exception:
            return None

        return None

    def row_to_document(self, row: pd.Series) -> Dict[str, Any]:

        doc = {}

        # 필수 필드
        doc['id'] = str(row.get('id', ''))
        doc['title'] = str(row.get('title', ''))
        doc['published_at'] = str(row.get('published_at', ''))
        doc['publisher'] = str(row.get('publisher', ''))
        doc['url'] = str(row.get('url', ''))

        # 선택 필드
        if 'canonical_url' in row:
            doc['canonical_url'] = str(row.get('canonical_url', ''))

        if 'category' in row:
            doc['category'] = str(row.get('category', ''))

        if 'oid' in row:
            doc['oid'] = str(row.get('oid', ''))

        if 'aid' in row:
            doc['aid'] = str(row.get('aid', ''))

        # 숫자 필드
        doc['publisher_tier'] = self.parse_float_field(row.get('publisher_tier'), 0.5)

        if 'event_conf' in row:
            doc['event_conf'] = self.parse_float_field(row.get('event_conf'))

        # 리스트 필드
        doc['companies'] = self.parse_list_field(row.get('stock_name'))  # CSV: stock_name → ES: companies
        doc['companies_kw'] = self.parse_list_field(row.get('companies_kw'))
        doc['tickers'] = self.parse_list_field(row.get('tickers'))
        doc['event_codes'] = self.parse_list_field(row.get('event_code'))  # CSV: event_code → ES: event_codes
        doc['events'] = self.parse_list_field(row.get('events'))
        doc['keyphrases'] = self.parse_list_field(row.get('keyphrases'))

        # 해시 필드
        if 'title_simhash' in row:
            doc['title_simhash'] = str(row.get('title_simhash', ''))

        # 본문
        if 'body' in row:
            doc['body'] = str(row.get('body', ''))

        # 임베딩
        if self.use_embedding and 'embedding' in row:
            embedding = self.parse_embedding_field(row.get('embedding'))
            if embedding:
                doc['embedding'] = embedding

        return doc

    def generate_docs(self, chunk: pd.DataFrame) -> Generator[Dict[str, Any], None, None]:
        """문서 제너레이터"""
        for idx, row in chunk.iterrows():
            try:
                doc = self.row_to_document(row)

                yield {
                    "_op_type": "index",
                    "_index": self.index_name,
                    "_id": doc["id"],
                    **doc
                }
            except Exception as e:
                logger.error(f"Row {idx} 변환 실패: {e}")
                continue

    def load(
            self,
            chunk_size: int = 10000,
            recreate: bool = False,
            encoding: str = 'utf-8'
    ):

        logger.info("=" * 60)
        logger.info(f"전처리된 CSV → ES 적재 시작")
        logger.info(f"  - CSV: {self.csv_path}")
        logger.info(f"  - Index: {self.index_name}")
        logger.info(f"  - Chunk size: {chunk_size}")
        logger.info("=" * 60)

        # 인덱스 준비
        self.prepare_index(recreate=recreate)

        # 적재 시작
        success_count = 0
        error_count = 0
        start_time = datetime.now()

        try:
            # CSV 읽기 (청크 단위)
            for chunk_num, chunk in enumerate(
                    pd.read_csv(self.csv_path, chunksize=chunk_size, encoding=encoding),
                    start=1
            ):
                logger.info(f"청크 {chunk_num} 처리 중... ({len(chunk)}행)")

                # Bulk 인덱싱
                for ok, info in helpers.streaming_bulk(
                        self.es,
                        self.generate_docs(chunk),
                        chunk_size=1000,
                        raise_on_error=False
                ):
                    if ok:
                        success_count += 1
                    else:
                        error_count += 1
                        logger.error(f"인덱싱 실패: {info}")

                logger.info(f"청크 {chunk_num} 완료 - 성공: {success_count:,}건")

        except UnicodeDecodeError:
            # 인코딩 fallback
            logger.warning(f"인코딩 {encoding} 실패, 다른 인코딩 시도")
            for enc in ['cp949', 'euc-kr', 'utf-8-sig']:
                try:
                    logger.info(f"인코딩 {enc} 시도")
                    self.load(chunk_size=chunk_size, recreate=False, encoding=enc)
                    return
                except Exception:
                    continue

            raise Exception("모든 인코딩 시도 실패")

        # 결과 출력
        elapsed = (datetime.now() - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info(" 적재 완료")
        logger.info(f"  - 성공: {success_count:,}건")
        logger.info(f"  - 실패: {error_count:,}건")
        logger.info(f"  - 소요시간: {elapsed:.1f}초")
        logger.info(f"  - 속도: {success_count / elapsed:.1f}건/초")
        logger.info("=" * 60)


def main():
    """CLI 실행"""
    import argparse
    import os
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="전처리된 CSV → ES 직접 적재")

    parser.add_argument("--csv", required=True, help="전처리된 CSV 파일 경로")
    parser.add_argument("--index", required=True, help="ES 인덱스명")
    parser.add_argument("--chunk-size", type=int, default=10000, help="청크 크기")
    parser.add_argument("--recreate-index", action="store_true", help="인덱스 재생성")
    parser.add_argument("--use-embedding", action="store_true", help="임베딩 필드 포함")
    parser.add_argument("--embed-model", default="intfloat/multilingual-e5-large")
    parser.add_argument("--encoding", default="utf-8", help="CSV 인코딩")

    args = parser.parse_args()

    # Loader 생성
    loader = PreprocessedCSVLoader(
        csv_path=args.csv,
        index_name=args.index,
        use_embedding=args.use_embedding,
        embed_model=args.embed_model
    )

    # 적재 실행
    loader.load(
        chunk_size=args.chunk_size,
        recreate=args.recreate_index,
        encoding=args.encoding
    )


if __name__ == "__main__":
    main()
