"""SQLAlchemy models for experiment tracking."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class RunStatus(str, PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"
    COMPLETED = "completed"


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False)
    per_domain_count: Mapped[int] = mapped_column(Integer, nullable=False)
    llm_model: Mapped[str] = mapped_column(String, nullable=False)
    temperature: Mapped[float] = mapped_column(default=0.1)
    seed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    git_commit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.PENDING)
    summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents: Mapped[list["Document"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    run: Mapped["Run"] = relationship(back_populates="documents")
    paraphrase: Mapped["Paraphrase"] = relationship(
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    evaluation: Mapped["Evaluation"] = relationship(
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )


class Paraphrase(Base):
    __tablename__ = "paraphrases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), unique=True)
    llm_model: Mapped[str] = mapped_column(String, nullable=False)
    temperature: Mapped[float] = mapped_column(default=0.0)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    paraphrased_text: Mapped[str] = mapped_column(Text, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="paraphrase")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), unique=True)
    kldi: Mapped[float] = mapped_column(default=0.0)
    token_stats: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    classification: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    errors: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped["Document"] = relationship(back_populates="evaluation")

