# homelab-monitor Comprehensive Review Report

## Executive Summary

- **Project**: homelab-monitor (Python CLI)
- **Version**: 0.2.0 (pyproject.toml) vs 0.1.0 (__init__.py) — version mismatch
- **Stack**: Python 3.11+, argparse, psutil, docker SDK, rich, pyyaml, pytest
- **Test Result**: 29/29 pass, 89% line coverage
- **Lint**: ruff finds 2 unused imports; mypy finds 5 errors (missing stubs + type bug)

---

## 1. Bugs / Code Issues

### 1.1 Version mismatch
- `pyproject.toml` says `0.2.0`
- `src/homelab_monitor/__init__.py` says `0.1.0`
- Fix: keep them in sync, or read version dynamically in `__init__.py`.

### 1.2 Unused imports in `cli.py`
- `from pathlib import Path` and `from typing import Any` are unused (ruff F401).

### 1.3 Type bug in `format.py`
- `_bytes_to_human(n: int)` divides `n /= 1024.0`, turning `int` into `float`. Mypy flags this. Signature should be `n: int | float` or cast to float.

### 1.4 Missing type stubs for mypy
- `yaml`, `psutil`, `docker` lack stubs in CI. Install `types-PyYAML`, `types-psutil`, `types-docker` (or add `mypy --install-types` step).

### 1.5 `requirements.txt` includes pytest as runtime dependency
- `pytest>=8.0.0` is listed in `requirements.txt` but should only be in `[dev]` extras per `pyproject.toml`. Keep `requirements.txt` lean for Docker builds.

### 1.6 Docker health logic bug
- In `monitor.py` line 49:
  ```python
  "health": health_status if health else "N/A",
  ```
  `health` is a dict like `{"Status": "healthy"}`; a non-empty dict is always truthy, so `"N/A"` is never returned even when there is no health check. The intent was probably to check `health_status` or whether the container defines a health check. If `attrs["State"]` has no `"Health"` key, `health = {}`, and `health_status = "N/A"` already, so the ternary is redundant but harmless. However, if `health = {}`, the code still works because `health_status` defaults to `"N/A"`. Not a runtime crash, but confusing logic.

### 1.7 `get_top_processes` has a race / performance quirk
- Calls `cpu_percent(interval=None)` in a loop, then sleeps globally with `psutil.cpu_percent(interval=0.1)`. This is a bit awkward: the global call may distort per-process readings. Better to use `time.sleep(0.1)` or document the behavior.

### 1.8 No handling of `docker` image `tags` being `None`
- `container.image.tags[0]` assumes `tags` is a list. The SDK usually returns a list, but defensive coding would use `(container.image.tags or [str(container.image.id)])[0]`.

---

## 2. Missing Features

1. **Prometheus `/metrics` exporter** — on roadmap, not implemented.
2. **Slack/Discord webhook alerts** — on roadmap, not implemented.
3. **Container auto-restart on unhealthy state** — on roadmap, not implemented.
4. **Systemd service/timer files** — on roadmap, not implemented.
5. **Historical trend logging (SQLite)** — on roadmap, not implemented.
6. **Logging configuration** — `monitor.py` uses a module-level logger but never configures handlers; users see no debug output by default.
7. **Thresholds for individual mount points** — current disk threshold is global; cannot set e.g. `/var` to 80% and `/tmp` to 95%.
8. **Per-container alert thresholds** — cannot alert if a specific container is unhealthy.
9. **CLI `--version` flag** — absent.
10. **Configuration schema validation / Pydantic** — YAML is parsed loosely; typos in keys are silently ignored.
11. **Exit-code granularity** — only 0 or 1; Nagios-style codes (0,1,2,3) or bitmask would help CI differentiation.
12. **Quiet / verbose flags** — no `-v`/`-q`.
13. **Cron-friendly single-line output** — `--json` exists but no `--one-line` or syslog formatter.
14. **Docker socket path override** — no `--docker-host` argument.
15. **Process filtering / denylist** — cannot exclude kernel threads or specific process names from top list.

---

## 3. Test Gaps

### 3.1 Coverage holes (from `pytest --cov`)
- `cli.py` line 67 (`if __name__ == "__main__":` block) — trivial but uncovered.
- `config.py` line 29 — `yaml.safe_load` returns non-dict (e.g. `None` or list) path not hit.
- `format.py` line 17 — PiB fallback in `_bytes_to_human` not hit.
- `monitor.py` lines 15-28 — `_get_docker_client` ImportError / DockerException branches not hit.
- `monitor.py` lines 100-101 — `AccessDenied` in `process_iter` not hit.
- `monitor.py` lines 120-121 — `AccessDenied` in oneshot enrichment not hit.
- `monitor.py` line 171 — memory alert branch not hit.
- `monitor.py` lines 180-181 — disk alert branch not hit.

### 3.2 Missing integration tests
- No test actually exercises `psutil` or Docker for real (expected in unit tests, but an integration marker would be useful).
- No test for `main()` with a real config file written to disk.
- No test for invalid `--top` negative values.
- No test for `--sort-by` with invalid value via CLI (argparse prevents it, but no explicit test).

### 3.3 Missing property-based / edge-case tests
- `_bytes_to_human` with `0`, negative numbers, or very large values.
- `load_config` with empty YAML file, YAML containing only comments, or permission-denied file.
- `get_thresholds` with nested non-numeric structures (e.g. `memory: {warn: 80, crit: 90}`).

---

## 4. CI/CD Issues

### 4.1 Duplicate workflow files
- `.github/workflows/ci.yml` and `.github/workflows/test.yml` both run on push/PR.
  - `test.yml` only runs pytest on 3.11/3.12.
  - `ci.yml` runs pytest + ruff + mypy + docker build on 3.11/3.12/3.13.
- **Problem**: tests run twice, wasting minutes. Consolidate or make `test.yml` a reusable workflow called by `ci.yml`.

### 4.2 `ci.yml` installs tools dynamically
- `pip install ruff` and `pip install mypy` inside the job means versions float. Pin them (e.g. `pip install ruff==0.15.0 mypy==1.10.0`) or use pre-commit.

### 4.3 No caching
- No `actions/cache` for pip dependencies; builds are slower than necessary.

### 4.4 `codecov-action@v4` token issue
- `codecov/codecov-action@v4` often requires a `CODECOV_TOKEN` secret; `fail_ci_if_error: false` masks misconfiguration.

### 4.5 Docker build does not use BuildKit cache
- No `--cache-from` or `docker/build-push-action` with layer caching.

### 4.6 No release automation
- No workflow to publish to PyPI on tag push.

---

## 5. Security / Hardening

1. **No input sanitization on `--config` path** — passing a directory or FIFO could hang `open()`.
2. **Docker client from environment** — relies on ambient Docker socket permissions; no option to restrict to read-only.
3. **Potential information disclosure** — JSON output includes full memory stats; running as root exposes all process names.
4. **No timeout on Docker operations** — `client.containers.list(all=True)` could hang if daemon is overloaded.

---

## 6. Detailed Enhancement Plan

### Phase A — Fix & Polish (1-2 days)
1. Sync version strings (`__init__.py` = `0.2.0`).
2. Remove unused imports in `cli.py`; fix `_bytes_to_human` signature.
3. Add `types-PyYAML`, `types-psutil`, `types-docker` to dev dependencies.
4. Move `pytest` out of `requirements.txt` (keep only runtime deps).
5. Add `--version` argument to CLI.
6. Add basic logging setup (`--verbose` / `--quiet`).

### Phase B — Testing & Quality (2-3 days)
1. Add tests for uncovered branches:
   - Docker SDK missing / daemon unreachable.
   - `psutil.AccessDenied` paths.
   - Memory and disk alert generation.
   - `_bytes_to_human` edge cases.
2. Add `pytest-xdist` and `pytest-randomly` for robustness.
3. Introduce `pytest` markers: `@pytest.mark.integration`, `@pytest.mark.docker`.
4. Add a `Makefile` or `justfile` for common tasks (`test`, `lint`, `mypy`, `coverage`).
5. Set coverage gate to 95% and enforce in CI.

### Phase C — CI/CD Consolidation (1 day)
1. Merge `test.yml` into `ci.yml` as a single workflow with multiple jobs:
   - `lint` (ruff + mypy)
   - `test` (matrix 3.11/3.12/3.13)
   - `docker` (build + smoke test)
2. Add `actions/cache` for pip and Docker layers.
3. Pin linter versions in CI or switch to pre-commit.ci.
4. Add a `publish` job triggered on tags using `pypa/gh-action-pypi-publish`.

### Phase D — Features (1-2 weeks)
1. **Pydantic config model** — validate YAML schema, give clear errors.
2. **Per-mount disk thresholds** — extend config:
   ```yaml
   thresholds:
     disk:
       default: 90.0
       mounts:
         "/var": 80.0
   ```
3. **Webhook alerts** — add `alerts.webhooks` config; fire on threshold breach.
4. **Container auto-restart** — `--auto-restart` flag to call `container.restart()` for unhealthy containers.
5. **Prometheus exporter** — optional `homelab-monitor exporter` subcommand using `prometheus-client`.
6. **SQLite trend logging** — `--log-db path.db` to insert snapshots.
7. **Systemd units** — ship `homelab-monitor.service` and `homelab-monitor.timer` in a `systemd/` directory.

### Phase E — Packaging & Distribution (1 day)
1. Add `__main__.py` so `python -m homelab_monitor` works without `.cli`.
2. Add console script entry point in `pyproject.toml`:
   ```toml
   [project.scripts]
   homelab-monitor = "homelab_monitor.cli:main"
   ```
3. Build wheel in CI and attach to GitHub Releases.

---

## 7. File Inventory

| File | Purpose | Issues |
|------|---------|--------|
| `pyproject.toml` | Build & project metadata | None major |
| `requirements.txt` | Runtime deps | Includes pytest |
| `README.md` | Docs | Good; mentions `argparse` but CLI actually uses `argparse` (OK) |
| `Dockerfile` | Container image | OK; could use non-root user |
| `.github/workflows/ci.yml` | Full CI | Duplicates test.yml; no caching |
| `.github/workflows/test.yml` | Basic CI | Redundant |
| `src/homelab_monitor/__init__.py` | Version | Out of sync |
| `src/homelab_monitor/cli.py` | Entrypoint | Unused imports; no `--version` |
| `src/homelab_monitor/config.py` | YAML loader | No schema validation |
| `src/homelab_monitor/format.py` | Rich tables | Type bug in `_bytes_to_human` |
| `src/homelab_monitor/monitor.py` | Core logic | Missing timeout; confusing health ternary |
| `tests/test_cli.py` | CLI tests | OK, could add `--version` test |
| `tests/test_config.py` | Config tests | OK, could add non-dict YAML test |
| `tests/test_format.py` | Format tests | OK, missing PiB / zero tests |
| `tests/test_monitor.py` | Monitor tests | Missing AccessDenied & alert branches |

---

*Report generated by comprehensive static analysis, dynamic testing, and manual code review.*
