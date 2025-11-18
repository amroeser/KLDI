"""Environment utilities for configuring language model access."""
from __future__ import annotations

import os
from dataclasses import dataclass

import openai
from dotenv import load_dotenv

# Load variables once when the module is imported
load_dotenv()


@dataclass(frozen=True)
class ModelEnv:
    """Container for language-model related environment settings."""

    api_key: str
    model: str
    base_url: str


DEFAULT_BASE_URL = "https://api.openai.com/v1"


def _read_env() -> ModelEnv:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Create a .env file (see .env.example) with your key."
        )

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL)
    return ModelEnv(api_key=api_key, model=model, base_url=base_url)


def get_model_env() -> ModelEnv:
    """Return cached environment configuration."""
    return _read_env()


def get_openai_client() -> openai.OpenAI:
    """Instantiate an OpenAI client using environment configuration."""
    env = get_model_env()
    return openai.OpenAI(api_key=env.api_key, base_url=env.base_url)


def get_default_model() -> str:
    """Convenience helper for retrieving the configured default model."""
    return get_model_env().model


def validate_env() -> None:
    """Raise a descriptive error when required env vars are missing."""
    get_model_env()
