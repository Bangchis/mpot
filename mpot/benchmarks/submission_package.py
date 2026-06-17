"""Create a compact soft-submission package from validated report artifacts.

This module is intentionally small and boring: it copies existing files into a
single folder and writes a manifest. It never creates benchmark numbers, plots,
or result tables by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import shutil
import time

from mpot.benchmarks.artifacts import read_json, write_json
from mpot.benchmarks.report_bundle import slugify


class SubmissionPackageError(RuntimeError):
    """Raised when strict packaging cannot continue."""


@dataclass
class SubmissionEntry:
    """One copied or missing file recorded in the submission manifest."""

    role: str
    source: str
    destination: str
    required: bool
    exists: bool
    copied: bool
    bytes: int
    note: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "source": self.source,
            "destination": self.destination,
            "required": self.required,
            "exists": self.exists,
            "copied": self.copied,
            "bytes": self.bytes,
            "note": self.note,
        }


def _copy_file(
    *,
    source: Path,
    destination: Path,
    role: str,
    required: bool,
    dry_run: bool,
    strict: bool,
    entries: list[SubmissionEntry],
) -> None:
    """Copy one file if it exists and record the result."""

    if not source.exists():
        entries.append(
            SubmissionEntry(
                role=role,
                source=str(source),
                destination=str(destination),
                required=required,
                exists=False,
                copied=False,
                bytes=0,
                note="missing required file" if required else "optional file not found",
            )
        )
        if strict and required:
            raise SubmissionPackageError(f"Missing required submission file: {source}")
        return

    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    entries.append(
        SubmissionEntry(
            role=role,
            source=str(source),
            destination=str(destination),
            required=required,
            exists=True,
            copied=not dry_run,
            bytes=source.stat().st_size,
            note="dry run: not copied" if dry_run else "",
        )
    )


def _copy_glob(
    *,
    root: Path,
    pattern: str,
    destination_dir: Path,
    role: str,
    required: bool,
    dry_run: bool,
    strict: bool,
    entries: list[SubmissionEntry],
) -> None:
    """Copy all files matching a pattern and record a missing marker if empty."""

    matches = sorted(path for path in root.glob(pattern) if path.is_file())
    if not matches:
        marker = destination_dir / pattern.replace("*", "NO_MATCH")
        entries.append(
            SubmissionEntry(
                role=role,
                source=str(root / pattern),
                destination=str(marker),
                required=required,
                exists=False,
                copied=False,
                bytes=0,
                note="no files matched pattern",
            )
        )
        if strict and required:
            raise SubmissionPackageError(f"No required submission files matched: {root / pattern}")
        return

    for source in matches:
        _copy_file(
            source=source,
            destination=destination_dir / source.name,
            role=role,
            required=required,
            dry_run=dry_run,
            strict=strict,
            entries=entries,
        )


def _known_files(label: str, report_dir: Path, docs_dir: Path) -> list[tuple[str, Path, str, bool]]:
    """Return fixed files that should be included in the package."""

    return [
        ("living report draft", report_dir / "REPORT_DRAFT.md", "report/REPORT_DRAFT.md", True),
        ("report checklist", report_dir / "REPORT_CHECKLIST.md", "report/REPORT_CHECKLIST.md", True),
        ("team ownership doc", docs_dir / "team_ownership.md", "docs/team_ownership.md", True),
        ("project plan doc", docs_dir / "mpi_mpot_project_plan.md", "docs/mpi_mpot_project_plan.md", True),
        ("final audit json", report_dir / f"FINAL_AUDIT_{label}.json", f"checks/FINAL_AUDIT_{label}.json", True),
        ("final audit markdown", report_dir / f"FINAL_AUDIT_{label}.md", f"checks/FINAL_AUDIT_{label}.md", True),
        ("experiment index json", report_dir / f"EXPERIMENT_INDEX_{label}.json", f"checks/EXPERIMENT_INDEX_{label}.json", True),
        ("experiment index markdown", report_dir / f"EXPERIMENT_INDEX_{label}.md", f"checks/EXPERIMENT_INDEX_{label}.md", True),
        ("ownership report json", report_dir / "TEAM_OWNERSHIP_REPORT.json", "checks/TEAM_OWNERSHIP_REPORT.json", True),
        ("ownership report markdown", report_dir / "TEAM_OWNERSHIP_REPORT.md", "checks/TEAM_OWNERSHIP_REPORT.md", True),
        ("member defense json", report_dir / "MEMBER_DEFENSE_GUIDE.json", "checks/MEMBER_DEFENSE_GUIDE.json", True),
        ("member defense markdown", report_dir / "MEMBER_DEFENSE_GUIDE.md", "checks/MEMBER_DEFENSE_GUIDE.md", True),
        ("environment markdown", report_dir / f"ENVIRONMENT_{label}.md", f"checks/ENVIRONMENT_{label}.md", True),
        ("communication markdown", report_dir / f"COMMUNICATION_{label}.md", f"checks/COMMUNICATION_{label}.md", True),
        ("granularity markdown", report_dir / f"GRANULARITY_{label}.md", f"checks/GRANULARITY_{label}.md", True),
        ("solution quality markdown", report_dir / f"SOLUTION_QUALITY_{label}.md", f"checks/SOLUTION_QUALITY_{label}.md", True),
        ("report sync json", report_dir / f"REPORT_SYNC_{label}.json", f"checks/REPORT_SYNC_{label}.json", True),
        ("report sync markdown", report_dir / f"REPORT_SYNC_{label}.md", f"checks/REPORT_SYNC_{label}.md", True),
        ("results summary json", report_dir / f"RESULTS_SUMMARY_{label}.json", f"report/RESULTS_SUMMARY_{label}.json", True),
        ("results summary markdown", report_dir / f"RESULTS_SUMMARY_{label}.md", f"report/RESULTS_SUMMARY_{label}.md", True),
        ("benchmark plan json", report_dir / "BENCHMARK_PLAN.json", "planning/BENCHMARK_PLAN.json", False),
        ("benchmark plan markdown", report_dir / "BENCHMARK_PLAN.md", "planning/BENCHMARK_PLAN.md", False),
        ("benchmark budget json", report_dir / f"BENCHMARK_BUDGET_{label}.json", f"planning/BENCHMARK_BUDGET_{label}.json", False),
        ("benchmark budget markdown", report_dir / f"BENCHMARK_BUDGET_{label}.md", f"planning/BENCHMARK_BUDGET_{label}.md", False),
        ("artifact manifest markdown", report_dir / "ARTIFACT_MANIFEST.md", "report/ARTIFACT_MANIFEST.md", False),
    ]


def _final_ready(report_dir: Path, label: str) -> bool | None:
    path = report_dir / f"FINAL_AUDIT_{label}.json"
    if not path.exists():
        return None
    try:
        payload = read_json(path)
    except Exception:
        return False
    return bool(payload.get("final_ready"))


def create_submission_package(
    *,
    label: str,
    report_dir: str | Path = "report",
    docs_dir: str | Path = "docs",
    output_dir: str | Path = "submission",
    clean: bool = False,
    dry_run: bool = False,
    strict: bool = False,
) -> dict[str, Any]:
    """Copy report artifacts into ``submission/<label>`` and return a manifest."""

    safe_label = slugify(label, fallback="submission")
    report_root = Path(report_dir)
    docs_root = Path(docs_dir)
    package_dir = Path(output_dir) / safe_label
    entries: list[SubmissionEntry] = []

    if clean and package_dir.exists() and not dry_run:
        shutil.rmtree(package_dir)

    for role, source, relative_dest, required in _known_files(safe_label, report_root, docs_root):
        _copy_file(
            source=source,
            destination=package_dir / relative_dest,
            role=role,
            required=required,
            dry_run=dry_run,
            strict=strict,
            entries=entries,
        )

    _copy_glob(
        root=report_root / "tables",
        pattern=f"*{safe_label}*",
        destination_dir=package_dir / "tables",
        role="result table artifact",
        required=True,
        dry_run=dry_run,
        strict=strict,
        entries=entries,
    )
    _copy_glob(
        root=report_root / "figures",
        pattern=f"*{safe_label}*.png",
        destination_dir=package_dir / "figures",
        role="report figure artifact",
        required=True,
        dry_run=dry_run,
        strict=strict,
        entries=entries,
    )
    _copy_glob(
        root=report_root / "figures",
        pattern=f"*{safe_label}*.gif",
        destination_dir=package_dir / "figures",
        role="report animation artifact",
        required=False,
        dry_run=dry_run,
        strict=strict,
        entries=entries,
    )

    final_ready = _final_ready(report_root, safe_label)
    missing_required = [entry for entry in entries if entry.required and not entry.exists]
    passed = not missing_required and final_ready is not False

    manifest = {
        "label": safe_label,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "package_dir": str(package_dir),
        "manifest_json": str(package_dir / "SUBMISSION_MANIFEST.json"),
        "manifest_markdown": str(package_dir / "SUBMISSION_MANIFEST.md"),
        "final_ready": final_ready,
        "passed": passed,
        "num_entries": len(entries),
        "num_missing_required": len(missing_required),
        "entries": [entry.to_json() for entry in entries],
        "note": "This package copies existing artifacts only; it does not generate experiment data.",
    }

    if not dry_run:
        write_submission_manifest(manifest)
    return manifest


def submission_markdown(payload: dict[str, Any]) -> str:
    """Render a submission package manifest as Markdown."""

    missing = [entry for entry in payload.get("entries", []) if entry.get("required") and not entry.get("exists")]
    lines = [
        "# Submission Package Manifest",
        "",
        f"Label: `{payload.get('label')}`",
        f"Package directory: `{payload.get('package_dir')}`",
        f"Passed: `{payload.get('passed')}`",
        f"Final audit ready: `{payload.get('final_ready')}`",
        "",
        "This package contains copied artifacts only. It must not be used as a",
        "source of new benchmark numbers.",
        "",
        "## Summary",
        "",
        f"- Entries: `{payload.get('num_entries')}`",
        f"- Missing required entries: `{payload.get('num_missing_required')}`",
        "",
    ]
    if missing:
        lines.extend(["## Missing Required Files", "", "| Role | Source |", "|---|---|"])
        for entry in missing:
            lines.append(f"| {entry.get('role')} | `{entry.get('source')}` |")
        lines.append("")

    lines.extend(["## Included Files", "", "| Required | Role | Destination |", "|---|---|---|"])
    for entry in payload.get("entries", []):
        required = "yes" if entry.get("required") else "no"
        destination = entry.get("destination") if entry.get("exists") else entry.get("source")
        lines.append(f"| {required} | {entry.get('role')} | `{destination}` |")
    lines.append("")
    return "\n".join(lines)


def write_submission_manifest(payload: dict[str, Any]) -> None:
    """Write JSON and Markdown manifests for a submission package."""

    json_path = Path(str(payload["manifest_json"]))
    markdown_path = Path(str(payload["manifest_markdown"]))
    write_json(json_path, payload)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(submission_markdown(payload), encoding="utf-8")
