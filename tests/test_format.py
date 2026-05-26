"""Tests for homelab_monitor.format."""

from __future__ import annotations

from homelab_monitor.format import format_table, _bytes_to_human


class TestBytesToHuman:
    def test_bytes(self):
        assert _bytes_to_human(512) == "512.0 B"

    def test_kib(self):
        assert _bytes_to_human(1536) == "1.5 KiB"

    def test_gib(self):
        assert _bytes_to_human(2 * 1024 ** 3) == "2.0 GiB"


class TestFormatTable:
    def test_includes_all_sections(self):
        health = {
            "cpu_percent": 12.5,
            "memory": {"percent": 45.0, "used": 4 * 1024 ** 3, "total": 8 * 1024 ** 3},
            "disk": [
                {
                    "mountpoint": "/",
                    "device": "/dev/sda1",
                    "fstype": "ext4",
                    "total": 100 * 1024 ** 3,
                    "used": 50 * 1024 ** 3,
                    "free": 50 * 1024 ** 3,
                    "percent": 50.0,
                }
            ],
            "top_processes": [
                {"pid": 1, "name": "init", "cpu_percent": 5.0, "memory_percent": 2.0}
            ],
            "docker_containers": [
                {
                    "id": "abc",
                    "name": "web",
                    "status": "running",
                    "health": "healthy",
                    "image": "nginx",
                }
            ],
            "alerts": [
                {"metric": "cpu", "value": 95.0, "threshold": 80.0}
            ],
        }
        output = format_table(health)
        assert "System Health" in output
        assert "Disk Usage by Mount" in output
        assert "Top Processes" in output
        assert "Docker Containers" in output
        assert "Alerts" in output
        assert "init" in output
        assert "web" in output

    def test_empty_optional_sections(self):
        health = {
            "cpu_percent": 5.0,
            "memory": {"percent": 20.0, "used": 1, "total": 8},
            "disk": [],
            "top_processes": [],
            "docker_containers": [],
            "alerts": [],
        }
        output = format_table(health)
        assert "System Health" in output
        assert "Disk Usage by Mount" in output
        assert "Top Processes" not in output
        assert "Docker Containers" not in output
        assert "Alerts" not in output
