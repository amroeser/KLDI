# Human-Like Text Paraphrasing – Run 510b28a7-c573-4002-8304-2295872f5d6c

## 1. Abstract

This report summarizes a single experimental run of the *Human-Like Text Paraphrasing System*.
We investigate whether KI-generated paraphrases of human-written texts can be reliably detected
as machine-generated based on the Kullback–Leibler Divergence Index (KLDI) between original
and paraphrased texts.

**Key findings (Run 510b28a7-c573-4002-8304-2295872f5d6c):**

- Number of documents (Human→KI): 500
- Number of pairs (Human→Human): 200
- ROC-AUC (KLDI as detector): 0.259 (CI [0.211, 0.321])
- Mann–Whitney p-value: 0.000000
- Cliff's delta: 0.481 (large)
- Adaptive threshold T_adaptive: 63.358

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

- Requested documents: 500
- Successfully processed documents: 500
- Domains included: law, medical, news, poetry

Per-domain summary:

| Domain | Count | Avg KLDI | Human-like | Detectable |
|--------|-------|----------|------------|-----------|
| law | 150 | 14.196 | 150 | 0 |
| medical | 151 | 10.141 | 151 | 0 |
| news | 48 | 17.009 | 48 | 0 |
| poetry | 151 | 11.704 | 151 | 0 |

### 3.2 Paraphrasing Procedure

For each document, a paraphrase is generated using the `ParaphraseAgent`.

- Model: `gpt-4.1-mini`
- Temperature: 0.100
- Max paraphrasing iterations per document (backend): 0

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

- Human→Human count: 200
- Human→KI count: 500
- Average KLDI (initial paraphrases): 12.984
- Average KLDI (best paraphrases): 12.489
- Average KLDI improvement (HK): 0.496
- Median KLDI difference (HK − HH): -14.637 (CI [-16.174, -13.845])

### 4.2 Discriminative Power of KLDI

- Mann–Whitney p-value: 0.000000
- ROC-AUC: 0.259 (CI [0.211, 0.321])
- Cliff's delta: 0.481 (large)

### 4.3 Adaptive Threshold and Classification

- Adaptive threshold T_adaptive: 63.358

Per-domain classification summary:

| Domain | Count | Avg KLDI | Human-like | Detectable |
|--------|-------|----------|------------|-----------|
| law | 150 | 14.196 | 150 | 0 |
| medical | 151 | 10.141 | 151 | 0 |
| news | 48 | 17.009 | 48 | 0 |
| poetry | 151 | 11.704 | 151 | 0 |

## 5. Discussion

**Rule-based interpretation** (from the statistical pipeline):

> Es besteht ein klarer und statistisch signifikanter Unterschied zwischen Human→Human und Human→KI, jedoch in entgegengesetzter Richtung zur erwarteten Detektion: Human→Human weist im Mittel höhere KLDI-Werte auf als Human→KI. Der KLDI ist in dieser Konfiguration daher kein sinnvoller KI-Detektor, sondern spiegelt vor allem methodische Verzerrungen (z. B. gewählte Richtung der Divergenz) wider.

**LLM-based summary** (optional, from AnalysisAgent):

> Die Ergebnisse zeigen, dass KI-Texte in dieser Stichprobe anhand des KLDI zwar statistisch signifikant vom menschlichen Text unterschieden werden können (p < 0,001), jedoch ist die Klassifikationsleistung mit einer invertierten AUC von etwa 0,26 gering, was auf eine schlechte Trennbarkeit hinweist. Die große Effektstärke (Cliffs Delta ≈ 0,48) und die robusten Stichprobengrößen von mehreren hundert Dokumenten sprechen für einen mittelgroßen bis großen Effekt, dennoch sind die KI-Texte in der Praxis nicht zuverlässig unterscheidbar. Insgesamt ist die Aussage durch die ausreichende Stichprobengröße und signifikante Effekte zwar robust, die praktische Erkennbarkeit der KI-Texte anhand des KLDI bleibt jedoch eingeschränkt und eher explorativ.

### 5.1 Highlights

- Iterative paraphrasing reduced average KLDI by 0.496 (initial vs. best paraphrases).
- Effect size (Cliff's delta) between Human→Human and Human→KI distributions is 0.481 (large).

### 5.2 Lowlights and Limitations

- KLDI shows limited discriminative power (ROC-AUC = 0.259), indicating strong overlap between Human→Human and Human→KI distributions.

## 6. Conclusion

For this run, the KLDI-based analysis suggests the following high-level answer to the
research question about KI-detectability:

> Die Ergebnisse zeigen, dass KI-Texte in dieser Stichprobe anhand des KLDI zwar statistisch signifikant vom menschlichen Text unterschieden werden können (p < 0,001), jedoch ist die Klassifikationsleistung mit einer invertierten AUC von etwa 0,26 gering, was auf eine schlechte Trennbarkeit hinweist. Die große Effektstärke (Cliffs Delta ≈ 0,48) und die robusten Stichprobengrößen von mehreren hundert Dokumenten sprechen für einen mittelgroßen bis großen Effekt, dennoch sind die KI-Texte in der Praxis nicht zuverlässig unterscheidbar. Insgesamt ist die Aussage durch die ausreichende Stichprobengröße und signifikante Effekte zwar robust, die praktische Erkennbarkeit der KI-Texte anhand des KLDI bleibt jedoch eingeschränkt und eher explorativ.

All conclusions should be interpreted in light of the sample size, domain selection and
known limitations of KLDI as a purely distributional similarity measure.

## 7. Appendix: Run Configuration

Creation timestamp: 2025-12-09T07:17:08.835633

| Parameter | Value |
|-----------|-------|
| Run ID | `510b28a7-c573-4002-8304-2295872f5d6c` |
| Status | `completed` |
| Requested count | 500 |
| Per-domain count | 125 |
| LLM model | `gpt-4.1-mini` |
| Temperature | 0.100 |
| Seed | 1475987267 |
| Parallelism (backend) | 20 |
