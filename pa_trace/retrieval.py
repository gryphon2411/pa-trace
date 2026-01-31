import re
from typing import List, Dict, Any, Tuple

def _tokenize(s: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", s.lower())

def retrieve_policy_chunks(policy_store: List[Dict[str, Any]], query: str, k: int = 3) -> List[Dict[str, Any]]:
    """
    Lightweight retrieval: score chunks by token overlap (good enough for MVP).
    Swap for BM25/embeddings later if desired.
    """
    q = set(_tokenize(query))
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for ch in policy_store:
        t = set(_tokenize(ch["text"]))
        score = len(q & t) / max(1, len(q))
        scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:k]]
