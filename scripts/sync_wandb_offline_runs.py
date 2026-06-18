#!/usr/bin/env python3
"""Sync local W&B offline runs after the user logs in.

The benchmark can log W&B runs in offline mode on macOS, Ubuntu VM, or weak
network connections. This script makes the final upload step repeatable: it
lists offline run directories, checks whether W&B has an API key, syncs each
run with `wandb sync`, and writes a local manifest.
"""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from shutil import which
import json
import netrc
import os
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--wandb-dir", default="wandb", help="Directory containing offline-run-* folders.")
    parser.add_argument(
        "--run-dir",
        action="append",
        default=[],
        help="Specific offline run directory to sync. Defaults to all wandb/offline-run-* directories.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of offline runs to sync.")
    parser.add_argument("--dry-run", action="store_true", help="List runs and write a manifest without syncing.")
    parser.add_argument(
        "--wandb-bin",
        default=None,
        help="Path to wandb executable. Defaults to the current venv's wandb binary, then PATH.",
    )
    parser.add_argument(
        "--manifest",
        default="report/WANDB_SYNC_offline_runs.json",
        help="Output JSON sync manifest.",
    )
    parser.add_argument(
        "--markdown",
        default="report/WANDB_SYNC_offline_runs.md",
        help="Output Markdown sync manifest.",
    )
    return parser.parse_args()


def find_wandb_binary(raw: str | None = None) -> str:
    """Find the W&B CLI in a venv-friendly way."""

    if raw:
        return raw
    venv_candidate = Path(sys.executable).with_name("wandb")
    if venv_candidate.exists():
        return str(venv_candidate)
    found = which("wandb")
    if found:
        return found
    raise FileNotFoundError("wandb executable not found. Install with `.venv/bin/python -m pip install wandb`.")


def discover_offline_runs(wandb_dir: str | Path, explicit: list[str] | None = None) -> list[Path]:
    """Return offline-run directories sorted by name."""

    if explicit:
        return sorted({Path(path) for path in explicit})
    root = Path(wandb_dir)
    if not root.exists():
        return []
    return sorted(path for path in root.glob("offline-run-*") if path.is_dir())


def wandb_status(wandb_bin: str) -> dict[str, object]:
    """Read `wandb status` as a JSON object, tolerating the heading line."""

    proc = subprocess.run([wandb_bin, "status"], cwd=ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "api_key": None}
    start = proc.stdout.find("{")
    if start < 0:
        return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "api_key": None}
    try:
        payload = json.loads(proc.stdout[start:])
    except json.JSONDecodeError:
        payload = {"api_key": None}
    payload["returncode"] = proc.returncode
    return payload


def has_wandb_credentials(status: dict[str, object]) -> bool:
    """Return True if W&B can likely authenticate without exposing the key."""

    if status.get("api_key"):
        return True
    if os.environ.get("WANDB_API_KEY"):
        return True
    try:
        auth = netrc.netrc().authenticators("api.wandb.ai")
    except (FileNotFoundError, netrc.NetrcParseError, OSError):
        auth = None
    return bool(auth and auth[2])


def sync_one_run(wandb_bin: str, run_dir: Path) -> dict[str, object]:
    """Sync one offline run and return a manifest row."""

    proc = subprocess.run([wandb_bin, "sync", str(run_dir)], cwd=ROOT, text=True, capture_output=True)
    return {
        "run_dir": str(run_dir),
        "status": "synced" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def manifest_markdown(payload: dict[str, object]) -> str:
    """Render the sync manifest as Markdown."""

    lines = [
        "# W&B Offline Sync Manifest",
        "",
        f"- created_at: `{payload.get('created_at')}`",
        f"- wandb_bin: `{payload.get('wandb_bin')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- logged_in: `{payload.get('logged_in')}`",
        f"- discovered_runs: `{payload.get('num_runs')}`",
        f"- synced_runs: `{payload.get('num_synced')}`",
        "",
        "## Runs",
        "",
        "| status | run dir | return code |",
        "|---|---|---:|",
    ]
    for row in payload.get("runs", []):
        lines.append(f"| `{row.get('status')}` | `{row.get('run_dir')}` | `{row.get('returncode')}` |")
    lines.append("")
    if not payload.get("logged_in") and not payload.get("dry_run"):
        lines.extend(
            [
                "## Next Step",
                "",
                "Run `.venv/bin/wandb login`, then rerun this sync script.",
                "",
            ]
        )
    return "\n".join(lines)


def write_manifest(payload: dict[str, object], json_path: str | Path, markdown_path: str | Path) -> tuple[Path, Path]:
    """Write JSON and Markdown manifests."""

    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_out.write_text(manifest_markdown(payload), encoding="utf-8")
    return json_out, markdown_out


def main() -> int:
    args = parse_args()
    try:
        wandb_bin = find_wandb_binary(args.wandb_bin)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    offline_runs = discover_offline_runs(args.wandb_dir, args.run_dir)
    if args.limit is not None:
        offline_runs = offline_runs[: args.limit]
    status = wandb_status(wandb_bin)
    logged_in = has_wandb_credentials(status)

    rows: list[dict[str, object]] = []
    if args.dry_run:
        rows = [{"run_dir": str(path), "status": "pending", "returncode": None} for path in offline_runs]
    elif not logged_in:
        rows = [{"run_dir": str(path), "status": "blocked_not_logged_in", "returncode": None} for path in offline_runs]
    else:
        for run_dir in offline_runs:
            rows.append(sync_one_run(wandb_bin, run_dir))

    payload = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "wandb_bin": wandb_bin,
        "dry_run": bool(args.dry_run),
        "logged_in": logged_in,
        "status_api_key_present": logged_in,
        "num_runs": len(offline_runs),
        "num_synced": sum(1 for row in rows if row.get("status") == "synced"),
        "runs": rows,
    }
    json_out, markdown_out = write_manifest(payload, args.manifest, args.markdown)
    print(f"wandb_logged_in: {logged_in}")
    print(f"offline_runs: {len(offline_runs)}")
    for row in rows:
        print(f"- {row['status']}: {row['run_dir']}")
    print(f"manifest_json: {json_out}")
    print(f"manifest_markdown: {markdown_out}")
    return 0 if args.dry_run or logged_in else 2


if __name__ == "__main__":
    raise SystemExit(main())
