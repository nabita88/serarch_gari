from __future__ import annotations
import os
import yaml
from typing import Optional
from elasticsearch import Elasticsearch


def create_es_client() -> Elasticsearch:
    host = os.getenv("ES_HOSTS", os.getenv("ES_HOST", "http://localhost:9200"))
    user = os.getenv("ES_USERNAME")
    pw = os.getenv("ES_PASSWORD")

    try:
        with open('config.yml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            es_config = config.get('elasticsearch', {})
            if 'cloud_id' in es_config:
                return Elasticsearch(
                    cloud_id=es_config['cloud_id'],
                    basic_auth=(es_config['username'], es_config['password']),
                    request_timeout=60
                )
            if 'host' in es_config:
                host = es_config.get('host', host)
                user = es_config.get('username', user)
                pw = es_config.get('password', pw)
    except Exception:
        pass

    if user and pw:
        return Elasticsearch(host, basic_auth=(user, pw), request_timeout=60, verify_certs=False)
    return Elasticsearch(host, request_timeout=60, verify_certs=False)


def connect_es(host: str, user: Optional[str], pw: Optional[str]) -> Elasticsearch:
    try:
        with open('config.yml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            es_config = config.get('elasticsearch', {})
            if 'cloud_id' in es_config:
                return Elasticsearch(
                    cloud_id=es_config['cloud_id'],
                    basic_auth=(es_config['username'], es_config['password']),
                    request_timeout=60
                )
            elif 'host' in es_config:
                return Elasticsearch(es_config['host'], request_timeout=60, verify_certs=False)
    except Exception as e:
        print(f"[정보] config.yml 로드 실패, 기본 설정 사용: {e}")
    if user and pw:
        return Elasticsearch(host, basic_auth=(user, pw), request_timeout=60, verify_certs=False)
    return Elasticsearch(host, request_timeout=60, verify_certs=False)


def _load_syn_lines(path: str):
    out = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    out.append(line)
    except Exception as e:
        print(f"[경고] 동의어 파일 로드 실패 {path}: {e}")
    return out


def ensure_company_synonyms_set(es: Elasticsearch, synonyms_file: str = 'config/company_synonyms.txt') -> bool:
    try:
        syns = [{"synonyms": s} for s in _load_syn_lines(synonyms_file)]
        if not syns:
            print("[경고] company_synonyms.txt 가 비어있습니다.")
        es.synonyms.put_synonym(id="companies", synonyms_set=syns)
        print(f"[정보] 동의어 세트 'companies' 업데이트: {len(syns)}개 규칙")
        return True
    except Exception as e:
        print(f"[경고] Company 동의어 API 실패, 인라인 폴백 예정: {e}")
        return False


def ensure_event_synonyms_set(es: Elasticsearch, synonyms_file: str = 'config/event_synonyms.txt') -> bool:
    try:
        syns = [{"synonyms": s} for s in _load_syn_lines(synonyms_file)]
        if not syns:
            print("[경고] event_synonyms.txt 가 비어있습니다.")
        es.synonyms.put_synonym(id="events", synonyms_set=syns)
        print(f"[정보] 동의어 세트 'events' 업데이트: {len(syns)}개 규칙")
        return True
    except Exception as e:
        print(f"[경고] Event 동의어 API 실패, 인라인 폴백 예정: {e}")
        return False
