"""Tests for homelab_monitor.config."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from homelab_monitor.config import get_thresholds, load_config


class TestLoadConfig:
    def test_missing_file_returns_empty(self, tmp_path: Path):
        missing = tmp_path / "missing.yml"
        assert load_config(missing) == {}

    def test_loads_valid_yaml(self, tmp_path: Path):
        cfg = tmp_path / "cfg.yml"
        cfg.write_text("thresholds:\n  cpu: 75.0\n")
        assert load_config(cfg) == {"thresholds": {"cpu": 75.0}}

    def test_invalid_yaml_returns_empty(self, tmp_path: Path):
        cfg = tmp_path / "bad.yml"
        cfg.write_text("{not yaml")
        assert load_config(cfg) == {}

    def test_default_path(self, tmp_path: Path):
        default = tmp_path / ".homelab-monitor.yml"
        default.write_text("foo: bar\n")
        with patch("homelab_monitor.config.DEFAULT_CONFIG_PATH", default):
            assert load_config() == {"foo": "bar"}


class TestGetThresholds:
    def test_extracts_thresholds(self):
        cfg = {"thresholds": {"cpu": 80.0, "memory": 90.0, "disk": 85.0}}
        assert get_thresholds(cfg) == {"cpu": 80.0, "memory": 90.0, "disk": 85.0}

    def test_ignores_missing_keys(self):
        assert get_thresholds({}) == {}
        assert get_thresholds({"thresholds": {"cpu": 80.0}}) == {"cpu": 80.0}

    def test_skips_non_numeric_values(self):
        cfg = {"thresholds": {"cpu": "high", "memory": 90.0}}
        assert get_thresholds(cfg) == {"memory": 90.0}

    def test_none_config_returns_empty(self):
        assert get_thresholds(None) == {}
