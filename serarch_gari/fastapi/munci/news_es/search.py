
from __future__ import annotations
from typing import List, Tuple, Dict, Any
from datetime import datetime

from elasticsearch import Elasticsearch

from .query import build_company_event_dsl
from .embedding import embedding_dim

def search_with_api_params(
    es: Elasticsearch,
    index: str,
    query: str,
    companies: List[str] = None,
    event_phrases: List[str] = None,
    event_labels: List[str] = None,
    date_range: Tuple[datetime, datetime] = None,
    use_flexible_matching: bool = True
) -> Dict[str, Any]:
    dsl = build_company_event_dsl(
        index_name=index,
        q=query,
        event_phrases=event_phrases,
        companies=companies,
        use_flexible_matching=use_flexible_matching
    )

    if date_range:
        start, end = date_range
        dsl["query"]["function_score"]["query"]["bool"]["filter"] = [
            {"range": {"published_at": {"gte": start.isoformat(), "lte": end.isoformat()}}}
        ]

    if event_labels and event_labels != ["other"]:
        if "should" not in dsl["query"]["function_score"]["query"]["bool"]:
            dsl["query"]["function_score"]["query"]["bool"]["should"] = []

        dsl["query"]["function_score"]["query"]["bool"]["should"].append({
            "terms": {"event_codes": event_labels, "boost": 5}
        })

    try:
        res = es.search(index=index, body=dsl)
        hits = res.get("hits", {}).get("hits", [])

        results = []
        for h in hits:
            s = h["_source"]
            results.append({
                "score": h.get("_score", 0.0),
                "title": s.get("title"),
                "body": s.get("body", "")[:500] if "body" in s else "",
                "publisher": s.get("publisher"),
                "published_at": s.get("published_at"),
                "url": s.get("url"),
                "companies": s.get("companies", []),
                "events": s.get("events", []),
                "event_codes": s.get("event_codes", []),
                "tickers": s.get("tickers", [])
            })

        return {
            "status": "success",
            "total_hits": res.get("hits", {}).get("total", {}).get("value", len(hits)),
            "results": results,
            "query_params": {
                "original_query": query,
                "extracted_companies": companies,
                "extracted_event_phrases": event_phrases,
                "extracted_event_labels": event_labels,
                "use_flexible_matching": use_flexible_matching
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "results": [],
            "query_params": {
                "original_query": query,
                "extracted_companies": companies,
                "extracted_event_phrases": event_phrases,
                "extracted_event_labels": event_labels
            }
        }

def smoke_search(es: Elasticsearch, index: str, query: str, use_embedding: bool, model_name: str):
    print("\n[SMOKE] Company+Event DSL (BM25)")
    from .query import build_company_event_dsl
    dsl = build_company_event_dsl(index, query)
    dsl["size"] = 10
    res = es.search(index=index, body=dsl)
    for i, h in enumerate(res["hits"]["hits"], 1):
        s = h["_source"]
        print(f"{i:02d}. [{s.get('publisher')}] {s.get('title')} ({s.get('published_at')}) ev={s.get('event_codes')} comp={s.get('companies')}")
        if s.get("url"):
            print("    ", s["url"])

    if use_embedding:
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(model_name)
        qvec = m.encode("query: " + query, normalize_embeddings=True).tolist()
        print("\n[SMOKE] kNN top 10 (with date filter)")
        knn = {
            "size": 10,
            "_source": ["title", "publisher", "published_at", "url"],
            "knn": {
                "field": "embedding", "query_vector": qvec, "k": 10, "num_candidates": 200,
                "filter": {"range": {"published_at": {"gte": "now-3y"}}}
            }
        }
        try:
            res2 = es.search(index=index, body=knn)
            for i, h in enumerate(res2["hits"]["hits"], 1):
                s = h["_source"]
                print(f"{i:02d}. [{s.get('publisher')}] {s.get('title')}  ({s.get('published_at')})")
                if s.get("url"):
                    print("    ", s["url"])
        except Exception as e:
            print("[warn] kNN smoke skipped:", e)
