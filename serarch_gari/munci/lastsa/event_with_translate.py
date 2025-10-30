from __future__ import annotations
import os, json, re, logging, threading
from typing import List, Optional, Dict, Any
from openai import OpenAI

# 공통 에러 핸들러 임포트
from munci.main_utils.error_handlers import (
    handle_api_error,
    handle_json_parse_error,
    APIErrorHandler
)

logger = logging.getLogger(__name__)


class UnifiedEventResult:
    """이벤트 분류 결과를 담는 데이터 클래스"""

    def __init__(self, labels: List[str], event_phrases: List[str], confidence: float, source: str, raw_response: str):
        self.labels = labels
        self.event_phrases = event_phrases
        self.confidence = confidence
        self.source = source
        self.raw_response = raw_response


try:
    from munci.lastsa.event_extractor.stock_event_label_classifier import StockEventLabelClassifier

    STOCK_EVENT_CLASSIFIER_AVAILABLE = True
except ImportError as e:
    StockEventLabelClassifier = None
    STOCK_EVENT_CLASSIFIER_AVAILABLE = False
    logger.warning(f"StockEventLabelClassifier module not found: {e}")

_event_classifier: Optional[object] = None
_lock = threading.Lock()  # Thread-Safe 보장

TRANSLATE_MODEL = os.getenv("OPENAI_TRANSLATE_MODEL", "gpt-5-mini")
EVENT_POST_TRANSLATE_TO = os.getenv("EVENT_POST_TRANSLATE_TO")


def initialize_event_classifier():
    """
    Thread-Safe 이벤트 분류기 초기화
    Lifespan에서 1번 호출되지만, 다른 곳에서도 안전하게 사용 가능
    """
    global _event_classifier

    # Double-Checked Locking Pattern
    if _event_classifier is None:
        with _lock:
            if _event_classifier is None and STOCK_EVENT_CLASSIFIER_AVAILABLE:
                try:
                    _event_classifier = StockEventLabelClassifier()
                    logger.info("StockEventLabelClassifier initialized.")
                except Exception as e:
                    logger.exception("Failed to init StockEventLabelClassifier: %s", e)

    return _event_classifier


@handle_api_error(default_return="", error_msg="GPT 번역 실패")
def _translate_with_gpt(client: Optional[OpenAI], text: str, target_lang: str) -> str:
    """GPT를 사용한 번역"""
    if not client or not target_lang or not text:
        return ""

    resp = client.chat.completions.create(
        model=TRANSLATE_MODEL,
        temperature=0,
        max_tokens=400,
        messages=[
            {"role": "system",
             "content": f"You are a professional translation engine. Translate into {target_lang}. Output only the translation. Preserve numbers and named entities."},
            {"role": "user", "content": text},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


@handle_json_parse_error(default_return={})
def _extract_json_block(text: str, expect_array: bool = False):
    """텍스트에서 JSON 블록 추출"""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.MULTILINE).strip()
    m = re.search(r"(\{.*\}|\[.*\])", t, flags=re.DOTALL)
    if not m:
        return [] if expect_array else {}

    data = json.loads(m.group(1))
    return data if isinstance(data, (list, dict)) else ([] if expect_array else {})


@APIErrorHandler.handle_openai_error
def classify_event_by_chatgpt(text: str) -> Dict[str, Any]:
    """ChatGPT를 사용한 이벤트 분류"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[GPT] OPENAI_API_KEY not found")
        return {}

    logger.info(f"[GPT] Starting classification for: {text[:50]}...")

    client = OpenAI(api_key=api_key)
    logger.debug("[GPT] OpenAI client initialized")

    SYSTEM_MSG = (
        "너는 금융/산업 뉴스의 '구체적 사건(event)'을 추출하는 전문가다. "
        "**중요: 모든 응답은 반드시 한국어로만 작성한다.** "
        "출력은 오직 JSON 객체 하나만 허용한다(코드블록/설명/주석/여분 텍스트 금지). "
        "스키마: {\"events\": <문자열 배열, 길이 0~2>, \"confidence\": <0~1 float>, \"reason\": <짧은 한국어 문장>}. "
        "events에는 제목에 실제로 존재하는 한국어 단어를 그대로 사용한 '핵심 명사구'만 넣는다(새 단어/의역/영어 번역 금지). "
        "reason도 반드시 한국어로 작성한다."
    )

    user_prompt = f"""아래 뉴스 제목에서 실제 일어난 사건을 나타내는 '핵심 명사/명사구'를 최대 2개 추출하세요.
**주의: 모든 결과는 반드시 한국어로 작성해야 합니다.**

뉴스 제목: {text}

출력 형식(JSON-only, 한국어):
{{"events": ["이벤트1"], "confidence": 0.90, "reason": "간단 근거"}}

응답:"""

    messages = [
        {"role": "system", "content": SYSTEM_MSG},
        {"role": "user", "content": "뉴스 제목: Samsung Electronics announces Q3 earnings\n\n출력 형식(JSON-only, 한국어):"},
        {"role": "assistant", "content": '{"events": ["Q3 실적 발표"], "confidence": 0.85, "reason": "제목에 명시됨"}'},
        {"role": "user", "content": user_prompt},
    ]

    logger.debug("[GPT] Calling OpenAI API with model: gpt-4-turbo-preview")

    resp = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=messages,
        temperature=0,
        max_tokens=200,
    )

    logger.info("[GPT] API call successful")

    content = (resp.choices[0].message.content or "").strip()
    logger.debug(f"[GPT] Raw response: {content}")

    data = _extract_json_block(content, expect_array=False)

    if isinstance(data, dict):
        data["raw_response"] = content

        if EVENT_POST_TRANSLATE_TO:
            try:
                data["events_translated"] = [
                    _translate_with_gpt(client, e, EVENT_POST_TRANSLATE_TO)
                    for e in data.get("events", [])
                ]
                data["reason_translated"] = _translate_with_gpt(
                    client, data.get("reason", ""), EVENT_POST_TRANSLATE_TO
                )
            except Exception:
                logger.exception("post-translation step failed")

        if not isinstance(data.get("events", []), list):
            data["events"] = []
        if not isinstance(data.get("confidence", 0.0), (int, float)):
            data["confidence"] = 0.0
        if not isinstance(data.get("reason", ""), str):
            data["reason"] = ""

        seen = set()
        cleaned = []
        for e in data["events"]:
            if isinstance(e, str):
                t = e.strip()
                # 한국어 포함 여부 검증 (선택적)
                if t and t not in seen:
                    # 한글이 하나라도 있으면 통과
                    has_korean = any('\uac00' <= c <= '\ud7a3' for c in t)
                    if has_korean or not t.isascii():  # 한글 또는 비ASCII
                        cleaned.append(t)
                        seen.add(t)
                    else:
                        logger.warning(f"[GPT] 영어 이벤트 감지, 제외: {t}")
            if len(cleaned) >= 2:
                break
        data["events"] = cleaned

        try:
            c = float(data.get("confidence", 0.0))
            if c < 0: c = 0.0
            if c > 1: c = 1.0
            data["confidence"] = round(c, 2)
        except Exception:
            data["confidence"] = 0.0

        logger.info(f"[GPT] Extracted: events={data.get('events')}, confidence={data.get('confidence')}")
        return data

    logger.warning("[GPT] Failed to parse response as dict")
    return {}


def classify_event(text: str) -> UnifiedEventResult:
    """통합 이벤트 분류 - StockEventLabelClassifier 우선, ChatGPT 보조"""
    from munci.rumerapi.utils.classifier_wrapper import get_classifier_wrapper

    # 래퍼를 통해 안전하게 분류
    wrapper = get_classifier_wrapper()
    result = wrapper.classify(text)

    # UnifiedEventResult로 변환
    return UnifiedEventResult(
        labels=result.labels,
        event_phrases=result.phrases,
        confidence=result.confidence,
        source=result.source,
        raw_response=result.raw_response
    )
