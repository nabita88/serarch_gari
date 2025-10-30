"""
MariaDB → Elasticsearch 동기화

MariaDB에서 뉴스 데이터를 읽어 Elasticsearch에 인덱싱
"""
from __future__ import annotations
import pymysql
import logging
from typing import Dict, Any, Generator
from datetime import datetime
from elasticsearch import helpers

from .es_client import create_es_client
from .index_schema import create_index
from .preprocess import NewsPreprocessor
from .config import KST

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MariaDBToElasticsearchSyncer:
    """MariaDB → Elasticsearch 동기화"""

    def __init__(
            self,
            db_config: Dict[str, Any],
            es_index: str,
            use_embedding: bool = False,
            embed_model: str = "",
            use_ai_events: bool = False
    ):

        self.db_config = db_config
        self.es_index = es_index
        self.es = create_es_client()
        self.preprocessor = NewsPreprocessor(use_embedding, embed_model, use_ai_events)

        logger.info(f"동기화 도구 초기화 - index: {es_index}")

    def fetch_news_from_db(
            self,
            start_date: str = None,
            end_date: str = None,
            batch_size: int = 1000,
            offset: int = 0
    ) -> Generator[Dict[str, Any], None, None]:

        conn = pymysql.connect(**self.db_config)

        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # SQL 쿼리 구성
                where_clauses = []
                params = []

                if start_date:
                    where_clauses.append("published_at >= %s")
                    params.append(start_date)

                if end_date:
                    where_clauses.append("published_at <= %s")
                    params.append(end_date)

                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

                # 전체 개수 조회
                count_sql = f"SELECT COUNT(*) as total FROM news_articles {where_sql}"
                cursor.execute(count_sql, params)
                total = cursor.fetchone()['total']
                logger.info(f"총 {total:,}건의 뉴스 조회 예정")

                # 배치 단위로 조회
                current_offset = offset
                processed = 0

                while True:
                    sql = f"""
                        SELECT 
                            id,
                            title,
                            published_at,
                            publisher,
                            category,
                            url,
                            stock_name,
                            body
                        FROM news_articles
                        {where_sql}
                        ORDER BY published_at DESC
                        LIMIT %s OFFSET %s
                    """

                    cursor.execute(sql, params + [batch_size, current_offset])
                    rows = cursor.fetchall()

                    if not rows:
                        break

                    for row in rows:
                        processed += 1
                        yield row

                    current_offset += batch_size

                    # 진행률 출력
                    logger.info(
                        f"진행: {processed:,}/{total:,} "
                        f"({processed / total * 100:.1f}%)"
                    )

        except Exception as e:
            logger.error(f"DB 조회 실패: {e}", exc_info=True)
            raise

        finally:
            conn.close()

    def transform_row_to_doc(self, row: Dict[str, Any]) -> Dict[str, Any]:

        # preprocess.py의 로직 재사용
        cols = {
            "date": "published_at",
            "category": "category",
            "title": "title",
            "publisher": "publisher",
            "url": "url",
            "companies": "stock_name"  # DB: stock_name → ES: companies
        }

        # 날짜 형식 변환 (MySQL datetime → ISO)
        if isinstance(row['published_at'], datetime):
            row['published_at'] = row['published_at'].astimezone(KST).isoformat()
        elif isinstance(row['published_at'], str):
            # 문자열인 경우 그대로 사용
            pass

        # body 필드 추가 (preprocess.py에 없는 경우)
        if 'body' in row and row['body']:
            # body는 별도 처리하지 않고 그대로 저장
            pass

        doc = self.preprocessor.preprocess_row(row, cols)

        # body 추가 (있는 경우)
        if 'body' in row and row['body']:
            doc['body'] = row['body'][:5000]  # 최대 5000자

        return doc

    def sync(
            self,
            start_date: str = None,
            end_date: str = None,
            batch_size: int = 1000,
            recreate_index: bool = False
    ):

        logger.info("=" * 60)
        logger.info("MariaDB → Elasticsearch 동기화 시작")
        logger.info(f"  - Index: {self.es_index}")
        logger.info(f"  - Period: {start_date or 'ALL'} ~ {end_date or 'NOW'}")
        logger.info(f"  - Batch size: {batch_size}")
        logger.info("=" * 60)

        # 인덱스 생성
        from .embedding import embedding_dim
        emb_dim = embedding_dim(self.preprocessor.model_name) if self.preprocessor.use_embedding else 0

        if recreate_index:
            from .index_schema import recreate_index as recreate
            recreate(self.es, self.es_index)
            logger.info("인덱스 재생성 완료")

        create_index(self.es, self.es_index, self.preprocessor.use_embedding, emb_dim)
        logger.info("인덱스 준비 완료")

        # 동기화 실행
        success_count = 0
        error_count = 0
        start_time = datetime.now()

        def doc_generator():
            nonlocal success_count, error_count

            for row in self.fetch_news_from_db(start_date, end_date, batch_size):
                try:
                    doc = self.transform_row_to_doc(row)
                    success_count += 1

                    yield {
                        "_op_type": "index",
                        "_index": self.es_index,
                        "_id": doc["id"],
                        **doc
                    }

                except Exception as e:
                    error_count += 1
                    logger.error(f"문서 변환 실패 (ID: {row.get('id')}): {e}")
                    continue

        # Bulk 인덱싱
        try:
            for ok, info in helpers.streaming_bulk(
                    self.es,
                    doc_generator(),
                    chunk_size=1000,
                    raise_on_error=False
            ):
                if not ok:
                    error_count += 1
                    logger.error(f"ES 인덱싱 실패: {info}")

        except Exception as e:
            logger.error(f"Bulk 인덱싱 에러: {e}", exc_info=True)
            raise

        # 결과 출력
        elapsed = (datetime.now() - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info(" 동기화 완료")
        logger.info(f"  - 성공: {success_count:,}건")
        logger.info(f"  - 실패: {error_count:,}건")
        logger.info(f"  - 소요시간: {elapsed:.1f}초")
        logger.info(f"  - 속도: {success_count / elapsed:.1f}건/초")
        logger.info("=" * 60)

    def sync_incremental(
            self,
            since_minutes: int = 60,
            batch_size: int = 100
    ):

        from datetime import timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(minutes=since_minutes)

        logger.info(f"증분 동기화: 최근 {since_minutes}분")

        self.sync(
            start_date=start_date.strftime("%Y-%m-%d %H:%M:%S"),
            end_date=end_date.strftime("%Y-%m-%d %H:%M:%S"),
            batch_size=batch_size,
            recreate_index=False
        )


def main():
    """CLI 실행"""
    import argparse
    import os
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="MariaDB → Elasticsearch 동기화")

    parser.add_argument("--index", required=True, help="ES 인덱스명")
    parser.add_argument("--start-date", help="시작일 (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="종료일 (YYYY-MM-DD)")
    parser.add_argument("--batch-size", type=int, default=1000, help="배치 크기")
    parser.add_argument("--recreate-index", action="store_true", help="인덱스 재생성")
    parser.add_argument("--use-embedding", action="store_true", help="임베딩 사용")
    parser.add_argument("--embed-model", default="intfloat/multilingual-e5-large")
    parser.add_argument("--use-ai-events", action="store_true", help="AI 이벤트 추출")
    parser.add_argument("--incremental", action="store_true", help="증분 동기화 (최근 1시간)")

    args = parser.parse_args()

    # DB 설정
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'user': os.getenv('DB_USERNAME'),
        'password': os.getenv('DB_PASSWORD'),
        'database': os.getenv('DB_DATABASE'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'charset': 'utf8mb4'
    }

    # Syncer 생성
    syncer = MariaDBToElasticsearchSyncer(
        db_config=db_config,
        es_index=args.index,
        use_embedding=args.use_embedding,
        embed_model=args.embed_model,
        use_ai_events=args.use_ai_events
    )

    # 동기화 실행
    if args.incremental:
        syncer.sync_incremental(since_minutes=60, batch_size=args.batch_size)
    else:
        syncer.sync(
            start_date=args.start_date,
            end_date=args.end_date,
            batch_size=args.batch_size,
            recreate_index=args.recreate_index
        )


if __name__ == "__main__":
    main()
