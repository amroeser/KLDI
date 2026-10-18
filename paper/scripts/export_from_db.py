"""Export the paper run (510b28a7-...) from the SQLite database into CSV/JSON.

Usage: python export_from_db.py <path/to/app.db> <output_dir>
Requires: numpy, nltk (punkt_tab)
"""
import csv, json, sqlite3, sys
from collections import defaultdict
from pathlib import Path

from kldi import kldi

RUN_ID = "510b28a7-c573-4002-8304-2295872f5d6c"
MAX_PAIRS_PER_DOMAIN = 50

db, out = sys.argv[1], Path(sys.argv[2])
(out / "data").mkdir(parents=True, exist_ok=True)
(out / "results").mkdir(parents=True, exist_ok=True)
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)

run = con.execute(
    "select id, requested_count, per_domain_count, llm_model, temperature, seed, status, created_at, updated_at, summary from runs where id=?",
    (RUN_ID,),
).fetchone()
summary = json.loads(run[9])
config = dict(zip(["run_id", "requested_count", "per_domain_count", "llm_model", "temperature", "seed", "status", "created_at", "updated_at"], run[:9]))
config["kldi_ngram_order"] = 2
config["kldi_epsilon"] = 1e-10
config["kldi_log_base"] = 2
config["human_human_max_pairs_per_domain"] = MAX_PAIRS_PER_DOMAIN
(out / "results" / "run_config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
(out / "results" / "run_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")

def write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

docs = con.execute(
    "select id, domain, source_url, retrieved_at, original_text from documents where run_id=? order by domain, id",
    (RUN_ID,),
).fetchall()
write(out / "data" / "source_passages.csv", ["document_id", "domain", "source_url", "retrieved_at", "original_text"], docs)

paras = con.execute(
    """select p.document_id, p.id, p.llm_model, p.temperature, p.generated_at, p.paraphrased_text
       from paraphrases p join documents d on d.id=p.document_id where d.run_id=? order by d.domain, d.id""",
    (RUN_ID,),
).fetchall()
write(out / "data" / "selected_paraphrases.csv", ["document_id", "paraphrase_id", "llm_model", "temperature", "generated_at", "paraphrased_text"], paras)

evals = con.execute(
    """select d.id, d.domain, e.kldi, e.token_stats, e.classification
       from evaluations e join documents d on d.id=e.document_id where d.run_id=? order by d.domain, d.id""",
    (RUN_ID,),
).fetchall()
rows = []
for doc_id, domain, k, ts, cls in evals:
    ts = json.loads(ts or "{}")
    rows.append([doc_id, domain, k, ts.get("kldi_initial"), ts.get("kldi_best"), ts.get("iterations"), ts.get("length_original"), ts.get("length_paraphrase"), cls])
write(out / "results" / "human_ai_scores.csv",
      ["document_id", "domain", "kldi", "kldi_initial", "kldi_best", "accepted_candidates", "length_original", "length_paraphrase", "classification"], rows)

# Human->Human reference: same construction as backend/services/pipeline.py
by_domain = defaultdict(list)
for doc_id, domain, _, _, text in docs:
    by_domain[domain].append((doc_id, text))
pairs = []
for domain, dd in by_domain.items():
    c = 0
    for i in range(len(dd) - 1):
        for j in range(i + 1, len(dd)):
            pairs.append([domain, dd[i][0], dd[j][0], kldi(dd[i][1], dd[j][1]), int(dd[i][1] == dd[j][1])])
            c += 1
            if c >= MAX_PAIRS_PER_DOMAIN:
                break
        if c >= MAX_PAIRS_PER_DOMAIN:
            break
write(out / "data" / "human_human_pairs.csv", ["domain", "document_id_a", "document_id_b", "kldi", "identical_text"], pairs)
print(f"docs={len(docs)} paraphrases={len(paras)} evals={len(evals)} hh_pairs={len(pairs)}")
