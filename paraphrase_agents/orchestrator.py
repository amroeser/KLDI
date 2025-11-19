from typing import List, Dict, Any, Optional
import numpy as np
import os
from concurrent.futures import ThreadPoolExecutor
from .agent import ParaphraseAgent
from .evaluator import KLDEvaluator
import time

class ParaphraseOrchestrator:
    """
    Orchestrates multiple paraphrasing agents to generate and evaluate paraphrases.
    """
    
    def __init__(self, num_agents: int = 3, model: Optional[str] = None):
        """
        Initialize the orchestrator with multiple agents.
        
        Args:
            num_agents: Number of paraphrase agents to use
            model: The OpenAI model to use for generation
        """
        self.agents = [ParaphraseAgent(model=model, temperature=0.5 + 0.1*i) for i in range(num_agents)]
        self.evaluator = KLDEvaluator()
        
    def paraphrase_with_feedback_loop(self, text: str, max_iterations: int = 3, target_kld: float = 0.5) -> Dict[str, Any]:
        """
        Generate a paraphrase using multiple agents and refine it based on feedback.
        
        Args:
            text: The original text to paraphrase
            max_iterations: Maximum number of refinement iterations
            target_kld: Target KL-Divergence value (lower = more similar to original)
            
        Returns:
            Dictionary containing the best paraphrase and evaluation metrics
        """
        # Initial paraphrases from all agents
        styles = ["casual", "professional", "concise", "detailed", "friendly"]
        paraphrases = []
        
        # Generate initial paraphrases
        for i, agent in enumerate(self.agents):
            style = styles[i % len(styles)]
            paraphrase = agent.paraphrase(text, style=style)
            evaluation = self.evaluator.evaluate_paraphrase(text, paraphrase)
            paraphrases.append({
                'text': paraphrase,
                'agent_id': i,
                'style': style,
                'evaluation': evaluation
            })
        
        # Select best initial paraphrase
        best_paraphrase = max(paraphrases, key=lambda x: x['evaluation']['score'])
        current_kld = best_paraphrase['evaluation']['kld']
        
        # Refinement loop
        iteration = 0
        while iteration < max_iterations and abs(current_kld - target_kld) > 0.1:
            iteration += 1
            
            # Get feedback for the current best paraphrase
            feedback = self._generate_feedback(
                text, 
                best_paraphrase['text'], 
                best_paraphrase['evaluation']
            )
            
            # Generate refined paraphrases
            refined_paraphrases = []
            for i, agent in enumerate(self.agents):
                refined = agent.paraphrase(
                    f"Original: {text}\nCurrent paraphrase: {best_paraphrase['text']}\nFeedback: {feedback}"
                )
                evaluation = self.evaluator.evaluate_paraphrase(text, refined)
                refined_paraphrases.append({
                    'text': refined,
                    'agent_id': i,
                    'iteration': iteration,
                    'evaluation': evaluation
                })
            
            # Update best paraphrase if improved
            best_refined = max(refined_paraphrases, key=lambda x: x['evaluation']['score'])
            if best_refined['evaluation']['score'] > best_paraphrase['evaluation']['score']:
                best_paraphrase = best_refined
                current_kld = best_paraphrase['evaluation']['kld']
            
            # Early stopping if we're close enough to target KLD
            if abs(current_kld - target_kld) < 0.1:
                break
        
        return best_paraphrase
    
    def _generate_feedback(self, original: str, paraphrase: str, evaluation: dict) -> str:
        """Generate feedback for the current paraphrase."""
        kld = evaluation['kld']
        length_ratio = evaluation['length_ratio']
        overlap = evaluation['word_overlap']
        
        feedback = []
        
        # KLD feedback
        if kld > 0.8:
            feedback.append("The paraphrase is too different from the original. Try to preserve more of the original meaning.")
        elif kld < 0.3:
            feedback.append("The paraphrase is too similar to the original. Try to be more creative with the rewording.")
        
        # Length feedback
        if length_ratio > 1.3:
            feedback.append("The paraphrase is too long. Try to be more concise.")
        elif length_ratio < 0.7:
            feedback.append("The paraphrase is too short. Try to include more details from the original.")
        
        # Word overlap feedback
        if overlap > 0.8:
            feedback.append("The paraphrase uses too many of the same words as the original. Try to use more synonyms and different phrasing.")
        elif overlap < 0.3:
            feedback.append("The paraphrase doesn't share enough words with the original. Try to preserve some key terms.")
        
        return " ".join(feedback) if feedback else "Good job! The paraphrase is well-balanced."
    
    def batch_paraphrase(self, texts: List[str], **kwargs) -> List[Dict[str, Any]]:
        """Paraphrase multiple texts in parallel."""
        if not texts:
            return []

        try:
            max_workers_env = int(os.getenv("ORCHESTRATOR_BATCH_PARALLELISM", "4"))
            max_workers = max(1, max_workers_env)
        except ValueError:
            max_workers = 4

        max_workers = min(max_workers, len(texts))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self.paraphrase_with_feedback_loop, text, **kwargs)
                for text in texts
            ]
            results: List[Dict[str, Any]] = []
            for future in futures:
                results.append(future.result())
        return results
