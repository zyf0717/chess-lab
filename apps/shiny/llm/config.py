from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is optional at import time
    load_dotenv = None

_DEFAULT_TIMEOUT_SEC = 30.0
_DEFAULT_MAX_TOKENS = 700
_DEFAULT_TEMPERATURE = 0.2
_ENV_LOADED = False


@dataclass(frozen=True, slots=True)
class LLMConfig:
    base_url: str
    model: str
    api_key: str | None
    chat_path: str = "/v1/chat/completions"
    reasoning_effort: str | None = None
    timeout_sec: float = _DEFAULT_TIMEOUT_SEC
    max_tokens: int = _DEFAULT_MAX_TOKENS
    temperature: float = _DEFAULT_TEMPERATURE


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def bootstrap_environment(
    env_path: Path | None = None, *, force: bool = False, override: bool = False
) -> Path | None:
    global _ENV_LOADED
    if _ENV_LOADED and not force:
        return env_path

    path = env_path or (repo_root() / ".env")
    if path.exists():
        if load_dotenv is not None:
            load_dotenv(path, override=override)
        else:
            _load_env_file(path, override=override)
    _ENV_LOADED = True
    return path


def _load_env_file(path: Path, *, override: bool = False) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value


def _parse_float(
    raw_value: str | None,
    *,
    default: float,
    min_value: float | None = None,
    max_value: float | None = None,
    name: str,
) -> tuple[float | None, str | None]:
    if raw_value in (None, ""):
        return default, None
    try:
        value = float(raw_value)
    except ValueError:
        return None, f"{name} must be a number."
    if min_value is not None and value < min_value:
        return None, f"{name} must be at least {min_value}."
    if max_value is not None and value > max_value:
        return None, f"{name} must be at most {max_value}."
    return value, None


def _parse_int(
    raw_value: str | None,
    *,
    default: int,
    min_value: int | None = None,
    name: str,
) -> tuple[int | None, str | None]:
    if raw_value in (None, ""):
        return default, None
    try:
        value = int(raw_value)
    except ValueError:
        return None, f"{name} must be an integer."
    if min_value is not None and value < min_value:
        return None, f"{name} must be at least {min_value}."
    return value, None


def load_llm_config(
    env: Mapping[str, str] | None = None,
) -> tuple[LLMConfig | None, str | None]:
    bootstrap_environment()
    source = env or os.environ

    base_url = (source.get("LLM_BASE_URL") or "").strip().rstrip("/")
    if not base_url:
        return None, "LLM commentary disabled: set LLM_BASE_URL in the repo root .env."

    model = (source.get("LLM_MODEL") or "").strip()
    if not model:
        return None, "LLM commentary disabled: set LLM_MODEL in the repo root .env."

    chat_path = (source.get("LLM_CHAT_PATH") or "/v1/chat/completions").strip()
    if not chat_path:
        chat_path = "/v1/chat/completions"
    if not chat_path.startswith("/"):
        chat_path = f"/{chat_path}"

    reasoning_effort = (source.get("LLM_REASONING_EFFORT") or "").strip().lower() or None
    if reasoning_effort not in {None, "low", "medium", "high"}:
        return None, "LLM_REASONING_EFFORT must be one of: low, medium, high."

    timeout_sec, error = _parse_float(
        source.get("LLM_TIMEOUT_SEC"),
        default=_DEFAULT_TIMEOUT_SEC,
        min_value=0.1,
        name="LLM_TIMEOUT_SEC",
    )
    if error is not None:
        return None, error

    max_tokens, error = _parse_int(
        source.get("LLM_MAX_TOKENS"),
        default=_DEFAULT_MAX_TOKENS,
        min_value=1,
        name="LLM_MAX_TOKENS",
    )
    if error is not None:
        return None, error

    temperature, error = _parse_float(
        source.get("LLM_TEMPERATURE"),
        default=_DEFAULT_TEMPERATURE,
        min_value=0.0,
        max_value=2.0,
        name="LLM_TEMPERATURE",
    )
    if error is not None:
        return None, error

    api_key = (source.get("LLM_API_KEY") or "").strip() or None
    config = LLMConfig(
        base_url=base_url,
        model=model,
        api_key=api_key,
        chat_path=chat_path,
        reasoning_effort=reasoning_effort,
        timeout_sec=timeout_sec,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return config, None
