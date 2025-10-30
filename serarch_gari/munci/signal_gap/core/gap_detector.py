
from __future__ import annotations
from typing import List, Optional, Dict
from dataclasses import dataclass
import logging

from munci.signal_gap.models.expectation_model import ExpectationModel, ExpectationStats
from munci.signal_gap.core.return_calculator import ReturnPath

logger = logging.getLogger(__name__)


@dataclass
class GapSignal:
    """괴리 신호"""
    stock_code: str
    stock_name: str
    event_code: str
    event_date: str
    anchor_date: str
    
    # 수익률 정보
    horizon: int
    actual_return: float     # 실제 수익률
    expected_return: float   # 기대 수익률 (중앙값)
    expected_mean: float     # 기대 평균
    expected_std: float      # 기대 표준편차
    expected_q25: float      # 25% 분위수
    expected_q75: float      # 75% 분위수
    
    # 괴리 지표
    z_score: float           # (actual - expected) / std
    percentile: float        # 역사적 분위수 (0~1)
    confidence: float        # 신뢰도 (0~1)
    
    # 분류
    direction: str           # "OVER" (과대반응) | "UNDER" (과소반응)
    magnitude: str           # "EXTREME" | "HIGH" | "MODERATE"
    
    # 메타
    sample_count: int        # 역사적 샘플 수


class GapDetector:

    
    def __init__(
        self,
        db_config: dict,
        z_threshold: float = 2.0,
        min_confidence: float = 0.5
    ):

        self.model = ExpectationModel(db_config)
        self.z_threshold = z_threshold
        self.min_confidence = min_confidence
    
    def detect_gap(
        self,
        stock_code: str,
        stock_name: str,
        event_code: str,
        event_date: str,
        returns: ReturnPath,
        horizon: int = 1
    ) -> Optional[GapSignal]:

        # Step 1: 기대효과 조회
        expectation = self.model.get_expectation(event_code, horizon)
        if not expectation:
            logger.debug(
                f"기대효과 없음: {event_code}, H={horizon}"
            )
            return None
        
        # Step 2: 실제 수익률 확인
        actual_return = returns.horizons.get(horizon)
        if actual_return is None:
            logger.debug(
                f"수익률 없음: {stock_code}, H={horizon}"
            )
            return None
        
        # Step 3: Z-score 계산
        expected_return = expectation.median  # robust estimator
        expected_std = expectation.std
        
        if expected_std == 0 or expected_std < 1e-6:
            logger.warning(
                f"표준편차 너무 작음: {event_code}, σ={expected_std}"
            )
            return None
        
        z_score = (actual_return - expected_return) / expected_std
        
        # Step 4: 임계값 필터
        if abs(z_score) < self.z_threshold:
            logger.debug(
                f"임계값 미달: {stock_name}, Z={z_score:.2f} < {self.z_threshold}"
            )
            return None
        
        # Step 5: 신뢰도 필터
        if expectation.confidence < self.min_confidence:
            logger.debug(
                f"신뢰도 부족: {stock_name}, "
                f"conf={expectation.confidence:.2f} < {self.min_confidence}"
            )
            return None
        
        # Step 6: 방향 및 강도 판정
        direction = "OVER" if z_score > 0 else "UNDER"
        
        if abs(z_score) >= 3.0:
            magnitude = "EXTREME"
        elif abs(z_score) >= 2.0:
            magnitude = "HIGH"
        else:
            magnitude = "MODERATE"
        
        # Step 7: 백분위 계산 (실제 수익률의 역사적 위치)
        percentile = self._calculate_percentile(
            actual_return, event_code, horizon
        )
        
        signal = GapSignal(
            stock_code=stock_code,
            stock_name=stock_name,
            event_code=event_code,
            event_date=event_date,
            anchor_date=returns.anchor_date,
            horizon=horizon,
            actual_return=actual_return,
            expected_return=expected_return,
            expected_mean=expectation.mean,
            expected_std=expected_std,
            expected_q25=expectation.q25,
            expected_q75=expectation.q75,
            z_score=z_score,
            percentile=percentile,
            confidence=expectation.confidence,
            direction=direction,
            magnitude=magnitude,
            sample_count=expectation.count
        )
        
        logger.info(
            f"🎯 괴리 탐지: {stock_name}({stock_code}), "
            f"Z={z_score:.2f} ({direction}/{magnitude}), "
            f"실제={actual_return*100:.2f}%, 기대={expected_return*100:.2f}%"
        )
        
        return signal
    
    def detect_gaps_batch(
        self,
        events: List[tuple],  # [(stock_code, stock_name, event_code, event_date, returns), ...]
        horizons: List[int] = None
    ) -> List[GapSignal]:

        if horizons is None:
            horizons = [1, 3, 5]
        
        all_signals = []
        
        for stock_code, stock_name, event_code, event_date, returns in events:
            for H in horizons:
                signal = self.detect_gap(
                    stock_code, stock_name, event_code,
                    event_date, returns, H
                )
                if signal:
                    all_signals.append(signal)
        
        logger.info(f"배치 탐지 완료: {len(all_signals)}개 신호")
        return all_signals
    
    def _calculate_percentile(
        self, 
        value: float, 
        event_code: str, 
        horizon: int
    ) -> float:

        import pymysql
        
        conn = None
        try:
            conn = pymysql.connect(**self.model.db_config)
            
            with conn.cursor() as cursor:
                # 현재 값보다 작은 샘플 수
                sql_below = f"""
                    SELECT COUNT(*) as count
                    FROM event_returns_history
                    WHERE event_code = %s
                      AND return_{horizon}d IS NOT NULL
                      AND return_{horizon}d < %s
                """
                cursor.execute(sql_below, (event_code, value))
                below_count = cursor.fetchone()[0]
                
                # 전체 샘플 수
                sql_total = f"""
                    SELECT COUNT(*) as count
                    FROM event_returns_history
                    WHERE event_code = %s
                      AND return_{horizon}d IS NOT NULL
                """
                cursor.execute(sql_total, (event_code,))
                total_count = cursor.fetchone()[0]
                
                if total_count == 0:
                    return 0.5  # 중립
                
                percentile = below_count / total_count
                
                logger.debug(
                    f"백분위 계산: {event_code} H={horizon}, "
                    f"val={value:.4f}, pct={percentile:.2f}"
                )
                
                return percentile
        
        except Exception as e:
            logger.error(f"백분위 계산 실패: {e}", exc_info=True)
            return 0.5  # 실패 시 중립
        
        finally:
            if conn:
                conn.close()
