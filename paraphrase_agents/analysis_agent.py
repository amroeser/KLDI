from __future__ import annotations

from typing import Any, Dict, Optional

from .config import get_default_model, get_openai_client


class AnalysisAgent:
    """LLM-basierter Agent zur Zusammenfassung der Run-Statistik.

    Er erhält die bereits berechneten numerischen Kennzahlen (stats_summary,
    per_domain, Meta-Infos) und erzeugt eine kurze, deutschsprachige
    wissenschaftliche Einordnung (2–3 Sätze).
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
        """Erzeuge eine kurze deutschsprachige Zusammenfassung.

        Die Funktion ist defensiv implementiert: bei API-Fehlern wird eine
        RuntimeError ausgelöst, die von der Pipeline abgefangen werden kann.
        """

        # Wir geben die Daten als kompaktes JSON-ähnliches Dict in den Prompt,
        # damit das Modell eine konsistente Einordnung vornehmen kann.
        content_dict = {
            "meta": meta,
            "stats": stats,
            "per_domain": per_domain,
        }

        system_prompt = (
            "Du bist ein wissenschaftlicher Assistent für Statistik und Machine Learning. "
            "Du erhältst numerische Kennzahlen einer Studie zur Erkennbarkeit von KI-Texten "
            "(KLDI-Verteilungen, AUC, p-Wert, Effektstärken, Konfidenzintervalle). "
            "Formuliere eine kurze Zusammenfassung auf Deutsch (maximal 2–3 Sätze), "
            "die die Robustheit der Ergebnisse einordnet. Erwähne explizit, ob KI-Texte in "
            "dieser Stichprobe anhand des KLDI klar erkennbar sind oder nicht (z.B. \"nicht "
            "zuverlässig unterscheidbar\"), und stütze dich dabei auf AUC, p-Wert, "
            "Stichprobengrößen und Effektstärken. Erwähne außerdem, ob die Stichprobengrößen "
            "ausreichend sind, ob der Effekt eher klein/ mittel/ groß ist und ob die Aussage "
            "eher explorativ oder robust ist. Verwende eine sachliche, wissenschaftlich "
            "klingende Sprache ohne Aufzählungen oder Überschriften."
        )

        user_prompt = (
            "Hier sind die Ergebnisse als Python-Dictionary:\n"
            f"{content_dict}\n\n"
            "Erstelle jetzt die beschriebene Zusammenfassung. Antworte nur mit dem Fließtext, "
            "ohne Aufzählungen und ohne weitere Erklärungen über den Prompt. Stelle klar, ob "
            "KI-Texte in dieser konkreten Stichprobe anhand des KLDI (inkl. AUC/p-Wert) als "
            "erkennbar gelten können oder nicht."
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
