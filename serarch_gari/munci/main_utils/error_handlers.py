
from __future__ import annotations
import functools
import logging
from typing import Callable, Any, Optional, TypeVar, Dict
from contextlib import contextmanager

logger = logging.getLogger(__name__)

T = TypeVar('T')




def handle_api_error(
        default_return: Any = None,
        error_msg: str = "API 호출 실패",
        log_level: str = "error"
):


    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_func = getattr(logger, log_level.lower(), logger.error)
                log_func(f"{error_msg}: {e}")
                if log_level.lower() in ["error", "critical"]:
                    logger.exception(f"[{func.__name__}] Traceback:")
                return default_return

        return wrapper

    return decorator


def handle_json_parse_error(default_return: Any = None):


    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (ValueError, TypeError) as e:
                logger.warning(f"[{func.__name__}] JSON 파싱 실패: {e}")
                return default_return

        return wrapper

    return decorator


def safe_execute(
        default_return: Any = None,
        exceptions: tuple = (Exception,),
        log_error: bool = True,
        fallback_func: Optional[Callable] = None
):


    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if log_error:
                    logger.exception(f"[{func.__name__}] 에러 발생: {e}")

                if fallback_func:
                    try:
                        return fallback_func(*args, **kwargs)
                    except Exception as fallback_error:
                        logger.error(f"Fallback 함수도 실패: {fallback_error}")

                return default_return

        return wrapper

    return decorator




@contextmanager
def suppress_and_log(
        exceptions: tuple = (Exception,),
        default_return: Any = None,
        error_msg: str = "작업 실패"
):

    try:
        yield
    except exceptions as e:
        logger.error(f"{error_msg}: {e}")
        return default_return


@contextmanager
def api_call_context(
        service_name: str,
        timeout: Optional[float] = None,
        retry_count: int = 0
):

    import time

    attempt = 0
    while attempt <= retry_count:
        try:
            logger.debug(f"[{service_name}] API 호출 시도 {attempt + 1}/{retry_count + 1}")

            if timeout:
                import signal

                def timeout_handler(signum, frame):
                    raise TimeoutError(f"{service_name} API 타임아웃 ({timeout}초)")

                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(timeout))

            yield

            if timeout:
                signal.alarm(0)

            logger.info(f"[{service_name}] API 호출 성공")
            break

        except TimeoutError as e:
            logger.error(f"[{service_name}] {e}")
            if attempt >= retry_count:
                raise
            attempt += 1
            time.sleep(1 * (2 ** attempt))  # 지수 백오프

        except Exception as e:
            if timeout:
                signal.alarm(0)

            logger.error(f"[{service_name}] API 호출 실패: {e}")

            if attempt >= retry_count:
                raise

            attempt += 1
            logger.info(f"[{service_name}] {attempt}초 후 재시도...")
            time.sleep(1 * attempt)



class ErrorHandler:
    """에러 핸들링 유틸리티 클래스"""

    @staticmethod
    def safe_call(
            func: Callable,
            *args,
            default: Any = None,
            error_msg: Optional[str] = None,
            **kwargs
    ) -> Any:

        try:
            return func(*args, **kwargs)
        except Exception as e:
            msg = error_msg or f"{func.__name__} 실행 실패"
            logger.exception(f"{msg}: {e}")
            return default

    @staticmethod
    def retry_call(
            func: Callable,
            *args,
            max_attempts: int = 3,
            delay: float = 1.0,
            backoff: float = 2.0,
            exceptions: tuple = (Exception,),
            **kwargs
    ) -> Any:

        import time

        last_exception = None
        for attempt in range(max_attempts):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                if attempt < max_attempts - 1:
                    wait_time = delay * (backoff ** attempt)
                    logger.warning(
                        f"[{func.__name__}] 시도 {attempt + 1}/{max_attempts} 실패. "
                        f"{wait_time:.1f}초 후 재시도... (에러: {e})"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"[{func.__name__}] 모든 재시도 실패")

        raise last_exception



class APIErrorHandler:
    """API 호출 전용 에러 핸들러"""

    @staticmethod
    def handle_openai_error(func: Callable) -> Callable:
        """OpenAI API 에러 처리"""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_type = type(e).__name__

                if "rate_limit" in str(e).lower():
                    logger.error(f"[OpenAI] Rate limit 초과: {e}")
                    return {"error": "rate_limit", "message": str(e)}
                elif "authentication" in str(e).lower() or "api_key" in str(e).lower():
                    logger.error(f"[OpenAI] 인증 실패: {e}")
                    return {"error": "auth_failed", "message": str(e)}
                elif "timeout" in str(e).lower():
                    logger.error(f"[OpenAI] 타임아웃: {e}")
                    return {"error": "timeout", "message": str(e)}
                else:
                    logger.exception(f"[OpenAI] 알 수 없는 에러: {e}")
                    return {"error": "unknown", "message": str(e)}

        return wrapper

    @staticmethod
    def handle_hyperclova_error(func: Callable) -> Callable:
        """HyperCLOVA API 에러 처리"""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = str(e).lower()

                if "401" in error_msg or "auth" in error_msg:
                    logger.warning("[HyperCLOVA] 인증 실패 - ChatGPT로 폴백")
                    return None  # None 반환하면 폴백 로직 실행
                elif "429" in error_msg or "rate" in error_msg:
                    logger.error("[HyperCLOVA] Rate limit 초과")
                    return None
                else:
                    logger.exception(f"[HyperCLOVA] 에러: {e}")
                    return None

        return wrapper


# =====================
# 5. 체이닝 가능한 핸들러
# =====================

class ChainableErrorHandler:
    """여러 에러 핸들러를 체이닝할 수 있는 클래스"""

    def __init__(self, func: Callable):
        self.func = func
        self.handlers: list = []

    def on_error(
            self,
            exception: type,
            handler: Callable[[Exception], Any]
    ) -> 'ChainableErrorHandler':
        """특정 예외에 대한 핸들러 추가"""
        self.handlers.append((exception, handler))
        return self

    def with_default(self, default: Any) -> 'ChainableErrorHandler':
        """기본 반환값 설정"""
        self.default = default
        return self

    def execute(self, *args, **kwargs) -> Any:
        """실행"""
        try:
            return self.func(*args, **kwargs)
        except Exception as e:
            for exc_type, handler in self.handlers:
                if isinstance(e, exc_type):
                    return handler(e)

            logger.exception(f"처리되지 않은 에러: {e}")
            return getattr(self, 'default', None)




if __name__ == "__main__":
    # 예시 1: 데코레이터 사용
    @handle_api_error(default_return={}, error_msg="API 호출 실패")
    def call_api():
        raise ConnectionError("네트워크 오류")


    result = call_api()
    print(f"결과: {result}")

    # 예시 2: 컨텍스트 매니저 사용
    with suppress_and_log(exceptions=(ValueError,), error_msg="파싱 실패"):
        data = int("invalid")

    # 예시 3: ErrorHandler 사용
    result = ErrorHandler.safe_call(
        lambda x: x / 0,
        10,
        default=0,
        error_msg="나누기 실패"
    )
    print(f"결과: {result}")

    # 예시 4: 체이닝 핸들러
    handler = ChainableErrorHandler(lambda: 1 / 0)
    handler.on_error(ZeroDivisionError, lambda e: "0으로 나눴습니다")
    handler.with_default("알 수 없는 에러")
    result = handler.execute()
    print(f"결과: {result}")
