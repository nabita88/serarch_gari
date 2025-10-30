
from __future__ import annotations
import logging
import os
from typing import List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """분류 결과 데이터 클래스"""
    labels: List[str] = field(default_factory=list)
    phrases: List[str] = field(default_factory=list)
    confidence: float = 0.0
    raw_response: str = ""
    source: str = "none"  # "hyperclova" | "chatgpt" | "both" | "none"
    error: Optional[str] = None  # 에러 메시지 (있을 경우)


class SafeClassifierWrapper:
    """에러 처리가 내장된 분류기 래퍼"""

    def __init__(self):
        self.hcx_classifier = None
        self.gpt_available = bool(os.getenv("OPENAI_API_KEY"))
        self._init_failed = False

    def initialize_hyperclova(self) -> bool:

        if self.hcx_classifier is not None:
            return True

        if self._init_failed:
            return False

        try:
            from munci.lastsa.event_extractor.stock_event_label_classifier import StockEventLabelClassifier
            self.hcx_classifier = StockEventLabelClassifier()
            logger.info("[HCX] Classifier initialized successfully")
            return True
        except ImportError as e:
            logger.warning(f"[HCX] Module not found: {e}")
            self._init_failed = True
            return False
        except Exception as e:
            logger.error(f"[HCX] Initialization failed: {e}", exc_info=True)
            self._init_failed = True
            return False

    def classify_with_hyperclova(self, text: str) -> ClassificationResult:

        if not text or not text.strip():
            logger.warning("[HCX] Empty text provided")
            return ClassificationResult(error="Empty input text")

        if not self.initialize_hyperclova():
            return ClassificationResult(error="HyperCLOVA not available")

        try:
            result = self.hcx_classifier.classify_event(text)

            labels = getattr(result, "labels", None)
            if labels is None or not isinstance(labels, list):
                logger.warning(f"[HCX] Invalid labels format: {labels}")
                labels = []

            confidence = getattr(result, "confidence", 0.0)
            try:
                confidence = float(confidence)
                if not (0.0 <= confidence <= 1.0):
                    logger.warning(f"[HCX] Confidence out of range: {confidence}")
                    confidence = max(0.0, min(1.0, confidence))
            except (TypeError, ValueError):
                logger.warning(f"[HCX] Invalid confidence value: {confidence}")
                confidence = 0.0

            raw = str(getattr(result, "raw_response", ""))

            logger.info(f"[HCX] Success: labels={labels}, conf={confidence:.2f}")
            return ClassificationResult(
                labels=labels,
                confidence=confidence,
                raw_response=raw,
                source="hyperclova"
            )

        except AttributeError as e:
            logger.error(f"[HCX] Result attribute error: {e}")
            return ClassificationResult(error=f"Invalid result format: {e}")
        except Exception as e:
            logger.error(f"[HCX] Classification error: {e}", exc_info=True)
            return ClassificationResult(error=str(e))

    def classify_with_chatgpt(self, text: str) -> ClassificationResult:

        if not text or not text.strip():
            logger.warning("[GPT] Empty text provided")
            return ClassificationResult(error="Empty input text")

        if not self.gpt_available:
            logger.debug("[GPT] OPENAI_API_KEY not set")
            return ClassificationResult(error="OpenAI API key not configured")

        try:
            from munci.lastsa.event_with_translate import classify_event_by_chatgpt
        except ImportError as e:
            logger.error(f"[GPT] Module import failed: {e}")
            return ClassificationResult(error=f"Import error: {e}")

        try:
            result = classify_event_by_chatgpt(text)

            if not result or not isinstance(result, dict):
                logger.warning(f"[GPT] Invalid result format: {type(result)}")
                return ClassificationResult(error="Invalid API response")

            phrases = result.get("events")
            if phrases is None or not isinstance(phrases, list):
                logger.warning(f"[GPT] Invalid events format: {phrases}")
                phrases = []

            confidence = result.get("confidence", 0.0)
            try:
                confidence = float(confidence)
                confidence = max(0.0, min(1.0, confidence))
            except (TypeError, ValueError):
                logger.warning(f"[GPT] Invalid confidence: {confidence}")
                confidence = 0.0

            raw = str(result.get("raw_response", ""))

            logger.info(f"[GPT] Success: phrases={phrases}, conf={confidence:.2f}")
            return ClassificationResult(
                labels=["other"],
                phrases=phrases,
                confidence=confidence,
                raw_response=raw,
                source="chatgpt"
            )

        except Exception as e:
            logger.error(f"[GPT] Classification error: {e}", exc_info=True)
            return ClassificationResult(error=str(e))

    def classify(self, text: str) -> ClassificationResult:

        if not text or not text.strip():
            logger.warning("[CLASSIFY] Empty text provided")
            return ClassificationResult(
                labels=["other"],
                error="Empty input text"
            )

        logger.info(f"[CLASSIFY] Starting: '{text[:50]}...'")

        # 1. HyperCLOVA 시도
        hcx_result = self.classify_with_hyperclova(text)

        # 2. ChatGPT 시도
        gpt_result = self.classify_with_chatgpt(text)

        # 3. 결과 통합
        merged = self._merge_results(hcx_result, gpt_result)

        logger.info(
            f"[CLASSIFY] Final: source={merged.source}, "
            f"labels={merged.labels}, phrases={merged.phrases}"
        )

        return merged

    def _merge_results(
            self,
            hcx: ClassificationResult,
            gpt: ClassificationResult
    ) -> ClassificationResult:

        hcx_valid = hcx.labels and hcx.labels != ["other"] and not hcx.error
        gpt_valid = gpt.phrases and not gpt.error

        # 케이스 1: 둘 다 성공
        if hcx_valid and gpt_valid:
            logger.info("[CLASSIFY] Using BOTH results")
            return ClassificationResult(
                labels=hcx.labels,
                phrases=gpt.phrases,
                confidence=max(hcx.confidence, gpt.confidence),
                raw_response=f"HCX: {hcx.raw_response}\nGPT: {gpt.raw_response}",
                source="both"
            )

        # 케이스 2: HCX만 성공
        if hcx_valid:
            logger.info("[CLASSIFY] Using HyperCLOVA only")
            return hcx

        # 케이스 3: GPT만 성공
        if gpt_valid:
            logger.info("[CLASSIFY] Using ChatGPT only")
            return gpt

        # 케이스 4: 둘 다 실패
        logger.warning("[CLASSIFY] Both classifiers failed")
        error_msg = f"HCX: {hcx.error or 'N/A'}, GPT: {gpt.error or 'N/A'}"
        return ClassificationResult(
            labels=["other"],
            error=error_msg
        )


# 싱글톤 인스턴스
_wrapper: Optional[SafeClassifierWrapper] = None


def get_classifier_wrapper() -> SafeClassifierWrapper:

    global _wrapper
    if _wrapper is None:
        _wrapper = SafeClassifierWrapper()
        logger.info("[WRAPPER] SafeClassifierWrapper initialized")
    return _wrapper


def reset_wrapper():
    """테스트용: 래퍼 초기화"""
    global _wrapper
    _wrapper = None
