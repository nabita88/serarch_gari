from __future__ import annotations
from typing import Dict, Any, List
import time
import json as json_lib
import http.client

def _retry(extractor, fn, max_retries=None, delay=None):
    """재시도 로직"""
    max_retries = max_retries or extractor.HYPERCLOVA_MAX_RETRIES
    delay = delay or extractor.HYPERCLOVA_RETRY_DELAY
    for i in range(max_retries):
        result = fn()
        if result and result.get("content"):
            return result
        error_type = result.get("error", "") if result else ""
        if error_type in ["no_api_key", "auth_failed", "http_400", "http_401", "http_403"]:
            extractor.logger.error(f"재시도 불가능한 오류: {error_type}")
            return result
        if error_type == "rate_limit":
            wait = 1
            print(f"   API 요청 한도 초과 (시도 {i + 1}/{max_retries}), {wait}초 대기 중...")
            time.sleep(wait)
        else:
            print(f"   API 호출 실패 (시도 {i + 1}/{max_retries}), {delay}초 대기 중...")
            time.sleep(delay)
    return {}

def _extract_with_hyperclova(extractor, text: str) -> List[str]:
    """HyperCLOVA X를 사용하여 회사명 추출"""
    user_prompt = f"""
        [작업]
        - 아래 텍스트에서 회사명을 모두 추출하고, 제공된 정규화 사전을 우선 적용해 **canonicalName**으로 통일한다.
        - 사전에 없거나 애매하면 '모호한 그룹 키워드 귀속' 규칙을 문맥에 맞게 적용한다.

        [입력 텍스트]
        {text}

        [도메인/제약]
        - 언어: ko
        - 도메인: 증권/IR/공시/뉴스 헤드라인
        - 제외: 기술명/서비스명/제품명/정부기관/해외지수/언론사 등 비-회사명
        - "현대에는/삼성에서/LG는"과 같이 그룹명 단독+조사만 있는 경우는 추출하지 않음

        [출력 형식(엄수)]
        - **오직 JSON만** 출력. 설명/코드블록/추가 문장 금지.
        - 스키마: {{"entities": ["<정규화된 회사명>", "..."]}}
        - 정렬: 텍스트 **등장 순서**. 중복 제거.
        - 기업명이 없으면 {{"entities": []}}.

        [검증용 예시(출력에 포함 금지)]
        - "네이버와 카카오, 쿠팡이 이커머스 시장을 주도한다."
          → {{"entities":["네이버","카카오","쿠팡"]}}
        - "현대에는 현대차와 기아가 전기차 시장에서 경쟁하고 있다."
          → {{"entities":["현대자동차","기아"]}}
    """
    response = _retry(extractor, lambda: _call_hyperclova_x(extractor, user_prompt))
    if response and response.get("error"):
        et = response.get("error", "unknown")
        emap = {
            "rate_limit": "HyperCLOVA API rate limit exceeded (429)",
            "http_500": "HyperCLOVA API server error (500)",
            "http_502": "HyperCLOVA API bad gateway (502)",
            "http_503": "HyperCLOVA API service unavailable (503)",
            "http_504": "HyperCLOVA API gateway timeout (504)",
            "timeout": "HyperCLOVA API timeout",
            "connection": "HyperCLOVA API connection error",
            "json_decode_error": "HyperCLOVA API JSON decode error"
        }
        if et in emap:
            raise Exception(emap[et])
        elif et in ["no_api_key", "auth_failed", "http_401", "http_403"]:
            raise Exception(f"HyperCLOVA API authentication error: {et}")
        elif et == "http_400":
            raise Exception(f"HyperCLOVA API bad request: {et}")
        elif et.startswith("http_"):
            raise Exception(f"HyperCLOVA API error: {et}")
        else:
            raise Exception(f"HyperCLOVA API unknown error: {et}")

    if response and response.get("content"):
        return _parse_company_list_from_llm(response["content"])
    return []

def _call_hyperclova_x(extractor, user_text: str) -> Dict[str, Any]:
    """HyperCLOVA X API 호출"""
    if not extractor.clova_api_key:
        extractor.logger.warning("CLOVA API 키가 설정되지 않았습니다.")
        return {"status": 0, "error": "no_api_key"}

    host = "clovastudio.stream.ntruss.com"
    path = "/v3/chat-completions/HCX-007"

    headers = {
        "Authorization": f"Bearer {extractor.clova_api_key}",
        "Content-Type": "application/json"
    }

    body = {
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": extractor.HYPERCLOVA_SYSTEM_PROMPT}]},
            {"role": "user", "content": [{"type": "text", "text": user_text}]}
        ],
        "thinking": {"effort": "none"},
        "topP": 0.8,
        "topK": 0,
        "temperature": 0.2,
        "repetitionPenalty": 1.1,
        "maxCompletionTokens": 512,
        "includeAiFilters": False
    }

    try:
        conn = http.client.HTTPSConnection(host, timeout=30)
        conn.request("POST", path, json_lib.dumps(body), headers)
        resp = conn.getresponse()
        data = resp.read().decode("utf-8", errors="ignore")
        conn.close()

        if resp.status == 429:
            extractor.logger.warning("API 요청 한도 초과 (429)")
            return {"error": "rate_limit"}
        elif resp.status == 401:
            extractor.logger.error("API 인증 실패 (401)")
            return {"error": "http_401"}
        elif resp.status == 403:
            extractor.logger.error("API 접근 권한 없음 (403)")
            return {"error": "http_403"}
        elif resp.status == 400:
            extractor.logger.error(f"API 잘못된 요청 (400): {data[:200]}")
            return {"error": "http_400"}
        elif resp.status == 500:
            extractor.logger.error("API 서버 에러 (500)")
            return {"error": "http_500"}
        elif resp.status == 502:
            extractor.logger.error("API Bad Gateway (502)")
            return {"error": "http_502"}
        elif resp.status == 503:
            extractor.logger.error("API Service Unavailable (503)")
            return {"error": "http_503"}
        elif resp.status == 504:
            extractor.logger.error("API Gateway Timeout (504)")
            return {"error": "http_504"}
        elif resp.status != 200:
            extractor.logger.error(f"API 호출 실패 - HTTP {resp.status}: {data[:200]}")
            return {"error": f"http_{resp.status}"}

        obj = json_lib.loads(data)
        content = obj.get("result", {}).get("message", {}).get("content")
        return {"content": content, "raw": obj}

    except json_lib.JSONDecodeError as e:
        extractor.logger.error(f"API 응답 파싱 실패: {e}")
        return {"error": "json_decode_error"}
    except http.client.HTTPException as e:
        extractor.logger.error(f"HTTP 연결 오류: {e}")
        return {"error": "connection"}
    except TimeoutError as e:
        extractor.logger.error(f"API 호출 타임아웃: {e}")
        return {"error": "timeout"}
    except Exception as e:
        extractor.logger.error(f"HCX-007 호출 중 예외 발생: {e}")
        return {"error": str(e)}

def _parse_company_list_from_llm(content: str):
    """LLM 응답에서 회사명 리스트 파싱"""
    try:
        # JSON 배열 형식 파싱 시도
        if '[' in content and ']' in content:
            start = content.find('[')
            end = content.rfind(']') + 1
            j = content[start:end]
            arr = json_lib.loads(j)
            if isinstance(arr, list):
                return [str(c).strip() for c in arr if c and str(c).strip()]
        
        # 줄 단위 파싱 폴백
        lines = content.split('\n')
        res = []
        import re
        for line in lines:
            line = line.strip()
            line = re.sub(r'^[-*•\d.)\s]+', '', line)
            line = re.sub(r'["\'\[\],]', '', line)
            if line and len(line) >= 2 and not line.startswith(('응답', '회사', '기업')):
                res.append(line)
        return res
    except Exception:
        return []
