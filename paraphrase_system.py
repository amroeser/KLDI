import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.stats import entropy
import nltk
from nltk.tokenize import sent_tokenize
from typing import List, Dict, Tuple
import os

from paraphrase_agents.config import get_default_model, get_openai_client

class ParaphraserAgent:
    def __init__(self, model: str | None = None):
        self.client = get_openai_client()
        self.model = model or get_default_model()
        
    def paraphrase(self, text: str, temperature: float = 0.7) -> str:
        """Paraphrase the input text to sound more natural."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that rephrases text to sound more natural and human-like while preserving the original meaning."},
                    {"role": "user", "content": f"Please paraphrase the following text to sound more natural and human-like. Keep the core meaning the same but vary the wording and sentence structure. Here's the text: {text}"}
                ],
                temperature=temperature,
                max_tokens=1000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error in paraphrasing: {e}")
            return text

class HumanLikenessEvaluator:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english')
        self.reference_corpus = []  # This should be populated with human-written text
        
    def calculate_kld(self, text: str) -> float:
        """Calculate KL-Divergence between the text and reference human text."""
        if not self.reference_corpus:
            # If no reference corpus, return a default value
            return 0.0
            
        # Combine reference corpus with current text
        all_texts = self.reference_corpus + [text]
        
        # Create TF-IDF vectors
        try:
            tfidf = self.vectorizer.fit_transform(all_texts)
            
            # Calculate probability distributions
            p = tfidf[-1].toarray().flatten()  # Current text
            q = tfidf[:-1].mean(axis=0).A1  # Average of reference texts
            
            # Add small epsilon to avoid division by zero
            p = p + 1e-10
            q = q + 1e-10
            
            # Calculate KL-Divergence
            kld = entropy(p, q)
            return kld
            
        except Exception as e:
            print(f"Error calculating KLD: {e}")
            return float('inf')

class RefinementAgent:
    def __init__(self, paraphraser: ParaphraserAgent, evaluator: HumanLikenessEvaluator):
        self.paraphraser = paraphraser
        self.evaluator = evaluator
        self.max_iterations = 3
        
    def refine_text(self, original_text: str) -> Tuple[str, float]:
        """Refine text through multiple paraphrasing iterations."""
        current_text = original_text
        best_text = current_text
        best_kld = float('inf')
        
        for i in range(self.max_iterations):
            # Paraphrase the text
            paraphrased = self.paraphraser.paraphrase(current_text)
            
            # Calculate KLD
            current_kld = self.evaluator.calculate_kld(paraphrased)
            
            # Update best result if improved
            if current_kld < best_kld:
                best_kld = current_kld
                best_text = paraphrased
                
            current_text = paraphrased
            
        return best_text, best_kld

class MultiAgentParaphraseSystem:
    def __init__(self):
        self.paraphraser = ParaphraserAgent()
        self.evaluator = HumanLikenessEvaluator()
        self.refiner = RefinementAgent(self.paraphraser, self.evaluator)
        
    def process_text(self, text: str) -> Dict[str, any]:
        """Process text through the entire pipeline."""
        # Initial paraphrase
        initial_paraphrase = self.paraphraser.paraphrase(text)
        initial_kld = self.evaluator.calculate_kld(initial_paraphrase)
        
        # Refinement
        final_text, final_kld = self.refiner.refine_text(initial_paraphrase)
        
        return {
            "original_text": text,
            "initial_paraphrase": initial_paraphrase,
            "initial_kld": initial_kld,
            "final_text": final_text,
            "final_kld": final_kld,
            "improvement": initial_kld - final_kld if initial_kld != float('inf') else 0
        }

def main():
    # Example usage
    system = MultiAgentParaphraseSystem()
    
    # Example text to paraphrase
    example_text = """
    The quick brown fox jumps over the lazy dog. This is a simple example sentence 
    that contains all the letters in the English alphabet.
    """
    
    result = system.process_text(example_text)
    
    print("\nOriginal Text:")
    print(result["original_text"])
    print("\nInitial Paraphrase:")
    print(result["initial_paraphrase"])
    print("\nFinal Refined Text:")
    print(result["final_text"])
    print(f"\nKLD Improvement: {result['improvement']:.4f}")

if __name__ == "__main__":
    main()
