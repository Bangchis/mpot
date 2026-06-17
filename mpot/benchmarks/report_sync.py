"""Check that living-report file references still point to real files.

The report is useful only if its code/file names match the repository. This
module scans selected Markdown files, extracts path-like references, ignores
template placeholders such as ``<label>``, and reports missing concrete paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import re
import time

from mpot.benchmarks.artifacts import write_json


DEFAULT_SYNC_DOCS = [
    "report/REPORT_DRAFT.md",
    "report/REPORT_POLISHED_DRAFT.md",
    "report/REPORT_CHECKLIST.md",
    "report/BENCHMARK_PLAN.md",
    "docs/mpot_algorithm_overview.md",
    "docs/mpot_parallel_algorithm_spec.md",
    "docs/mpi_mpot_project_plan.md",
    "docs/team_ownership.md",
]

PATH_RE = re.compile(
    r"(?P<path>(?:\./)?(?:requirements-local\.txt|"
    r"(?:configs|docs|mpot|report|results|scripts|submission|tests)/[A-Za-z0-9_./<>*{}-]+))"
)
PLACEHOLDER_MARKERS = ("<", ">", "{", "}", "*")
TRAILING_PUNCTUATION = ".,;:)"


@dataclass
class ReportReference:
    """One path-like reference found in a Markdown file."""

    document: str
    line: int
    raw: str
    path: str
    exists: bool
    ignored: bool
    reason: str

    def to_json(self) -> dict[str, Any]:
        return {
            "document": self.document,
            "line": self.line,
            "raw": self.raw,
            "path": self.path,
            "exists": self.exists,
            "ignored": self.ignored,
            "reason": self.reason,
        }


def _clean_path(raw: str) -> str:
    path = raw.strip().strip("`'\"")
    while path and path[-1] in TRAILING_PUNCTUATION:
        path = path[:-1]
    return path[2:] if path.startswith("./") else path


def _should_ignore(path: str, exists: bool = False) -> str:
    if not path:
        return "empty"
    if any(marker in path for marker in PLACEHOLDER_MARKERS):
        return "template placeholder"
    if path.endswith("/"):
        return ""
    suffix = Path(path).suffix
    if not suffix and not exists:
        return "not a concrete file or directory"
    if not suffix and "/" not in path and path != "requirements-local.txt":
        return "not a file-like reference"
    return ""


def _extract_paths(line: str) -> list[str]:
    return [_clean_path(match.group("path")) for match in PATH_RE.finditer(line)]


def discover_report_references(
    *,
    repo_root: str | Path = ".",
    documents: list[str | Path] | None = None,
) -> list[ReportReference]:
    """Return path references discovered in living report Markdown files."""

    root = Path(repo_root).resolve()
    docs = [Path(path) for path in (documents or DEFAULT_SYNC_DOCS)]
    references: list[ReportReference] = []
    seen: set[tuple[str, int, str]] = set()

    for document in docs:
        doc_path = document if document.is_absolute() else root / document
        relative_doc = document.as_posix() if not document.is_absolute() else str(document)
        if not doc_path.exists():
            references.append(
                ReportReference(relative_doc, 0, relative_doc, relative_doc, False, False, "document is missing")
            )
            continue
        for line_number, line in enumerate(doc_path.read_text(encoding="utf-8").splitlines(), start=1):
            for raw_path in _extract_paths(line):
                key = (relative_doc, line_number, raw_path)
                if key in seen:
                    continue
                seen.add(key)
                candidate = root / raw_path
                exists = candidate.exists()
                reason = _should_ignore(raw_path, exists=exists)
                references.append(
                    ReportReference(
                        document=relative_doc,
                        line=line_number,
                        raw=raw_path,
                        path=raw_path,
                        exists=exists,
                        ignored=bool(reason),
                        reason=reason,
                    )
                )
    return references


def build_report_sync(
    *,
    repo_root: str | Path = ".",
    documents: list[str | Path] | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """Build a JSON-friendly report-sync payload."""

    refs = discover_report_references(repo_root=repo_root, documents=documents)
    checked = [ref for ref in refs if not ref.ignored]
    missing = [ref for ref in checked if not ref.exists]
    return {
        "label": label or "",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "repo_root": str(Path(repo_root).resolve()),
        "passed": not missing,
        "num_references": len(refs),
        "num_checked": len(checked),
        "num_ignored": len(refs) - len(checked),
        "num_missing": len(missing),
        "references": [ref.to_json() for ref in refs],
        "missing": [ref.to_json() for ref in missing],
        "note": "Placeholder paths containing <...>, {...}, or * are ignored.",
    }


def report_sync_markdown(payload: dict[str, Any]) -> str:
    """Render report-sync payload as Markdown."""

    verdict = "PASS" if payload.get("passed") else "FAIL"
    lines = [
        "# Report Sync Check",
        "",
        "This file checks whether concrete file paths mentioned by the living",
        "report and project docs still exist in the repository.",
        "",
        f"- label: `{payload.get('label', '')}`",
        f"- verdict: **{verdict}**",
        f"- checked references: `{payload.get('num_checked')}`",
        f"- ignored placeholders: `{payload.get('num_ignored')}`",
        f"- missing references: `{payload.get('num_missing')}`",
        "",
    ]
    missing = payload.get("missing", [])
    if missing:
        lines.extend(["## Missing Concrete Paths", "", "| document | line | path |", "|---|---:|---|"])
        for item in missing:
            lines.append(f"| `{item['document']}` | {item['line']} | `{item['path']}` |")
        lines.append("")
    lines.extend(["## Checked Paths", "", "| status | document | line | path |", "|---|---|---:|---|"])
    for item in payload.get("references", []):
        if item.get("ignored"):
            continue
        status = "PASS" if item.get("exists") else "FAIL"
        lines.append(f"| {status} | `{item['document']}` | {item['line']} | `{item['path']}` |")
    lines.append("")
    return "\n".join(lines)


def write_report_sync(
    *,
    payload: dict[str, Any],
    json_path: str | Path,
    markdown_path: str | Path,
) -> tuple[Path, Path]:
    """Write report-sync JSON and Markdown artifacts."""

    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    write_json(json_out, payload)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(report_sync_markdown(payload), encoding="utf-8")
    return json_out, markdown_out
