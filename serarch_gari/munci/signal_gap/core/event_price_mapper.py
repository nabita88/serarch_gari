
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import pymysql
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class AnchorPrice:
    """기준가격 정보"""
    stock_code: str
    event_date: str          # 이벤트 발생일 (YYYYMMDD)
    anchor_date: str         # 앵커 거래일 (YYYYMMDD)
    anchor_close: float      # 기준 종가
    volume: int              # 거래량
    market_cap: float = 0.0  # 시가총액 (선택)


class EventPriceMapper:
    """이벤트 → 주가 앵커 매핑"""
    
    def __init__(self, db_config: dict):

        self.db_config = db_config
    
    def get_anchor_price(
        self,
        stock_code: str,
        event_date: str  # YYYYMMDD
    ) -> Optional[AnchorPrice]:

        conn = None
        try:
            conn = pymysql.connect(**self.db_config)
            
            # 종목코드 6자리 패딩 추가
            stock_code_padded = stock_code.zfill(6)
            
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 이벤트일 이후 첫 거래일 찾기
                # 날짜 형식 변환: YYYYMMDD -> YYYY-MM-DD
                event_date_formatted = f"{event_date[:4]}-{event_date[4:6]}-{event_date[6:]}" if len(event_date) == 8 else event_date
                
                sql = """
                    SELECT 
                        stock_code,
                        trade_date as anchor_date,
                        close_price as anchor_close,
                        0 as volume,
                        0 as market_cap
                    FROM stock_daily_prices
                    WHERE stock_code = %s
                      AND trade_date >= %s
                    ORDER BY trade_date ASC
                    LIMIT 1
                """
                cursor.execute(sql, (stock_code_padded, event_date_formatted))
                row = cursor.fetchone()
                
                if not row:
                    logger.warning(
                        f"앵커 가격 없음: stock={stock_code}, date={event_date}"
                    )
                    return None
                
                # 날짜 형식 변환: YYYY-MM-DD -> YYYYMMDD
                anchor_date = row['anchor_date']
                if isinstance(anchor_date, str):
                    anchor_date_str = anchor_date.replace('-', '')
                else:
                    anchor_date_str = anchor_date.strftime('%Y%m%d')
                
                anchor = AnchorPrice(
                    stock_code=stock_code,
                    event_date=event_date,
                    anchor_date=anchor_date_str,
                    anchor_close=float(row['anchor_close']),
                    volume=int(row['volume']),
                    market_cap=float(row.get('market_cap', 0))
                )
                
                logger.debug(
                    f"앵커 조회: {stock_code} @ {anchor.anchor_date} "
                    f"= {anchor.anchor_close:,.0f}원"
                )
                
                return anchor
                
        except Exception as e:
            logger.error(f"앵커 가격 조회 실패: {e}", exc_info=True)
            return None
        finally:
            if conn:
                conn.close()
    
    def get_anchor_prices_batch(
        self,
        events: list[tuple[str, str]]  # [(stock_code, event_date), ...]
    ) -> Dict[tuple, AnchorPrice]:

        result = {}
        
        for stock_code, event_date in events:
            anchor = self.get_anchor_price(stock_code, event_date)
            if anchor:
                result[(stock_code, event_date)] = anchor
        
        return result
