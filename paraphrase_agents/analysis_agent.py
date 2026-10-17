from __future__ import annotations

from typing import Any, Dict, Optional

from .config import get_default_model, get_openai_client


class AnalysisAgent:
    """LLM-based agent for summarizing run-level statistics.

    It receives already computed numerical metrics (stats_summary,
    per_domain, meta information) and produces a short, English
    scientific-style interpretation (2–3 sentences).
    """

    def __init__(self, model: Optional[str] = None, temperature: float = 0.2) -> None:
        self.model = model or get_default_model()
        self.temperature = temperature
        self.client = get_openai_client()

    def summarize_run(
        self,
        stats: Dict[str, Any],
        per_domain: Dict[str, Any],
        meta: Dict[str, Any],
    ) -> str:
        """Create a short English summary of the run.

        The function is implemented defensively: on API errors it raises a
        RuntimeError which can be handled by the pipeline.
        """

        # Wir geben die Daten als kompaktes JSON-ähnliches Dict in den Prompt,
        # damit das Modell eine konsistente Einordnung vornehmen kann.
        content_dict = {
            "meta": meta,
            "stats": stats,
            "per_domain": per_domain,
        }

        system_prompt = (
            "You are a scientific assistant for statistics and machine learning. "
            "You receive numerical results from a study on the detectability of AI-generated texts "
            "(KLDI distributions, AUC, p-values, effect sizes, confidence intervals). "
            "Write a short English summary (maximum 2–3 sentences) that assesses the robustness "
            "of the findings. Explicitly state whether AI-generated texts are clearly detectable "
            "in this sample based on KLDI (including AUC and p-value) or not. Base your judgement "
            "on AUC, p-values, sample sizes and effect sizes. Also mention whether the sample sizes "
            "are sufficient, whether the effect is small/medium/large, and whether the overall "
            "statement should be considered exploratory or robust. Use a neutral, scientific tone "
            "without bullet points or headings."
        )

        user_prompt = (
            "Here are the results as a Python-style dictionary:\n"
            f"{content_dict}\n\n"
            "Now produce the requested summary. Answer only with continuous prose, without bullet "
            "points and without referring to the prompt. Clearly state whether AI-generated texts "
            "in this concrete sample can be considered detectable based on KLDI (including AUC and "
            "p-value) or not."
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_tokens=400,
        )

        choice = response.choices[0]
        content = getattr(choice.message, "content", None)
        if not content:
            raise RuntimeError("AnalysisAgent returned empty content")
        return content.strip()
