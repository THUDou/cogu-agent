import math
from collections import Counter
from typing import Any, Optional


class BM25Scorer:

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self._k1 = k1
        self._b = b
        self._documents: list[str] = []
        self._doc_ids: list[str] = []
        self._avg_doc_len: float = 0.0
        self._doc_len: list[int] = []
        self._doc_freq: Counter = Counter()
        self._total_docs: int = 0

    def index(self, doc_id: str, text: str):
        self._documents.append(text)
        self._doc_ids.append(doc_id)
        tokens = self._tokenize(text)
        self._doc_len.append(len(tokens))
        self._total_docs += 1

        unique_terms = set(tokens)
        for term in unique_terms:
            self._doc_freq[term] += 1

        self._avg_doc_len = sum(self._doc_len) / self._total_docs if self._total_docs > 0 else 1.0

    def _tokenize(self, text: str) -> list[str]:
        result = []
        current = []
        for ch in text.lower():
            if ch.isalnum() or '\u4e00' <= ch <= '\u9fff':
                current.append(ch)
            else:
                if current:
                    result.append("".join(current))
                    current = []
        if current:
            result.append("".join(current))
        return result

    def _idf(self, term: str) -> float:
        df = self._doc_freq.get(term, 0)
        if df == 0:
            return 0.0
        return math.log((self._total_docs - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, query: str, doc_id: str = "", doc_text: str = "") -> float:
        if not query:
            return 0.0

        if doc_id and doc_id in self._doc_ids:
            idx = self._doc_ids.index(doc_id)
            doc_text = self._documents[idx]
            doc_len = self._doc_len[idx]
        else:
            doc_len = len(self._tokenize(doc_text))

        query_terms = self._tokenize(query)
        doc_terms = self._tokenize(doc_text)
        term_freqs = Counter(doc_terms)

        score = 0.0
        seen = set()
        for term in query_terms:
            if term in seen:
                continue
            seen.add(term)
            tf = term_freqs.get(term, 0)
            idf = self._idf(term)
            numerator = tf * (self._k1 + 1)
            denominator = tf + self._k1 * (1 - self._b + self._b * doc_len / max(self._avg_doc_len, 1))
            score += idf * numerator / max(denominator, 0.001)

        return score

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        if not query:
            return []
        results = []
        for i, doc_id in enumerate(self._doc_ids):
            s = self.score(query, doc_id=doc_id)
            if s > 0:
                results.append((doc_id, s))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


class RRFRanker:

    def __init__(self, k: int = 60, default_bm25_weight: float = 0.4, default_vector_weight: float = 0.6):
        self._k = k
        self._bm25_weight = default_bm25_weight
        self._vector_weight = default_vector_weight

    def _reciprocal_rank(self, rank: int) -> float:
        return 1.0 / (self._k + rank)

    def fuse(
        self,
        bm25_results: list[tuple[str, float]],
        vector_results: list[tuple[str, float]],
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        bm25_ranks: dict[str, int] = {}
        for rank, (doc_id, _) in enumerate(bm25_results):
            bm25_ranks[doc_id] = rank + 1

        vector_ranks: dict[str, int] = {}
        for rank, (doc_id, _) in enumerate(vector_results):
            vector_ranks[doc_id] = rank + 1

        all_ids = set(bm25_ranks.keys()) | set(vector_ranks.keys())
        scores: dict[str, float] = {}

        for doc_id in all_ids:
            rrf_score = 0.0
            if doc_id in bm25_ranks:
                rrf_score += self._bm25_weight * self._reciprocal_rank(bm25_ranks[doc_id])
            if doc_id in vector_ranks:
                rrf_score += self._vector_weight * self._reciprocal_rank(vector_ranks[doc_id])
            scores[doc_id] = rrf_score

        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_results[:top_k]
