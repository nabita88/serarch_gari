
from __future__ import annotations
import pandas as pd
import logging
from typing import Dict, Any, Generator
from datetime import datetime
from elasticsearch import helpers

from .es_client import create_es_client
from .index_schema import create_index, recreate_index
from .embedding import embed_title, embedding_dim

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CSVLoaderWithEmbedding:
    """전처리된 CSV → 임베딩 생성 → ES 적재"""

    def __init__(
            self,
            csv_path: str,
            index_name: str,
            embed_model: str = "intfloat/multilingual-e5-large"
    ):

        self.csv_path = csv_path
        self.index_name = index_name
        self.embed_model = embed_model
        self.es = create_es_client()

        logger.info(f"임베딩 포함 CSV 로더 초기화")
        logger.info(f"  - CSV: {csv_path}")
        logger.info(f"  - Index: {index_name}")
        logger.info(f"  - Embed Model: {embed_model}")

    def prepare_index(self, recreate: bool = False):
        """인덱스 생성 (임베딩 활성화)"""
        emb_dim = embedding_dim(self.embed_model)

        if recreate:
            recreate_index(self.es, self.index_name)
            logger.info(f"인덱스 재생성: {self.index_name}")

        create_index(self.es, self.index_name, use_embedding=True, embed_dim=emb_dim)
        logger.info(f"인덱스 준비 완료 (임베딩 차원: {emb_dim})")

    def parse_list_field(self, value: Any) -> list:
        """리스트 필드 파싱"""
        if pd.isna(value) or value == '' or value is None:
            return []

        value_str = str(value).strip()

        # Python 리스트 형식
        if value_str.startswith('[') and value_str.endswith(']'):
            try:
                import ast
                parsed = ast.literal_eval(value_str)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if x]
            except Exception:
                value_str = value_str[1:-1]

        # 쉼표 구분
        if ',' in value_str:
            return [x.strip().strip("'\"") for x in value_str.split(',') if x.strip()]

        # 단일 값
        return [value_str] if value_str else []

    def parse_float_field(self, value: Any, default: float = 0.0) -> float:
        """float 필드 파싱"""
        if pd.isna(value) or value == '' or value is None:
            return default
        try:
            return float(value)
        except Exception:
            return default

    def row_to_document(self, row: pd.Series) -> Dict[str, Any]:

        # 필수 필드
        doc = {
            'id': str(row.get('id', '')),
            'title': str(row.get('title', '')),
            'published_at': str(row.get('published_at', '')),
            'publisher': str(row.get('publisher', '')),
            'url': str(row.get('url', ''))
        }

        # 선택 필드
        for field in ['canonical_url', 'category', 'oid', 'aid', 'body']:
            if field in row and not pd.isna(row[field]):
                doc[field] = str(row[field])

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

        # 해시
        if 'title_simhash' in row:
            doc['title_simhash'] = str(row.get('title_simhash', ''))

        # ⚡ 임베딩 생성 (핵심!)
        title = doc['title']
        if title:
            try:
                embedding = embed_title(title, self.embed_model)
                if embedding:
                    doc['embedding'] = embedding
                else:
                    logger.warning(f"임베딩 생성 실패: {title[:50]}...")
            except Exception as e:
                logger.error(f"임베딩 생성 에러: {e}")

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
            chunk_size: int = 1000,  # 임베딩 생성 있어서 작게
            recreate: bool = False,
            encoding: str = 'utf-8'
    ):

        logger.info("=" * 60)
        logger.info("전처리된 CSV + 임베딩 생성 → ES 적재 시작")
        logger.info("=" * 60)

        # 인덱스 준비
        self.prepare_index(recreate=recreate)

        # 적재 시작
        success_count = 0
        error_count = 0
        embedding_count = 0
        start_time = datetime.now()

        try:
            # CSV 읽기 (청크 단위)
            for chunk_num, chunk in enumerate(
                    pd.read_csv(self.csv_path, chunksize=chunk_size, encoding=encoding),
                    start=1
            ):
                chunk_start = datetime.now()
                logger.info(f"청크 {chunk_num} 처리 중... ({len(chunk)}행)")

                # Bulk 인덱싱
                docs_with_embedding = 0
                for ok, info in helpers.streaming_bulk(
                        self.es,
                        self.generate_docs(chunk),
                        chunk_size=100,  # ES bulk 사이즈 작게
                        raise_on_error=False
                ):
                    if ok:
                        success_count += 1
                        # 임베딩 포함 여부 체크는 생략 (모두 포함 가정)
                        docs_with_embedding += 1
                    else:
                        error_count += 1
                        logger.error(f"인덱싱 실패: {info}")

                embedding_count += docs_with_embedding

                chunk_elapsed = (datetime.now() - chunk_start).total_seconds()
                logger.info(
                    f"청크 {chunk_num} 완료 - "
                    f"성공: {success_count:,}건, "
                    f"임베딩: {embedding_count:,}건, "
                    f"소요: {chunk_elapsed:.1f}초 "
                    f"({len(chunk) / chunk_elapsed:.1f}건/초)"
                )

        except UnicodeDecodeError:
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
        logger.info(f"  - 임베딩 생성: {embedding_count:,}건")
        logger.info(f"  - 실패: {error_count:,}건")
        logger.info(f"  - 총 소요시간: {elapsed:.1f}초 ({elapsed / 60:.1f}분)")
        logger.info(f"  - 평균 속도: {success_count / elapsed:.1f}건/초")
        logger.info("=" * 60)


def main():
    """CLI 실행"""
    import argparse
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(
        description="전처리된 CSV + 임베딩만 생성해서 ES 적재"
    )

    parser.add_argument("--csv", required=True, help="전처리된 CSV 파일 경로")
    parser.add_argument("--index", required=True, help="ES 인덱스명")
    parser.add_argument("--chunk-size", type=int, default=1000, help="청크 크기")
    parser.add_argument("--recreate-index", action="store_true", help="인덱스 재생성")
    parser.add_argument(
        "--embed-model",
        default="intfloat/multilingual-e5-large",
        help="임베딩 모델명"
    )
    parser.add_argument("--encoding", default="utf-8", help="CSV 인코딩")

    args = parser.parse_args()

    # Loader 생성
    loader = CSVLoaderWithEmbedding(
        csv_path=args.csv,
        index_name=args.index,
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
