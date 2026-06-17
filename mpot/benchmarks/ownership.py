"""Generate per-member code ownership and line-count evidence.

The course rubric requires each group member to own a meaningful part of the
implementation. This module turns the ownership split into a reproducible JSON
and Markdown artifact instead of relying on a hand-written claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import time

from mpot.benchmarks.artifacts import write_json


DEFAULT_MINIMUM_LINES_PER_MEMBER = 250
DEFAULT_RECOMMENDED_MAX_LINES_PER_MEMBER = 700
COUNTED_SUFFIXES = {".py", ".json"}
IGNORED_DIR_NAMES = {".git", ".venv", "__pycache__", "results", "report"}


DEFAULT_MEMBER_FILES: dict[str, dict[str, Any]] = {
    "Member A": {
        "area": "2D planning problem and configuration",
        "files": [
            "mpot/benchmarks/problem_2d.py",
            "mpot/benchmarks/config.py",
            "configs/local_smoke.json",
            "configs/local_benchmark.json",
            "configs/variant_open_2d.json",
            "configs/variant_narrow_passage_2d.json",
            "configs/variant_cluttered_2d.json",
        ],
    },
    "Member B": {
        "area": "Local optimizer, serial baseline, and correctness",
        "files": [
            "mpot/benchmarks/local_runner.py",
            "mpot/benchmarks/reduction.py",
            "mpot/benchmarks/correctness.py",
            "scripts/run_serial.py",
            "scripts/compare_serial_mpi.py",
        ],
    },
    "Member C": {
        "area": "MPI parallelization, mapping, rank behavior, and communication trace",
        "files": [
            "mpot/benchmarks/mpi_scheduler.py",
            "mpot/benchmarks/mpi_runner.py",
            "mpot/benchmarks/communication.py",
            "scripts/run_mpi.py",
            "scripts/analyze_communication.py",
        ],
    },
    "Member D": {
        "area": "Metrics, plots, result tables, and load-balance evidence",
        "files": [
            "mpot/benchmarks/metrics.py",
            "mpot/benchmarks/plots.py",
            "mpot/benchmarks/result_tables.py",
            "scripts/analyze_granularity.py",
            "scripts/plot_results.py",
        ],
    },
}


@dataclass
class LineCount:
    """Line-count summary for one source/config file."""

    path: str
    exists: bool
    counted: bool
    suffix: str
    total_lines: int
    blank_lines: int
    comment_lines: int
    meaningful_lines: int
    note: str

    def to_json(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "exists": self.exists,
            "counted": self.counted,
            "suffix": self.suffix,
            "total_lines": self.total_lines,
            "blank_lines": self.blank_lines,
            "comment_lines": self.comment_lines,
            "meaningful_lines": self.meaningful_lines,
            "note": self.note,
        }


def _is_ignored(path: Path) -> bool:
    return any(part in IGNORED_DIR_NAMES for part in path.parts)


def _expand_member_paths(repo_root: Path, entries: list[str]) -> list[Path]:
    """Expand owned file/directory entries into countable paths."""

    paths: list[Path] = []
    for entry in entries:
        candidate = repo_root / entry
        if candidate.is_dir():
            for child in sorted(candidate.rglob("*")):
                if child.is_file() and child.suffix in COUNTED_SUFFIXES and not _is_ignored(child.relative_to(repo_root)):
                    paths.append(child)
        else:
            paths.append(candidate)
    return paths


def count_file_lines(repo_root: str | Path, file_path: str | Path) -> LineCount:
    """Count meaningful code/config lines for one file."""

    root = Path(repo_root).resolve()
    path = Path(file_path)
    absolute = (path if path.is_absolute() else root / path).resolve()
    try:
        relative = absolute.relative_to(root).as_posix()
    except ValueError:
        relative = str(path)
    suffix = absolute.suffix

    if not absolute.exists():
        return LineCount(relative, False, False, suffix, 0, 0, 0, 0, "missing file")
    if not absolute.is_file():
        return LineCount(relative, True, False, suffix, 0, 0, 0, 0, "not a file")
    if suffix not in COUNTED_SUFFIXES:
        return LineCount(relative, True, False, suffix, 0, 0, 0, 0, "suffix not counted")

    total = 0
    blank = 0
    comment = 0
    meaningful = 0
    for line in absolute.read_text(encoding="utf-8").splitlines():
        total += 1
        stripped = line.strip()
        if not stripped:
            blank += 1
            continue
        if suffix == ".py" and stripped.startswith("#"):
            comment += 1
            continue
        meaningful += 1

    note = "python nonblank noncomment lines" if suffix == ".py" else "json nonblank config lines"
    return LineCount(relative, True, True, suffix, total, blank, comment, meaningful, note)


def _duplicate_files(member_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    owners_by_path: dict[str, list[str]] = {}
    for member in member_rows:
        for file_row in member["files"]:
            if not file_row.get("counted"):
                continue
            owners_by_path.setdefault(file_row["path"], []).append(member["member"])
    return [
        {"path": path, "owners": owners}
        for path, owners in sorted(owners_by_path.items())
        if len(owners) > 1
    ]


def build_ownership_report(
    *,
    repo_root: str | Path = ".",
    member_files: dict[str, dict[str, Any]] | None = None,
    minimum_lines_per_member: int = DEFAULT_MINIMUM_LINES_PER_MEMBER,
    recommended_max_lines_per_member: int = DEFAULT_RECOMMENDED_MAX_LINES_PER_MEMBER,
) -> dict[str, Any]:
    """Build a JSON-friendly ownership and line-count report."""

    root = Path(repo_root).resolve()
    spec = member_files or DEFAULT_MEMBER_FILES
    members: list[dict[str, Any]] = []

    for member, details in spec.items():
        file_paths = _expand_member_paths(root, [str(value) for value in details.get("files", [])])
        counts = [count_file_lines(root, path) for path in file_paths]
        counted = [item for item in counts if item.counted]
        missing = [item for item in counts if not item.exists]
        meaningful_lines = sum(item.meaningful_lines for item in counted)
        within_recommended_size = meaningful_lines <= int(recommended_max_lines_per_member)
        members.append(
            {
                "member": member,
                "area": str(details.get("area", "")),
                "minimum_lines": int(minimum_lines_per_member),
                "recommended_max_lines": int(recommended_max_lines_per_member),
                "passed": meaningful_lines >= int(minimum_lines_per_member) and within_recommended_size and not missing,
                "within_recommended_size": within_recommended_size,
                "meaningful_lines": meaningful_lines,
                "total_lines": sum(item.total_lines for item in counted),
                "counted_files": len(counted),
                "missing_files": len(missing),
                "files": [item.to_json() for item in counts],
            }
        )

    duplicates = _duplicate_files(members)
    failed = [member for member in members if not member["passed"]]
    total_meaningful = sum(member["meaningful_lines"] for member in members)
    minimum_total = int(minimum_lines_per_member) * len(members)
    return {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "repo_root": str(root),
        "minimum_lines_per_member": int(minimum_lines_per_member),
        "recommended_max_lines_per_member": int(recommended_max_lines_per_member),
        "minimum_total_lines": minimum_total,
        "total_meaningful_lines": total_meaningful,
        "num_members": len(members),
        "num_failed_members": len(failed),
        "passed": not failed and not duplicates and total_meaningful >= minimum_total,
        "duplicate_files": duplicates,
        "members": members,
        "note": (
            "Counts cover the compact primary defense set for each member. "
            "They exclude blank Python lines, Python comment-only lines, docs, slides, results, report text, "
            "and shared support modules that no single member has to defend in full."
        ),
    }


def _fmt_bool(value: bool) -> str:
    return "PASS" if value else "FAIL"


def ownership_markdown(payload: dict[str, Any]) -> str:
    """Render an ownership report as Markdown."""

    verdict = "PASS" if payload.get("passed") else "FAIL"
    lines = [
        "# Team Code Ownership Report",
        "",
        "This report is generated from the current repository state. It supports",
        "the course requirement that each member owns at least 250 lines of",
        "meaningful project code or configuration.",
        "",
        f"- created_at: `{payload['created_at']}`",
        f"- verdict: **{verdict}**",
        f"- minimum_lines_per_member: `{payload['minimum_lines_per_member']}`",
        f"- recommended_max_lines_per_member: `{payload['recommended_max_lines_per_member']}`",
        f"- minimum_total_lines: `{payload['minimum_total_lines']}`",
        f"- total_meaningful_lines: `{payload['total_meaningful_lines']}`",
        f"- failed_members: `{payload['num_failed_members']}`",
        "",
        "## Member Summary",
        "",
        "| status | member | area | files | meaningful lines | minimum | recommended max |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for member in payload["members"]:
        lines.append(
                "| {status} | {member} | {area} | {files} | {lines_} | {minimum} | {maximum} |".format(
                    status=_fmt_bool(bool(member["passed"])),
                    member=member["member"],
                    area=member["area"],
                    files=member["counted_files"],
                    lines_=member["meaningful_lines"],
                    minimum=member["minimum_lines"],
                    maximum=member["recommended_max_lines"],
                )
            )

    lines.extend(["", "## File Details", "", "| member | file | counted | meaningful | total | note |", "|---|---|---:|---:|---:|---|"])
    for member in payload["members"]:
        for file_row in member["files"]:
            lines.append(
                "| {member} | `{path}` | {counted} | {meaningful} | {total} | {note} |".format(
                    member=member["member"],
                    path=file_row["path"],
                    counted="yes" if file_row["counted"] else "no",
                    meaningful=file_row["meaningful_lines"],
                    total=file_row["total_lines"],
                    note=file_row["note"],
                )
            )

    lines.extend(["", "## Duplicate Ownership", ""])
    duplicates = payload.get("duplicate_files", [])
    if duplicates:
        lines.extend(["| file | owners |", "|---|---|"])
        for row in duplicates:
            lines.append(f"| `{row['path']}` | {', '.join(row['owners'])} |")
    else:
        lines.append("No counted source/config file is assigned to more than one member.")

    lines.extend(["", payload["note"], ""])
    return "\n".join(lines)


def write_ownership_report(
    *,
    payload: dict[str, Any],
    json_path: str | Path,
    markdown_path: str | Path,
) -> tuple[Path, Path]:
    """Write ownership JSON and Markdown artifacts."""

    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    write_json(json_out, payload)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(ownership_markdown(payload), encoding="utf-8")
    return json_out, markdown_out
