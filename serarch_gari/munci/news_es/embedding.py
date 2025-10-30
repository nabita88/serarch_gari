
from __future__ import annotations
from typing import Optional, List

_EMB_MODEL = None

def embed_title(title: str, model_name: str) -> Optional[List[float]]:
    global _EMB_MODEL
    try:
        if _EMB_MODEL is None:
            from sentence_transformers import SentenceTransformer
            _EMB_MODEL = SentenceTransformer(model_name)
        txt = "passage: " + (title or "")
        vec = _EMB_MODEL.encode(txt, normalize_embeddings=True)
        return vec.tolist()
    except Exception as e:
        print("[warn] embedding skipped:", e)
        return None

def embedding_dim(model_name: str) -> int:
    try:
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(model_name)
        return m.get_sentence_embedding_dimension()
    except Exception:
        return 1024 if "large" in model_name.lower() else 768
