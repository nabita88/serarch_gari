

from __future__ import annotations
import sys
from pathlib import Path


project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import pymysql
import logging
import math
import json

from munci.rumerapi.utils.date_utils import to_yyyymmdd, to_db_date, from_db_date

logger = logging.getLogger(__name__)


class DailyGapScanner:
    """일일 괴리 스캐너 (뉴스 테이블을 읽되, 공시형 계산 경로 사용)"""

    def __init__(
        self,
        db_config: dict,
        z_threshold: float = 2.0,        # 기본 2.0
        min_samples: int = 10,           # 간단 계산용 최소 샘플 수
        min_confidence: float = 0.5      # 히스토리 계산용 최소 신뢰도
    ):

        self.db_config = db_config
        self.z_threshold = z_threshold
        self.min_samples = min_samples
        self.min_confidence = min_confidence

        # 종목코드 매핑 로드
        self.stock_code_map = self._load_stock_code_map()

        # 히스토리 기반 계산 경로 준비 (지연 로딩; 실패 시 간단 계산으로 폴백)
        self.use_history_calc = False
        try:
            from munci.signal_gap.core.event_price_mapper import EventPriceMapper
            from munci.signal_gap.core.return_calculator import ReturnCalculator
            from munci.signal_gap.core.gap_detector import GapDetector
            self._mapper = EventPriceMapper(db_config)
            self._calculator = ReturnCalculator(db_config)
            self._detector = GapDetector(db_config, z_threshold, min_confidence)
            self.use_history_calc = True
            logger.info("히스토리 기반 계산 경로 활성화 (event_returns_history 사용)")
        except Exception as e:
            logger.warning(f"히스토리 기반 계산 모듈 로딩 실패 → 간단 계산 사용: {e}")

        # news_gaps 테이블의 칼럼(특히 calc_mode) 존재 여부 캐시
        self._news_gaps_columns: Optional[set] = None

    # --------------------------- public API ---------------------------

    def scan(self, scan_date: str = None) -> List[dict]:

        if scan_date is None:
            scan_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

        logger.info(f"{'=' * 60}")
        logger.info(f"일일 괴리 스캔 시작: {scan_date}")
        logger.info(f"{'=' * 60}")

        signals = self._scan_news(scan_date)

        # DB 저장
        self._save_signals(signals)

        # 요약
        self._print_summary(signals, scan_date)

        return signals

    # --------------------------- core ---------------------------

    def _scan_news(self, scan_date: str) -> List[dict]:

        conn = None
        signals = []

        try:
            conn = pymysql.connect(**self.db_config)

            # YYYYMMDD -> YYYY-MM-DD (DB 쿼리용)
            db_date = to_db_date(scan_date)

            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Step 1: 당일 뉴스 이벤트 조회
                sql = """
                      SELECT url        as news_id,
                             title      as title,
                             stock_name as companies,
                             event_code as event_code,
                             date       as news_date
                      FROM comprehensive_analyzed_news
                      WHERE date = %s
                        AND stock_name IS NOT NULL
                        AND event_code IS NOT NULL
                      ORDER BY date
                      """
                cursor.execute(sql, (db_date,))
                news_list = cursor.fetchall()

                logger.info(f"[뉴스] {len(news_list)}건의 이벤트 발견")

                if not news_list:
                    logger.warning("뉴스 이벤트가 없습니다")
                    return []

            # Step 2: 캐시 준비 (지연 로딩)
            price_cache = None
            stats_cache = None

            # Step 3: 각 뉴스 처리
            for idx, news in enumerate(news_list, 1):
                try:
                    news_id = news['news_id']
                    news_title = news.get('title', '')
                    companies = news.get('companies', '')
                    event_code_list = news.get('event_code', '')
                    # DB에서 가져온 날짜를 YYYYMMDD로 통일
                    news_date = from_db_date(news['news_date'])

                    if not companies or not event_code_list:
                        continue

                    company_list = [c.strip() for c in str(companies).split(',') if c.strip()]
                    event_list = [e.strip() for e in str(event_code_list).split(',')
                                  if e.strip() and e.strip().lower() != 'other']

                    if not event_list:
                        continue

                    # 종목코드 변환
                    for company_name in company_list:
                        stock_code = self.stock_code_map.get(company_name)
                        if not stock_code:
                            continue

                        for event_code in event_list:
                            gap = None

                            # 1) 히스토리 기반 계산 경로 시도
                            if self.use_history_calc:
                                gap = self._detect_gap_history_based(
                                    news_id, news_title, stock_code,
                                    company_name, event_code, news_date
                                )

                            # 2) 실패 시 간단 계산으로 폴백 (지연 캐시 로딩)
                            if not gap:
                                if price_cache is None or stats_cache is None:
                                    logger.info("폴백 대비 가격/통계 캐시 로딩 중...")
                                    price_cache = self._load_price_cache(conn, db_date)
                                    stats_cache = self._load_stats_cache(conn, db_date)
                                    logger.info(f" 캐시 로드 완료: {len(price_cache)}종목 / {len(stats_cache)}이벤트")

                                gap = self._detect_gap_simple(
                                    news_id, news_title, stock_code,
                                    company_name, event_code, news_date,
                                    price_cache, stats_cache
                                )

                            if gap:
                                signals.append(gap)
                                mode_tag = gap.get('calc_mode', 'NA')
                                logger.info(
                                    f"[{idx}/{len(news_list)}] "
                                    f" [{mode_tag}] {gap['stock_name']}: {gap['event_code']}, "
                                    f"Z={gap['z_score']:.2f} "
                                    f"({gap['direction']}/{gap['magnitude']})"
                                )

                except Exception as e:
                    logger.error(
                        f"[{idx}/{len(news_list)}] 뉴스 처리 실패: {e}"
                    )
                    continue

        except Exception as e:
            logger.error(f"뉴스 스캔 실패: {e}", exc_info=True)

        finally:
            if conn:
                conn.close()

        logger.info(f"[뉴스] {len(signals)}개 괴리 신호 탐지")
        return signals


    def _detect_gap_history_based(
        self, news_id: str, news_title: str,
        stock_code: str, stock_name: str, event_code: str, news_date: str
    ) -> dict | None:

        try:
            # event_code는 이미 AI로 분류되어 있으므로 정규화 불필요
            if not event_code or event_code.strip().lower() == "other":
                return None

            # 앵커 가격 → 수익률(1D) 계산
            anchor = self._mapper.get_anchor_price(stock_code, news_date)
            if not anchor:
                return None

            returns = self._calculator.calculate_returns(
                stock_code, anchor.anchor_date, anchor.anchor_close, horizons=[1]
            )

            # 히스토리 분포 대비 괴리 탐지
            sig = self._detector.detect_gap(
                stock_code=stock_code,
                stock_name=stock_name,
                event_code=event_code,
                event_date=news_date,
                returns=returns,
                horizon=1
            )
            if not sig:
                return None

            expected_return = getattr(sig, "expected_return", None)
            if expected_return is None:
                expected_return = getattr(sig, "expected_mean", None)

            return {
                "calc_mode": "HISTORY",
                "news_id": news_id,
                "news_title": news_title,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "event_code": event_code,
                "news_date": news_date,  # YYYYMMDD 그대로 유지
                "horizon": 1,
                "actual_return": getattr(sig, "actual_return", None),
                "expected_return": expected_return,
                "expected_std": getattr(sig, "expected_std", None),
                "z_score": getattr(sig, "z_score", None),
                "direction": getattr(sig, "direction", None),
                "magnitude": getattr(sig, "magnitude", None),
                "sample_count": getattr(sig, "sample_count", None),
            }
        except Exception as e:
            logger.error(f"[히스토리 방식] 괴리 탐지 실패: {e}")
            return None

    # --------------------------- 간단 계산(폴백) ---------------------------

    def _load_stock_code_map(self) -> dict:
        """normalized_aliases.json에서 종목명 -> 종목코드 매핑 로드"""
        project_root = Path(__file__).parent.parent.parent.parent
        json_path = project_root / "examples" / "normalized_aliases.json"

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

    def _load_price_cache(self, conn, scan_date: str) -> dict:
        """가격 데이터를 메모리에 캐싱 (간단 계산에서 사용)"""
        cache = {}

        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                           SELECT stock_code, trade_date, close_price
                           FROM stock_daily_prices
                           WHERE trade_date BETWEEN DATE_SUB(%s, INTERVAL 5 DAY)
                                     AND DATE_ADD(%s, INTERVAL 5 DAY)
                           ORDER BY stock_code, trade_date
                           """, (scan_date, scan_date))

            for row in cursor:
                stock_code = row['stock_code']
                date = row['trade_date']
                price = float(row['close_price'])

                if stock_code not in cache:
                    cache[stock_code] = []
                cache[stock_code].append((date, price))

        return cache

    def _load_stats_cache(self, conn, scan_date: str) -> dict:
        """이벤트별 통계를 메모리에 캐싱 (포인트-인-타임; 간단 계산에서 사용)"""
        cache = {}

        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                           SELECT event_code,
                                  AVG(return_1d)    as mean,
                                  STDDEV(return_1d) as std,
                                  COUNT(*)          as cnt
                           FROM news_returns
                           WHERE return_1d IS NOT NULL
                             AND news_date BETWEEN DATE_SUB(%s, INTERVAL 365 DAY) AND %s
                           GROUP BY event_code
                           """, (scan_date, scan_date))

            for row in cursor:
                cache[row['event_code']] = {
                    'mean': float(row['mean']) if row['mean'] else 0,
                    'std': float(row['std']) if row['std'] else 0,
                    'cnt': int(row['cnt'])
                }

        return cache

    def _detect_gap_simple(
        self, news_id: str, news_title: str,
        stock_code: str, stock_name: str, event_code: str, news_date: str,
        price_cache: dict, stats_cache: dict
    ) -> dict | None:


        # 가격 데이터 확인
        if stock_code not in price_cache:
            return None

        prices = price_cache[stock_code]
        # YYYYMMDD -> date 객체
        news_date_obj = datetime.strptime(news_date, '%Y%m%d').date()

        # 앵커 가격 찾기 (뉴스일자 이상 첫 거래일)
        anchor_idx = None
        for idx, (date, price) in enumerate(prices):
            if date >= news_date_obj:
                anchor_idx = idx
                break

        if anchor_idx is None or anchor_idx + 1 >= len(prices):
            return None

        anchor_price = prices[anchor_idx][1]
        price_1d = prices[anchor_idx + 1][1]

        # 실제 수익률 (로그)
        actual = math.log(price_1d / anchor_price)

        # 통계 확인 (event_code 그대로 사용)
        if event_code not in stats_cache:
            return None

        stats = stats_cache[event_code]

        if stats['cnt'] < self.min_samples:
            return None

        expected = stats['mean']
        std = stats['std']

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
        elif abs(z) >= 1.0:
            magnitude = "MODERATE"
        else:
            magnitude = "LOW"

        return {
            "calc_mode": "SIMPLE",
            "news_id": news_id,
            "news_title": news_title,
            "stock_code": stock_code,
            "stock_name": stock_name,
            "event_code": event_code,  # 정규화 없이 그대로 사용
            "news_date": news_date,  # YYYYMMDD 그대로 유지
            "horizon": 1,
            "actual_return": actual,
            "expected_return": expected,
            "expected_std": std,
            "z_score": z,
            "direction": direction,
            "magnitude": magnitude,
            "sample_count": stats['cnt']
        }

    # --------------------------- 저장/요약 ---------------------------

    def _get_news_gaps_columns(self, conn) -> set:
        """news_gaps 테이블 컬럼 목록 (자동 감지)"""
        if self._news_gaps_columns is not None:
            return self._news_gaps_columns

        cols = set()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SHOW COLUMNS FROM news_gaps")
            for row in cursor:
                cols.add(row['Field'])
        self._news_gaps_columns = cols
        logger.info(f"news_gaps columns: {sorted(cols)}")
        return cols

    def _save_signals(self, signals: List[dict]):

        if not signals:
            logger.info("저장할 신호가 없습니다")
            return

        conn = None
        try:
            conn = pymysql.connect(**self.db_config)
            cols = self._get_news_gaps_columns(conn)
            has_calc_mode = 'calc_mode' in cols

            with conn.cursor() as cursor:
                for s in signals:
                    # YYYYMMDD 그대로 사용 (이미 통일된 형식)
                    news_date_str = s['news_date']

                    if has_calc_mode:
                        sql = """
                            INSERT INTO news_gaps
                            (news_id, news_title, stock_code, stock_name, event_code,
                             news_date, horizon, actual_return, expected_return, expected_std,
                             z_score, direction, magnitude, sample_count, calc_mode)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                z_score = VALUES(z_score),
                                direction = VALUES(direction),
                                magnitude = VALUES(magnitude),
                                calc_mode = VALUES(calc_mode)
                        """
                        values = (
                            s['news_id'], s['news_title'], s['stock_code'], s['stock_name'],
                            s['event_code'], news_date_str, s['horizon'],
                            s['actual_return'], s['expected_return'], s['expected_std'],
                            s['z_score'], s['direction'], s['magnitude'], s['sample_count'],
                            s.get('calc_mode', None)
                        )
                    else:
                        sql = """
                            INSERT INTO news_gaps
                            (news_id, news_title, stock_code, stock_name, event_code,
                             news_date, horizon, actual_return, expected_return, expected_std,
                             z_score, direction, magnitude, sample_count)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                z_score = VALUES(z_score),
                                direction = VALUES(direction),
                                magnitude = VALUES(magnitude)
                        """
                        values = (
                            s['news_id'], s['news_title'], s['stock_code'], s['stock_name'],
                            s['event_code'], news_date_str, s['horizon'],
                            s['actual_return'], s['expected_return'], s['expected_std'],
                            s['z_score'], s['direction'], s['magnitude'], s['sample_count']
                        )

                    cursor.execute(sql, values)

                conn.commit()
                logger.info(f" DB 저장 완료: {len(signals)}건 (calc_mode column: {'YES' if has_calc_mode else 'NO'})")

        except Exception as e:
            logger.error(f"DB 저장 실패: {e}", exc_info=True)
            if conn:
                conn.rollback()

        finally:
            if conn:
                conn.close()

    def _print_summary(self, signals: List[dict], scan_date: str):
        """스캔 결과 요약 출력 (calc_mode 요약 포함)"""
        logger.info(f"{'=' * 60}")
        logger.info(f"스캔 결과 요약 ({scan_date})")
        logger.info(f"{'=' * 60}")

        if not signals:
            logger.info("괴리 신호가 발견되지 않았습니다")
            return

        # 전체 통계
        logger.info(f"총 신호 수: {len(signals)}개")

        # 방향별 통계
        over_count = sum(1 for s in signals if s['direction'] == "OVER")
        under_count = sum(1 for s in signals if s['direction'] == "UNDER")
        logger.info(f"  - 과대반응 (OVER): {over_count}개")
        logger.info(f"  - 과소반응 (UNDER): {under_count}개")

        # 강도별 통계
        extreme_count = sum(1 for s in signals if s['magnitude'] == "EXTREME")
        high_count = sum(1 for s in signals if s['magnitude'] == "HIGH")
        moderate_count = sum(1 for s in signals if s['magnitude'] == "MODERATE")
        logger.info(f"  - EXTREME: {extreme_count}개")
        logger.info(f"  - HIGH: {high_count}개")
        logger.info(f"  - MODERATE: {moderate_count}개")

        # 모드별 통계
        history_count = sum(1 for s in signals if s.get('calc_mode') == "HISTORY")
        simple_count = sum(1 for s in signals if s.get('calc_mode') == "SIMPLE")
        logger.info(f"  - calc_mode: HISTORY={history_count} / SIMPLE={simple_count}")

        # Top 5 신호
        logger.info(f"\n{'=' * 60}")
        logger.info(" Top 5 신호 (|Z| 기준)")
        logger.info(f"{'=' * 60}")

        top_signals = sorted(signals, key=lambda s: abs(s['z_score']), reverse=True)[:5]

        for rank, sig in enumerate(top_signals, 1):
            mode_tag = sig.get('calc_mode', 'NA')
            logger.info(
                f"{rank}. [{mode_tag}] {sig['stock_name']}({sig['stock_code']}) "
                f"Z={sig['z_score']:+.2f} ({sig['direction']})"
            )
            logger.info(
                f"   실제={sig['actual_return'] * 100:+.2f}%, "
                f"기대={sig['expected_return'] * 100:+.2f}%"
            )

        logger.info(f"{'=' * 60}")


# --------------------------- convenience runners ---------------------------

def run_daily_scan(
    db_config: dict,
    scan_date: str = None,
    z_threshold: float = 2.0,        # 기본 2.0
    min_samples: int = 10,
    min_confidence: float = 0.5
) -> List[dict]:

    scanner = DailyGapScanner(
        db_config,
        z_threshold=z_threshold,
        min_samples=min_samples,
        min_confidence=min_confidence
    )
    return scanner.scan(scan_date=scan_date)


def run_backfill_scan(
    db_config: dict,
    start_date: str,
    end_date: str,
    z_threshold: float = 2.0,
    min_confidence: float = 0.5
):

    from datetime import datetime, timedelta

    logger.info(f"백필 스캔 시작: {start_date} ~ {end_date}")

    scanner = DailyGapScanner(
        db_config, z_threshold=z_threshold, min_confidence=min_confidence
    )

    # 날짜 범위 생성
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")

    current = start
    total_signals = 0

    while current <= end:
        scan_date_str = current.strftime("%Y%m%d")

        try:
            signals = scanner.scan(scan_date=scan_date_str)
            total_signals += len(signals)
        except Exception as e:
            logger.error(f"스캔 실패 ({scan_date_str}): {e}")

        current += timedelta(days=1)

    logger.info(f"{'=' * 60}")
    logger.info(f"백필 스캔 완료")
    logger.info(f"  - 기간: {start_date} ~ {end_date}")
    logger.info(f"  - 총 신호: {total_signals}개")
    logger.info(f"{'=' * 60}")


# --------------------------- CLI ---------------------------

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    # 원본 뉴스 스캐너는 settings를 사용했지만, 환경변수도 지원
    try:
        from munci.rumerapi.core.config import settings
        DB_HOST = settings.db_host
        DB_USERNAME = settings.db_username
        DB_PASSWORD = settings.db_password
        DB_DATABASE = settings.db_database
        DB_PORT = settings.db_port
    except Exception:
        load_dotenv()
        DB_HOST = os.getenv('DB_HOST', 'localhost')
        DB_USERNAME = os.getenv('DB_USERNAME')
        DB_PASSWORD = os.getenv('DB_PASSWORD')
        DB_DATABASE = os.getenv('DB_DATABASE')
        DB_PORT = int(os.getenv('DB_PORT', 3306))

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    db_config = {
        'host': DB_HOST,
        'user': DB_USERNAME,
        'password': DB_PASSWORD,
        'database': DB_DATABASE,
        'port': DB_PORT
    }

    import sys
    if len(sys.argv) > 1:
        mode = sys.argv[1]

        if mode == "backfill" and len(sys.argv) >= 4:
            # 백필 모드
            start_date = sys.argv[2]
            end_date = sys.argv[3]
            run_backfill_scan(db_config, start_date, end_date)

        elif mode == "date" and len(sys.argv) >= 3:
            # 특정 날짜 스캔
            scan_date = sys.argv[2]
            run_daily_scan(db_config, scan_date=scan_date)

        else:
            print("Usage:")
            print("  python daily_scanner.py                    # 어제 스캔")
            print("  python daily_scanner.py date 20240101      # 특정 날짜")
            print("  python daily_scanner.py backfill 20240101 20241012  # 백필")

    else:
        # 기본: 어제 스캔
        run_daily_scan(db_config)
