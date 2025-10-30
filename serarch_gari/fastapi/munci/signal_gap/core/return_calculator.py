
from __future__ import annotations
import math
from typing import List, Dict, Optional
import pymysql
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ReturnPath:
    """수익률 경로"""
    stock_code: str
    anchor_date: str
    anchor_price: float
    horizons: Dict[int, Optional[float]] = field(default_factory=dict)
    # horizons[H] = log(price_H / anchor_price)
    # None이면 데이터 없음


class ReturnCalculator:
    """수익률 계산기"""
    
    def __init__(self, db_config: dict):

        self.db_config = db_config
    
    def calculate_returns(
        self,
        stock_code: str,
        anchor_date: str,
        anchor_price: float,
        horizons: List[int] = None
    ) -> ReturnPath:

        if horizons is None:
            horizons = [1, 3, 5]
        
        conn = None
        returns = {}
        
        try:
            conn = pymysql.connect(**self.db_config)
            
            # 종목코드 6자리 패딩 추가
            stock_code_padded = stock_code.zfill(6)
            
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # anchor_date 형식 변환: YYYYMMDD -> YYYY-MM-DD
                anchor_date_formatted = f"{anchor_date[:4]}-{anchor_date[4:6]}-{anchor_date[6:]}" if len(anchor_date) == 8 else anchor_date
                
                for H in horizons:
                    # 앵커 이후 H번째 거래일 종가 조회
                    sql = """
                        SELECT close_price, trade_date as date
                        FROM stock_daily_prices
                        WHERE stock_code = %s
                          AND trade_date > %s
                        ORDER BY trade_date ASC
                        LIMIT %s, 1
                    """
                    # LIMIT offset, count → H-1번째부터 1개
                    cursor.execute(sql, (stock_code_padded, anchor_date_formatted, H-1))
                    row = cursor.fetchone()
                    
                    if row:
                        future_price = float(row['close_price'])
                        future_date = row['date']
                        
                        # 로그수익률 계산
                        log_return = math.log(future_price / anchor_price)
                        returns[H] = log_return
                        
                        logger.debug(
                            f"{stock_code} {H}D: "
                            f"{anchor_price:,.0f} → {future_price:,.0f} "
                            f"= {log_return:.4f} ({log_return*100:.2f}%)"
                        )
                    else:
                        returns[H] = None
                        logger.debug(
                            f"{stock_code} {H}D: 데이터 없음 "
                            f"(anchor={anchor_date})"
                        )
        
        except Exception as e:
            logger.error(f"수익률 계산 실패: {e}", exc_info=True)
            # 실패 시 모든 horizon을 None으로
            returns = {H: None for H in horizons}
        
        finally:
            if conn:
                conn.close()
        
        return ReturnPath(
            stock_code=stock_code,
            anchor_date=anchor_date,
            anchor_price=anchor_price,
            horizons=returns
        )
    
    def calculate_price_path(
        self,
        stock_code: str,
        start_date: str,
        days: int = 10
    ) -> List[tuple[str, float]]:

        conn = None
        try:
            conn = pymysql.connect(**self.db_config)
            
            # 종목코드 6자리 패딩 추가
            stock_code_padded = stock_code.zfill(6)
            
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # start_date 형식 변환: YYYYMMDD -> YYYY-MM-DD
                start_date_formatted = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}" if len(start_date) == 8 else start_date
                
                sql = """
                    SELECT trade_date as date, close_price
                    FROM stock_daily_prices
                    WHERE stock_code = %s
                      AND trade_date >= %s
                    ORDER BY trade_date ASC
                    LIMIT %s
                """
                cursor.execute(sql, (stock_code_padded, start_date_formatted, days))
                rows = cursor.fetchall()
                
                return [(row['date'], float(row['close_price'])) for row in rows]
        
        finally:
            if conn:
                conn.close()
