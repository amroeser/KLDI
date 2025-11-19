from __future__ import annotations

import json

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Base, SessionLocal, engine
from .domains import DOMAINS
from .schemas import (
    DocumentRow,
    EnvConfig,
    EnvConfigUpdate,
    RunCreate,
    RunDetail,
    RunList,
    RunSummary,
)
from .services import results as results_service
from .services import runs as run_service
from .services import env_config as env_config_service


app = FastAPI(title="Windsurf Paraphrasing Backend")

settings = get_settings()

# CORS: Frontend-Origin aus Konfiguration/Umgebung (FRONTEND_ORIGIN)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Session:
  db = SessionLocal()
  try:
      yield db
  finally:
      db.close()


@app.on_event("startup")
def on_startup() -> None:
    # For early development we auto-create tables; migrations handle prod.
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check():
    settings = get_settings()
    return {"status": "ok", "environment": settings.environment}


@app.get("/domains")
def list_domains():
    """Return the list of available domains (topics) for analysis."""
    return [{"slug": d.slug, "name": d.name} for d in DOMAINS]


@app.post("/runs", response_model=RunDetail)
def create_run(payload: RunCreate, db: Session = Depends(get_db)):
    run = run_service.create_run(db, payload.count, payload.domains)
    return RunDetail.model_validate(run)


@app.get("/runs", response_model=RunList)
def list_runs(db: Session = Depends(get_db)):
    runs, total = run_service.list_runs(db)
    return RunList(items=[RunSummary.model_validate(r) for r in runs], total=total)


@app.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = run_service.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunDetail.model_validate(run)


@app.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: str, db: Session = Depends(get_db)):
    deleted = run_service.delete_run(db, run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Run not found")
    return Response(status_code=204)


@app.get("/runs/{run_id}/rows", response_model=list[DocumentRow])
def get_run_rows(run_id: str, db: Session = Depends(get_db)):
    rows = results_service.get_run_rows(db, run_id)
    return [DocumentRow.model_validate(r) for r in rows]


@app.get("/runs/{run_id}/export")
def export_run(run_id: str, format: str = "csv", db: Session = Depends(get_db)):
    if format != "csv":
        raise HTTPException(status_code=400, detail="Only CSV export is supported")
    csv_data, filename = results_service.export_run_csv(db, run_id)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/runs/{run_id}/summary_export")
def export_run_summary(run_id: str, db: Session = Depends(get_db)):
    run = run_service.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    summary = run.summary or {}
    json_data = json.dumps(summary, indent=2, ensure_ascii=False)
    return Response(
        content=json_data,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=run_{run_id}_summary.json"},
    )


@app.get("/env-config", response_model=EnvConfig)
def get_env_config():
    """Return current env-style configuration (.env or defaults).

    Sensible defaults werden aus .env.example / Startscript übernommen.
    """
    return env_config_service.get_env_config()


@app.post("/env-config", response_model=EnvConfig)
def update_env_config(payload: EnvConfigUpdate):
    """Update env-style configuration and persist to .env.

    Änderungen werden beim nächsten ./start.sh-Lauf wirksam.
    """
    return env_config_service.update_env_config(payload)
