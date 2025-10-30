from __future__ import annotations
from typing import Dict, Any, List, Tuple

from .companies import resolve_company, load_alias_index
from .events_es import resolve_event_from_query, _extract_event_keywords_from_query, load_event_alias_index, \
    EVENT_CODE2LABEL

from .config import SPACE


def parse_intent(q: str) -> Dict[str, Any]:
    canonicals, _tickers = resolve_company(q)
    ev_codes, matched_aliases = resolve_event_from_query(q)

    event_keywords = _extract_event_keywords_from_query(q)

    resid = q
    for a in matched_aliases:
        resid = resid.replace(a, " ")
    resid = SPACE.sub(" ", resid).strip()

    return {
        "companies": canonicals,
        "event_codes": ev_codes,
        "event_keywords": event_keywords,
        "event_phrases": [],  # 기본값 빈 리스트
        "residual": resid,
    }


def build_company_event_dsl(
        index_name: str,
        q: str,
        event_phrases: List[str] = None,
        companies: List[str] = None,
        use_flexible_matching: bool = False
) -> Dict[str, Any]:
    intent = parse_intent(q)

    if companies is not None:
        intent["companies"] = companies
    if event_phrases is not None:
        intent["event_phrases"] = event_phrases

    companies_lc = [c.lower() for c in intent["companies"]]
    event_codes = intent["event_codes"]
    event_keywords = intent.get("event_keywords", [])
    resid = intent["residual"]

    base_filter = [{"range": {"published_at": {"gte": "now-3y"}}}]
    must, should = [], []

    if companies_lc:
        if use_flexible_matching:
            should.append({"constant_score": {"filter": {"terms": {"companies_kw": companies_lc}}, "boost": 8}})
            should.append(
                {"match": {"companies_raw": {"query": " ".join(intent["companies"]), "operator": "OR", "boost": 6}}})
        else:
            must.append({"terms": {"companies_kw": companies_lc}})

            company_title_should = []
            _, _, canon2aliases = load_alias_index()
            for company in intent["companies"]:
                company_title_should.append({
                    "match": {"title": {"query": company, "operator": "OR"}}
                })

                if company in canon2aliases:
                    for alias in canon2aliases[company]:
                        if alias != company:
                            company_title_should.append({
                                "match": {"title": {"query": alias, "operator": "OR"}}
                            })

            if company_title_should:
                must.append({
                    "bool": {
                        "should": company_title_should,
                        "minimum_should_match": 1
                    }
                })

    if event_phrases:
        for phrase in event_phrases:
            if phrase:
                should.append({
                    "match_phrase": {
                        "title": {
                            "query": phrase,
                            "slop": 3,
                            "boost": 3
                        }
                    }
                })

                words = phrase.split()
                if len(words) > 1:
                    should.append({
                        "match": {
                            "title": {
                                "query": phrase,
                                "operator": "AND",
                                "boost": 2.5
                            }
                        }
                    })

                should.append({
                    "match": {
                        "title": {
                            "query": phrase,
                            "operator": "OR",
                            "minimum_should_match": "50%",
                            "boost": 2
                        }
                    }
                })

                should.append({
                    "match": {
                        "body": {
                            "query": phrase,
                            "operator": "OR",
                            "minimum_should_match": "30%",
                            "boost": 1.5
                        }
                    }
                })

                phrase_idx = event_phrases.index(phrase) if phrase in event_phrases else 999
                if companies_lc and len(companies_lc) > 0 and phrase_idx < 2:
                    for company in intent["companies"][:2]:
                        should.append({
                            "match_phrase": {
                                "title": {
                                    "query": f"{company} {phrase}",
                                    "slop": 12,
                                    "boost": 9
                                }
                            }
                        })

    if event_codes:
        should.append({"terms": {"event_codes": event_codes, "boost": 10}})
        should.append({"match": {"events": {"query": q, "boost": 8}}})

        event_alias_idx = load_event_alias_index()
        for code in event_codes:
            label = EVENT_CODE2LABEL.get(code, code)
            should.append({"match": {"title": {"query": label, "boost": 6}}})

            for alias, alias_code in event_alias_idx.items():
                if alias_code == code:
                    should.append({"match": {"title": {"query": alias, "boost": 5}}})

    elif event_keywords and not event_phrases:
        for keyword in event_keywords:
            should.append({"match": {"title": {"query": keyword, "boost": 5}}})
            should.append({"match_phrase": {"title": {"query": keyword, "boost": 7}}})

        should.append({"match": {"events": {"query": q, "boost": 4}}})

    if resid:
        should.extend([
            {"match_phrase": {"title": {"query": resid, "boost": 4}}},
            {"match": {"title": {"query": resid, "operator": "AND", "boost": 2}}}
        ])

    if not companies_lc and not event_codes and not event_keywords and not event_phrases:
        if resid:
            should.append({"multi_match": {
                "query": resid,
                "fields": ["title^3", "body^2", "events^2"],
                "type": "best_fields",
                "boost": 2
            }})
        else:
            should.append({"match": {"title": {"query": q, "boost": 1}}})

    if must:
        min_should = 0
    else:
        min_should = 1

    inner = {
        "bool": {
            **({"must": must} if must else {}),
            **({"should": should} if should else {}),
            "filter": base_filter,
            "minimum_should_match": min_should
        }
    }

    source_fields = ["title", "publisher", "published_at", "url", "companies", "companies_kw",
                     "events", "event_codes", "tickers", "body"]

    return {
        "size": 20,
        "_source": source_fields,
        "query": {
            "function_score": {
                "query": inner,
                "functions": [
                    {"field_value_factor": {"field": "publisher_tier", "factor": 1.0, "missing": 0.5}},
                    {"gauss": {"published_at": {"origin": "now", "scale": "30d", "decay": 0.7}}},
                    {"field_value_factor": {"field": "event_conf", "factor": 1.5, "missing": 1.0}}
                ],
                "score_mode": "sum",
                "boost_mode": "multiply"
            }
        }
    }


def build_es_dsl(index_name: str, q: str) -> Dict[str, Any]:
    canonicals, tickers = resolve_company(q)
    should: List[Dict[str, Any]] = []

    if canonicals:
        should.append(
            {"constant_score": {"filter": {"terms": {"companies_kw": [c.lower() for c in canonicals]}}, "boost": 10}})
        should.append({"match": {"companies_raw": {"query": q, "operator": "AND", "boost": 8}}})
    else:
        should.append({"match_phrase": {"title": {"query": q, "slop": 0, "boost": 6}}})
        should.append({"match": {"title": {"query": q, "operator": "AND", "boost": 4}}})

    body = {
        "size": 20,
        "_source": ["title", "publisher", "published_at", "url", "companies", "companies_raw", "tickers"],
        "query": {
            "bool": {
                "should": should,
                "filter": [{"range": {"published_at": {"gte": "now-3y"}}}],
                "minimum_should_match": 1
            }
        }
    }
    return body
