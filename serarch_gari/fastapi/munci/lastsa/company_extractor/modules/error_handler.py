from __future__ import annotations
import re
from typing import Optional, List, Callable, Any, TypeVar

T = TypeVar('T')


def safe_compile_pattern(alias: str) -> Optional[re.Pattern]:
    """정규식 패턴을 안전하게 컴파일"""
    try:
        return re.compile(re.escape(alias), re.IGNORECASE)
    except Exception as e:
        print(f"[WARNING] Pattern compilation failed: {alias} - {e}")
        return None


def safe_pattern_finditer(pattern: re.Pattern, text: str) -> List[re.Match]:
    """패턴 매칭을 안전하게 수행"""
    try:
        return list(pattern.finditer(text))
    except Exception as e:
        print(f"[WARNING] Pattern matching failed: {e}")
        return []


def safe_dict_get(dictionary: dict, key: str, default: Any = None) -> Any:
    """딕셔너리 조회를 안전하게 수행"""
    try:
        return dictionary.get(key, default)
    except Exception as e:
        print(f"[WARNING] Dictionary lookup failed: {key} - {e}")
        return default


def safe_list_get(lst: list, index: int, default: Any = None) -> Any:
    """리스트 접근을 안전하게 수행"""
    try:
        return lst[index] if 0 <= index < len(lst) else default
    except Exception as e:
        print(f"[WARNING] List access failed: index={index} - {e}")
        return default


def safe_execute(func: Callable[..., T], *args, default: T = None,
                 error_msg: str = "Function execution failed", **kwargs) -> T:
    """함수 실행을 안전하게 수행"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"[WARNING] {error_msg}: {e}")
        return default


def safe_json_load(file_path: str) -> Optional[dict]:
    """JSON 파일을 안전하게 로드"""
    import json
    import os

    try:
        if not os.path.exists(file_path):
            print(f"[WARNING] File not found: {file_path}")
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[WARNING] JSON parsing failed: {file_path} - {e}")
        return None
    except Exception as e:
        print(f"[WARNING] File load failed: {file_path} - {e}")
        return None


def safe_file_write(file_path: str, content: str) -> bool:
    """파일을 안전하게 작성"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"[WARNING] File write failed: {file_path} - {e}")
        return False


def safe_string_similarity(s1: str, s2: str) -> float:
    """문자열 유사도를 안전하게 계산"""
    try:
        from difflib import SequenceMatcher
        return SequenceMatcher(None, s1, s2).ratio()
    except Exception as e:
        print(f"[WARNING] Similarity calculation failed: {s1} vs {s2} - {e}")
        return 0.0
