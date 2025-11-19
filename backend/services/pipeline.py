from __future__ import annotations

import itertools
import os
import random
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple
import io

from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from scipy.stats import mannwhitneyu
from sklearn.metrics import roc_auc_score

from ..database import SessionLocal
from ..domains import DOMAINS
from ..models import Document, Evaluation, Paraphrase, Run, RunStatus
from paraphrase_agents.agent import ParaphraseAgent
from paraphrase_agents.evaluator import KLDEvaluator
from paraphrase_agents.analysis_agent import AnalysisAgent

# Snippet length configuration
MIN_PARAGRAPH_LENGTH = 80
MAX_PARAGRAPH_LENGTH = 220

# How many paraphrasing refinement steps per Dokument maximal
try:
    MAX_PARAPHRASE_ITERATIONS = max(1, int(os.getenv("MAX_PARAPHRASE_ITERATIONS", "5")))
except ValueError:
    MAX_PARAPHRASE_ITERATIONS = 5

# Wie oft wir höchstens versuchen, Snippets zu scrapen (Faktor * requested_count),
# bevor der Run als fehlgeschlagen gilt
MAX_SCRAPE_ATTEMPTS_FACTOR = 5

# Mindest-Stichprobengröße für robuste statistische Aussagen (pro Gruppe)
MIN_ROBUST_SAMPLE_SIZE = 30

# Anzahl Bootstrap-Samples für Konfidenzintervalle
BOOTSTRAP_SAMPLES = 200

# Intra-Run-Parallelität (Anzahl gleichzeitiger Dokumente)
try:
    PARALLELISM = max(1, int(os.getenv("PARALLELISM", "10")))
except ValueError:  # Fallback bei ungültigem Wert
    PARALLELISM = 10


def fetch_snippet_from_sources(sources: List[str]) -> Tuple[str, str]:
    """Fetch a real text snippet from the configured source URLs.

    Unterstützt sowohl HTML-Seiten als auch PDF-Dokumente.
    - HTML: wir extrahieren Text aus <p>-Tags.
    - PDF: wir extrahieren Fließtext aus den ersten Seiten.

    Der zurückgegebene Text landet als `original_text` in der Tabelle,
    die Paraphrase ist anschließend der OpenAI-Output zu genau diesem
    Ausschnitt.
    """
    if not sources:
        return "", ""

    # Wir versuchen ein paar zufällige Quellen, bis wir einen brauchbaren
    # Absatz finden.
    candidate_urls = list(sources)
    random.shuffle(candidate_urls)

    for url in candidate_urls[:5]:
        try:
            resp = requests.get(url, timeout=20)
            if resp.status_code != 200:
                continue

            content_type = resp.headers.get("Content-Type", "").lower()

            # HTML / Text-Seiten
            if "text/html" in content_type or "text/" in content_type:
                soup = BeautifulSoup(resp.text, "html.parser")
                paragraphs = [
                    " ".join(p.get_text(separator=" ", strip=True).split())
                    for p in soup.find_all("p")
                ]

                # Filter auf sinnvolle Länge
                candidates = [
                    p
                    for p in paragraphs
                    if MIN_PARAGRAPH_LENGTH <= len(p) <= MAX_PARAGRAPH_LENGTH
                ]

                if not candidates:
                    # Fallback: ggf. längere Texte kürzen
                    for p in paragraphs:
                        if len(p) > MIN_PARAGRAPH_LENGTH:
                            candidates.append(p[:MAX_PARAGRAPH_LENGTH])

                if not candidates:
                    continue

                snippet = random.choice(candidates)
                return snippet, url

            # PDF-Dokumente
            if "application/pdf" in content_type or url.lower().endswith(".pdf"):
                reader = PdfReader(io.BytesIO(resp.content))
                texts: list[str] = []
                # Nur die ersten paar Seiten auswerten, um Laufzeit zu begrenzen
                for page in reader.pages[:5]:
                    try:
                        page_text = page.extract_text() or ""
                    except Exception:
                        page_text = ""
                    if page_text:
                        texts.append(page_text)

                full_text = "\n".join(texts)
                if not full_text.strip():
                    continue

                # Primitive Absatzbildung: nach Doppel-Umbrüchen oder Punkten splitten
                raw_paragraphs = [
                    " ".join(part.strip().split())
                    for part in full_text.replace("\r", "\n").split("\n\n")
                ]

                paragraphs = [p for p in raw_paragraphs if p]

                candidates = [
                    p
                    for p in paragraphs
                    if MIN_PARAGRAPH_LENGTH <= len(p) <= MAX_PARAGRAPH_LENGTH
                ]

                if not candidates:
                    for p in paragraphs:
                        if len(p) > MIN_PARAGRAPH_LENGTH:
                            candidates.append(p[:MAX_PARAGRAPH_LENGTH])

                if not candidates:
                    continue

                snippet = random.choice(candidates)
                return snippet, url
        except Exception:
            # Bei Netzwerk-/Parsingfehlern einfach die nächste Quelle probieren
            continue

    # Wenn alles fehlschlägt, kein Dokument erzeugen
    return "", ""


def _paraphrase_and_score(
    snippet: str,
    paraphraser: ParaphraseAgent,
    evaluator: KLDEvaluator,
) -> Dict[str, object] | None:
    """Führe die iterative Paraphrasierung und KLDI-Bewertung für ein Dokument durch.

    Diese Funktion ist thread-fähig und berührt keine Datenbankobjekte; sie kann
    daher gefahrlos im ThreadPoolExecutor ausgeführt werden.
    """

    best_paraphrase_text: str | None = None
    best_kld: float = float("inf")
    initial_kld: float | None = None
    iterations_used = 0

    for iteration in range(1, MAX_PARAPHRASE_ITERATIONS + 1):
        paraphrase_text = paraphraser.paraphrase(snippet)
        kld_value = evaluator.calculate_kld(snippet, paraphrase_text)

        if initial_kld is None:
            initial_kld = kld_value

        if kld_value < best_kld:
            best_kld = kld_value
            best_paraphrase_text = paraphrase_text

        iterations_used = iteration

    if best_paraphrase_text is None:
        return None

    return {
        "best_paraphrase_text": best_paraphrase_text,
        "best_kld": float(best_kld),
        "initial_kld": float(initial_kld) if initial_kld is not None else None,
        "iterations_used": iterations_used,
    }


def process_run_job(run_id: str, domain_slugs: List[str] | None = None) -> None:
    session = SessionLocal()
    try:
        run = session.get(Run, run_id)
        if not run:
            return
        # Seed python-level randomness for reproducible scraping/snippet Auswahl
        if run.seed is not None:
            random.seed(run.seed)
        run.status = RunStatus.RUNNING
        run.summary = {
            "stage": "initializing",
            "processed": 0,
            "expected": run.requested_count,
            "parallelism": PARALLELISM,
        }
        session.commit()

        paraphraser = ParaphraseAgent(model=run.llm_model, temperature=run.temperature)
        evaluator = KLDEvaluator(bootstrap_corpus=True)

        # Ermittele, welche Domains für diesen Run aktiv sind
        if domain_slugs:
            active_domains = [d for d in DOMAINS if d.slug in domain_slugs]
            if not active_domains:
                active_domains = DOMAINS
        else:
            active_domains = DOMAINS

        # Merke die ausgewählten Domains im Summary, damit im UI ersichtlich ist,
        # welche Themenfelder für diesen Run verwendet wurden
        if isinstance(run.summary, dict):
            run.summary["domains"] = [d.slug for d in active_domains]
            session.commit()

        total_created = 0
        hk_values: List[float] = []  # Human→KI KLDI-Werte (bestes Ergebnis nach Iterationen)
        hk_initial_values: List[float] = []  # KLDI nach erster Paraphrasierung
        domain_stats: Dict[str, Dict[str, float | int]] = defaultdict(
            lambda: {"count": 0, "kldi_sum": 0.0, "human_like": 0, "detectable": 0}
        )

        # Wir rotieren über alle aktiven Domains, bis genau requested_count Dokumente erzeugt wurden
        max_attempts = run.requested_count * MAX_SCRAPE_ATTEMPTS_FACTOR
        attempts = 0
        domain_cycle = itertools.cycle(active_domains)

        # Parallelisierte Verarbeitung von Dokumenten in Batches
        with ThreadPoolExecutor(max_workers=PARALLELISM) as executor:
            while total_created < run.requested_count and attempts < max_attempts:
                futures: Dict[object, Tuple[Document, str, str]] = {}

                # Baue einen Batch von bis zu PARALLELISM Dokumenten
                while (
                    len(futures) < PARALLELISM
                    and total_created + len(futures) < run.requested_count
                    and attempts < max_attempts
                ):
                    domain = next(domain_cycle)
                    attempts += 1

                    snippet, source_url = fetch_snippet_from_sources(domain.sources)
                    if not snippet:
                        continue

                    document = Document(
                        run_id=run.id,
                        domain=domain.slug,
                        source_url=source_url,
                        retrieved_at=datetime.utcnow(),
                        original_text=snippet,
                    )
                    session.add(document)
                    session.flush()

                    future = executor.submit(
                        _paraphrase_and_score,
                        snippet,
                        paraphraser,
                        evaluator,
                    )
                    futures[future] = (document, domain.slug, snippet)

                if not futures:
                    # Keine weiteren Snippets konnten gewonnen werden
                    break

                # Ergebnisse einsammeln und in der DB speichern
                for future in as_completed(futures):
                    document, domain_slug, snippet = futures[future]
                    try:
                        result = future.result()
                    except Exception:
                        # Paraphrasierung fehlgeschlagen -> Dokument verwerfen
                        session.delete(document)
                        session.flush()
                        continue

                    if not result:
                        session.delete(document)
                        session.flush()
                        continue

                    best_paraphrase_text = result["best_paraphrase_text"]
                    best_kld = float(result["best_kld"])
                    initial_kld = result["initial_kld"]
                    iterations_used = int(result["iterations_used"])

                    session.add(
                        Paraphrase(
                            document_id=document.id,
                            llm_model=run.llm_model,
                            temperature=run.temperature,
                            paraphrased_text=best_paraphrase_text,
                        )
                    )

                    token_stats = {
                        "length_original": len(snippet.split()),
                        "length_paraphrase": len(best_paraphrase_text.split()),
                        "iterations": iterations_used,
                    }
                    if initial_kld is not None:
                        token_stats["kldi_initial"] = float(initial_kld)
                    token_stats["kldi_best"] = float(best_kld)

                    session.add(
                        Evaluation(
                            document_id=document.id,
                            kldi=best_kld,
                            token_stats=token_stats,
                            classification="human-like",  # Platzhalter; finale Klassifikation folgt später
                        )
                    )

                    total_created += 1
                    hk_values.append(best_kld)
                    if initial_kld is not None:
                        hk_initial_values.append(initial_kld)
                    stats = domain_stats[domain_slug]
                    stats["count"] += 1
                    stats["kldi_sum"] += best_kld
                    stats["human_like"] += 1

                    # Fortschritt grob aktualisieren (nicht bei jedem einzelnen Dokument committen)
                    if total_created % 10 == 0:
                        run.summary = {
                            "stage": "processing",
                            "processed": total_created,
                            "expected": run.requested_count,
                            "parallelism": PARALLELISM,
                        }
                        session.commit()

        # Wenn wir trotz mehrfacher Versuche nicht genug Dokumente erzeugen konnten, schlagen wir fehl.
        if total_created < run.requested_count:
            run.status = RunStatus.FAILED
            run.summary = {
                "stage": "failed",
                "error": f"Only {total_created} of {run.requested_count} documents could be scraped and processed.",
                "processed": total_created,
                "expected": run.requested_count,
            }
            session.commit()
            return

        # Prüfe, ob alle ausgewählten Domains mindestens ein Dokument liefern konnten.
        # Wenn einzelne Domains keine Dokumente liefern (z.B. wegen toter Links oder
        # nicht auswertbarer PDFs), vermerken wir das als Warnung im Summary, lassen
        # den Run aber weiterlaufen, solange insgesamt Dokumente vorhanden sind.
        missing_domains = [d.slug for d in active_domains if domain_stats[d.slug]["count"] == 0]
        if missing_domains and total_created > 0:
            if isinstance(run.summary, dict):
                warnings = run.summary.get("warnings") or []
                warnings.append(
                    "No documents processed for domains: "
                    + ", ".join(sorted(missing_domains))
                )
                run.summary["warnings"] = warnings
                run.summary["missing_domains"] = missing_domains
                session.commit()

        # Baseline Human→Human KLDI und statistische Tests
        run.summary = {
            "stage": "computing_stats",
            "processed": total_created,
            "expected": run.requested_count,
            "parallelism": PARALLELISM,
        }
        session.commit()
        hh_values: List[float] = []
        if total_created > 1:
            docs = (
                session.query(Document)
                .filter(Document.run_id == run.id)
                .order_by(Document.domain, Document.id)
                .all()
            )
            # Erzeuge eine begrenzte Anzahl Human→Human-Paare pro Domäne
            pairs: List[Tuple[str, str]] = []
            max_pairs_per_domain = 50
            by_domain: Dict[str, List[Document]] = defaultdict(list)
            for d in docs:
                by_domain[d.domain].append(d)
            for domain, dom_docs in by_domain.items():
                if len(dom_docs) < 2:
                    continue
                local_pairs = 0
                for i in range(len(dom_docs) - 1):
                    for j in range(i + 1, len(dom_docs)):
                        pairs.append((dom_docs[i].original_text, dom_docs[j].original_text))
                        local_pairs += 1
                        if local_pairs >= max_pairs_per_domain:
                            break
                    if local_pairs >= max_pairs_per_domain:
                        break
            for t1, t2 in pairs:
                hh_values.append(evaluator.calculate_kld(t1, t2))

        # Adaptive Schwelle und statistische Bewertung
        stats_summary: Dict[str, object] = {}
        adaptive_threshold: float | None = None
        p_value: float | None = None
        auc: float | None = None
        cliffs_delta: float | None = None
        cliffs_magnitude: str | None = None
        roc_auc_ci: Tuple[float, float] | None = None
        kldi_median_diff: float | None = None
        kldi_median_diff_ci: Tuple[float, float] | None = None
        robust_samples: bool = False

        if hh_values and hk_values:
            hh_arr = np.array(hh_values)
            hk_arr = np.array(hk_values)

            # Stichprobengröße prüfen
            n_hh = len(hh_arr)
            n_hk = len(hk_arr)
            robust_samples = n_hh >= MIN_ROBUST_SAMPLE_SIZE and n_hk >= MIN_ROBUST_SAMPLE_SIZE

            # Verteilungszusammenfassung (für Boxplots / Dichtevisualisierung)
            hh_min = float(np.min(hh_arr))
            hh_q1 = float(np.percentile(hh_arr, 25))
            hh_median = float(np.median(hh_arr))
            hh_q3 = float(np.percentile(hh_arr, 75))
            hh_max = float(np.max(hh_arr))
            hh_mean = float(np.mean(hh_arr))

            hk_min = float(np.min(hk_arr))
            hk_q1 = float(np.percentile(hk_arr, 25))
            hk_median = float(np.median(hk_arr))
            hk_q3 = float(np.percentile(hk_arr, 75))
            hk_max = float(np.max(hk_arr))
            hk_mean = float(np.mean(hk_arr))

            # Schwelle: oberes Quartil plus 1.5*IQR als "klar über menschlichem Bereich"
            iqr = hh_q3 - hh_q1
            adaptive_threshold = float(hh_q3 + 1.5 * iqr)

            # Mann-Whitney-U-Test Human→Human vs Human→KI
            try:
                stat, p_value = mannwhitneyu(hh_arr, hk_arr, alternative="two-sided")
            except Exception:
                p_value = None

            # ROC/AUC für KLDI als Detektor
            labels = [0] * len(hh_arr) + [1] * len(hk_arr)
            scores = list(hh_arr) + list(hk_arr)
            try:
                auc = float(roc_auc_score(labels, scores))
            except Exception:
                auc = None

            # Effektstärke: Cliff's Delta (HH vs HK, höhere Werte = eher KI)
            try:
                greater = 0
                less = 0
                for x in hh_arr:
                    for y in hk_arr:
                        if x > y:
                            greater += 1
                        elif x < y:
                            less += 1
                denom = float(n_hh * n_hk)
                cliffs_delta = (greater - less) / denom if denom > 0 else None
                if cliffs_delta is not None:
                    ad = abs(cliffs_delta)
                    if ad < 0.147:
                        cliffs_magnitude = "negligible"
                    elif ad < 0.33:
                        cliffs_magnitude = "small"
                    elif ad < 0.474:
                        cliffs_magnitude = "medium"
                    else:
                        cliffs_magnitude = "large"
            except Exception:
                cliffs_delta = None
                cliffs_magnitude = None

            # Bootstrap-Konfidenzintervalle nur, wenn Stichprobe halbwegs groß ist
            roc_auc_ci = None
            kldi_median_diff = None
            kldi_median_diff_ci = None
            if robust_samples and auc is not None:
                rng = np.random.default_rng()
                auc_samples: List[float] = []
                diff_samples: List[float] = []
                for _ in range(BOOTSTRAP_SAMPLES):
                    # Resample pro Gruppe
                    hh_bs = rng.choice(hh_arr, size=n_hh, replace=True)
                    hk_bs = rng.choice(hk_arr, size=n_hk, replace=True)
                    labels_bs = [0] * n_hh + [1] * n_hk
                    scores_bs = list(hh_bs) + list(hk_bs)
                    try:
                        auc_bs = roc_auc_score(labels_bs, scores_bs)
                    except Exception:
                        continue
                    auc_samples.append(auc_bs)
                    diff_samples.append(float(np.median(hk_bs) - np.median(hh_bs)))

                if auc_samples:
                    low, high = np.percentile(auc_samples, [2.5, 97.5])
                    roc_auc_ci = (float(low), float(high))
                if diff_samples:
                    kldi_median_diff = float(np.median(diff_samples))
                    low, high = np.percentile(diff_samples, [2.5, 97.5])
                    kldi_median_diff_ci = (float(low), float(high))

            # Aggregierte KLDI-Iterationswerte
            if hk_initial_values:
                kldi_initial_avg = float(np.mean(hk_initial_values))
                kldi_best_avg = float(np.mean(hk_values))
                kldi_avg_improvement = float(
                    kldi_initial_avg - kldi_best_avg
                )
            else:
                kldi_initial_avg = None
                kldi_best_avg = None
                kldi_avg_improvement = None

            stats_summary = {
                "human_human_count": len(hh_arr),
                "human_ki_count": len(hk_arr),
                "adaptive_threshold": adaptive_threshold,
                "mannwhitney_p": p_value,
                "roc_auc": auc,
                "roc_auc_ci": roc_auc_ci,
                "cliffs_delta": cliffs_delta,
                "cliffs_delta_magnitude": cliffs_magnitude,
                "kldi_initial_avg": kldi_initial_avg,
                "kldi_best_avg": kldi_best_avg,
                "kldi_avg_improvement": kldi_avg_improvement,
                "kldi_median_diff": kldi_median_diff,
                "kldi_median_diff_ci": kldi_median_diff_ci,
                "robust_sample_sizes": robust_samples,
                "parallelism": PARALLELISM,
                # Verteilungszusammenfassung (Boxplot-Style)
                "hh_min": hh_min,
                "hh_q1": hh_q1,
                "hh_median": hh_median,
                "hh_q3": hh_q3,
                "hh_max": hh_max,
                "hh_mean": hh_mean,
                "hk_min": hk_min,
                "hk_q1": hk_q1,
                "hk_median": hk_median,
                "hk_q3": hk_q3,
                "hk_max": hk_max,
                "hk_mean": hk_mean,
            }

        # Finale Klassifikation mit adaptiver Schwelle, falls vorhanden
        if adaptive_threshold is not None:
            evals = (
                session.query(Evaluation)
                .join(Document, Evaluation.document_id == Document.id)
                .filter(Document.run_id == run.id)
                .all()
            )
            # Reset domain_stats und neu zählen mit finaler Klassifikation
            for stats in domain_stats.values():
                stats["human_like"] = 0
                stats["detectable"] = 0
            for ev in evals:
                cls = "human-like" if ev.kldi <= adaptive_threshold else "detectable"
                ev.classification = cls
                dom = ev.document.domain
                stats = domain_stats[dom]
                stats[cls.replace("-", "_")] += 1

        # Textuelle Einwertung
        interpretation = "Nicht genug Daten für eine statistische Bewertung."
        if adaptive_threshold is not None and auc is not None:
            # Basis-Aussage abhängig von Signifikanz, AUC und Effektstärke
            if p_value is not None and p_value < 0.05 and auc >= 0.7:
                if stats_summary.get("robust_sample_sizes") and stats_summary.get("cliffs_delta_magnitude") in {
                    "medium",
                    "large",
                }:
                    interpretation = (
                        "Starke Evidenz: KLDI hoch und Unterschied statistisch signifikant "
                        "mit ausreichender Stichprobengröße und mindestens mittlerer Effektstärke. "
                        "KI-Text ist in dieser Stichprobe robust erkennbar."
                    )
                else:
                    interpretation = (
                        "Signifikanter Unterschied im KLDI und erhöhte AUC, aber Stichprobengröße "
                        "oder Effektstärke sind begrenzt. Ergebnis ist als vorläufig/explorativ zu werten."
                    )
            else:
                interpretation = (
                    "Keine klare Signifikanz oder niedrige AUC: die KLDI-Verteilungen von Human→Human "
                    "und Human→KI überlappen stark. Eine zuverlässige Unterscheidung ist anhand des KLDI "
                    "in dieser Stichprobe nicht möglich."
                )

        # Per-Domain-Zusammenfassung vorbereiten (für LLM und finale Summary)
        if total_created > 0:
            per_domain_summary = {
                domain: {
                    "count": stats["count"],
                    "avg_kld": stats["kldi_sum"] / stats["count"] if stats["count"] else 0.0,
                    "human_like": stats["human_like"],
                    "detectable": stats["detectable"],
                }
                for domain, stats in domain_stats.items()
            }
        else:
            per_domain_summary = {}

        # LLM-basierte Zusammenfassung der Statistik (optional)
        llm_summary: str | None = None
        try:
            # Nur versuchen, wenn Statistiken vorhanden sind und das LLM verfügbar ist
            if stats_summary:
                analysis_agent = AnalysisAgent(model=run.llm_model)
                meta_info = {
                    "requested_count": run.requested_count,
                    "documents_processed": total_created,
                    "domains": [d.slug for d in active_domains],
                }
                llm_summary = analysis_agent.summarize_run(
                    stats=stats_summary,
                    per_domain=per_domain_summary,
                    meta=meta_info,
                )
        except Exception:
            # LLM-Zusammenfassung ist optional; bei Fehlern bleiben wir bei der
            # regelbasierten Interpretation.
            llm_summary = None

        if total_created == 0:
            run.status = RunStatus.FAILED
            run.summary = {
                "stage": "failed",
                "error": "No documents processed",
                "documents_processed": 0,
                "processed": 0,
                "expected": run.requested_count,
                "domains": [d.slug for d in active_domains],
                "analysis": {
                    "interpretation": interpretation,
                    "llm_summary": llm_summary,
                }
                if interpretation or llm_summary
                else None,
            }
        else:
            run.status = RunStatus.COMPLETED
            run.summary = {
                "stage": "completed",
                "documents_processed": total_created,
                "processed": total_created,
                "expected": run.requested_count,
                "domains": [d.slug for d in active_domains],
                "per_domain": per_domain_summary,
                "stats": stats_summary,
                "analysis": {
                    "interpretation": interpretation,
                    "llm_summary": llm_summary,
                },
            }
        session.commit()
    except Exception as exc:  # pragma: no cover
        session.rollback()
        run = session.get(Run, run_id)
        if run:
            run.status = RunStatus.FAILED
            run.summary = {
                "stage": "failed",
                "error": str(exc),
                "processed": 0,
                "expected": run.requested_count if hasattr(run, "requested_count") else None,
            }
            session.commit()
    finally:
        session.close()
