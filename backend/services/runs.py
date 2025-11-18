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


USE_ASYNC_QUEUE = os.getenv("USE_ASYNC_QUEUE", "0") == "1"


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
        llm_model="gpt-4.1",
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
        # Original behaviour: enqueue in Redis/RQ and let a worker process it
        default_queue.enqueue(process_run_job, run.id, selected_slugs)
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
