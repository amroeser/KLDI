import numpy as np
from collections import Counter
import nltk
from nltk.util import ngrams
from typing import List, Tuple, Dict, Sequence, Optional

from .corpus import HumanCorpusRepository, bootstrap_human_corpus


def _ensure_nltk_tokenizers() -> None:
    """Ensure required NLTK tokenizer resources are available.

    Newer NLTK-Versionen verwenden teils "punkt_tab"; wir versuchen beide
    Ressourcen zu laden und laden sie bei Bedarf leise nach.
    """
    for resource in ("punkt", "punkt_tab"):
        try:
            nltk.data.find(f"tokenizers/{resource}")
        except LookupError:
            try:
                nltk.download(resource, quiet=True)
            except Exception:
                # Wenn der Download scheitert (z. B. offline), lassen wir die
                # Ausnahme später beim Tokenisieren hochkommen.
                pass


class KLDEvaluator:
    """
    Evaluates text quality using KL-Divergence and other metrics.
    """
    
    def __init__(
        self,
        n: int = 2,
        epsilon: float = 1e-10,
        corpus_repo: Optional[HumanCorpusRepository] = None,
        bootstrap_corpus: bool = False,
    ):
        """
        Initialize the evaluator with n-gram size.
        
        Args:
            n: The n-gram size to use (default: 2 for bigrams)
            epsilon: Smoothing factor to enforce overlapping support
        """
        self.n = n
        self.epsilon = epsilon
        self.corpus_repo = corpus_repo or HumanCorpusRepository()
        self.reference_texts: List[str] = []
        if bootstrap_corpus:
            self._load_reference_texts(force=bootstrap_corpus)
        else:
            self._load_reference_texts(force=False)

    def _load_reference_texts(self, force: bool = False) -> None:
        documents = bootstrap_human_corpus(self.corpus_repo, force=force)
        self.reference_texts = [doc.text for doc in documents if doc.text.strip()]
        
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text and optionally convert to n-grams."""
        _ensure_nltk_tokenizers()
        tokens = nltk.word_tokenize(text.lower())
        if self.n <= 1:
            return tokens
        return [" ".join(gram) for gram in ngrams(tokens, self.n)]

    def _build_distribution(self, tokens: Sequence[str], vocab: Sequence[str]) -> np.ndarray:
        """Convert token counts into a probability distribution over vocab."""
        counts = Counter(tokens)
        dist = np.array([counts[token] for token in vocab], dtype=float)
        total = dist.sum()
        if total == 0:
            return np.zeros_like(dist)
        return dist / total
    
    def calculate_kld(self, original: str, paraphrase: str) -> float:
        """
        Calculate KL-Divergence between original and paraphrased text.
        Lower values indicate more similar n-gram distributions.
        """
        p_tokens = self._tokenize(original)
        q_tokens = self._tokenize(paraphrase)

        vocab = sorted(set(p_tokens) | set(q_tokens))
        if self.reference_texts:
            reference_tokens = []
            for text in self.reference_texts:
                reference_tokens.extend(self._tokenize(text))
            if reference_tokens:
                vocab = sorted(set(vocab) | set(reference_tokens))

        if not vocab:
            return 0.0

        p = self._build_distribution(p_tokens, vocab)
        q = self._build_distribution(q_tokens, vocab)

        # Ensure support condition via smoothing on Q
        q = (q + self.epsilon) / (1 + self.epsilon * len(vocab))

        mask = p > 0
        if not np.any(mask):
            return 0.0

        ratio = p[mask] / q[mask]
        return float(np.sum(p[mask] * np.log2(ratio)))
    
    def evaluate_paraphrase(self, original: str, paraphrase: str) -> dict:
        """
        Evaluate the quality of a paraphrase.
        
        Returns:
            Dictionary containing evaluation metrics
        """
        # Calculate KL-Divergence
        kld = self.calculate_kld(original, paraphrase)
        
        # Calculate length ratio
        orig_len = len(original.split())
        para_len = len(paraphrase.split())
        length_ratio = para_len / orig_len if orig_len > 0 else 1.0
        
        # Calculate word overlap
        orig_words = set(original.lower().split())
        para_words = set(paraphrase.lower().split())
        common_words = orig_words.intersection(para_words)
        overlap_ratio = len(common_words) / len(orig_words) if orig_words else 0.0
        
        return {
            'kld': kld,
            'length_ratio': length_ratio,
            'word_overlap': overlap_ratio,
            'score': self._calculate_overall_score(kld, length_ratio, overlap_ratio)
        }
    
    def _calculate_overall_score(self, kld: float, length_ratio: float, overlap_ratio: float) -> float:
        """
        Calculate an overall score for the paraphrase quality.
        Lower KLD is better, length ratio close to 1 is better, moderate overlap is good.
        """
        # Normalize KLD (lower is better)
        kld_score = 1.0 / (1.0 + kld) if kld > 0 else 1.0
        
        # Penalize length ratios that are too different from 1.0
        length_score = 1.0 - abs(1.0 - length_ratio) * 0.5
        
        # Ideal overlap is around 0.5-0.7 - we want some but not too much overlap
        overlap_score = 1.0 - abs(0.6 - overlap_ratio)
        
        # Weighted average of scores
        return (kld_score * 0.5 + length_score * 0.25 + overlap_score * 0.25) * 100
