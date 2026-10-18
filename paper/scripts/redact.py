"""Build the public data release from the full export.

Texts from sources whose licence does not permit redistribution are replaced
by an empty string; their SHA-256 hash (computed on the full text) is kept so
that the full private copy can be verified against the public one.

Usage: python redact.py <full_export_dir> <public_dir>
"""
import csv, hashlib, shutil, sys
from pathlib import Path
from urllib.parse import urlparse

RESTRICTED_HOSTS = {"web.archive.org", "chlaep.org.uy"}

full, pub = Path(sys.argv[1]), Path(sys.argv[2])
sha = lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest()

def rw(name, text_col, restricted_ids=None):
    rows = list(csv.DictReader(open(full / name, encoding="utf-8")))
    ids = set()
    for r in rows:
        restricted = (urlparse(r["source_url"]).hostname in RESTRICTED_HOSTS) if restricted_ids is None else (r["document_id"] in restricted_ids)
        r[f"{text_col}_sha256"] = sha(r[text_col])
        r["text_redacted"] = int(restricted)
        if restricted:
            ids.add(r["document_id"])
            r[text_col] = ""
    (pub / name).parent.mkdir(parents=True, exist_ok=True)
    with open(pub / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return ids

restricted = rw("data/source_passages.csv", "original_text")
rw("data/selected_paraphrases.csv", "paraphrased_text", restricted)
for p in ["data/human_human_pairs.csv", "results/human_ai_scores.csv", "results/run_config.json", "results/run_summary.json"]:
    (pub / p).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(full / p, pub / p)
print(f"redacted documents: {len(restricted)}")
