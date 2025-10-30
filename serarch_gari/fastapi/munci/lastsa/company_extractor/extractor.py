from __future__ import annotations
import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict

from .models import ExtractionResult, CompanyInfo
from .modules import utils, data, aliases, patterns, validation, ensemble, hcx


class FinalCompanyExtractor:
    HYPERCLOVA_SYSTEM_PROMPT = (
        """
        너의 역할은 '뉴스/공시/증권 커뮤니케이션' 텍스트에서 '정규화된 회사명'을 추출·정제하는 NER·정규화 에이전트다.
        원문 표기는 참고만 하고, 결과는 반드시 '공식 명칭(canonicalName)'으로 통일한다.

        필수 규칙
        - 문장에 기업명이 여러 개일 수 있음 → 등장하는 모든 기업명을 **중복 없이** 추출한다(등장 순서 유지).
        - 연결어/구분자에 나열된 기업명은 각각 분리: 와/과/및/그리고/하고, 콤마(,), 점(·/ㆍ), 슬래시(/), 앰퍼샌드(&).
        - 조사/어미는 제거 후 판정: 은/는/이/가/을/를/에/에서/에게/에는/에도/으로/로/만/까지/부터/조차/뿐/의 등.
        - 추출 제외: "현대에는", "삼성에서", "LG는"처럼 **그룹명 단독 + 조사**만 있는 경우(맥락 키워드 없음).
        - 대소문자/띄어쓰기/기호 차이는 무시하고 회사명 판단(예: 카카오 페이 → 카카오페이).

        정규화 규칙(예시)
        - "현대차", "현차" → "현대자동차"
        - "기아차" → "기아"

        모호한 그룹 키워드 귀속(문맥 기반)
        - "삼성" + {반도체, HBM, 메모리, 파운드리, 갤럭시} → 삼성전자
        - "LG" + {배터리, LFP, ESS, 소재} → LG에너지솔루션
        - "현대차", "현차" → 현대자동차
        - "카카오" 기본은 카카오(지주격). 단 {간편결제/PG/QR} → 카카오페이, {게임} → 카카오게임즈, {은행} → 카카오뱅크
        - 단독 "현대/삼성/LG" + 조사(에는/는/에서/의 등)만 있을 때는 추출하지 않음.

        출력 형식
        - 오직 **단일 JSON 객체**만 출력. JSON 외 텍스트(설명/코드블록/머리말/추론로그) 금지.
        - 스키마: {"entities": ["<정규화된 회사명>", "..."]}
        - 기업명이 없으면 {"entities": []}를 반환.
        """
    )

    HYPERCLOVA_MAX_RETRIES = 2
    HYPERCLOVA_RETRY_DELAY = 2
    DEFAULT_CONFIDENCE_THRESHOLD = 0.55
    MIN_CONSENSUS_METHODS = 1
    MAX_PATTERN_COUNT = 1000
    CACHE_MAX_SIZE = 1000

    def __init__(self, data_path: Optional[str] = None, db_config: Optional[Dict] = None) -> None:
        self.DATA_PATH = self._get_data_path(data_path)
        self._print_init_info()
        self._setup_environment()
        self._setup_database(db_config)  # DB 설정 추가
        self._load_data()
        self._initialize_config()
        self._initialize_stats()

    def _get_data_path(self, data_path: Optional[str]) -> str:
        if data_path is None:
            return str(Path(__file__).parent / "sysm")
        return data_path

    def _print_init_info(self):
        print("\n" + "=" * 70)
        print("초정밀 기업명 추출기 (모듈 버전) 초기화 중...")
        print("=" * 70)
        print(f"데이터 경로: {self.DATA_PATH}")
        self._print_file_check()

    def _print_file_check(self):
        files_to_check = [
            ("normalized_aliases.json", "정규화된 별칭 사전"),
            ("stock_master.csv", "상장사 마스터"),
            ("comprehensive_companies.json", "종합 기업 DB"),
            (".env", "환경 설정"),
        ]
        print("\n필수 파일 확인:")
        for filename, description in files_to_check:
            path = os.path.join(self.DATA_PATH, filename)
            status = '[확인]' if os.path.exists(path) else '[누락]'
            print(f"  {status} {filename:<30} ({description})")
        print()

    def _setup_environment(self):
        self._load_env()
        self.logger = utils.setup_logging(self.DATA_PATH)
        self.clova_api_key = os.getenv('CLOVA_API_KEY', '')

    def _load_env(self):
        try:
            from dotenv import load_dotenv
            from pathlib import Path

            # 프로젝트 루트의 .env 파일 경로 찾기
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent.parent
            env_path = project_root / ".env"

            if env_path.exists():
                load_dotenv(dotenv_path=env_path)
            else:
                load_dotenv()
        except Exception:
            pass

    def _setup_database(self, db_config: Optional[Dict]):
        """DB 연결 설정"""
        self.db_conn = None
        self.use_db = False

        if db_config:
            try:
                import pymysql
                self.db_conn = pymysql.connect(
                    host=db_config.get('host', 'localhost'),
                    port=db_config.get('port', 3306),
                    user=db_config.get('username'),
                    password=db_config.get('password'),
                    database=db_config.get('database'),
                    charset='utf8mb4',
                    cursorclass=pymysql.cursors.DictCursor
                )
                self.use_db = True
                print("[확인] 데이터베이스 연결 성공")
            except Exception as e:
                print(f"[경고] 데이터베이스 연결 실패: {e}")
                print("[안내] DB 없이 계속 진행합니다")
        else:
            print("[안내] DB 설정 없음 - DB 없이 실행합니다")

    def _load_data(self):
        self.company_master: Dict[str, Dict] = data._load_enhanced_company_master(self)
        self.alias_to_official: Dict[str, str] = {}
        self.company_aliases: Dict[str, List[str]] = defaultdict(list)

        self._merge_aliases()
        self.company_aliases = aliases._build_enhanced_company_aliases(self)
        self.company_patterns = patterns._build_advanced_patterns(self)

    def _merge_aliases(self):
        try:
            alias_path = os.path.join(self.DATA_PATH, "normalized_aliases.json")
            aliases._merge_krx_aliases(self, alias_path)
            print("KRX 정규화 사전 병합 완료")
        except Exception as e:
            print(f"안내: normalized_aliases.json 병합 실패: {str(e)[:100]}")

    def _initialize_config(self):
        self.extraction_weights = {
            'hyperclova_x': 0.55,
            'pattern_matching': 0.45,
        }
        self.confidence_threshold = self.DEFAULT_CONFIDENCE_THRESHOLD
        self.min_consensus_methods = self.MIN_CONSENSUS_METHODS

    def _initialize_stats(self):
        self.extraction_stats = {
            'total_processed': 0,
            'false_negative_recovery': 0
        }
        self.extraction_cache: Dict[str, Any] = {}

    def _get_company_codes_from_db(self, company_name: str) -> Optional[Dict[str, str]]:
        """DB에서 stock_code, corp_code 조회"""
        if not self.use_db or not self.db_conn:
            return None

        try:
            with self.db_conn.cursor() as cursor:
                sql = """
                      SELECT stock_code, corp_code
                      FROM stock_list
                      WHERE company_name = %s LIMIT 1 \
                      """
                cursor.execute(sql, (company_name,))
                result = cursor.fetchone()

                if result:
                    return {
                        'stock_code': result.get('stock_code'),
                        'corp_code': result.get('corp_code')
                    }
        except Exception as e:
            self.logger.error(f"{company_name} DB 조회 실패: {e}")

        return None

    def _enrich_with_codes(self, companies: List[str]) -> Dict[str, CompanyInfo]:
        """기업명 리스트에 stock_code, corp_code 추가"""
        company_details = {}

        for company in companies:
            # 기본 정보 (company_master에서)
            info = self.company_master.get(company, {})

            company_info = CompanyInfo(
                name=company,
                stock_code=info.get('code'),
                corp_code=None,
                sector=info.get('sector'),
                market=info.get('market')
            )

            # DB에서 추가 코드 조회
            codes = self._get_company_codes_from_db(company)
            if codes:
                if not company_info.stock_code:
                    company_info.stock_code = codes.get('stock_code')
                company_info.corp_code = codes.get('corp_code')

            company_details[company] = company_info

        return company_details

    def extract_companies(self, text: str,
                          context: Optional[Dict] = None,
                          exclude_analyst_reports: bool = True,
                          verbose: bool = True) -> ExtractionResult:

        if not self._is_valid_text(text):
            return ExtractionResult([], {}, {}, {})

        if self._should_filter_analyst_report(text, context, exclude_analyst_reports, verbose):
            return ExtractionResult([], {}, {}, {'filtered_reason': 'analyst_report'})

        cached_result = self._get_cached_result(text, context, verbose)
        if cached_result:
            return cached_result

        return self._perform_extraction(text, context, verbose)

    def _is_valid_text(self, text: str) -> bool:
        return bool(text and len(text.strip()) >= 5)

    def _should_filter_analyst_report(self, text: str, context: Optional[Dict],
                                      exclude_analyst_reports: bool, verbose: bool) -> bool:
        if exclude_analyst_reports and utils._is_analyst_report(text, context):
            if verbose:
                print(f"   [필터링] 애널리스트 리포트 감지: {text[:50]}...")
            return True
        return False

    def _get_cached_result(self, text: str, context: Optional[Dict],
                           verbose: bool) -> Optional[ExtractionResult]:
        cache_key = utils._generate_cache_key(text, context)
        if cache_key in self.extraction_cache:
            if verbose:
                print("   [캐시] 캐시에서 결과 반환")
            return self.extraction_cache[cache_key]
        return None

    def _perform_extraction(self, text: str, context: Optional[Dict],
                            verbose: bool) -> ExtractionResult:
        start = time.time()
        if verbose:
            print(f"[시작] 초정밀 추출: {text[:50]}...")

        extraction_results = self._run_extraction_methods(text, verbose)
        ens = ensemble._ensemble_integration(self, extraction_results, text, context)
        validated = validation._validate_candidates(self, ens, text, context)
        final = ensemble._candidate_recovery_and_refinement(self, validated, text, context, verbose)

        # DB에서 코드 정보 추가
        if final.companies:
            final.company_details = self._enrich_with_codes(final.companies)

        self._update_cache_and_stats(text, context, final)
        self._print_extraction_result(final, start, verbose)

        return final

    def _run_extraction_methods(self, text: str, verbose: bool) -> Dict[str, List[str]]:
        results: Dict[str, List[str]] = {}
        results.update(self._run_pattern_matching(text, verbose))
        results.update(self._run_hyperclova(text, verbose))
        return results

    def _run_pattern_matching(self, text: str, verbose: bool) -> Dict[str, List[str]]:
        try:
            pattern_result = patterns._extract_with_patterns(self, text)
            if verbose and pattern_result:
                print(f"  [확인] 패턴 매칭: {len(pattern_result)}개 발견")
            return {'pattern_matching': pattern_result}
        except Exception as e:
            self.logger.error(f"패턴 매칭 실패: {e}")
            return {'pattern_matching': []}

    def _run_hyperclova(self, text: str, verbose: bool) -> Dict[str, List[str]]:
        if not self.clova_api_key:
            return {}

        try:
            hyper_res = hcx._extract_with_hyperclova(self, text)
            if verbose and hyper_res:
                print(f"  [확인] HyperCLOVA: {len(hyper_res)}개 발견")
            return {'hyperclova_x': hyper_res}
        except Exception as e:
            self.logger.error(f"HyperCLOVA 추출 실패: {e}")
            raise

    def _update_cache_and_stats(self, text: str, context: Optional[Dict],
                                result: ExtractionResult):
        cache_key = utils._generate_cache_key(text, context)
        self.extraction_cache[cache_key] = result
        self.extraction_stats['total_processed'] += 1

    def _print_extraction_result(self, result: ExtractionResult, start_time: float,
                                 verbose: bool):
        if verbose and result.companies:
            elapsed = time.time() - start_time
            avg_conf = sum(result.confidence_scores.values()) / max(1, len(result.confidence_scores))
            print(
                f"  [완료] 추출 완료: {len(result.companies)}개 기업, {elapsed:.2f}초, 평균 신뢰도: {avg_conf:.3f}")

            # 코드 정보 출력
            if result.company_details:
                print("  [안내] 기업 코드:")
                for company, details in result.company_details.items():
                    print(f"    - {company}: 종목코드={details.stock_code}, 법인코드={details.corp_code}")

    def _normalize_to_official_name(self, company: str) -> str:
        return aliases._normalize_to_official_name(self, company)

    def _find_similar_companies(self, company: str, threshold: float = 0.8) -> List[str]:
        return aliases._find_similar_companies(self, company, threshold)

    def __del__(self):
        """소멸자 - DB 연결 정리"""
        if hasattr(self, 'db_conn') and self.db_conn:
            try:
                self.db_conn.close()
                print("[안내] 데이터베이스 연결 종료")
            except:
                pass
