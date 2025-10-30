
from __future__ import annotations
from typing import Iterable, Dict, Any
from elasticsearch import helpers
from elasticsearch import Elasticsearch

from .es_client import ensure_company_synonyms_set, ensure_event_synonyms_set, _load_syn_lines

def create_index(es: Elasticsearch, index: str, use_embedding: bool, embed_dim: int):
    use_company_syn_set = ensure_company_synonyms_set(es)
    use_event_syn_set   = ensure_event_synonyms_set(es)

    company_inline = _load_syn_lines('config/company_synonyms.txt') if not use_company_syn_set else []
    event_inline   = _load_syn_lines('config/event_synonyms.txt') if not use_event_syn_set else []

    settings = {
        "analysis": {
            "filter": {
                "ko_pos_drop": {"type": "keep_types", "types": ["Noun", "Alpha", "Number"]},
                "ko_syn": {"type": "synonym_graph", "synonyms": ["AI, 인공지능", "모바일, 스마트폰"]},
                "shingle_2_3": {"type": "shingle", "min_shingle_size": 2, "max_shingle_size": 3},
                "company_syn": (
                    {"type": "synonym_graph", "lenient": True, "synonyms_set": "companies"}
                    if use_company_syn_set else
                    {"type": "synonym_graph", "lenient": True, "synonyms": company_inline}
                ),
                "event_syn": (
                    {"type": "synonym_graph", "lenient": True, "synonyms_set": "events"}
                    if use_event_syn_set else
                    {"type": "synonym_graph", "lenient": True, "synonyms": event_inline}
                ),
            },
            "tokenizer": {
                "ko_nori_index": {"type": "nori_tokenizer", "decompound_mode": "mixed"},
                "ko_nori_search": {"type": "nori_tokenizer", "decompound_mode": "discard"},
                "ch3": {"type": "nGram", "min_gram": 3, "max_gram": 3}
            },
            "analyzer": {
                "ko_title_index": {
                    "type": "custom",
                    "tokenizer": "ko_nori_index",
                    "filter": ["lowercase", "ko_pos_drop", "shingle_2_3"]
                },
                "ko_title_search": {
                    "type": "custom",
                    "tokenizer": "ko_nori_search",
                    "filter": ["lowercase", "ko_syn", "ko_pos_drop", "shingle_2_3"]
                },
                "ko_body_index": {
                    "type": "custom",
                    "tokenizer": "ko_nori_index",
                    "filter": ["lowercase", "ko_pos_drop"]
                },
                "ko_body_search": {
                    "type": "custom",
                    "tokenizer": "ko_nori_search",
                    "filter": ["lowercase", "ko_syn", "ko_pos_drop"]
                },
                "company_index": {"type": "custom", "tokenizer": "keyword", "filter": ["lowercase"]},
                "company_search": {"type": "custom", "tokenizer": "keyword", "filter": ["lowercase", "company_syn"]},
                "event_index":   {"type": "custom", "tokenizer": "keyword", "filter": ["lowercase"]},
                "event_search":  {"type": "custom", "tokenizer": "keyword", "filter": ["lowercase", "event_syn"]},
                "ko_keyphrase": {"type": "custom", "tokenizer": "standard", "filter": ["lowercase"]},
                "char3": {"type": "custom", "tokenizer": "ch3", "filter": ["lowercase"]}
            }
        }
    }
    mappings = {
        "properties": {
            "title": {"type": "text", "analyzer": "ko_title_index", "search_analyzer": "ko_title_search"},
            "lead": {"type": "text", "analyzer": "ko_body_index", "search_analyzer": "ko_body_search"},
            "body": {"type": "text", "analyzer": "ko_body_index", "search_analyzer": "ko_body_search"},
            "keyphrases": {"type": "text", "analyzer": "ko_keyphrase"},
            "title_char3": {"type": "text", "analyzer": "char3"},
            "body_char3": {"type": "text", "analyzer": "char3"},
            "title_simhash": {"type": "keyword"},
            "published_at": {"type": "date"},
            "publisher": {"type": "keyword"},
            "publisher_tier": {"type": "float"},
            "category": {"type": "keyword"},
            "url": {"type": "keyword"},
            "canonical_url": {"type": "keyword"},
            "companies":   {"type": "text", "analyzer": "company_index", "search_analyzer": "company_search"},
            "companies_kw": {"type": "keyword"},
            "companies_raw": {"type": "text", "analyzer": "company_index", "search_analyzer": "company_search"},
            "tickers": {"type": "keyword"},
            "events":      {"type": "text", "analyzer": "event_index", "search_analyzer": "event_search"},
            "event_codes": {"type": "keyword"},
            "event_conf":  {"type": "float"}
        }
    }
    if use_embedding:
        mappings["properties"]["embedding"] = {
            "type": "dense_vector", "dims": int(embed_dim),
            "index": True, "similarity": "cosine",
            "index_options": {"type": "hnsw", "m": 16, "ef_construction": 100}
        }
    body = {"settings": settings, "mappings": mappings}
    if es.indices.exists(index=index):
        return
    es.indices.create(index=index, body=body)

def recreate_index(es: Elasticsearch, index: str):
    if es.indices.exists(index=index):
        es.indices.delete(index=index)

def bulk_index(es: Elasticsearch, docs_iter: Iterable[Dict[str, Any]]):
    es_with_timeout = es.options(request_timeout=120)
    helpers.bulk(es_with_timeout, docs_iter, chunk_size=1000)
