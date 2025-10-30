from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import pymysql
import logging

from munci.rumerapi.core.config import settings

logger = logging.getLogger(__name__)


class NewsGapChecker:

    def __init__(self):
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
            logger.warning("DB 설정 없음 - Gap 체크 불가")

    def check(self, stock_code: str, days: int = 3) -> Dict[str, Any]:

        if not self.db_config:
            return {
                "has_gap": False,
                "gap_signals": [],
                "price_change": None
            }

        result = {
            "has_gap": False,
            "gap_signals": [],
            "price_change": None
        }

        gaps = self.check_gaps(stock_code, days)
        if gaps:
            result["has_gap"] = True
            result["gap_signals"] = gaps

        result["price_change"] = self._get_price_change(stock_code, days)

        return result

    def check_gaps(self, stock_code: str, days: int = 3) -> List[dict]:

        if not self.db_config:
            return []

        conn = pymysql.connect(**self.db_config)

        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

                cursor.execute("""
                               SELECT news_id,
                                      news_title,
                                      event_code,
                                      news_date,
                                      horizon,
                                      z_score,
                                      direction,
                                      magnitude,
                                      actual_return,
                                      expected_return,
                                      sample_count
                               FROM news_gaps
                               WHERE stock_code = %s
                                 AND news_date >= %s
                               ORDER BY ABS(z_score) DESC LIMIT 5
                               """, (stock_code, start_date))

                gaps = []
                for row in cursor.fetchall():
                    gaps.append({
                        "news_id": row['news_id'],
                        "news_title": row['news_title'],
                        "event_code": row['event_code'],
                        "news_date": row['news_date'],
                        "horizon": row['horizon'],
                        "z_score": float(row['z_score']),
                        "direction": row['direction'],
                        "magnitude": row['magnitude'],
                        "actual_return": float(row['actual_return']) * 100,
                        "expected_return": float(row['expected_return']) * 100,
                        "sample_count": row['sample_count']
                    })

                return gaps

        except Exception as e:
            logger.exception(f"Gap check failed: {e}")
            return []

        finally:
            conn.close()

    def _get_price_change(self, stock_code: str, days: int) -> Optional[float]:
        """가격 변동률"""
        if not self.db_config:
            return None

        conn = pymysql.connect(**self.db_config)

        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

                cursor.execute("""
                               SELECT (MAX(close_price) - MIN(close_price)) / MIN(close_price) * 100 as change_pct
                               FROM stock_daily_prices
                               WHERE stock_name = %s
                                 AND trade_date >= %s
                               """, (stock_code, start_date))

                result = cursor.fetchone()
                if result and result['change_pct']:
                    return float(result['change_pct'])

        except Exception as e:
            logger.exception(f"Price change failed: {e}")
            return None

        finally:
            conn.close()

        return None

    def list_gaps(
            self,
            days: int = 7,
            direction: Optional[str] = None,
            magnitude: Optional[str] = None,
            min_z: float = 2.0,
            limit: int = 20
    ) -> List[dict]:

        if not self.db_config:
            return []

        conn = pymysql.connect(**self.db_config)

        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

            where_clauses = ["news_date >= %s", "ABS(z_score) >= %s"]
            params = [start_date, min_z]

            if direction:
                where_clauses.append("direction = %s")
                params.append(direction)

            if magnitude:
                where_clauses.append("magnitude = %s")
                params.append(magnitude)

            where_sql = " AND ".join(where_clauses)

            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(f"""
                    SELECT
                        id,
                        news_id,
                        news_title,
                        stock_code,
                        stock_name,
                        event_code,
                        news_date,
                        horizon,
                        z_score,
                        direction,
                        magnitude,
                        actual_return,
                        expected_return,
                        sample_count,
                        detected_at
                    FROM news_gaps
                    WHERE {where_sql}
                    ORDER BY ABS(z_score) DESC
                    LIMIT %s
                """, params + [limit])

                gaps = []
                for row in cursor.fetchall():
                    gaps.append({
                        "id": row['id'],
                        "news_id": row['news_id'],
                        "news_title": row['news_title'],
                        "stock_code": row['stock_code'],
                        "stock_name": row['stock_name'],
                        "event_code": row['event_code'],
                        "news_date": row['news_date'],
                        "horizon": row['horizon'],
                        "z_score": float(row['z_score']),
                        "direction": row['direction'],
                        "magnitude": row['magnitude'],
                        "actual_return": float(row['actual_return']) * 100,
                        "expected_return": float(row['expected_return']) * 100,
                        "sample_count": row['sample_count'],
                        "detected_at": row['detected_at'].isoformat() if row['detected_at'] else None
                    })

                return gaps

        except Exception as e:
            logger.exception(f"List gaps failed: {e}")
            return []

        finally:
            conn.close()

    def get_stats(self, days: int = 7) -> Dict[str, Any]:

        if not self.db_config:
            return {
                "period_days": days,
                "total": 0,
                "by_direction": {},
                "by_magnitude": {},
                "by_event_code": {}
            }

        conn = pymysql.connect(**self.db_config)

        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 전체 개수
                cursor.execute("""
                               SELECT COUNT(*) as total
                               FROM news_gaps
                               WHERE news_date >= %s
                               """, (start_date,))
                total = cursor.fetchone()['total']

                # 방향별
                cursor.execute("""
                               SELECT direction, COUNT(*) as count
                               FROM news_gaps
                               WHERE news_date >= %s
                               GROUP BY direction
                               """, (start_date,))
                by_direction = {row['direction']: row['count'] for row in cursor.fetchall()}

                # 강도별
                cursor.execute("""
                               SELECT magnitude, COUNT(*) as count
                               FROM news_gaps
                               WHERE news_date >= %s
                               GROUP BY magnitude
                               """, (start_date,))
                by_magnitude = {row['magnitude']: row['count'] for row in cursor.fetchall()}

                # 이벤트별
                cursor.execute("""
                               SELECT event_code, COUNT(*) as count
                               FROM news_gaps
                               WHERE news_date >= %s
                               GROUP BY event_code
                               ORDER BY count DESC
                                   LIMIT 10
                               """, (start_date,))
                by_event = {row['event_code']: row['count'] for row in cursor.fetchall()}

                return {
                    "period_days": days,
                    "total": total,
                    "by_direction": by_direction,
                    "by_magnitude": by_magnitude,
                    "by_event_code": by_event
                }

        except Exception as e:
            logger.exception(f"Get stats failed: {e}")
            return {
                "period_days": days,
                "total": 0,
                "by_direction": {},
                "by_magnitude": {},
                "by_event_code": {}
            }

        finally:
            conn.close()
