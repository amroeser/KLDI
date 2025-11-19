from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple
import os
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import Run
from .results import get_run_rows


def _format_float(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "n/a"


def _format_ci(ci: Tuple[float, float] | List[float] | None, digits: int = 3) -> str:
    if not ci or len(ci) != 2:
        return "n/a"
    low, high = ci
    return f"[{float(low):.{digits}f}, {float(high):.{digits}f}]"


def _format_domains_list(domains: List[str] | None) -> str:
    if not domains:
        return "(none)"
    return ", ".join(sorted(domains))


def _format_per_domain_counts(per_domain: Dict[str, Dict[str, Any]] | None) -> str:
    if not per_domain:
        return "(no domain-level statistics available)"
    lines: List[str] = ["| Domain | Count | Avg KLDI | Human-like | Detectable |", "|--------|-------|----------|------------|-----------|"]
    for domain, stats in sorted(per_domain.items(), key=lambda x: x[0]):
        count = stats.get("count", 0)
        avg_kld = stats.get("avg_kld", 0.0)
        human_like = stats.get("human_like", 0)
        detectable = stats.get("detectable", 0)
        lines.append(
            f"| {domain} | {count} | {_format_float(avg_kld, 3)} | {human_like} | {detectable} |"
        )
    return "\n".join(lines)


def _format_config_table(run: Run, summary: Dict[str, Any]) -> str:
    lines = ["| Parameter | Value |", "|-----------|-------|"]
    lines.append(f"| Run ID | `{run.id}` |")
    lines.append(f"| Status | `{run.status.value}` |")
    lines.append(f"| Requested count | {run.requested_count} |")
    lines.append(f"| Per-domain count | {run.per_domain_count} |")
    lines.append(f"| LLM model | `{run.llm_model}` |")
    lines.append(f"| Temperature | {_format_float(run.temperature, 3)} |")
    if run.seed is not None:
        lines.append(f"| Seed | {run.seed} |")
    if run.git_commit:
        lines.append(f"| Git commit | `{run.git_commit}` |")

    stats = summary.get("stats") or {}
    lines.append(f"| Parallelism (backend) | {stats.get('parallelism', 'n/a')} |")

    # Environment-related info (if present in summary)
    meta = summary.get("meta") or {}
    if "openai_base_url" in meta:
        lines.append(f"| OpenAI base URL | `{meta['openai_base_url']}` |")

    return "\n".join(lines)


def generate_run_markdown_report(db: Session, run_id: str) -> str:
    """Generate an academic-style Markdown report for a single run.

    The report closely follows the methodology and terminology documented
    in the project README, so that it can be used directly in academic
    or technical reports.
    """

    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise ValueError(f"Run {run_id} not found")

    summary: Dict[str, Any] = run.summary or {}
    stats: Dict[str, Any] = summary.get("stats") or {}
    analysis: Dict[str, Any] = summary.get("analysis") or {}
    per_domain: Dict[str, Any] = summary.get("per_domain") or {}

    # Core counts
    documents_processed = summary.get("documents_processed") or summary.get("processed") or 0
    requested_count = summary.get("expected") or run.requested_count
    domains = summary.get("domains") or []

    # Statistics
    hh_count = stats.get("human_human_count")
    hk_count = stats.get("human_ki_count")
    adaptive_threshold = stats.get("adaptive_threshold")
    mannwhitney_p = stats.get("mannwhitney_p")
    roc_auc = stats.get("roc_auc")
    roc_auc_ci = stats.get("roc_auc_ci")
    cliffs_delta = stats.get("cliffs_delta")
    cliffs_delta_magnitude = stats.get("cliffs_delta_magnitude")
    kldi_median_diff = stats.get("kldi_median_diff")
    kldi_median_diff_ci = stats.get("kldi_median_diff_ci")
    kldi_initial_avg = stats.get("kldi_initial_avg")
    kldi_best_avg = stats.get("kldi_best_avg")
    kldi_avg_improvement = stats.get("kldi_avg_improvement")

    # Verteilungsstatistiken (Boxplot-Style)
    hh_min = stats.get("hh_min")
    hh_q1 = stats.get("hh_q1")
    hh_median = stats.get("hh_median")
    hh_q3 = stats.get("hh_q3")
    hh_max = stats.get("hh_max")
    hh_mean = stats.get("hh_mean")

    hk_min = stats.get("hk_min")
    hk_q1 = stats.get("hk_q1")
    hk_median = stats.get("hk_median")
    hk_q3 = stats.get("hk_q3")
    hk_max = stats.get("hk_max")
    hk_mean = stats.get("hk_mean")

    interpretation = analysis.get("interpretation") or ""
    llm_summary = analysis.get("llm_summary") or ""

    per_domain_table = _format_per_domain_counts(per_domain)
    config_table = _format_config_table(run, summary)

    # Derive highlight/lowlight bullets in a simple, reproducible way
    highlights: List[str] = []
    lowlights: List[str] = []

    if roc_auc is not None:
        if roc_auc >= 0.8:
            highlights.append(
                f"KLDI achieves high discriminative power in this run (ROC-AUC = {_format_float(roc_auc, 3)})."
            )
        elif roc_auc < 0.6:
            lowlights.append(
                f"KLDI shows limited discriminative power (ROC-AUC = {_format_float(roc_auc, 3)}), indicating strong overlap between Human→Human and Human→KI distributions."
            )

    if kldi_avg_improvement is not None:
        if kldi_avg_improvement > 0:
            highlights.append(
                f"Iterative paraphrasing reduced average KLDI by {_format_float(kldi_avg_improvement, 3)} (initial vs. best paraphrases)."
            )

    if cliffs_delta is not None and cliffs_delta_magnitude:
        highlights.append(
            f"Effect size (Cliff's delta) between Human→Human and Human→KI distributions is {_format_float(cliffs_delta, 3)} ({cliffs_delta_magnitude})."
        )

    if not highlights:
        highlights.append("No strong positive findings were detected; results should be interpreted as exploratory.")

    if not lowlights:
        lowlights.append("No additional methodological weaknesses beyond general KLDI limitations were identified in this run.")

    def _as_bullets(items: List[str]) -> str:
        return "\n".join(f"- {item}" for item in items)

    # Run timing
    created = run.created_at.isoformat() if isinstance(run.created_at, datetime) else str(run.created_at)

    markdown = f"""# Human-Like Text Paraphrasing – Run {run.id}

## 1. Abstract

This report summarizes a single experimental run of the *Human-Like Text Paraphrasing System*.
We investigate whether KI-generated paraphrases of human-written texts can be reliably detected
as machine-generated based on the Kullback–Leibler Divergence Index (KLDI) between original
and paraphrased texts.

**Key findings (Run {run.id}):**

- Number of documents (Human→KI): {hk_count if hk_count is not None else documents_processed}
- Number of pairs (Human→Human): {hh_count if hh_count is not None else "n/a"}
- ROC-AUC (KLDI as detector): {_format_float(roc_auc, 3)} (CI { _format_ci(roc_auc_ci, 3) })
- Mann–Whitney p-value: {_format_float(mannwhitney_p, 6) if mannwhitney_p is not None else "n/a"}
- Cliff's delta: {_format_float(cliffs_delta, 3) if cliffs_delta is not None else "n/a"} ({cliffs_delta_magnitude or "n/a"})
- Adaptive threshold T_adaptive: {_format_float(adaptive_threshold, 3) if adaptive_threshold is not None else "n/a"}

## 2. Introduction

The central research question of this project is:

> Sind KI-generierte Paraphrasen von menschlichen Texten anhand des
> Kullback-Leibler-Divergenz-Index (KLDI) zuverlässig als KI-Text erkennbar?

To address this question, the system scrapes pre‑2019 human-written texts from four fixed domains,
generates paraphrases using an OpenAI-compatible LLM, and compares the KLDI distributions of
Human→Human vs. Human→KI text pairs.

## 3. Methods

### 3.1 Data and Domains

Human-written source texts are scraped from documented, pre‑2019 sources (poetry, law, medicine/health, news).

For this run:

- Requested documents: {requested_count}
- Successfully processed documents: {documents_processed}
- Domains included: {_format_domains_list(domains)}

Per-domain summary:

{per_domain_table}

### 3.2 Paraphrasing Procedure

For each document, a paraphrase is generated using the `ParaphraseAgent`.

- Model: `{run.llm_model}`
- Temperature: {_format_float(run.temperature, 3)}
- Max paraphrasing iterations per document (backend): {_format_float(stats.get('max_paraphrase_iterations', None) or 0, 0)}

When iterative refinement is active, the system keeps the paraphrase with the lowest observed KLDI.

### 3.3 KLDI Computation

For each (Original P, Paraphrase Q) pair, the KLDEvaluator computes KLDI as described in the
project README:

1. Tokenization via NLTK (optionally n-grams).
2. Shared vocabulary X = Tokens(P) ∪ Tokens(Q).
3. Empirical distributions p(x) and q(x) based on token frequencies.
4. Support smoothing of Q: q'(x) = (q(x) + ε) / (1 + ε |X|), with ε ≈ 1e-10.
5. KLDI: D(P || Q) = Σ_x p(x) log2(p(x) / q'(x)), restricted to p(x) > 0.

### 3.4 Statistical Evaluation

Two KLDI distributions are constructed:

- Human→KI: D(P_human || Q_ki) for all paraphrases.
- Human→Human: KLDI between pairs of original texts within the same domain.

From the Human→Human distribution, an adaptive threshold is derived:

- Quartiles Q1, Q3 and IQR = Q3 − Q1.
- Adaptive threshold: T_adaptive = Q3 + 1.5 · IQR.

Each paraphrase is classified as:

- "human-like" if D(P || Q) ≤ T_adaptive.
- "detectable" if D(P || Q) > T_adaptive.

We further compute Mann–Whitney U-test, ROC/AUC, effect sizes (Cliff's delta) and
bootstrap confidence intervals, in line with the methodology described in the README.

### 3.5 Reproducibility

Run-level metadata and configuration are persisted in the database, including model,
temperature, seed and (optionally) Git commit.

## 4. Results

### 4.1 Descriptive Statistics

- Human→Human count: {hh_count if hh_count is not None else "n/a"}
- Human→KI count: {hk_count if hk_count is not None else documents_processed}
- Average KLDI (initial paraphrases): {_format_float(kldi_initial_avg, 3) if kldi_initial_avg is not None else "n/a"}
- Average KLDI (best paraphrases): {_format_float(kldi_best_avg, 3) if kldi_best_avg is not None else "n/a"}
- Average KLDI improvement (HK): {_format_float(kldi_avg_improvement, 3) if kldi_avg_improvement is not None else "n/a"}
- Median KLDI difference (HK − HH): {_format_float(kldi_median_diff, 3) if kldi_median_diff is not None else "n/a"} (CI { _format_ci(kldi_median_diff_ci, 3) })

### 4.2 Discriminative Power of KLDI

- Mann–Whitney p-value: {_format_float(mannwhitney_p, 6) if mannwhitney_p is not None else "n/a"}
- ROC-AUC: {_format_float(roc_auc, 3)} (CI { _format_ci(roc_auc_ci, 3) })
- Cliff's delta: {_format_float(cliffs_delta, 3) if cliffs_delta is not None else "n/a"} ({cliffs_delta_magnitude or "n/a"})

### 4.3 Adaptive Threshold and Classification

- Adaptive threshold T_adaptive: {_format_float(adaptive_threshold, 3) if adaptive_threshold is not None else "n/a"}

Per-domain classification summary:

{per_domain_table}

## 5. Discussion

**Rule-based interpretation** (from the statistical pipeline):

> {interpretation or "(no rule-based interpretation available)"}

**LLM-based summary** (optional, from AnalysisAgent):

> {llm_summary or "(no LLM-based summary available)"}

### 5.1 Highlights

{_as_bullets(highlights)}

### 5.2 Lowlights and Limitations

{_as_bullets(lowlights)}

## 6. Conclusion

For this run, the KLDI-based analysis suggests the following high-level answer to the
research question about KI-detectability:

> {llm_summary or interpretation or "No robust statement about KI detectability can be made based on this run."}

All conclusions should be interpreted in light of the sample size, domain selection and
known limitations of KLDI as a purely distributional similarity measure.

## 7. Appendix: Run Configuration

Creation timestamp: {created}

{config_table}
"""

    try:
        base_dir = Path("data") / "reports"
        base_dir.mkdir(parents=True, exist_ok=True)
        file_path = base_dir / f"run_{run.id}_report.md"
        file_path.write_text(markdown, encoding="utf-8")
    except Exception:
        pass

    return markdown
