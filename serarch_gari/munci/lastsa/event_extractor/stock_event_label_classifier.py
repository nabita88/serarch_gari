

import os
import re
import ast
import json
import time
import uuid
import logging
import http.client
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from textwrap import dedent

from dotenv import load_dotenv
from munci.lastsa.event_extractor.labels_config import get_registry  # 사용 환경에 존재해야 함



@dataclass
class LabelResult:
    labels: List[str]
    confidence: float
    reason: str = ""
    raw_response: str = ""


class StockEventLabelClassifier:

    def __init__(self):
        self._load_env_config()
        self._setup_logging()
        self._load_label_registry()
        self.system_prompt = self._build_system_prompt()

        print("Stock Event Label Classifier 초기화 완료!")
        print("HyperCLOVA X API 연결 설정됨" if self.clova_api_key else "CLOVA_API_KEY가 설정되지 않음 - .env 또는 환경변수 확인 필요")
        print(f"   - Host: {self.clova_api_host}")
        print(f"   - Model: {self.clova_model_id}")
        print(f"   - Priority Profile: {self.priority_profile or 'disabled'}")
        print(f"   - API 호출 간격: {self.min_api_interval:.0f}초 (분당 {60.0 / self.min_api_interval:.1f}회)")

    def _load_env_config(self) -> None:
        """환경변수 로드 및 기본 설정"""
        load_dotenv()

        # API / 모델
        self.clova_api_key: str = (os.getenv("CLOVA_API_KEY", "") or "").strip()
        self.clova_api_host: str = os.getenv("CLOVA_API_HOST", "clovastudio.stream.ntruss.com").strip()
        self.app_type: str = os.getenv("CLOVA_APP_TYPE", "testapp").strip()  # testapp | serviceapp
        env_model = (os.getenv("CLOVA_MODEL_ID", "HCX-007") or "HCX-007").strip().upper()
        if env_model != "HCX-007":
            print(f"CLOVA_MODEL_ID={env_model} -> HCX-007로 강제 고정합니다.")
        self.clova_model_id: str = "HCX-007"  # 고정

        # 호출 간격
        rate_per_min = float(os.getenv("CLOVA_RATE_LIMIT_PER_MIN", "15"))
        self.min_api_interval: float = 60.0 / rate_per_min if rate_per_min > 0 else 3.0

        # 프로파일
        self.priority_profile = (os.getenv("PRIORITY_PROFILE", "intraday_kr") or "").strip()
        if self.priority_profile.lower() in {"", "none", "off"}:
            self.priority_profile = None

        # 프롬프트 옵션
        try:
            self.prompt_top_examples = int(os.getenv("PROMPT_TOP_EXAMPLES", "12"))
        except Exception:
            self.prompt_top_examples = 12

    def _setup_logging(self) -> None:
        """로깅 초기화 — 중복 핸들러 제거"""
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_dir / "label_classifier.log", encoding="utf-8"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("LabelClassifier")

    def _load_label_registry(self) -> None:
        """레지스트리를 로드하고 파생 속성 생성"""
        self.registry = get_registry(self.priority_profile)
        self.valid_labels, self.compiled_triggers, self.fine_first, self.priority_rank = self._build_label_registry(
            self.registry
        )

    def _build_label_registry(self, registry: dict):
        """레지스트리 파생: (1) 유효 라벨, (2) 컴파일된 트리거, (3) 세분 목록, (4) 우선순위 매핑"""
        import re as _re

        # 1) 라벨 키 소문자 정규화
        norm = {}
        for name, spec in registry.items():
            if not isinstance(name, str):
                continue
            lname = name.strip().lower()
            if not lname:
                continue
            norm[lname] = dict(spec or {})

        # 2) 유효 라벨 집합
        valid = set(norm.keys())

        # 3) 트리거 정규식
        compiled_triggers = {}
        for lname, spec in norm.items():
            pats = spec.get("triggers") or []
            if pats:
                compiled_triggers[lname] = [_re.compile(p, _re.I) for p in pats]

        # 4) 세분 라벨 + 우선순위
        fine_first = [lname for lname, spec in norm.items() if spec.get("fine")]
        priority_rank = {lname: int(spec.get("priority", 10 ** 6)) for lname, spec in norm.items()}

        return valid, compiled_triggers, fine_first, priority_rank

    def _build_system_prompt(self) -> str:
        """허용 라벨(화이트리스트) 및 우선 라벨을 포함한 시스템 프롬프트 생성"""
        allowed = sorted(self.valid_labels | {"other"})  # other 포함
        allowed_str = ", ".join(allowed)

        topN = [name for name, _ in
                sorted(self.priority_rank.items(), key=lambda kv: int(kv[1]))[: self.prompt_top_examples]]
        top_names = ", ".join(topN)

        prompt = dedent("""
            너는 한국 주식시장 뉴스 분류 전문가다. 뉴스 제목을 보고 정확한 이벤트 라벨을 부여한다.

            ### 핵심 분류 규칙 (매우 중요) ###
            1. M&A/인수합병 → company.mna_deal (인수, 합병, M&A, 지분인수 등)
            2. 대규모 계약/수주 → company.big_contract_update (공급계약, 수주, 납품계약 등)
            3. 반도체 생산/기술 → sector.semicon_node_transition (양산, 수율, HBM, 공정 등)
            4. 바이오 임상 → sector.biotech_clinical_result (임상, 1/2/3상, 탑라인 등)
            5. 바이오 승인 → sector.biotech_regulatory (FDA, EMA, 허가/승인 등)
            6. 주식분할 → company.stock_split (액면분할/역분할 등)
            7. 실적 발표 → company.earnings_result (영업익/매출, 컨센서스, 흑/적전 등)
            8. 가이던스 → company.guidance_update (가이던스/전망 상향·하향 등)
            9. 증권사 의견 → analyst.target_price / analyst.rating_change (목표가/투자의견 등)
            10. 지수 편입/편출 → flow.index_inout (KOSPI200/KOSDAQ150 편입/편출 등)
            11. 회사 법률 위반→ company.violation_of_law (법률위반/압수수색/구속 등)
            12. 유상증자/주주배정/3자배정 → company.capital_increase_rights
            13. 무상증자/주식배당 → company.bonus_issue
            14. 감자/자본감소 → company.capital_reduction
            15. 유무상증자 혼합 → company.capital_increase_mixed
            16. 상각형 조건부자본증권(신종자본/AT1) 발행 → company.at1_issue
            17. 전환사채(CB)/신주인수권부사채(BW)/교환사채(EB) 발행 → 
            company.convertible_bond_issue / company.bw_issue / company.exchangeable_bond_issue
            18. 합병(흡수/신설) → company.mna_merger / 분할 → company.corporate_split / 
            주식교환·이전 → company.share_exchange_transfer / 분할합병 → company.split_merger
            19. 영업양수·양도 → company.business_acquisition / company.business_disposal
            20. 유형자산 양수·양도(토지/건물/설비 등) → company.tangible_asset_acquisition / company.tangible_asset_disposal
            21. 타법인 주식·출자증권 양수·양도 → company.equity_acquisition / company.equity_disposal
            22. 주권 관련 사채권 권리 양수·양도 → company.security_bond_rights_acq / company.security_bond_rights_disp
            23. 자산양수도(기타) → company.asset_transaction_misc / 풋백옵션 → company.putback_option
            24. 자기주식 취득/처분 → company.buyback_acquire / company.buyback_dispose
            25. 자사주 신탁 체결/해지 → company.buyback_trust_sign / company.buyback_trust_terminate
            26. 부도(디폴트) → company.default_event / 영업정지 → company.business_suspension / 
            회생절차 개시신청 → company.rehabilitation_apply / 해산사유 발생 → company.dissolution_cause
            27. 해외 증권시장 상장(ADR/GDR/나스닥 등) → company.listing_overseas
            28. 채권은행 관리절차(워크아웃) 개시/중단 → company.workout_start / company.workout_end

            ### 충돌 우선순위 규칙(3줄 고정) ###
            세분 > 포괄
            정확 키워드 > 일반 키워드
            법적/공시 용어 > 기사 관용어

            ### 출력 규칙(텍스트, 3줄만) ###
            - 아래 형식 그대로 **3줄만** 출력(설명·코드펜스·JSON·불필요 텍스트 금지)
            - 라벨은 반드시 화이트리스트의 **완전한 라벨명**만 사용, 최대 2개(쉼표로 구분)
            - 해당없음은 'other' 1개만 사용

            라벨: company.xxx[,company.yyy]
            정확도: 0.00~1.00 (예: 0.92)
            근거: 한국어 1~2문장으로 핵심 키워드/맥락 근거
        """).strip()
        return prompt

    def _build_messages(self, title: str, source: str = "") -> List[Dict]:
        """HCX 대화 메시지 생성 — content는 block 배열 구조 사용"""
        src = source if source else "N/A"
        user_prompt = (
            f"제목: {title}\n"
            f"출처: {src}\n\n"
            "반드시 아래 3줄 형식으로만 답변:\n"
            "라벨: company.xxx[,company.yyy]\n"
            "정확도: 0.00~1.00\n"
            "근거: 한국어 1~2문장\n"
            "- 1건이면 1개만, 2건 이상이면 상위 2개만\n"
            "- 허용 라벨 없으면 'other' 1개만\n"
        )
        return [
            {"role": "system", "content": [{"type": "text", "text": self.system_prompt}]},
            {"role": "user", "content": [{"type": "text", "text": user_prompt}]},
        ]


    def _clova_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.clova_api_key}",
            "Content-Type": "application/json",
            "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
        }

    def _extract_response_content(self, obj: dict) -> Tuple[str, Optional[str], Optional[dict]]:
        """API 응답에서 content, thinking, usage 추출"""
        result = obj.get("result") or {}
        message = result.get("message") or {}
        usage = obj.get("usage") or result.get("usage")
        content = message.get("content", "")
        thinking = message.get("thinkingContent")

        if isinstance(content, list):
            content = "\n".join(p.get("text", "") for p in content
                                if isinstance(p, dict) and p.get("type") == "text")
        if isinstance(thinking, list):
            thinking = "\n".join(p.get("text", "") for p in thinking
                                 if isinstance(p, dict) and p.get("type") == "text") or None
        if not content:
            alt = (result.get("outputText") or result.get("text") or result.get("output")
                   or obj.get("outputText") or "")
            if isinstance(alt, list):
                alt = "\n".join(str(x) for x in alt if x)
            content = str(alt)
        return content or "", thinking, usage

    def _make_api_body(self, messages: List[Dict[str, str]], token_key: str) -> dict:
        """API 요청 바디 생성 — HCX-007 기본값"""
        return {
            "messages": messages,
            "thinking": {"effort": "none"},
            "topP": 0.8,
            "topK": 0,
            "temperature": 0.2,
            "repetitionPenalty": 1.1,
            "maxCompletionTokens": 512,
            "includeAiFilters": False
        }

    def _http_request(self, path: str, token_key: str, messages: List[Dict[str, str]]) -> dict:
        """단일 HTTP 요청 실행 (재시도 없음)"""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.clova_api_host, timeout=30)
            payload = json.dumps(self._make_api_body(messages, token_key), ensure_ascii=False).encode("utf-8")
            headers = dict(self._clova_headers())
            conn.request("POST", path, payload, headers)
            resp = conn.getresponse()
            status = resp.status
            resp_headers = {k: v for (k, v) in resp.getheaders()}
            raw = resp.read().decode("utf-8", errors="ignore")
            return {"status": status, "headers": resp_headers, "raw": raw, "error": None}
        except Exception as e:
            self.logger.error(f"HCX-007 네트워크 예외: {e} (path={path})")
            return {"status": None, "headers": {}, "raw": str(e), "error": "network_error"}
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def _try_single_request(self, path: str, token_key: str, messages: List[Dict[str, str]],
                            max_retries: int, base_wait: float) -> dict:

        import random

        for attempt in range(max_retries + 1):
            result = self._http_request(path, token_key, messages)
            status = result["status"]
            resp_headers = result["headers"]
            raw = result["raw"]
            error = result["error"]

            # 네트워크 에러 → 재시도
            if error == "network_error":
                if attempt < max_retries:
                    time.sleep(base_wait * (2 ** attempt) + random.uniform(0, 0.4))
                    continue
                return {"ok": False, "status": None, "content": "", "thinking": None,
                        "usage": None, "headers": {}, "error": "network_error", "raw": raw}

            # 200 성공
            if status == 200:
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    return {"ok": False, "status": status, "content": "", "thinking": None,
                            "usage": None, "headers": resp_headers, "error": "json_decode_error", "raw": raw}
                content, thinking, usage = self._extract_response_content(obj)
                self.logger.info(f"HCX-007 OK")
                return {"ok": True, "status": status, "content": content, "thinking": thinking,
                        "usage": usage, "headers": resp_headers, "error": None, "raw": obj}

            # 404 → 경로 오류
            if status == 404:
                self.logger.error(f"HCX-007 404 경로 오류")
                return {"ok": False, "status": status, "content": "", "thinking": None,
                        "usage": None, "headers": resp_headers, "error": "http_404", "raw": raw}

            # 401 → 인증 실패
            if status == 401:
                self.logger.error(f"HCX-007 401 인증 실패")
                return {"ok": False, "status": status, "content": "", "thinking": None,
                        "usage": None, "headers": resp_headers, "error": "auth_failed", "raw": raw}

            # 429 Rate Limit → 재시도
            if status == 429 and attempt < max_retries:
                retry_after = resp_headers.get("Retry-After")
                try:
                    wait = float(retry_after) if retry_after else base_wait * (2 ** attempt)
                except Exception:
                    wait = base_wait * (2 ** attempt)
                time.sleep(max(1.0, wait))
                continue

            # 5xx 서버 에러 → 재시도
            if status and status >= 500 and attempt < max_retries:
                time.sleep(base_wait * (2 ** attempt) + random.uniform(0, 0.4))
                continue

            # 기타 에러 (400 포함)
            self.logger.error(f"HCX-007 오류 (HTTP {status}): {str(raw)[:200]}")
            return {"ok": False, "status": status, "content": "", "thinking": None,
                    "usage": None, "headers": resp_headers, "error": f"http_{status}", "raw": raw}

        # 재시도 소진
        return {"ok": False, "status": status, "content": "", "thinking": None,
                "usage": None, "headers": resp_headers, "error": "max_retries_exceeded", "raw": raw}

    def _call_hyperclova_x(self, messages: List[Dict[str, str]]) -> dict:

        if not self.clova_api_key:
            self.logger.warning("CLOVA API 키가 설정되지 않았습니다.")
            return {"ok": False, "status": None, "content": "", "thinking": None,
                    "usage": None, "headers": {}, "error": "missing_api_key", "raw": None}

        token_key = "maxCompletionTokens"
        max_retries = 2
        base_wait = 1.2

        tried = []

        # 1) app_type 경로 우선 시도
        if self.app_type in {"testapp", "serviceapp"}:
            path1 = f"/{self.app_type}/v3/chat-completions/{self.clova_model_id}"
            r1 = self._try_single_request(path1, token_key, messages, max_retries, base_wait)
            tried.append(("app_path", r1))
            if r1.get("ok") or r1.get("error") != "http_404":
                return r1

        # 2) 일반 경로 폴백
        path2 = f"/v3/chat-completions/{self.clova_model_id}"
        r2 = self._try_single_request(path2, token_key, messages, max_retries, base_wait)
        tried.append(("vanilla_path", r2))
        return r2


    def _ordered_labels(self) -> List[str]:
        """우선순위 + 이름순으로 안정된 라벨 순회 순서"""
        return sorted(self.valid_labels, key=lambda v: (self.priority_rank.get(v, 10 ** 6), v))

    def _parse_triplet_output(self, content: str) -> Tuple[List[str], float, str]:
        """모델 3줄 출력/JSON 출력 파싱 → (라벨 리스트, 정확도, 근거)"""
        if not content:
            return (["other"], 0.0, "")
        text = str(content).strip()
        text = re.sub(r"^```(?:json|txt)?\s*|\s*```$", "", text, flags=re.I | re.M)



        # JSON 시도
        j = None
        try:
            j = json.loads(text)
        except Exception:
            try:
                j = ast.literal_eval(text)
            except Exception:
                j = None

        if isinstance(j, dict):
            labels_raw = j.get("라벨") or j.get("label") or j.get("labels") or j.get("Label") or j.get("Labels") or ""
            conf = j.get("정확도") or j.get("confidence") or j.get("Confidence") or 0.0
            reason = j.get("근거") or j.get("reason") or j.get("이유") or j.get("basis") or j.get("rationale") or ""
        else:
            m_label = re.search(r"(?im)^\s*(라벨|labels?)\s*[:=：\-–—]\s*(.+)\s*$", text)
            m_conf = re.search(r"(?im)^\s*(정확도|confidence)\s*[:=：\-–—]\s*([0-9]+(?:\.[0-9]+)?)", text)
            m_reason = re.search(r"(?im)^\s*(근거|reason|이유|basis|rationale)\s*[:=：\-–—]\s*(.+)\s*$", text)
            labels_raw = (m_label.group(2).strip() if m_label else "")
            conf = (float(m_conf.group(2)) if m_conf else 0.0)
            reason = (m_reason.group(2).strip() if m_reason else "")

        # 정확도 보정
        try:
            if isinstance(conf, str):
                m = re.search(r"([0-9]+(?:\.[0-9]+)?)", conf)
                conf = float(m.group(1)) if m else 0.0
            conf = float(conf)
            if 1.0 < conf <= 100.0:
                conf = conf / 100.0
            conf = max(0.0, min(1.0, conf))
        except Exception:
            conf = 0.0

        # 라벨 후보
        candidates: List[str] = []
        if labels_raw:
            # 리스트 입력 보완
            token_src: List[str] = []
            if isinstance(labels_raw, list):
                token_src = [str(x) for x in labels_raw if x]
            else:
                token_src = [str(labels_raw)]

            # 1) 'company . mna_deal' 패턴
            full = []
            for src in token_src:
                full.extend(re.findall(r"(?:flow|company|sector|calendar|krx|analyst)\s*\.\s*[a-z0-9_]+",
                                       src, flags=re.I))
            full = [re.sub(r"\s*\.\s*", ".", f).lower() for f in full]  # 점 주변만 정규화
            if full:
                candidates.extend(full)

            # 2) 토큰 분리 + 약칭 처리 + 접미 매핑
            if not full:
                tokens: List[str] = []
                for src in token_src:
                    tokens.extend([t for t in re.split(r"[,/|\s]+", src) if t.strip()])

                alias = {
                    "m&a": "company.mna_deal", "mna": "company.mna_deal",
                    "merger": "company.mna_deal", "acquisition": "company.mna_deal",
                    "stock_split": "company.stock_split", "split": "company.stock_split",
                    "earnings": "company.earnings_result", "earnings_result": "company.earnings_result",
                    "guidance": "company.guidance_update",
                    "index_inout": "flow.index_inout",
                    "target_price": "analyst.target_price", "rating_change": "analyst.rating_change",
                    "pdufa": "sector.biotech_pdufa_set",
                    "nda": "sector.biotech_nda_bla_filing", "bla": "sector.biotech_nda_bla_filing",
                    "ind": "sector.biotech_ind_clearance",
                    "buyback": "company.buyback_update",
                }

                ordered_labels = self._ordered_labels()

                for t in tokens:
                    tok = re.sub(r"\s+", "", t).strip().lower()
                    if not tok:
                        continue
                    if tok in self.valid_labels:
                        candidates.append(tok)
                        continue
                    if tok in alias:
                        candidates.append(alias[tok])
                        continue
                    if '.' not in tok and tok != 'other':
                        for v in ordered_labels:  # 결정적 순회
                            if v.endswith('.' + tok):
                                candidates.append(v)
                                break


        normed, seen = [], set()
        for t in candidates:
            lab = t.strip().strip(',"\')(').lower()
            lab = re.sub(r"\s*\.\s*", ".", lab)  # 점 주변만 정규화
            if lab in self.valid_labels and lab not in seen:
                normed.append(lab)
                seen.add(lab)

        if not normed:
            normed = ["other"]

        # 우선순위 정렬 후 2개 제한
        normed = self._prioritize(normed)[:2]
        conf = conf if conf else (0.7 if normed and normed[0] != "other" else 0.5)
        return (normed, conf, reason)

    def _validate_labels(self, labels: List[str]) -> List[str]:
        out, seen = [], set()
        for lab in labels:
            l = lab.lower().strip()
            if l in self.valid_labels and l not in seen:
                out.append(l)
                seen.add(l)
        return out if out else ["other"]

    def _prioritize(self, labels: List[str]) -> List[str]:
        pr = self.priority_rank
        uniq = list(dict.fromkeys(labels))
        return sorted(uniq, key=lambda x: pr.get(x, 10 ** 6))


    def _rule_based_backstop(self, title: str) -> List[str]:
        """모델이 other/저신뢰일 때 제목 트리거로 보정"""
        if not title:
            return []
        txt = str(title).strip()
        hits = set()
        for lab, patterns in self.compiled_triggers.items():
            for pat in patterns:
                if pat.search(txt):
                    if lab in self.valid_labels:
                        hits.add(lab)
        if not hits:
            return []
        cand = sorted(
            hits,
            key=lambda x: (0 if x in self.fine_first else 1, self.priority_rank.get(x, 10 ** 6))
        )
        return self._prioritize(cand)[:2]

    # ---------------------
    # Public: Single Title
    # ---------------------
    def classify_event(self, title: str, source: str = "") -> LabelResult:
        """단일 제목 분류"""
        if not title or len(title.strip()) < 5:
            return LabelResult(labels=["other"], confidence=0.0, reason="제목 부족", raw_response="")

        # 1차: 모델 호출
        r1 = self._call_hyperclova_x(self._build_messages(title, source))
        if not r1.get("ok") or r1.get("status") != 200:
            err = r1.get("error") or "api_error"
            status = r1.get("status")

            # API 에러는 Exception으로 전파하여 fail.csv에 저장되도록 함
            if status in [429, 401, 403, 400, 500, 502, 503, 504] or err in [
                "network_error", "json_decode_error", "auth_failed", "exhausted"
            ]:
                error_msg = f"HyperCLOVA API 에러: {err} (HTTP {status})"
                self.logger.error(error_msg)
                raise Exception(error_msg)

            # 기타 에러의 경우 룰 기반 백스톱 시도
            rb = self._rule_based_backstop(title)
            if rb:
                return LabelResult(rb, 0.75, reason=f"룰 기반 보정(모델 실패:{err})", raw_response=str(r1.get("raw") or ""))
            return LabelResult(["other"], 0.0, reason=f"API 호출 실패: {err}", raw_response=str(r1.get("raw") or ""))

        labels1, conf1, reason1 = self._parse_triplet_output(r1.get("content", ""))
        v1 = self._validate_labels(labels1)

        # 룰 백스톱: 저신뢰 or other
        if (len(v1) == 1 and v1[0] == "other") or (conf1 < 0.6):
            rb = self._rule_based_backstop(title)
            if rb:
                return LabelResult(rb, 0.75, reason=f"룰 기반 보정(모델:{','.join(v1)} conf={conf1:.2f})",
                                   raw_response=r1.get("content", ""))

        # 기본 결과 반환
        return LabelResult(v1[:2], conf1, reason1, r1.get("content", ""))
