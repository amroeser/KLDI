from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Tuple

from ..schemas import EnvConfig, EnvConfigUpdate


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"


def _parse_env_file(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _render_env_content(values: Dict[str, str]) -> str:
    # Schreibe nur die relevanten Keys in definierter Reihenfolge,
    # plus einen Kommentar-Hinweis oben.
    lines = [
        "# Managed by frontend env editor. You can edit this file manually as well.",
    ]

    def add(key: str, comment: str | None = None):
        if comment:
            lines.append(f"# {comment}")
        val = values.get(key, "")
        lines.append(f"{key}={val}")
        lines.append("")

    add("OPENAI_API_KEY", "OpenAI API Key")
    add("OPENAI_MODEL", "Override default model (defaults to gpt-4o-mini)")
    add("OPENAI_BASE_URL", "Override inference base URL")
    add("BACKEND_PORT", "Backend port for FastAPI (used by start.sh)")
    add("FRONTEND_PORT_BASE", "Base port for frontend http.server (start.sh)")

    return "\n".join(lines).rstrip() + "\n"


def get_env_config() -> EnvConfig:
    raw = _parse_env_file(ENV_PATH)
    env_exists = ENV_PATH.exists()

    # Defaults wie in .env.example / start.sh
    api_key_configured = bool(raw.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY"))
    openai_model = raw.get("OPENAI_MODEL") or "gpt-4o-mini"
    openai_base_url = raw.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"

    backend_port = raw.get("BACKEND_PORT") or os.getenv("BACKEND_PORT") or "8101"
    frontend_port_base = raw.get("FRONTEND_PORT_BASE") or os.getenv("FRONTEND_PORT_BASE") or "5500"

    return EnvConfig(
        api_key_configured=api_key_configured,
        openai_model=openai_model,
        openai_base_url=openai_base_url,
        backend_port=int(backend_port) if backend_port else None,
        frontend_port_base=int(frontend_port_base) if frontend_port_base else None,
        env_exists=env_exists,
    )


def update_env_config(update: EnvConfigUpdate) -> EnvConfig:
    # Bestehende Werte lesen und mit Update mergen
    current = _parse_env_file(ENV_PATH)

    def set_if_not_none(key: str, value):
        if value is not None:
            current[key] = str(value)

    set_if_not_none("OPENAI_API_KEY", update.openai_api_key)
    set_if_not_none("OPENAI_MODEL", update.openai_model)
    set_if_not_none("OPENAI_BASE_URL", update.openai_base_url)
    set_if_not_none("BACKEND_PORT", update.backend_port)
    set_if_not_none("FRONTEND_PORT_BASE", update.frontend_port_base)

    content = _render_env_content(current)
    ENV_PATH.write_text(content, encoding="utf-8")

    return get_env_config()
