"""Pure-Python BM25 keyword index over the chunk store.

Embeddings are weakest exactly where personal data is hardest: names, amounts,
and code-switched Marathi/Hinglish. BM25 catches the literal matches the vector
search misses; retriever.py fuses both result lists with reciprocal-rank fusion.

Kept dependency-free on purpose — the index is a few thousand chunks of personal
chats, rebuilt in milliseconds whenever the store's chunk count changes.
"""
import math
import re
from collections import Counter
from typing import Dict, List

from . import store

# \w is Unicode-aware: Devanagari, Latin, and digits all count as word chars
_WORD_RE = re.compile(r"\w+", re.UNICODE)
K1 = 1.5
B = 0.75


def tokenize(text: str) -> List[str]:
    return [t.lower() for t in _WORD_RE.findall(text)]


class BM25Index:
    def __init__(self, docs: List[Dict]):
        """docs: [{id, text, metadata}, ...] as returned by store.get_all()."""
        self.docs = docs
        self.doc_tf = [Counter(tokenize(d["text"])) for d in docs]
        self.doc_lens = [sum(tf.values()) for tf in self.doc_tf]
        self.avg_len = (sum(self.doc_lens) / len(docs)) if docs else 0.0
        self.df: Counter = Counter()
        for tf in self.doc_tf:
            self.df.update(tf.keys())
        self.n = len(docs)

    def _idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        if df == 0:
            return 0.0
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int) -> List[Dict]:
        terms = tokenize(query)
        scored = []
        for i, tf in enumerate(self.doc_tf):
            score = 0.0
            for term in terms:
                freq = tf.get(term, 0)
                if not freq:
                    continue
                norm = freq + K1 * (1 - B + B * self.doc_lens[i] / self.avg_len)
                score += self._idf(term) * freq * (K1 + 1) / norm
            if score > 0:
                scored.append((score, i))
        scored.sort(key=lambda t: (-t[0], t[1]))
        return [{"id": self.docs[i]["id"], "text": self.docs[i]["text"],
                 "metadata": self.docs[i]["metadata"], "score": s}
                for s, i in scored[:top_k]]

    def contacts(self) -> List[str]:
        return sorted({d["metadata"].get("contact", "") for d in self.docs} - {""})


_index: BM25Index = None
_index_count = -1


def get_index() -> BM25Index:
    """Cached index; a changed chunk count (new ingest) triggers a rebuild."""
    global _index, _index_count
    current = store.count()
    if _index is None or current != _index_count:
        _index = BM25Index(store.get_all())
        _index_count = current
    return _index


def search(query: str, top_k: int) -> List[Dict]:
    return get_index().search(query, top_k)


def known_contacts() -> List[str]:
    return get_index().contacts()
