"""Command-line interface for homelab-monitor."""

from __future__ import annotations

import argparse
import json
import sys

from .config import get_thresholds, load_config
from .format import format_table
from .monitor import get_system_health


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="homelab-monitor",
        description="CLI tool for homelab health — Docker, disk, CPU, RAM, and top processes.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of top processes to display (default: 5).",
    )
    parser.add_argument(
        "--sort-by",
        choices=["cpu", "memory"],
        default="cpu",
        help="Sort top processes by cpu or memory (default: cpu).",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to YAML config file (default: ~/.homelab-monitor.yml).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    config = load_config(args.config)
    thresholds = get_thresholds(config)

    health = get_system_health(top_n=args.top, sort_by=args.sort_by, thresholds=thresholds)

    if args.json:
        print(json.dumps(health, indent=2, default=str))
    else:
        print(format_table(health))

    return 1 if health.get("alerts") else 0


if __name__ == "__main__":
    sys.exit(main())
