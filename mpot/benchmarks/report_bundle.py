"""Build a report artifact bundle from real benchmark outputs.

The living report should only cite results that exist on disk. This module
copies selected CSV/JSON/PNG files into a stable report folder and writes a
manifest that records exactly where each artifact came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import re
import shutil
import time

from mpot.benchmarks.artifacts import read_json, write_json
from mpot.benchmarks.plots import plot_runtime_vs_input_size, plot_speedup


RUN_DATA_FILES = (
    "config.json",
    "summary.json",
    "task_results.csv",
    "task_results.json",
    "best_trajectory.npy",
)
SERIAL_FIGURE_FILES = (
    "best_path.png",
    "cost_by_task.png",
)
MPI_DATA_FILES = (
    "rank_timings.csv",
    "comm_events.csv",
    "task_assignment.csv",
)
MPI_FIGURE_FILES = (
    "best_path.png",
    "cost_by_task.png",
    "rank_time_breakdown.png",
)


class BundleError(RuntimeError):
    """Raised when a required report artifact is missing or inconsistent."""


@dataclass
class BundleEntry:
    """One source-to-destination copy recorded in the report manifest."""

    role: str
    source: str
    destination: str
    exists: bool
    copied: bool
    bytes: int
    note: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "source": self.source,
            "destination": self.destination,
            "exists": self.exists,
            "copied": self.copied,
            "bytes": self.bytes,
            "note": self.note,
        }


def slugify(value: str, fallback: str = "artifact") -> str:
    """Return a filesystem-safe ASCII slug."""

    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    slug = slug.strip("-._")
    return slug or fallback


def default_bundle_name(label: str | None = None) -> str:
    """Return a timestamped bundle name that is safe for filenames."""

    prefix = slugify(label, fallback="report-bundle") if label else "report-bundle"
    return f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}"


def _as_paths(values: Iterable[str | Path] | None) -> list[Path]:
    return [Path(value) for value in values or []]


def _read_run_id(run_dir: Path) -> str:
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        return run_dir.name
    summary = read_json(summary_path)
    return str(summary.get("run_id") or run_dir.name)


def _copy_file(
    *,
    source: Path,
    destination: Path,
    role: str,
    strict: bool,
    dry_run: bool,
    entries: list[BundleEntry],
    note: str = "",
) -> None:
    """Copy one artifact and append a manifest entry."""

    if not source.exists():
        entry = BundleEntry(
            role=role,
            source=str(source),
            destination=str(destination),
            exists=False,
            copied=False,
            bytes=0,
            note=note or "missing source file",
        )
        entries.append(entry)
        if strict:
            raise BundleError(f"Required artifact is missing: {source}")
        return

    copied = False
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied = True

    entries.append(
        BundleEntry(
            role=role,
            source=str(source),
            destination=str(destination),
            exists=True,
            copied=copied,
            bytes=source.stat().st_size,
            note=note,
        )
    )


def _copy_run_data(
    *,
    run_dir: Path,
    run_kind: str,
    bundle_name: str,
    artifacts_dir: Path,
    figures_dir: Path,
    strict: bool,
    dry_run: bool,
    entries: list[BundleEntry],
) -> dict[str, Any]:
    """Copy one serial or MPI run into the report bundle."""

    if run_kind not in {"serial", "mpi"}:
        raise ValueError("run_kind must be 'serial' or 'mpi'.")

    run_id = _read_run_id(run_dir)
    run_slug = slugify(run_id)
    data_dest = artifacts_dir / run_kind / run_slug

    for filename in RUN_DATA_FILES:
        _copy_file(
            source=run_dir / filename,
            destination=data_dest / filename,
            role=f"{run_kind} data",
            strict=strict,
            dry_run=dry_run,
            entries=entries,
        )

    if run_kind == "mpi":
        for filename in MPI_DATA_FILES:
            role = {
                "rank_timings.csv": "mpi timing data",
                "comm_events.csv": "mpi communication data",
                "task_assignment.csv": "mpi assignment data",
            }[filename]
            _copy_file(
                source=run_dir / filename,
                destination=data_dest / filename,
                role=role,
                strict=strict,
                dry_run=dry_run,
                entries=entries,
            )

    figure_files = MPI_FIGURE_FILES if run_kind == "mpi" else SERIAL_FIGURE_FILES
    copied_figures = []
    for filename in figure_files:
        figure_name = f"{bundle_name}_{run_kind}_{run_slug}_{filename}"
        figure_name = slugify(figure_name.replace(".png", "")) + ".png"
        figure_dest = figures_dir / figure_name
        _copy_file(
            source=run_dir / filename,
            destination=figure_dest,
            role=f"{run_kind} figure",
            strict=strict,
            dry_run=dry_run,
            entries=entries,
        )
        copied_figures.append(str(figure_dest))

    summary = read_json(run_dir / "summary.json") if (run_dir / "summary.json").exists() else {}
    return {
        "run_kind": run_kind,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "artifact_dir": str(data_dest),
        "figures": copied_figures,
        "mode": summary.get("mode"),
        "total_tasks": summary.get("total_tasks"),
        "size": summary.get("size"),
    }


def _copy_report_json(
    *,
    path: Path,
    role: str,
    artifacts_dir: Path,
    strict: bool,
    dry_run: bool,
    entries: list[BundleEntry],
) -> str:
    name = slugify(path.parent.name or path.stem)
    destination = artifacts_dir / role.replace(" ", "_") / name / path.name
    _copy_file(
        source=path,
        destination=destination,
        role=role,
        strict=strict,
        dry_run=dry_run,
        entries=entries,
    )
    return str(destination)


def _copy_correctness_artifacts(
    *,
    path: Path,
    artifacts_dir: Path,
    strict: bool,
    dry_run: bool,
    entries: list[BundleEntry],
) -> dict[str, str | None]:
    """Copy correctness JSON and the optional task comparison CSV."""

    destination = _copy_report_json(
        path=path,
        role="correctness report",
        artifacts_dir=artifacts_dir,
        strict=strict,
        dry_run=dry_run,
        entries=entries,
    )
    copied: dict[str, str | None] = {"report": destination, "task_comparison_csv": None}
    if not path.exists():
        return copied

    payload = read_json(path)
    csv_value = payload.get("task_comparison_csv")
    if not csv_value:
        return copied

    csv_path = Path(str(csv_value))
    if not csv_path.is_absolute() and not csv_path.exists():
        csv_path = path.parent / csv_path.name
    destination_path = Path(destination).parent / "task_comparison.csv"
    _copy_file(
        source=csv_path,
        destination=destination_path,
        role="correctness task comparison",
        strict=strict,
        dry_run=dry_run,
        entries=entries,
    )
    copied["task_comparison_csv"] = str(destination_path)
    return copied


def _record_generated_plot(
    *,
    source_description: str,
    destination: Path,
    role: str,
    entries: list[BundleEntry],
) -> None:
    entries.append(
        BundleEntry(
            role=role,
            source=source_description,
            destination=str(destination),
            exists=destination.exists(),
            copied=False,
            bytes=destination.stat().st_size if destination.exists() else 0,
            note="generated directly into report/figures from result summaries",
        )
    )


def create_report_bundle(
    *,
    report_dir: str | Path = "report",
    bundle_name: str | None = None,
    serial_runs: Iterable[str | Path] | None = None,
    mpi_runs: Iterable[str | Path] | None = None,
    correctness_reports: Iterable[str | Path] | None = None,
    validation_reports: Iterable[str | Path] | None = None,
    results_dir: str | Path = "results",
    label: str | None = None,
    fixed_size: int | None = None,
    input_size: int | None = None,
    generate_plots: bool = True,
    clean_existing: bool = False,
    strict: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create a report bundle and return the JSON manifest.

    Strict mode is intentionally the default. A bundle is meant to support real
    report claims, so missing files should fail early instead of silently
    producing a misleading manifest.
    """

    report_root = Path(report_dir)
    bundle_name = slugify(bundle_name or default_bundle_name(label))
    artifacts_dir = report_root / "artifacts" / bundle_name
    figures_dir = report_root / "figures"
    entries: list[BundleEntry] = []

    if clean_existing and artifacts_dir.exists() and not dry_run:
        shutil.rmtree(artifacts_dir)

    copied_runs = []
    for run_dir in _as_paths(serial_runs):
        copied_runs.append(
            _copy_run_data(
                run_dir=run_dir,
                run_kind="serial",
                bundle_name=bundle_name,
                artifacts_dir=artifacts_dir,
                figures_dir=figures_dir,
                strict=strict,
                dry_run=dry_run,
                entries=entries,
            )
        )

    for run_dir in _as_paths(mpi_runs):
        copied_runs.append(
            _copy_run_data(
                run_dir=run_dir,
                run_kind="mpi",
                bundle_name=bundle_name,
                artifacts_dir=artifacts_dir,
                figures_dir=figures_dir,
                strict=strict,
                dry_run=dry_run,
                entries=entries,
            )
        )

    copied_correctness = [
        _copy_correctness_artifacts(
            path=path,
            artifacts_dir=artifacts_dir,
            strict=strict,
            dry_run=dry_run,
            entries=entries,
        )
        for path in _as_paths(correctness_reports)
    ]
    copied_validation = [
        _copy_report_json(
            path=path,
            role="validation report",
            artifacts_dir=artifacts_dir,
            strict=strict,
            dry_run=dry_run,
            entries=entries,
        )
        for path in _as_paths(validation_reports)
    ]

    generated_plots = []
    if generate_plots and dry_run:
        suffix = f"_{label}" if label else ""
        for role, filename in [
            ("aggregate runtime figure", f"runtime_vs_input_size{suffix}.png"),
            ("aggregate speedup figure", f"speedup{suffix}.png"),
        ]:
            destination = figures_dir / filename
            entries.append(
                BundleEntry(
                    role=role,
                    source=f"would generate from {Path(results_dir)}",
                    destination=str(destination),
                    exists=destination.exists(),
                    copied=False,
                    bytes=destination.stat().st_size if destination.exists() else 0,
                    note="dry run: plot not generated",
                )
            )
    elif generate_plots:
        source_description = f"generated from {Path(results_dir)}"
        try:
            runtime_plot = plot_runtime_vs_input_size(
                results_dir,
                figures_dir,
                label=label,
                fixed_size=fixed_size,
            )
            generated_plots.append(str(runtime_plot))
            _record_generated_plot(
                source_description=source_description,
                destination=runtime_plot,
                role="aggregate runtime figure",
                entries=entries,
            )
        except Exception as exc:
            if strict:
                raise BundleError(f"Could not generate runtime-vs-N plot: {exc}") from exc
            entries.append(
                BundleEntry(
                    role="aggregate runtime figure",
                    source=source_description,
                    destination=str(figures_dir),
                    exists=False,
                    copied=False,
                    bytes=0,
                    note=f"plot skipped: {exc}",
                )
            )

        try:
            speedup_plot = plot_speedup(
                results_dir,
                figures_dir,
                label=label,
                input_size=input_size,
            )
            generated_plots.append(str(speedup_plot))
            _record_generated_plot(
                source_description=source_description,
                destination=speedup_plot,
                role="aggregate speedup figure",
                entries=entries,
            )
        except Exception as exc:
            if strict:
                raise BundleError(f"Could not generate speedup plot: {exc}") from exc
            entries.append(
                BundleEntry(
                    role="aggregate speedup figure",
                    source=source_description,
                    destination=str(figures_dir),
                    exists=False,
                    copied=False,
                    bytes=0,
                    note=f"plot skipped: {exc}",
                )
            )

    manifest_path = artifacts_dir / "manifest.json"
    markdown_path = report_root / "ARTIFACT_MANIFEST.md"
    manifest = {
        "bundle_name": bundle_name,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "report_dir": str(report_root),
        "artifacts_dir": str(artifacts_dir),
        "figures_dir": str(figures_dir),
        "strict": strict,
        "dry_run": dry_run,
        "results_dir": str(results_dir),
        "label": label,
        "fixed_size": fixed_size,
        "input_size": input_size,
        "clean_existing": clean_existing,
        "note": "Use only listed real artifacts for report Results. Do not invent numbers.",
        "runs": copied_runs,
        "correctness_reports": copied_correctness,
        "validation_reports": copied_validation,
        "generated_plots": generated_plots,
        "entries": [entry.to_json() for entry in entries],
        "manifest_path": str(manifest_path),
        "markdown_path": str(markdown_path),
    }

    if not dry_run:
        write_json(manifest_path, manifest)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(build_manifest_markdown(manifest), encoding="utf-8")
    return manifest


def build_manifest_markdown(manifest: dict[str, Any]) -> str:
    """Build a compact human-readable manifest for teammates."""

    lines = [
        "# Report Artifact Manifest",
        "",
        f"Bundle: `{manifest['bundle_name']}`",
        "",
        "This file is generated from real local artifacts. Only use numbers and",
        "figures that can be traced to this manifest or to a newer generated",
        "manifest. Do not add invented runtime, speedup, or correctness values to",
        "the report.",
        "",
        "## Runs",
        "",
    ]
    if manifest["runs"]:
        lines.append("| Kind | Run id | N | Processes | Source |")
        lines.append("|---|---|---:|---:|---|")
        for run in manifest["runs"]:
            lines.append(
                "| {kind} | `{run_id}` | {n} | {size} | `{source}` |".format(
                    kind=run.get("run_kind", ""),
                    run_id=run.get("run_id", ""),
                    n=run.get("total_tasks", ""),
                    size=run.get("size", ""),
                    source=run.get("run_dir", ""),
                )
            )
    else:
        lines.append("No runs were included.")

    lines.extend(
        [
            "",
            "## Copied Artifacts",
            "",
            "| Role | Source | Destination | Status |",
            "|---|---|---|---|",
        ]
    )
    for entry in manifest["entries"]:
        status = "copied" if entry["copied"] else "generated" if entry["exists"] else "missing"
        lines.append(
            f"| {entry['role']} | `{entry['source']}` | `{entry['destination']}` | {status} |"
        )

    lines.extend(
        [
            "",
            "## Next Manual Step",
            "",
            "When final benchmark runs are available, regenerate this manifest with the",
            "final serial/MPI/correctness/validation artifacts and then update the",
            "Results section of `report/REPORT_DRAFT.md` from those files only.",
            "",
        ]
    )
    return "\n".join(lines)
