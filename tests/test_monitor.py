"""Tests for homelab_monitor.monitor."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import psutil
import pytest

from homelab_monitor.monitor import (
    get_disk_usage_per_mount,
    get_docker_containers,
    get_system_health,
    get_top_processes,
)


class FakePartition:
    def __init__(self, device: str, mountpoint: str, fstype: str) -> None:
        self.device = device
        self.mountpoint = mountpoint
        self.fstype = fstype


class FakeUsage:
    def __init__(self, total: int, used: int, free: int, percent: float) -> None:
        self.total = total
        self.used = used
        self.free = free
        self.percent = percent


class FakeProcess:
    def __init__(self, pid: int, name: str, cpu: float, mem: float) -> None:
        self._pid = pid
        self._name = name
        self._cpu = cpu
        self._mem = mem

    def pid(self) -> int:
        return self._pid

    def name(self) -> str:
        return self._name

    def cpu_percent(self, interval: float | None = None) -> float:
        return self._cpu

    def memory_percent(self) -> float:
        return self._mem

    def oneshot(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        pass


class TestGetDockerContainers:
    def test_returns_empty_when_sdk_missing(self):
        with patch("homelab_monitor.monitor._get_docker_client", return_value=None):
            assert get_docker_containers() == []

    def test_returns_container_data(self):
        fake_container = MagicMock()
        fake_container.short_id = "abc123"
        fake_container.name = "web"
        fake_container.status = "running"
        fake_container.image.tags = ["nginx:latest"]
        fake_container.image.id = "sha256:xxx"
        fake_container.attrs = {"State": {"Health": {"Status": "healthy"}}}

        fake_client = MagicMock()
        fake_client.containers.list.return_value = [fake_container]

        with patch("homelab_monitor.monitor._get_docker_client", return_value=fake_client):
            result = get_docker_containers()

        assert len(result) == 1
        assert result[0]["id"] == "abc123"
        assert result[0]["name"] == "web"
        assert result[0]["status"] == "running"
        assert result[0]["health"] == "healthy"
        assert result[0]["image"] == "nginx:latest"

    def test_uses_image_id_when_no_tags(self):
        fake_container = MagicMock()
        fake_container.short_id = "def456"
        fake_container.name = "app"
        fake_container.status = "exited"
        fake_container.image.tags = []
        fake_container.image.id = "sha256:yyy"
        fake_container.attrs = {"State": {}}

        fake_client = MagicMock()
        fake_client.containers.list.return_value = [fake_container]

        with patch("homelab_monitor.monitor._get_docker_client", return_value=fake_client):
            result = get_docker_containers()

        assert result[0]["image"] == "sha256:yyy"
        assert result[0]["health"] == "N/A"


class TestGetDiskUsagePerMount:
    @patch("psutil.disk_partitions")
    @patch("psutil.disk_usage")
    def test_returns_usages(self, mock_disk_usage, mock_partitions):
        mock_partitions.return_value = [
            FakePartition("/dev/sda1", "/", "ext4"),
            FakePartition("/dev/sda2", "/home", "ext4"),
        ]

        def fake_usage(path: str) -> FakeUsage:
            if path == "/":
                return FakeUsage(100, 50, 50, 50.0)
            return FakeUsage(200, 20, 180, 10.0)

        mock_disk_usage.side_effect = fake_usage

        result = get_disk_usage_per_mount()
        assert len(result) == 2
        assert result[0]["mountpoint"] == "/"
        assert result[0]["percent"] == 50.0
        assert result[1]["mountpoint"] == "/home"
        assert result[1]["percent"] == 10.0

    @patch("psutil.disk_partitions")
    @patch("psutil.disk_usage")
    def test_skips_permission_error(self, mock_disk_usage, mock_partitions):
        mock_partitions.return_value = [
            FakePartition("/dev/sda1", "/", "ext4"),
            FakePartition("/dev/sda2", "/secret", "ext4"),
        ]

        def fake_usage(path: str) -> FakeUsage:
            if path == "/secret":
                raise PermissionError
            return FakeUsage(100, 50, 50, 50.0)

        mock_disk_usage.side_effect = fake_usage
        result = get_disk_usage_per_mount()
        assert len(result) == 1
        assert result[0]["mountpoint"] == "/"


class TestGetTopProcesses:
    @patch("psutil.process_iter")
    @patch("psutil.cpu_percent")
    def test_sort_by_cpu(self, mock_cpu_percent, mock_process_iter):
        p1 = MagicMock()
        p1.pid = 1
        p1.name.return_value = "a"
        p1.cpu_percent.return_value = 10.0
        p1.memory_percent.return_value = 5.0
        p1.oneshot.return_value.__enter__ = lambda s: s
        p1.oneshot.return_value.__exit__ = lambda *a, **k: None

        p2 = MagicMock()
        p2.pid = 2
        p2.name.return_value = "b"
        p2.cpu_percent.return_value = 30.0
        p2.memory_percent.return_value = 2.0
        p2.oneshot.return_value.__enter__ = lambda s: s
        p2.oneshot.return_value.__exit__ = lambda *a, **k: None

        mock_process_iter.return_value = [p1, p2]
        mock_cpu_percent.return_value = 0.0

        result = get_top_processes(top_n=2, sort_by="cpu")
        assert [r["pid"] for r in result] == [2, 1]
        assert result[0]["cpu_percent"] == 30.0

    @patch("psutil.process_iter")
    @patch("psutil.cpu_percent")
    def test_sort_by_memory(self, mock_cpu_percent, mock_process_iter):
        p1 = MagicMock()
        p1.pid = 1
        p1.name.return_value = "a"
        p1.cpu_percent.return_value = 10.0
        p1.memory_percent.return_value = 5.0
        p1.oneshot.return_value.__enter__ = lambda s: s
        p1.oneshot.return_value.__exit__ = lambda *a, **k: None

        p2 = MagicMock()
        p2.pid = 2
        p2.name.return_value = "b"
        p2.cpu_percent.return_value = 30.0
        p2.memory_percent.return_value = 20.0
        p2.oneshot.return_value.__enter__ = lambda s: s
        p2.oneshot.return_value.__exit__ = lambda *a, **k: None

        mock_process_iter.return_value = [p1, p2]
        mock_cpu_percent.return_value = 0.0

        result = get_top_processes(top_n=2, sort_by="memory")
        assert [r["pid"] for r in result] == [2, 1]
        assert result[0]["memory_percent"] == 20.0

    def test_invalid_sort_by_raises(self):
        with pytest.raises(ValueError, match="sort_by must be 'cpu' or 'memory'"):
            get_top_processes(sort_by="invalid")


class TestGetSystemHealth:
    @patch("homelab_monitor.monitor.get_docker_containers", return_value=[])
    @patch("homelab_monitor.monitor.get_disk_usage_per_mount", return_value=[])
    @patch("homelab_monitor.monitor.get_top_processes", return_value=[])
    @patch("psutil.cpu_percent", return_value=12.5)
    @patch("psutil.virtual_memory")
    def test_returns_dict(self, mock_vm, mock_cpu, mock_top, mock_disk, mock_docker):
        mock_vm.return_value._asdict.return_value = {"percent": 45.0, "used": 4, "total": 8}
        result = get_system_health(top_n=3)
        assert isinstance(result, dict)
        assert "cpu_percent" in result
        assert "memory" in result
        assert "disk" in result
        assert "top_processes" in result
        assert "docker_containers" in result
        assert "alerts" in result
        assert result["cpu_percent"] == 12.5

    @patch("homelab_monitor.monitor.get_docker_containers", return_value=[])
    @patch("homelab_monitor.monitor.get_disk_usage_per_mount", return_value=[])
    @patch("homelab_monitor.monitor.get_top_processes", return_value=[])
    @patch("psutil.cpu_percent", return_value=85.0)
    @patch("psutil.virtual_memory")
    def test_cpu_alert(self, mock_vm, mock_cpu, mock_top, mock_disk, mock_docker):
        mock_vm.return_value._asdict.return_value = {"percent": 45.0, "used": 4, "total": 8}
        result = get_system_health(thresholds={"cpu": 80.0})
        assert any(a["metric"] == "cpu" for a in result["alerts"])

    @patch("homelab_monitor.monitor.get_docker_containers", return_value=[])
    @patch("homelab_monitor.monitor.get_disk_usage_per_mount", return_value=[])
    @patch("homelab_monitor.monitor.get_top_processes", return_value=[])
    @patch("psutil.cpu_percent", return_value=10.0)
    @patch("psutil.virtual_memory")
    def test_no_alert_when_within_threshold(self, mock_vm, mock_cpu, mock_top, mock_disk, mock_docker):
        mock_vm.return_value._asdict.return_value = {"percent": 45.0, "used": 4, "total": 8}
        result = get_system_health(thresholds={"cpu": 80.0})
        assert result["alerts"] == []
