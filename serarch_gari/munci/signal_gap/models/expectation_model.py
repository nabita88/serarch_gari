
from __future__ import annotations
from typing import Dict, List, Optional
from dataclasses import dataclass
import pymysql
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExpectationStats:
    """기대효과 통계"""
    event_code: str
    horizon: int
    mean: float              # 평균 수익률
    median: float            # 중앙값 (robust estimator)
    std: float               # 표준편차
    q25: float               # 25% 분위수
    q75: float               # 75% 분위수
    iqr: float               # IQR = q75 - q25
    count: int               # 샘플 수
    confidence: float        # 신뢰도 (샘플 수 기반)


class ExpectationModel:
    """기대효과 계산 모델"""
    
    def __init__(
        self, 
        db_config: dict, 
        min_samples: int = 10,
        lookback_days: int = 365
    ):

        self.db_config = db_config
        self.min_samples = min_samples
        self.lookback_days = lookback_days
        self._cache: Dict[str, ExpectationStats] = {}
    
    def get_expectation(
        self,
        event_code: str,
        horizon: int = 1
    ) -> Optional[ExpectationStats]:

        cache_key = f"{event_code}_{horizon}_{self.lookback_days}"
        
        # 캐시 확인
        if cache_key in self._cache:
            logger.debug(f"캐시 히트: {cache_key}")
            return self._cache[cache_key]
        
        # DB 조회
        conn = None
        try:
            conn = pymysql.connect(**self.db_config)
            
            with conn.cursor() as cursor:
                # 과거 동일 이벤트의 수익률 조회
                sql = f"""
                    SELECT return_{horizon}d as ret
                    FROM event_returns_history
                    WHERE event_code = %s
                      AND return_{horizon}d IS NOT NULL
                      AND event_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                """
                cursor.execute(sql, (event_code, self.lookback_days))
                rows = cursor.fetchall()
                
                if len(rows) < self.min_samples:
                    logger.warning(
                        f"샘플 부족: {event_code} H={horizon}, "
                        f"n={len(rows)} < {self.min_samples}"
                    )
                    return None
                
                # numpy 배열로 변환
                returns = np.array([float(r[0]) for r in rows])
                
                # 통계 계산
                q25 = float(np.percentile(returns, 25))
                q75 = float(np.percentile(returns, 75))
                
                stats = ExpectationStats(
                    event_code=event_code,
                    horizon=horizon,
                    mean=float(np.mean(returns)),
                    median=float(np.median(returns)),
                    std=float(np.std(returns, ddof=1)),  # 표본 표준편차
                    q25=q25,
                    q75=q75,
                    iqr=q75 - q25,
                    count=len(returns),
                    confidence=self._calculate_confidence(len(returns))
                )
                
                # 캐시 저장
                self._cache[cache_key] = stats
                
                logger.info(
                    f"기대효과: {event_code} H={horizon}, "
                    f"μ={stats.mean:.4f}, σ={stats.std:.4f}, "
                    f"n={stats.count}, conf={stats.confidence:.2f}"
                )
                
                return stats
        
        except Exception as e:
            logger.error(f"기대효과 계산 실패: {e}", exc_info=True)
            return None
        
        finally:
            if conn:
                conn.close()
    
    def _calculate_confidence(self, n: int) -> float:

        return min(1.0, n / 100.0)
    
    def clear_cache(self):
        """캐시 초기화 (일일 배치 시작 시 호출)"""
        self._cache.clear()
        logger.info("기대효과 캐시 초기화")
    
    def get_all_expectations(
        self,
        event_codes: List[str],
        horizons: List[int] = None
    ) -> Dict[tuple, ExpectationStats]:

        if horizons is None:
            horizons = [1, 3, 5]
        
        result = {}
        
        for event_code in event_codes:
            for horizon in horizons:
                stats = self.get_expectation(event_code, horizon)
                if stats:
                    result[(event_code, horizon)] = stats
        
        return result
