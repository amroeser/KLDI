from typing import Dict, List, Optional
import numpy as np
from nltk.tokenize import sent_tokenize
import nltk

from .config import get_default_model, get_openai_client

# Download required NLTK data
nltk.download('punkt', quiet=True)

class ParaphraseAgent:
    def __init__(self, model: Optional[str] = None, temperature: float = 0.7):
        """
        Initialize the paraphrasing agent.
        
        Args:
            model: The OpenAI model to use for generation
            temperature: Controls randomness in generation (0.0 to 1.0)
        """
        self.model = model or get_default_model()
        self.temperature = temperature
        self.client = get_openai_client()
        
    def paraphrase(self, text: str, style: str = "casual") -> str:
        """Paraphrase the input text in a human-like manner.

        The model is instructed to stay close to the original while still
        changing the phrasing. We also defensively retry when the API
        returns empty or identical content.

        Args:
            text: The text to paraphrase
            style: The style of paraphrasing (e.g., 'casual', 'formal', 'concise')

        Returns:
            The paraphrased text (or the original text as a last-resort fallback)
        """
        system_prompt = (
            "You are a helpful assistant that rephrases text to sound more "
            f"{style} and human-like. "
            "Your goal is to make the text sound natural while preserving the original meaning. "
            "Keep the paraphrase as close as possible to the original in content, sentence count, "
            "and overall length. Prefer small, local changes in phrasing over large rewrites, and "
            "reuse important words and expressions where appropriate. "
            "Always change the wording at least slightly; do NOT return the input text unchanged. "
            "Vary sentence structure and word choice only as much as needed to sound natural. "
            "IMPORTANT: Respond with the paraphrased text ONLY, without any explanations, "
            "prefixes, suffixes, or quotation marks."
        )

        max_attempts = 3
        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": (
                                f"Please paraphrase the following text in a {style} style:\n\n{text}"
                            ),
                        },
                    ],
                    temperature=self.temperature,
                    max_tokens=2000,
                )

                # Defensive handling: some clients may return message.content = None
                choice = response.choices[0]
                content = getattr(choice.message, "content", None)
                if not content:
                    print(
                        f"Paraphrasing returned empty content (attempt {attempt}), retrying..."
                    )
                    continue

                candidate = content.strip()
                if not candidate:
                    print(
                        f"Paraphrasing returned whitespace-only content (attempt {attempt}), retrying..."
                    )
                    continue

                # Avoid accepting outputs that are effectively identical to the input
                if candidate == text or candidate.lower().strip() == text.lower().strip():
                    print(
                        f"Paraphrasing returned text identical to input (attempt {attempt}), retrying..."
                    )
                    continue

                return candidate
            except Exception as e:  # pragma: no cover - defensive logging
                last_error = e
                print(f"Error in paraphrasing (attempt {attempt}): {str(e)}")
                continue

        # Last-resort: wir konnten trotz mehrfacher Versuche keinen brauchbaren,
        # vom Input unterscheidbaren Paraphrase erzeugen. In diesem Fall wird
        # ein Fehler ausgelöst, damit der Run sichtbar fehlschlägt und keine
        # 1:1-Kopien in die Auswertung gelangen.
        if last_error is not None:
            msg = (
                f"Paraphrasing failed after {max_attempts} attempts due to errors: "
                f"{last_error}"
            )
        else:
            msg = (
                "Paraphrasing returned only empty or identical content "
                f"after {max_attempts} attempts."
            )
        raise RuntimeError(msg)

    def batch_paraphrase(self, texts: List[str], style: str = "casual") -> List[str]:
        """
        Paraphrase multiple texts in parallel.
        
        Args:
            texts: List of texts to paraphrase
            style: The style of paraphrasing
            
        Returns:
            List of paraphrased texts
        """
        return [self.paraphrase(text, style) for text in texts]

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences using NLTK's sentence tokenizer.
        """
        return sent_tokenize(text)
