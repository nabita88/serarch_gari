
from __future__ import annotations
import re, hashlib
from datetime import datetime
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse, unquote
from typing import Optional, Tuple, List

from .config import SPACE, PUNCT, KST, PUBLISHER_TIER

def split_companies(raw: str) -> List[str]:
    if not raw:
        return []
    parts = re.split(r"[,\\|/·]", raw)
    return [p.strip() for p in parts if p.strip()]

def normalize_publisher(name: str) -> Tuple[str, float]:
    std = (name or "").strip()
    tier = PUBLISHER_TIER.get(std, 0.5)
    return std, tier

def canonicalize_naver_news(url: str) -> Tuple[str, Optional[str], Optional[str]]:
    if not url:
        return "", None, None
    u = urlparse(url)
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    keep = {}
    for k, v in q.items():
        lk = k.lower()
        if lk in ("oid", "office_id", "aid", "article_id", "date"):
            keep[lk] = v
    if "office_id" in keep and "oid" not in keep:
        keep["oid"] = keep.pop("office_id")
    if "article_id" in keep and "aid" not in keep:
        keep["aid"] = keep.pop("article_id")
    query_sorted = urlencode(dict(sorted(keep.items())), doseq=False)
    path_decoded = unquote(u.path)
    canon = urlunparse((u.scheme.lower(), u.netloc.lower(), path_decoded, "", query_sorted, ""))
    return canon, keep.get("oid"), keep.get("aid")

def normalize_title(title: str) -> str:
    t = (title or "").strip()
    t = SPACE.sub(" ", t)
    t = PUNCT.sub(" ", t)
    t = SPACE.sub(" ", t).strip()
    return t

def generate_keyphrases(title: str, max_n: int = 32) -> List[str]:
    toks = re.findall(r"[A-Za-z0-9가-힣]{2,}", (title or "").lower())
    phrases = set()
    for i in range(len(toks)):
        phrases.add(toks[i])
        if i + 1 < len(toks):
            bi = f"{toks[i]} {toks[i + 1]}"; phrases.add(bi); phrases.add(bi.replace(" ", ""))
        if i + 2 < len(toks):
            tri = f"{toks[i]} {toks[i + 1]} {toks[i + 2]}"; phrases.add(tri); phrases.add(tri.replace(" ", ""))
    out = list(phrases); out.sort()
    return out[:max_n]

def simhash64(text: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9가-힣]{2,}", (text or "").lower())
    v = [0] * 64
    for tok in tokens:
        h = int.from_bytes(hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest(), "big")
        for i in range(64):
            v[i] += 1 if (h >> i) & 1 else -1
    res = 0
    for i in range(64):
        if v[i] > 0:
            res |= (1 << i)
    return hex(res)

def iso_to_mysql_dt(iso_dt: Optional[str]) -> Optional[str]:
    if not iso_dt:
        return None
    try:
        dt = datetime.fromisoformat(iso_dt.replace("Z", "+00:00")).astimezone(KST)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None
