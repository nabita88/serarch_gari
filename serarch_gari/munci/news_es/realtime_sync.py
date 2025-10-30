
from __future__ import annotations
import pymysql
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from .sync_from_db import MariaDBToElasticsearchSyncer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RealtimeSyncer:


    def __init__(
            self,
            db_config: Dict[str, Any],
            es_index: str,
            poll_interval: int = 60,
            lookback_minutes: int = 5
    ):

        self.db_config = db_config
        self.es_index = es_index
        self.poll_interval = poll_interval
        self.lookback_minutes = lookback_minutes

        self.syncer = MariaDBToElasticsearchSyncer(
            db_config=db_config,
            es_index=es_index,
            use_embedding=False,  # 실시간은 빠르게
            use_ai_events=False
        )

        # 마지막 동기화 시점
        self.last_sync_time: Optional[datetime] = None

        logger.info(f"RealtimeSyncer initialized")
        logger.info(f"  - Poll interval: {poll_interval}초")
        logger.info(f"  - Lookback: {lookback_minutes}분")

    def get_changed_news_ids(self) -> list:

        conn = pymysql.connect(**self.db_config)

        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 마지막 동기화 시점 계산
                if self.last_sync_time:
                    since = self.last_sync_time
                else:
                    # 처음 실행시 lookback 적용
                    since = datetime.now() - timedelta(minutes=self.lookback_minutes)

                # 변경된 뉴스 조회
                sql = """
                    SELECT id
                    FROM news_articles
                    WHERE updated_at >= %s OR created_at >= %s
                    ORDER BY updated_at DESC
                """

                cursor.execute(sql, (since, since))
                rows = cursor.fetchall()

                return [row['id'] for row in rows]

        except Exception as e:
            logger.error(f"변경 사항 조회 실패: {e}", exc_info=True)
            return []

        finally:
            conn.close()

    def sync_by_ids(self, news_ids: list):

        if not news_ids:
            return

        conn = pymysql.connect(**self.db_config)

        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # ID로 뉴스 조회
                placeholders = ','.join(['%s'] * len(news_ids))
                sql = f"""
                    SELECT 
                        id, title, published_at, publisher,
                        category, url, stock_name, body
                    FROM news_articles
                    WHERE id IN ({placeholders})
                """

                cursor.execute(sql, news_ids)
                rows = cursor.fetchall()

                # ES에 인덱싱
                from elasticsearch import helpers

                def doc_generator():
                    for row in rows:
                        try:
                            doc = self.syncer.transform_row_to_doc(row)
                            yield {
                                "_op_type": "index",
                                "_index": self.es_index,
                                "_id": doc["id"],
                                **doc
                            }
                        except Exception as e:
                            logger.error(f"문서 변환 실패 (ID: {row.get('id')}): {e}")
                            continue

                # Bulk 인덱싱
                success, failed = helpers.bulk(
                    self.syncer.es,
                    doc_generator(),
                    chunk_size=100,
                    raise_on_error=False
                )

                logger.info(f"동기화 완료: 성공 {success}건, 실패 {len(failed)}건")

        except Exception as e:
            logger.error(f"ID 기반 동기화 실패: {e}", exc_info=True)

        finally:
            conn.close()

    def run(self):
        """실시간 동기화 시작 (무한 루프)"""
        logger.info("=" * 60)
        logger.info(" 실시간 동기화 시작")
        logger.info("=" * 60)

        try:
            while True:
                loop_start = time.time()

                # 1. 변경된 뉴스 조회
                changed_ids = self.get_changed_news_ids()

                if changed_ids:
                    logger.info(f" 변경 감지: {len(changed_ids)}건")

                    # 2. 동기화
                    self.sync_by_ids(changed_ids)

                    # 3. 마지막 동기화 시점 업데이트
                    self.last_sync_time = datetime.now()

                else:
                    logger.info(" 변경 없음")

                # 4. 다음 폴링까지 대기
                elapsed = time.time() - loop_start
                sleep_time = max(0, self.poll_interval - elapsed)

                if sleep_time > 0:
                    logger.info(f"💤 {sleep_time:.1f}초 대기 중...")
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("\n  사용자 중단 (Ctrl+C)")

        except Exception as e:
            logger.error(f" 실시간 동기화 에러: {e}", exc_info=True)
            raise

        finally:
            logger.info("=" * 60)
            logger.info(" 실시간 동기화 종료")
            logger.info("=" * 60)


def main():
    """CLI 실행"""
    import argparse
    import os
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="MariaDB → ES 실시간 동기화")

    parser.add_argument("--index", required=True, help="ES 인덱스명")
    parser.add_argument("--poll-interval", type=int, default=60, help="폴링 주기 (초)")
    parser.add_argument("--lookback-minutes", type=int, default=5, help="역방향 조회 시간 (분)")

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

    # Syncer 생성 및 실행
    syncer = RealtimeSyncer(
        db_config=db_config,
        es_index=args.index,
        poll_interval=args.poll_interval,
        lookback_minutes=args.lookback_minutes
    )

    syncer.run()


if __name__ == "__main__":
    main()
