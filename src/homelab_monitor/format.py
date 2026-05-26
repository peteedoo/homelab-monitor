"""Output formatting helpers for homelab-monitor."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table


def _bytes_to_human(n: int) -> str:
    """Convert bytes to a human-readable string."""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PiB"


def format_table(health: dict[str, Any]) -> str:
    """Pretty-print health data as a set of Rich tables."""
    console = Console(force_terminal=True, color_system="auto")
    tables: list[Table] = []

    # System overview
    overview = Table(title="System Health", show_header=False)
    overview.add_column("Metric", style="cyan")
    overview.add_column("Value", style="magenta")
    overview.add_row("CPU %", f"{health.get('cpu_percent', 0):.1f}%")
    mem = health.get("memory", {})
    overview.add_row("Memory %", f"{mem.get('percent', 0):.1f}%")
    overview.add_row("Memory used", _bytes_to_human(mem.get("used", 0)))
    overview.add_row("Memory total", _bytes_to_human(mem.get("total", 0)))
    tables.append(overview)

    # Disk per mount
    disk_table = Table(title="Disk Usage by Mount")
    disk_table.add_column("Mountpoint", style="cyan")
    disk_table.add_column("Device", style="green")
    disk_table.add_column("Used", justify="right")
    disk_table.add_column("Total", justify="right")
    disk_table.add_column("%", justify="right")
    for d in health.get("disk", []):
        disk_table.add_row(
            d["mountpoint"],
            d["device"],
            _bytes_to_human(d["used"]),
            _bytes_to_human(d["total"]),
            f"{d['percent']:.1f}%",
        )
    tables.append(disk_table)

    # Top processes
    top = health.get("top_processes", [])
    if top:
        proc_table = Table(title="Top Processes")
        proc_table.add_column("PID", justify="right", style="cyan")
        proc_table.add_column("Name", style="green")
        proc_table.add_column("CPU %", justify="right")
        proc_table.add_column("Mem %", justify="right")
        for p in top:
            proc_table.add_row(
                str(p["pid"]),
                p["name"],
                f"{p['cpu_percent']:.1f}%",
                f"{p['memory_percent']:.2f}%",
            )
        tables.append(proc_table)

    # Docker containers
    containers = health.get("docker_containers", [])
    if containers:
        docker_table = Table(title="Docker Containers")
        docker_table.add_column("ID", style="cyan")
        docker_table.add_column("Name", style="green")
        docker_table.add_column("Status")
        docker_table.add_column("Health")
        docker_table.add_column("Image")
        for c in containers:
            docker_table.add_row(
                c["id"],
                c["name"],
                c["status"],
                c.get("health", "N/A"),
                c["image"],
            )
        tables.append(docker_table)

    # Alerts
    alerts = health.get("alerts", [])
    if alerts:
        alert_table = Table(title="Alerts", style="bold red")
        alert_table.add_column("Metric", style="cyan")
        alert_table.add_column("Value", justify="right")
        alert_table.add_column("Threshold", justify="right")
        for a in alerts:
            alert_table.add_row(
                a.get("metric", "?"),
                f"{a.get('value', 0):.1f}%",
                f"{a.get('threshold', 0):.1f}%",
            )
        tables.append(alert_table)

    # Render all tables into one string
    lines: list[str] = []
    for tbl in tables:
        console.begin_capture()
        console.print(tbl)
        lines.append(console.end_capture())
    return "\n".join(lines)
