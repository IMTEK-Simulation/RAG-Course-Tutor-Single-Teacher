from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

TOKEN_PATTERN = re.compile(r"[A-Za-zÄÖÜäöüß0-9\\]+")
STOPWORDS = {
    "aber", "als", "am", "an", "auch", "auf", "aus", "bei", "bin", "bis",
    "das", "der", "die", "ein", "eine", "einer", "eines", "für", "hat",
    "ich", "im", "in", "ist", "kann", "man", "mit", "oder", "sich", "sie",
    "sind", "und", "von", "was", "wie", "wird", "wo", "zu", "zum",
    "a", "an", "and", "are", "as", "at", "be", "can", "for", "from",
    "how", "in", "is", "of", "on", "or", "the", "to", "what", "with",
}


def tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_PATTERN.findall(text)
        if len(token) > 1 and token.lower() not in STOPWORDS
    ]


class CourseRetriever:
    def __init__(self, corpus_path: Path):
        data = json.loads(corpus_path.read_text(encoding="utf-8"))
        self.chunks: list[dict] = data["chunks"]
        self.documents = [tokenize(chunk["text"] + " " + chunk["section"]) for chunk in self.chunks]
        self.doc_freq = Counter()
        for doc in self.documents:
            self.doc_freq.update(set(doc))
        self.avg_len = sum(map(len, self.documents)) / max(len(self.documents), 1)

    def lexical_search(self, query: str, top_k: int) -> list[dict]:
        terms = tokenize(query)
        n_docs = len(self.documents)
        results: list[dict] = []
        for index, doc in enumerate(self.documents):
            frequencies = Counter(doc)
            heading = Counter(tokenize(self.chunks[index]["section"]))
            score = 0.0
            for term in terms:
                df = self.doc_freq.get(term, 0)
                if not df:
                    continue
                idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
                tf = frequencies[term]
                denominator = tf + 1.5 * (1 - 0.75 + 0.75 * len(doc) / self.avg_len)
                score += idf * (tf * 2.5 / denominator)
                if heading[term]:
                    score += idf * 1.4
            if score > 0:
                results.append({**self.chunks[index], "score": round(score, 4)})
        return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]
