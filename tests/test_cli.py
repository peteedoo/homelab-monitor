"""Tests for homelab_monitor.cli."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from homelab_monitor.cli import build_parser, main


class TestBuildParser:
    def test_defaults(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.json is False
        assert args.top == 5
        assert args.sort_by == "cpu"
        assert args.config is None

    def test_parsing(self):
        parser = build_parser()
        args = parser.parse_args(["--json", "--top", "10", "--sort-by", "memory", "--config", "/tmp/cfg.yml"])
        assert args.json is True
        assert args.top == 10
        assert args.sort_by == "memory"
        assert args.config == "/tmp/cfg.yml"


class TestMain:
    @patch("homelab_monitor.cli.load_config", return_value={})
    @patch("homelab_monitor.cli.get_system_health")
    @patch("homelab_monitor.cli.format_table", return_value="pretty")
    def test_text_output(self, mock_fmt, mock_health, mock_load, capsys):
        mock_health.return_value = {"alerts": []}
        code = main([])
        assert code == 0
        captured = capsys.readouterr()
        assert "pretty" in captured.out

    @patch("homelab_monitor.cli.load_config", return_value={})
    @patch("homelab_monitor.cli.get_system_health")
    def test_json_output(self, mock_health, mock_load, capsys):
        mock_health.return_value = {"cpu_percent": 10.0, "alerts": []}
        code = main(["--json"])
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["cpu_percent"] == 10.0

    @patch("homelab_monitor.cli.load_config", return_value={})
    @patch("homelab_monitor.cli.get_system_health")
    def test_nonzero_exit_on_alert(self, mock_health, mock_load):
        mock_health.return_value = {"alerts": [{"metric": "cpu"}]}
        code = main([])
        assert code == 1
