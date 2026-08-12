"""Configuration helpers for homelab-monitor."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path.home() / ".homelab-monitor.yml"


def load_config(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Load YAML configuration from *path* or the default location.

    Returns an empty dict if the file does not exist or cannot be parsed.
    """
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        return {}

    try:
        with cfg_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
            if isinstance(data, dict):
                return data
            return {}
    except Exception:
        return {}


def get_thresholds(config: dict[str, Any] | None = None) -> dict[str, float]:
    """Extract alert thresholds from configuration dict.

    Expected structure:

    .. code-block:: yaml

        thresholds:
          cpu: 80.0
          memory: 90.0
          disk: 90.0
    """
    cfg = config or {}
    thresholds = cfg.get("thresholds", {})
    result: dict[str, float] = {}
    for key in ("cpu", "memory", "disk"):
        if key in thresholds:
            try:
                result[key] = float(thresholds[key])
            except (TypeError, ValueError):
                continue
    return result
