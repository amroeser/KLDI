from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class RunCreate(BaseModel):
    count: int = Field(ge=1, le=2000)
    domains: Optional[list[str]] = None


class RunSummary(BaseModel):
    id: str
    status: str
    requested_count: int
    per_domain_count: int
    llm_model: str
    temperature: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunDetail(RunSummary):
    seed: Optional[int]
    git_commit: Optional[str]
    summary: Optional[dict]


class RunList(BaseModel):
    items: List[RunSummary]
    total: int


class DocumentRow(BaseModel):
    id: str
    domain: str
    source_url: str
    original_text: str
    paraphrased_text: str
    kldi: float
    classification: Optional[str]
    kldi_initial: Optional[float] = None
    kldi_best: Optional[float] = None
    iterations: Optional[int] = None


class EnvConfig(BaseModel):
    # OpenAI / LLM Einstellungen
    api_key_configured: bool = False
    openai_model: Optional[str] = None
    openai_base_url: Optional[str] = None

    # Ports
    backend_port: Optional[int] = None
    frontend_port_base: Optional[int] = None

    # Meta
    env_exists: bool = False


class EnvConfigUpdate(BaseModel):
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    openai_base_url: Optional[str] = None
    backend_port: Optional[int] = None
    frontend_port_base: Optional[int] = None
