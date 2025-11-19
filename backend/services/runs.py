"""Service layer for managing runs."""
from __future__ import annotations

import os
import random
from math import ceil
from typing import List, Tuple

from sqlalchemy.orm import Session

from ..domains import DOMAINS
from ..models import Run, RunStatus
from ..queue import default_queue
from .pipeline import process_run_job
from paraphrase_agents.config import get_default_model


USE_ASYNC_QUEUE = os.getenv("USE_ASYNC_QUEUE", "0") == "1"
# Konfigurierbares Timeout für den Run-Processing-Job in der RQ-Queue
try:
    RUN_JOB_TIMEOUT = int(os.getenv("RUN_JOB_TIMEOUT", "1800"))
except ValueError:
    RUN_JOB_TIMEOUT = 1800


def create_run(db: Session, count: int, domains: List[str] | None = None) -> Run:
    # Determine which domains are active for this run
    if domains:
        active_domains = [d for d in DOMAINS if d.slug in domains]
        # Fallback: if no valid slugs were provided, use all
        if not active_domains:
            active_domains = DOMAINS
    else:
        active_domains = DOMAINS

    per_domain = ceil(count / len(active_domains))
    seed = random.randint(0, 2**31 - 1)
    git_commit = os.getenv("GIT_COMMIT")
    run = Run(
        requested_count=count,
        per_domain_count=per_domain,
        llm_model=get_default_model(),
        temperature=0.1,
        status=RunStatus.PENDING,
        seed=seed,
        git_commit=git_commit,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Pass selected domain slugs to the pipeline so it only processes those topics
    selected_slugs = [d.slug for d in active_domains]

    if USE_ASYNC_QUEUE:
        # Original behaviour: enqueue in Redis/RQ und Worker verarbeitet
        # Das Job-Timeout ist konfigurierbar, damit große Runs (z.B. 500 Texte)
        # nicht nach dem RQ-Default von 180s abbrechen.
        default_queue.enqueue(
            process_run_job,
            run.id,
            selected_slugs,
            job_timeout=RUN_JOB_TIMEOUT,
        )
    else:
        # Synchronous fallback: run the pipeline in-process (avoids macOS fork issues)
        process_run_job(run.id, selected_slugs)

    return run


def list_runs(db: Session) -> Tuple[list[Run], int]:
    runs = db.query(Run).order_by(Run.created_at.desc()).all()
    total = db.query(Run).count()
    return runs, total


def get_run(db: Session, run_id: str) -> Run | None:
    return db.query(Run).filter(Run.id == run_id).first()


def delete_run(db: Session, run_id: str) -> bool:
    """Delete a run and all associated data.

    Thanks to the cascading relationships on the SQLAlchemy models,
    associated Documents, Paraphrases und Evaluations werden automatisch
    mitgelöscht.
    """

    run = get_run(db, run_id)
    if not run:
        return False
    db.delete(run)
    db.commit()
    return True
