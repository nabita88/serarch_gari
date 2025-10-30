from __future__ import annotations
import pymysql
from datetime import datetime, timedelta
import math
import logging
import json
from pathlib import Path

from munci.rumerapi.core.config import settings

logger = logging.getLogger(__name__)


class NewsGapScanner:
    """뉴스 괴리 스캐너"""

    def __init__(self, z_threshold: float = 2.0, min_samples: int = 10):
        self.z_threshold = z_threshold
        self.min_samples = min_samples

        # 종목코드 매핑 로드
        self.stock_code_map = self._load_stock_code_map()

        # DB 설정
        if all([settings.db_host, settings.db_username, settings.db_password, settings.db_database]):
            self.db_config = {
                'host': settings.db_host,
                'user': settings.db_username,
                'password': settings.db_password,
                'database': settings.db_database,
                'port': settings.db_port
            }
        else:
            self.db_config = None
            logger.warning("DB 설정 없음 - Gap 스캔 불가")

    def _load_stock_code_map(self) -> dict:
        """normalized_aliases.json에서 종목명 -> 종목코드 매핑 로드"""
        project_root = Path(__file__).parent.parent.parent.parent
        json_path = project_root / "examples" / "normalized_aliases.json"

        logger.info(f"종목코드 매핑 파일 경로: {json_path}")
        logger.info(f"파일 존재 여부: {json_path.exists()}")

        if not json_path.exists():
            logger.warning(f"종목코드 매핑 파일 없음: {json_path}")
            return {}

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        stock_map = {}
        for main_name, aliases in data.items():
            if not aliases or len(aliases) == 0:
                continue

            stock_code = None
            for alias in aliases:
                if alias.isdigit():
                    stock_code = alias
                    break

            if not stock_code:
                continue

            stock_map[main_name] = stock_code

            for alias in aliases:
                if not alias.isdigit():
                    stock_map[alias] = stock_code

        logger.info(f"종목코드 매핑 로드 완료: {len(stock_map)}개")
        return stock_map

    def build_history(self, start_date: str, end_date: str, batch_size: int = 1000):
        """과거 뉴스의 수익률 이력 구축"""
        if not self.db_config:
            raise ValueError("DB 설정이 필요합니다")

        logger.info(f"{'=' * 60}")
        logger.info(f"뉴스 수익률 DB 구축: {start_date} ~ {end_date}")
        logger.info(f"{'=' * 60}")

        conn = pymysql.connect(**self.db_config)

        try:
            # 테이블 및 스키마 확인
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES LIKE 'news_returns'")
                if not cursor.fetchone():
                    logger.error("news_returns 테이블이 존재하지 않습니다!")
                    return

                cursor.execute("DESCRIBE news_returns")
                columns = cursor.fetchall()
                for col in columns:
                    if col[0] == 'news_date':
                        logger.info(f"news_date 컬럼 타입: {col[1]}")
                        if 'date' not in col[1].lower():
                            logger.warning(f"news_date 컬럼 타입 수정: {col[1]} -> DATE")
                            cursor.execute("ALTER TABLE news_returns MODIFY COLUMN news_date DATE NOT NULL")
                            conn.commit()
                            logger.info("news_date 컬럼을 DATE 타입으로 변경 완료")
                        break

            logger.info(" DB 테이블 확인 완료")

            # 날짜 형식 변환 (YYYYMMDD -> date 객체)
            start_date_obj = datetime.strptime(start_date, '%Y%m%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y%m%d').date()

            # 뉴스 조회
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("""
                               SELECT url        as news_id,
                                      stock_name as companies,
                                      event_code as event_code,
                                      date       as news_date
                               FROM comprehensive_analyzed_news
                               WHERE date BETWEEN %s AND %s
                                 AND stock_name IS NOT NULL
                                 AND event_code IS NOT NULL
                               """, (start_date_obj, end_date_obj))

                news_list = cursor.fetchall()
                logger.info(f"뉴스 {len(news_list)}건 발견")

                if not news_list:
                    logger.warning("조건에 맞는 뉴스가 없습니다!")
                    return

            # 가격 데이터 캐싱
            logger.info("가격 데이터 로딩 중...")
            price_cache = self._load_price_cache(conn, start_date_obj, end_date_obj)
            logger.info(f" 가격 캐시 로드 완료: {len(price_cache)}개 종목")

            saved = 0
            processed = 0
            batch_data = []

            for news in news_list:
                processed += 1

                try:
                    news_id = news['news_id']
                    companies = news.get('companies', '')
                    event_code_list = news.get('event_code', '')
                    news_date = news['news_date']  # DATE 객체 그대로 사용

                    if not companies or not event_code_list:
                        continue

                    company_list = [c.strip() for c in str(companies).split(',') if c.strip()]
                    event_list = [e.strip() for e in str(event_code_list).split(',')
                                  if e.strip() and e.strip().lower() != 'other']

                    if not event_list:
                        continue

                    for company_name in company_list:
                        stock_code = self.stock_code_map.get(company_name)
                        if not stock_code:
                            continue

                        for event in event_list:
                            result = self._calculate_return(stock_code, news_date, price_cache)
                            if result:
                                batch_data.append((
                                    news_id, stock_code, company_name, event, news_date,
                                    result['anchor_price'], result['r1'], result['r3'], result['r5']
                                ))
                                saved += 1

                except Exception as e:
                    logger.error(f"뉴스 처리 실패: {e}")
                    continue

                # 배치 저장
                if len(batch_data) >= batch_size:
                    self._batch_insert(conn, batch_data)
                    batch_data = []
                    logger.info(f"진행: {processed}/{len(news_list)}건 처리, {saved}건 저장")

            # 남은 데이터 저장
            if batch_data:
                self._batch_insert(conn, batch_data)

            conn.commit()
            logger.info(f"{'=' * 60}")
            logger.info(f" 완료: 처리 {processed}건, 저장 {saved}건")
            logger.info(f"{'=' * 60}")

        except Exception as e:
            logger.exception(f" build_history 실패: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def _load_price_cache(self, conn, start_date, end_date) -> dict:
        """가격 데이터를 메모리에 캐싱 (date 객체 사용)"""
        cache = {}

        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                           SELECT stock_code, trade_date, close_price
                           FROM stock_daily_prices
                           WHERE trade_date BETWEEN DATE_SUB(%s, INTERVAL 5 DAY)
                                     AND DATE_ADD(%s, INTERVAL 5 DAY)
                           ORDER BY stock_code, trade_date
                           """, (start_date, end_date))

            for row in cursor:
                stock_code = row['stock_code']
                date = row['trade_date']
                
                # trade_date를 date 객체로 변환 (안전 장치)
                if isinstance(date, str):
                    if len(date) == 10:  # YYYY-MM-DD
                        date = datetime.strptime(date, '%Y-%m-%d').date()
                    elif len(date) == 8:  # YYYYMMDD
                        date = datetime.strptime(date, '%Y%m%d').date()
                    else:
                        continue
                elif isinstance(date, datetime):
                    date = date.date()
                # 이미 date 객체면 그대로 사용
                
                price = float(row['close_price'])

                if stock_code not in cache:
                    cache[stock_code] = []
                cache[stock_code].append((date, price))

        return cache

    def _calculate_return(self, stock_code: str, news_date, price_cache: dict) -> dict | None:
        """캐시된 데이터로 수익률 계산 (date 객체 사용)"""
        if stock_code not in price_cache:
            return None

        prices = price_cache[stock_code]

        # news_date를 date 객체로 변환 (안전 장치)
        if isinstance(news_date, str):
            if len(news_date) == 10:  # YYYY-MM-DD
                news_date = datetime.strptime(news_date, '%Y-%m-%d').date()
            elif len(news_date) == 8:  # YYYYMMDD
                news_date = datetime.strptime(news_date, '%Y%m%d').date()
            else:
                return None
        elif isinstance(news_date, datetime):
            news_date = news_date.date()
        # 이미 date 객체면 그대로 사용

        # 앵커 가격 찾기 (뉴스 날짜 이후 첫 거래일)
        anchor_idx = None
        for idx, (date, price) in enumerate(prices):
            if date >= news_date:
                anchor_idx = idx
                break

        if anchor_idx is None:
            return None

        anchor_date, anchor_price = prices[anchor_idx]

        # 1일 후 = 앵커 다음 거래일
        # 3일 후 = 앵커로부터 3거래일 후
        # 5일 후 = 앵커로부터 5거래일 후
        r1 = None
        r3 = None
        r5 = None

        if anchor_idx + 1 < len(prices):
            price_1d = prices[anchor_idx + 1][1]
            r1 = math.log(price_1d / anchor_price)

        if anchor_idx + 3 < len(prices):
            price_3d = prices[anchor_idx + 3][1]
            r3 = math.log(price_3d / anchor_price)

        if anchor_idx + 5 < len(prices):
            price_5d = prices[anchor_idx + 5][1]
            r5 = math.log(price_5d / anchor_price)

        return {
            'anchor_price': anchor_price,
            'r1': r1,
            'r3': r3,
            'r5': r5
        }

    def _batch_insert(self, conn, batch_data: list):
        """배치 INSERT"""
        if not batch_data:
            return

        with conn.cursor() as cursor:
            cursor.executemany("""
                               INSERT INTO news_returns
                               (news_id, stock_code, stock_name, event_code, news_date, anchor_price, return_1d, return_3d, return_5d)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY
                               UPDATE
                                   return_1d = VALUES(return_1d), 
                                   return_3d = VALUES(return_3d),
                                   return_5d = VALUES(return_5d)
                               """, batch_data)
        conn.commit()

    def scan_recent(self, hours: int = 48):
        """최근 N시간 뉴스의 괴리 탐지"""
        if not self.db_config:
            raise ValueError("DB 설정이 필요합니다")

        logger.info(f"{'=' * 60}")
        logger.info(f"최근 {hours}시간 뉴스 괴리 스캔")
        logger.info(f"{'=' * 60}")

        now = datetime.now()
        start = now - timedelta(hours=hours)
        start_date = start.date()  # date 객체로 변환

        conn = pymysql.connect(**self.db_config)
        gaps = []

        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("""
                               SELECT url        as news_id,
                                      title      as title,
                                      stock_name as companies,
                                      event_code as event_code,
                                      date       as news_date
                               FROM comprehensive_analyzed_news
                               WHERE date >= %s
                                 AND stock_name IS NOT NULL
                                 AND event_code IS NOT NULL
                               ORDER BY date DESC
                               """, (start_date,))

                news_list = cursor.fetchall()
                logger.info(f"뉴스 {len(news_list)}건 발견")

            for news in news_list:
                news_id = news['news_id']
                news_title = news.get('title', '')
                companies = news.get('companies', '')
                event_code_list = news.get('event_code', '')
                news_date = news['news_date']  # DATE 객체 그대로 사용

                if not companies or not event_code_list:
                    continue

                company_list = [c.strip() for c in str(companies).split(',') if c.strip()]
                event_list = [e.strip() for e in str(event_code_list).split(',')
                              if e.strip() and e.strip().lower() != 'other']

                if not event_list:
                    continue

                for company_name in company_list:
                    stock_code = self.stock_code_map.get(company_name)
                    if not stock_code:
                        continue

                    for event in event_list:
                        gap = self._detect_gap(
                            conn, news_id, news_title, stock_code, event, news_date
                        )

                        if gap:
                            gaps.append(gap)
                            logger.info(
                                f" {gap['stock_name']}: {event}, "
                                f"Z={gap['z_score']:.2f} "
                                f"({gap['direction']}/{gap['magnitude']})"
                            )

            self._save_gaps(conn, gaps)

            logger.info(f"{'=' * 60}")
            logger.info(f"✅ {len(gaps)}개 괴리 신호 탐지")
            logger.info(f"{'=' * 60}")

        finally:
            conn.close()

        return gaps

    def _detect_gap(
            self, conn, news_id: str, news_title: str,
            stock_code: str, event_code: str, news_date
    ) -> dict | None:
        """괴리 탐지 (date 객체 사용)"""
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 종목명
            cursor.execute(
                "SELECT corp_name FROM stock_list WHERE stock_code = %s",
                (stock_code,)
            )
            corp = cursor.fetchone()
            if not corp:
                return None

            stock_name = corp['corp_name']

            # 앵커 가격
            cursor.execute("""
                           SELECT trade_date as date, close_price as close_price
                           FROM stock_daily_prices
                           WHERE stock_code = %s
                             AND trade_date >= %s
                           ORDER BY trade_date ASC
                               LIMIT 1
                           """, (stock_code, news_date))

            anchor = cursor.fetchone()
            if not anchor:
                return None

            anchor_price = float(anchor['close_price'])
            anchor_date = anchor['date']  # DATE 객체

            # 1일 후 가격
            cursor.execute("""
                           SELECT close_price as close_price
                           FROM stock_daily_prices
                           WHERE stock_code = %s
                             AND trade_date > %s
                           ORDER BY trade_date ASC LIMIT 1
                           """, (stock_code, anchor_date))

            p1 = cursor.fetchone()
            if not p1:
                return None

            actual = math.log(float(p1['close_price']) / anchor_price)

            # 기대 수익률 (prefix 매칭 지원)
            event_prefix = event_code.split('.')[0] if '.' in event_code else event_code

            cursor.execute("""
                           SELECT AVG(return_1d)    as mean,
                                  STDDEV(return_1d) as std,
                                  COUNT(*)          as cnt
                           FROM news_returns
                           WHERE (event_code = %s OR event_code LIKE %s)
                             AND return_1d IS NOT NULL
                             AND news_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
                           """, (event_code, f"{event_prefix}.%"))

            stats = cursor.fetchone()

            if not stats or stats['cnt'] < self.min_samples:
                return None

            expected = float(stats['mean'])
            std = float(stats['std'])

            if std < 1e-6:
                return None

            z = (actual - expected) / std

            if abs(z) < self.z_threshold:
                return None

            direction = "OVER" if z > 0 else "UNDER"

            if abs(z) >= 3.0:
                magnitude = "EXTREME"
            elif abs(z) >= 2.0:
                magnitude = "HIGH"
            else:
                magnitude = "MODERATE"

            return {
                "news_id": news_id,
                "news_title": news_title,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "event_code": event_code,
                "news_date": news_date,  # DATE 객체 그대로
                "horizon": 1,
                "actual_return": actual,
                "expected_return": expected,
                "expected_std": std,
                "z_score": z,
                "direction": direction,
                "magnitude": magnitude,
                "sample_count": stats['cnt']
            }

    def _save_gaps(self, conn, gaps: list):
        """괴리 신호 저장"""
        if not gaps:
            return

        with conn.cursor() as cursor:
            for g in gaps:
                cursor.execute("""
                               INSERT INTO news_gaps
                               (news_id, news_title, stock_code, stock_name, event_code,
                                news_date, horizon, actual_return, expected_return, expected_std,
                                z_score, direction, magnitude, sample_count)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY
                               UPDATE
                                   z_score =
                               VALUES (z_score), direction =
                               VALUES (direction), magnitude =
                               VALUES (magnitude)
                               """, (
                                   g['news_id'], g['news_title'], g['stock_code'], g['stock_name'],
                                   g['event_code'], g['news_date'], g['horizon'],
                                   g['actual_return'], g['expected_return'], g['expected_std'],
                                   g['z_score'], g['direction'], g['magnitude'], g['sample_count']
                               ))

        conn.commit()
        logger.info(f"DB 저장 완료: {len(gaps)}건")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    scanner = NewsGapScanner()
    scanner.build_history("20250101", "20250930")
