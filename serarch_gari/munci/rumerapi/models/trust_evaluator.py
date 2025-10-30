
from typing import Dict, List, Optional, Tuple
from enum import Enum


class TrustLevel(Enum):
    """신뢰도 레벨"""
    HIGH = "높음"
    MEDIUM = "중간"
    LOW = "낮음"
    VERY_LOW = "매우 낮음"


class TrustEvaluator:
    """검색 결과의 신뢰도를 평가하는 클래스"""
    
    def __init__(self):
        # 신뢰도 임계값 설정
        self.thresholds = {
            'high_confidence': 0.95,      # 95% 이상
            'medium_confidence': 0.60,    # 60% 이상
            'low_confidence': 0.30,        # 30% 이상
            'high_relevance': 0.80,        # 관련도 80% 이상
            'medium_relevance': 0.50,      # 관련도 50% 이상
            'min_exact_matches': 1,        # 최소 정확 매칭 수
        }
    
    def evaluate_search_result(self, search_result: Dict) -> Dict:

        # 기본 정보 추출
        has_news = self._has_valid_news(search_result)
        confidence = self._get_classification_confidence(search_result)
        relevance_scores = self._get_relevance_scores(search_result)
        exact_match_count = len(search_result.get('exact_matches', []))
        partial_match_count = len(search_result.get('partial_matches', []))
        
        # 신뢰도 결정
        trust_level, reason = self._determine_trust_level(
            has_news=has_news,
            confidence=confidence,
            relevance_scores=relevance_scores,
            exact_match_count=exact_match_count,
            partial_match_count=partial_match_count
        )
        
        # 신뢰도 점수 계산 (0-100)
        trust_score = self._calculate_trust_score(
            confidence=confidence,
            relevance_scores=relevance_scores,
            exact_match_count=exact_match_count,
            has_news=has_news
        )
        
        # 결과 구성
        result = {
            'trust_level': trust_level.value,
            'trust_score': trust_score,
            'confidence': confidence,
            'has_news': has_news,
            'news_count': len(search_result.get('matches', [])),
            'exact_matches': exact_match_count,
            'partial_matches': partial_match_count,
            'avg_relevance': sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0,
            'reason': reason,
            'details': self._create_detailed_report(
                trust_level, trust_score, confidence, 
                has_news, exact_match_count, relevance_scores
            )
        }
        
        return result
    
    def _has_valid_news(self, search_result: Dict) -> bool:
        """유효한 뉴스가 있는지 확인"""
        matches = search_result.get('matches', [])
        return len(matches) > 0 and search_result.get('status') == 'success'
    
    def _get_classification_confidence(self, search_result: Dict) -> float:
        """이벤트 분류 정확도 추출"""
        label_result = search_result.get('label_result', {})
        return label_result.get('confidence', 0.0)
    
    def _get_relevance_scores(self, search_result: Dict) -> List[float]:
        """관련도 점수 리스트 추출"""
        matches = search_result.get('matches', [])
        return [match.get('relevance_score', 0.0) for match in matches]
    
    def _determine_trust_level(self, 
                              has_news: bool,
                              confidence: float,
                              relevance_scores: List[float],
                              exact_match_count: int,
                              partial_match_count: int) -> Tuple[TrustLevel, str]:

        # 뉴스가 없는 경우
        if not has_news:
            return TrustLevel.LOW, "관련 뉴스를 찾을 수 없음"
        
        # 평균 관련도 계산
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
        max_relevance = max(relevance_scores) if relevance_scores else 0
        
        # 신뢰도 "높음" 조건
        if (confidence >= self.thresholds['high_confidence'] and 
            exact_match_count >= self.thresholds['min_exact_matches'] and
            max_relevance >= self.thresholds['high_relevance']):
            return TrustLevel.HIGH, f"높은 분류 정확도({confidence:.1%})와 정확한 매칭 {exact_match_count}건"
        
        # 신뢰도 "중간" 조건
        if (confidence >= self.thresholds['medium_confidence'] and 
            (exact_match_count > 0 or avg_relevance >= self.thresholds['medium_relevance'])):
            if exact_match_count > 0:
                return TrustLevel.MEDIUM, f"중간 수준의 정확도({confidence:.1%})와 매칭 결과"
            else:
                return TrustLevel.MEDIUM, f"부분 매칭만 존재 (관련도: {avg_relevance:.1%})"
        
        # 신뢰도 "낮음" 조건
        if confidence >= self.thresholds['low_confidence'] or partial_match_count > 0:
            return TrustLevel.LOW, f"낮은 분류 정확도({confidence:.1%}) 또는 부분 매칭만 존재"
        
        # 신뢰도 "매우 낮음"
        return TrustLevel.VERY_LOW, "분류 정확도가 매우 낮고 정확한 매칭이 없음"
    
    def _calculate_trust_score(self,
                              confidence: float,
                              relevance_scores: List[float],
                              exact_match_count: int,
                              has_news: bool) -> float:
        """
        종합 신뢰도 점수 계산 (0-100)
        """
        if not has_news:
            return 0.0
        
        # 가중치 설정
        weights = {
            'confidence': 0.4,      # 분류 정확도 40%
            'relevance': 0.3,       # 관련도 30%
            'exact_match': 0.2,     # 정확 매칭 20%
            'news_count': 0.1       # 뉴스 개수 10%
        }
        
        # 각 요소 점수 계산
        confidence_score = confidence * 100
        
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
        relevance_score = avg_relevance * 100
        
        exact_match_score = min(100, exact_match_count * 33.33)  # 3개 이상이면 100점
        
        news_count_score = min(100, len(relevance_scores) * 20)  # 5개 이상이면 100점
        
        # 가중 평균 계산
        trust_score = (
            confidence_score * weights['confidence'] +
            relevance_score * weights['relevance'] +
            exact_match_score * weights['exact_match'] +
            news_count_score * weights['news_count']
        )
        
        return round(trust_score, 1)
    
    def _create_detailed_report(self,
                               trust_level: TrustLevel,
                               trust_score: float,
                               confidence: float,
                               has_news: bool,
                               exact_match_count: int,
                               relevance_scores: List[float]) -> str:
        """상세 보고서 생성"""
        
        # 이모지 매핑
        emoji_map = {
            TrustLevel.HIGH: "✅",
            TrustLevel.MEDIUM: "⚠️",
            TrustLevel.LOW: "❌",
            TrustLevel.VERY_LOW: "⛔"
        }
        
        # 색상 표시 (터미널용)
        color_map = {
            TrustLevel.HIGH: "\033[92m",      # 녹색
            TrustLevel.MEDIUM: "\033[93m",    # 노란색
            TrustLevel.LOW: "\033[91m",       # 빨간색
            TrustLevel.VERY_LOW: "\033[95m"   # 보라색
        }
        color_reset = "\033[0m"
        
        report = []
        report.append(f"\n{'='*60}")
        report.append(f"{emoji_map[trust_level]} 신뢰도 평가 결과")
        report.append(f"{'='*60}")
        
        # 메인 결과
        report.append(f"{color_map[trust_level]}신뢰도: {trust_level.value}{color_reset}")
        report.append(f"종합 점수: {trust_score:.1f}/100")
        
        # 세부 지표
        report.append(f"\n📊 세부 지표:")
        report.append(f"  • 분류 정확도: {confidence:.1%}")
        report.append(f"  • 검색 결과: {'있음' if has_news else '없음'}")
        
        if has_news:
            avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
            max_relevance = max(relevance_scores) if relevance_scores else 0
            
            report.append(f"  • 정확 매칭: {exact_match_count}건")
            report.append(f"  • 평균 관련도: {avg_relevance:.1%}")
            report.append(f"  • 최고 관련도: {max_relevance:.1%}")
            report.append(f"  • 총 검색 결과: {len(relevance_scores)}건")
        
        # 신뢰도 해석
        report.append(f"\n💡 해석:")
        if trust_level == TrustLevel.HIGH:
            report.append("  높은 신뢰도로 해당 뉴스/이벤트가 존재합니다.")
            report.append("  검색 결과를 신뢰하고 활용할 수 있습니다.")
        elif trust_level == TrustLevel.MEDIUM:
            report.append("  중간 수준의 신뢰도입니다.")
            report.append("  추가 검증이나 확인이 필요할 수 있습니다.")
        elif trust_level == TrustLevel.LOW:
            report.append("  신뢰도가 낮습니다.")
            report.append("  검색 결과가 부정확하거나 관련성이 낮을 수 있습니다.")
        else:
            report.append("  매우 낮은 신뢰도입니다.")
            report.append("  검색 결과를 신뢰하기 어렵습니다.")
        
        report.append(f"{'='*60}\n")
        
        return "\n".join(report)
    
    def get_simple_trust(self, search_result: Dict) -> str:
        """
        간단한 신뢰도만 반환 (높음/중간/낮음)
        """
        evaluation = self.evaluate_search_result(search_result)
        return evaluation['trust_level']
    
    def print_trust_evaluation(self, search_result: Dict) -> None:
        """
        신뢰도 평가 결과를 출력
        """
        evaluation = self.evaluate_search_result(search_result)
        print(evaluation['details'])
        return evaluation

