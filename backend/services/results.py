"""Service helpers for fetching and exporting run results."""
from __future__ import annotations

from io import StringIO
from typing import List, Tuple

import csv
from sqlalchemy.orm import Session

from ..models import Document, Evaluation, Paraphrase, Run


def get_run_rows(db: Session, run_id: str) -> List[dict]:
    """Return all result rows for a run.

    Each row is a dict that matches the DocumentRow schema fields.
    """
    rows: List[dict] = []

    query = (
        db.query(Document, Paraphrase, Evaluation)
        .join(Paraphrase, Paraphrase.document_id == Document.id)
        .join(Evaluation, Evaluation.document_id == Document.id)
        .filter(Document.run_id == run_id)
        .order_by(Document.domain, Document.id)
    )

    for doc, para, ev in query.all():
        token_stats = ev.token_stats or {}
        rows.append(
            {
                "id": doc.id,
                "domain": doc.domain,
                "source_url": doc.source_url,
                "original_text": doc.original_text,
                "paraphrased_text": para.paraphrased_text,
                "kldi": float(ev.kldi),
                "classification": ev.classification,
                "kldi_initial": token_stats.get("kldi_initial"),
                "kldi_best": token_stats.get("kldi_best"),
                "iterations": token_stats.get("iterations"),
            }
        )

    return rows


def export_run_csv(db: Session, run_id: str) -> Tuple[str, str]:
    """Export run results as CSV.

    Returns (csv_content, filename).
    """
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise ValueError(f"Run {run_id} not found")

    rows = get_run_rows(db, run_id)

    output = StringIO()
    writer = csv.writer(output)

    header = [
        "id",
        "domain",
        "source_url",
        "original_text",
        "paraphrased_text",
        "kldi",
        "classification",
        "kldi_initial",
        "kldi_best",
        "iterations",
    ]
    writer.writerow(header)

    for r in rows:
        writer.writerow(
            [
                r["id"],
                r["domain"],
                r["source_url"],
                r["original_text"],
                r["paraphrased_text"],
                f"{r['kldi']:.6f}",
                r.get("classification") or "",
                "" if r.get("kldi_initial") is None else f"{r['kldi_initial']:.6f}",
                "" if r.get("kldi_best") is None else f"{r['kldi_best']:.6f}",
                "" if r.get("iterations") is None else str(r["iterations"]),
            ]
        )

    filename = f"run_{run_id}.csv"
    return output.getvalue(), filename
