"""Core monitoring logic for system and Docker health."""

from __future__ import annotations

import logging
from typing import Any

import psutil

logger = logging.getLogger(__name__)


def _get_docker_client() -> Any | None:
    """Try to import and return a Docker client, or None if unavailable."""
    try:
        from docker import from_env
        from docker.errors import DockerException

        try:
            client = from_env()
            client.ping()
            return client
        except DockerException:
            logger.debug("Docker daemon not reachable")
            return None
    except ImportError:
        logger.debug("docker SDK not installed")
        return None


def get_docker_containers() -> list[dict[str, Any]]:
    """List all Docker containers with status and health (if available)."""
    client = _get_docker_client()
    if client is None:
        return []

    containers: list[dict[str, Any]] = []
    try:
        for container in client.containers.list(all=True):
            attrs = container.attrs or {}
            state = attrs.get("State", {})
            health = state.get("Health", {})
            health_status = health.get("Status", "N/A")
            containers.append(
                {
                    "id": container.short_id,
                    "name": container.name,
                    "status": container.status,
                    "health": health_status if health else "N/A",
                    "image": container.image.tags[0] if container.image.tags else str(container.image.id),
                }
            )
    except Exception as exc:  # pragma: no cover
        logger.debug("Error listing containers: %s", exc)

    return containers


def get_disk_usage_per_mount() -> list[dict[str, Any]]:
    """Return disk usage for all mounted filesystems."""
    usages: list[dict[str, Any]] = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            usages.append(
                {
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent,
                }
            )
        except PermissionError:
            continue
    return usages


def get_top_processes(top_n: int = 5, sort_by: str = "cpu") -> list[dict[str, Any]]:
    """Return top N processes sorted by CPU or memory usage.

    Parameters
    ----------
    top_n:
        Number of processes to return.
    sort_by:
        Either ``"cpu"`` or ``"memory"``.
    """
    if sort_by not in {"cpu", "memory"}:
        raise ValueError("sort_by must be 'cpu' or 'memory'")

    procs: list[psutil.Process] = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            # Trigger initial cpu_percent snapshot (requires interval=0)
            proc.cpu_percent(interval=None)
            procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Give psutil a tiny moment to accumulate CPU percentages
    psutil.cpu_percent(interval=0.1)

    enriched: list[dict[str, Any]] = []
    for proc in procs:
        try:
            with proc.oneshot():
                cpu = proc.cpu_percent()
                mem = proc.memory_percent()
                enriched.append(
                    {
                        "pid": proc.pid,
                        "name": proc.name(),
                        "cpu_percent": cpu,
                        "memory_percent": mem,
                    }
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    enriched.sort(key=lambda p: p[key], reverse=True)
    return enriched[:top_n]


def get_system_health(
    top_n: int = 5,
    sort_by: str = "cpu",
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Collect system health metrics.

    Parameters
    ----------
    top_n:
        Number of top processes to return.
    sort_by:
        Sort top processes by ``"cpu"`` or ``"memory"``.
    thresholds:
        Optional mapping of ``{"cpu": 80.0, "memory": 90.0, "disk": 90.0}``.
        Used downstream to compute alert status.

    Returns
    -------
    dict
        Dictionary with CPU, memory, disk, top processes, Docker containers,
        and alert information.
    """
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = dict(psutil.virtual_memory()._asdict())
    disk_usages = get_disk_usage_per_mount()
    top_processes = get_top_processes(top_n=top_n, sort_by=sort_by)
    docker_containers = get_docker_containers()

    alerts: list[dict[str, Any]] = []
    thresholds = thresholds or {}

    if "cpu" in thresholds and cpu_percent > thresholds["cpu"]:
        alerts.append(
            {
                "metric": "cpu",
                "value": cpu_percent,
                "threshold": thresholds["cpu"],
            }
        )

    mem_percent = memory.get("percent", 0.0)
    if "memory" in thresholds and mem_percent > thresholds["memory"]:
        alerts.append(
            {
                "metric": "memory",
                "value": mem_percent,
                "threshold": thresholds["memory"],
            }
        )

    for d in disk_usages:
        if "disk" in thresholds and d["percent"] > thresholds["disk"]:
            alerts.append(
                {
                    "metric": "disk",
                    "mountpoint": d["mountpoint"],
                    "value": d["percent"],
                    "threshold": thresholds["disk"],
                }
            )

    return {
        "cpu_percent": cpu_percent,
        "memory": memory,
        "disk": disk_usages,
        "top_processes": top_processes,
        "docker_containers": docker_containers,
        "alerts": alerts,
        "thresholds": thresholds,
    }
