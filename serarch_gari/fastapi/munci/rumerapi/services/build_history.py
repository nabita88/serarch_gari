
from __future__ import annotations
from typing import Optional, Dict, List, Tuple
import pymysql
import logging
from datetime import datetime
from dataclasses import dataclass

from munci.signal_gap.core.event_price_mapper import EventPriceMapper
from munci.signal_gap.core.return_calculator import ReturnCalculator
from munci.lastsa.event_extractor import StockEventLabelClassifier
from munci.rumerapi.utils.date_utils import to_yyyymmdd, from_db_date

logger = logging.getLogger(__name__)


@dataclass
class ProcessingStats:
    """처리 통계"""
    total_processed: int = 0
    total_saved: int = 0
    ai_classified_count: int = 0
    ai_other_count: int = 0
    no_summary_count: int = 0
    no_stock_code_count: int = 0
    no_anchor_count: int = 0
    no_return_count: int = 0


class EventReturnsHistoryBuilder:
    """이벤트 수익률 이력 구축 클래스"""

    def __init__(self, db_config: dict):

        self.db_config = db_config
        self.classifier = None
        self.mapper = None
        self.calculator = None
        self.conn = None
        self.stats = ProcessingStats()

    def initialize_components(self):
        """구성 요소 초기화"""
        try:
            self.classifier = StockEventLabelClassifier()
            logger.info("AI 분류기 초기화 완료")
        except Exception as e:
            logger.error(f"AI 분류기 초기화 실패: {e}")
            raise

        self.mapper = EventPriceMapper(self.db_config)
        self.calculator = ReturnCalculator(self.db_config)
        self.conn = pymysql.connect(**self.db_config)

    def cleanup(self):
        """리소스 정리"""
        if self.conn:
            self.conn.close()

    def fetch_events(self, start_date: str, end_date: str) -> List[Dict]:

        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                  SELECT corp_code,
                         rcept_dt as event_date,
                         report_nm,
                         summary,
                         corp_name
                  FROM rumors_opendart
                  WHERE rcept_dt BETWEEN %s AND %s
                  ORDER BY rcept_dt
                  """
            cursor.execute(sql, (start_date, end_date))
            events = cursor.fetchall()
            
            # DB에서 가져온 날짜를 YYYYMMDD로 통일
            for event in events:
                event['event_date'] = to_yyyymmdd(event['event_date'])

        logger.info(f"총 {len(events)}건의 이벤트 발견")
        return events

    def classify_event(self, event: Dict) -> Optional[str]:

        # summary 체크
        if not event.get('summary'):
            self.stats.no_summary_count += 1
            logger.debug(f"Summary 없음: {event['corp_name']} - {event['report_nm']}")
            return None

        # AI 분류
        try:
            result = self.classifier.classify_event(
                title=event['summary']
            )

            # 분류 결과 확인
            if not result.labels or result.labels[0] == "other":
                self.stats.ai_other_count += 1
                logger.debug(
                    f"AI 분류 불가(other): {event['corp_name']} - "
                    f"신뢰도: {result.confidence:.2f}"
                )
                return None

            event_code = result.labels[0]
            self.stats.ai_classified_count += 1

            logger.debug(
                f"AI 분류: {event['corp_name']} - "
                f"{event_code} (신뢰도: {result.confidence:.2f})"
            )

            return event_code

        except Exception as e:
            logger.error(f"AI 분류 실패: {event['corp_name']} - {e}")
            return None

    def get_stock_code(self, corp_code: str) -> Optional[str]:

        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT stock_code FROM stock_list WHERE corp_code = %s",
                (corp_code,)
            )
            row = cursor.fetchone()

        if not row:
            self.stats.no_stock_code_count += 1
            logger.debug(f"종목코드 없음: {corp_code}")
            return None

        return row['stock_code']

    def calculate_returns(self, stock_code: str, event_date: str) -> Optional[Tuple]:

        # 앵커 가격 조회 (YYYYMMDD 형식 그대로 사용)
        anchor = self.mapper.get_anchor_price(stock_code, event_date)
        if not anchor:
            self.stats.no_anchor_count += 1
            logger.debug(f"앵커 없음: {stock_code} @ {event_date}")
            return None

        # 수익률 계산
        returns = self.calculator.calculate_returns(
            stock_code,
            anchor.anchor_date,
            anchor.anchor_close,
            horizons=[1, 3, 5]
        )

        # 수익률 체크
        if all(v is None for v in returns.horizons.values()):
            self.stats.no_return_count += 1
            logger.debug(f"수익률 없음: {stock_code}")
            return None

        return anchor, returns

    def save_to_database(self, stock_code: str, event_date: str,
                        event_code: str, anchor, returns) -> bool:


        try:
            with self.conn.cursor() as cursor:
                insert_sql = """
                    INSERT INTO event_returns_history
                    (stock_code, event_date, event_code, anchor_date,
                     anchor_price, return_1d, return_3d, return_5d,
                     volume, market_cap, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        anchor_date = VALUES(anchor_date),
                        anchor_price = VALUES(anchor_price),
                        return_1d = VALUES(return_1d),
                        return_3d = VALUES(return_3d),
                        return_5d = VALUES(return_5d),
                        volume = VALUES(volume),
                        market_cap = VALUES(market_cap),
                        updated_at = NOW()
                """
                cursor.execute(insert_sql, (
                    stock_code,
                    event_date,  # YYYYMMDD 그대로 사용
                    event_code,
                    anchor.anchor_date,
                    anchor.anchor_close,
                    returns.horizons.get(1),
                    returns.horizons.get(3),
                    returns.horizons.get(5),
                    anchor.volume,
                    anchor.market_cap
                ))

            self.stats.total_saved += 1
            return True

        except Exception as e:
            logger.error(f"DB 저장 실패: {e}")
            return False

    def process_single_event(self, event: Dict) -> bool:

        # 1. AI 분류
        event_code = self.classify_event(event)
        if not event_code:
            return False

        # 2. 종목코드 조회
        stock_code = self.get_stock_code(event['corp_code'])
        if not stock_code:
            return False

        # 3. 수익률 계산
        result = self.calculate_returns(stock_code, event['event_date'])
        if not result:
            return False

        anchor, returns = result

        # 4. DB 저장
        saved = self.save_to_database(
            stock_code,
            event['event_date'],
            event_code,
            anchor,
            returns
        )

        return saved

    def log_progress(self, idx: int, total: int):
        """진행 상황 로그"""
        if idx % 100 == 0:
            progress_pct = idx / total * 100
            logger.info(
                f"진행: {idx}/{total} ({progress_pct:.1f}%), "
                f"저장: {self.stats.total_saved}건, "
                f"AI분류: {self.stats.ai_classified_count}건"
            )

    def log_final_stats(self):
        """최종 통계 로그"""
        stats = self.stats

        logger.info("=" * 60)
        logger.info(" AI 기반 수익률 DB 구축 완료")
        logger.info(f"   - 전체 처리: {stats.total_processed}건")
        logger.info(f"   - 저장 완료: {stats.total_saved}건")

        if stats.total_processed > 0:
            save_rate = stats.total_saved / stats.total_processed * 100
            logger.info(f"   - 저장률: {save_rate:.1f}%")

        logger.info("")
        logger.info(" AI 분류 통계:")
        logger.info(f"   - 분류 성공: {stats.ai_classified_count}건")
        logger.info(f"   - 분류 불가(other): {stats.ai_other_count}건")
        logger.info(f"   - Summary 없음: {stats.no_summary_count}건")

        if stats.ai_classified_count + stats.ai_other_count > 0:
            success_rate = stats.ai_classified_count / (stats.ai_classified_count + stats.ai_other_count) * 100
            logger.info(f"   - AI 분류 성공률: {success_rate:.1f}%")

        logger.info("")
        logger.info(" 스킵 사유:")
        logger.info(f"   - Summary 없음: {stats.no_summary_count}건")
        logger.info(f"   - AI other 분류: {stats.ai_other_count}건")
        logger.info(f"   - 종목코드 없음: {stats.no_stock_code_count}건")
        logger.info(f"   - 앵커 가격 없음: {stats.no_anchor_count}건")
        logger.info(f"   - 수익률 계산 불가: {stats.no_return_count}건")
        logger.info("=" * 60)

    def build(self, start_date: str, end_date: str, batch_size: int = 10):

        logger.info(f"AI 기반 수익률 DB 구축 시작: {start_date} ~ {end_date}")

        try:
            # 초기화
            self.initialize_components()

            # 이벤트 조회
            events = self.fetch_events(start_date, end_date)

            # 각 이벤트 처리
            for idx, event in enumerate(events, 1):
                self.stats.total_processed += 1

                # 진행 상황 로그
                self.log_progress(idx, len(events))

                try:
                    # 단일 이벤트 처리
                    self.process_single_event(event)

                    # 배치 커밋
                    # 배치 커밋 (저장 성공한 건수 기준)
                    if self.stats.total_saved > 0 and self.stats.total_saved % batch_size == 0:
                        self.conn.commit()
                        logger.info(f"DB 커밋: {self.stats.total_saved}건 저장됨")

                except Exception as e:
                    logger.error(
                        f"이벤트 처리 실패: {event.get('corp_name', 'Unknown')} "
                        f"@ {event.get('event_date', 'Unknown')}: {e}"
                    )
                    continue

            # 최종 커밋
            self.conn.commit()

            # 통계 출력
            self.log_final_stats()

        except Exception as e:
            logger.error(f"배치 작업 실패: {e}", exc_info=True)
            if self.conn:
                self.conn.rollback()
            raise

        finally:
            self.cleanup()


def build_event_returns_history(
    db_config: dict,
    start_date: str = "20200101",
    end_date: str = "20241231",
    batch_size: int = 10
):

    builder = EventReturnsHistoryBuilder(db_config)
    builder.build(start_date, end_date, batch_size)


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 환경 변수 로드
    load_dotenv()

    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'user': os.getenv('DB_USERNAME'),
        'password': os.getenv('DB_PASSWORD'),
        'database': os.getenv('DB_DATABASE'),
        'port': int(os.getenv('DB_PORT', 3306))
    }

    # 실행
    build_event_returns_history(
        db_config,
        start_date="20240101",  # 최근 2년
        end_date="20251013"
    )