"""
Configuration loader.

Reads application.yaml, resolves ${ENV_VAR} placeholders from environment
variables, and exposes a typed AppSettings object.
"""

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Environment variable resolution
# ---------------------------------------------------------------------------

def _resolve_env_vars(value: Any) -> Any:
    """Recursively replace ${VAR} placeholders with os.environ values."""
    if isinstance(value, str):
        # Only match valid env-var names (letters, digits, underscores)
        return re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}").sub(
            lambda m: os.environ.get(m.group(1), ""), value
        )
    if isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


# ---------------------------------------------------------------------------
# Key conversion  (camelCase / kebab-case → snake_case)
# ---------------------------------------------------------------------------

def _to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.replace("-", "_").lower()


def _convert_keys(obj: Any, preserve_keys: bool = False) -> Any:
    if isinstance(obj, dict):
        return {
            (k if preserve_keys else _to_snake(k)): _convert_keys(v, preserve_keys=(k == "sparql_queries" or k == "sparql-queries"))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_convert_keys(item) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# Pydantic settings models
# ---------------------------------------------------------------------------

class KgmConfig(BaseModel):
    base_url: str = "http://kgm:8080"
    sparql_queries: dict[str, str] = {}


class CorsConfig(BaseModel):
    origin: str = "*"


class CustomUrlPickerConfig(BaseModel):
    cors: CorsConfig = CorsConfig()


class AppSettings(BaseModel):
    kgm: KgmConfig = KgmConfig()
    custom_url_picker: CustomUrlPickerConfig = CustomUrlPickerConfig()


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_settings(config_path: str | Path | None = None) -> AppSettings:
    """
    Load configuration from a YAML file.

    Lookup order for the file:
    1. Explicit *config_path* argument
    2. CONFIG_PATH environment variable
    3. ``application.yaml`` at the project root (two levels up from this file)
    """
    if config_path is None:
        config_path = os.environ.get(
            "CONFIG_PATH",
            str(Path(__file__).resolve().parent.parent / "application.yaml"),
        )

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path) as fh:
        raw = yaml.safe_load(fh) or {}

    resolved = _resolve_env_vars(raw)
    converted = _convert_keys(resolved)
    return AppSettings.model_validate(converted)
