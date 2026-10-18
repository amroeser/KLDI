"""KLDI as computed in the experiment (paraphrase_agents/evaluator.py, KLDEvaluator(n=2)).

Note: the evaluator default n=2 means word *bigrams* after NLTK word_tokenize on lowercased text.
"""
from collections import Counter

import nltk
import numpy as np
from nltk.util import ngrams

N = 2
EPSILON = 1e-10


def _tokens(text: str, n: int = N):
    toks = nltk.word_tokenize(text.lower())
    return toks if n <= 1 else [" ".join(g) for g in ngrams(toks, n)]


def kldi(original: str, paraphrase: str, n: int = N, eps: float = EPSILON) -> float:
    p_t, q_t = _tokens(original, n), _tokens(paraphrase, n)
    vocab = sorted(set(p_t) | set(q_t))
    if not vocab:
        return 0.0
    cp, cq = Counter(p_t), Counter(q_t)
    p = np.array([cp[v] for v in vocab], dtype=float)
    q = np.array([cq[v] for v in vocab], dtype=float)
    p = p / p.sum() if p.sum() else p
    q = q / q.sum() if q.sum() else q
    q = (q + eps) / (1 + eps * len(vocab))
    m = p > 0
    if not np.any(m):
        return 0.0
    return float(np.sum(p[m] * np.log2(p[m] / q[m])))
