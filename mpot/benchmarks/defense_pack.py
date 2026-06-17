"""Generate a compact defense guide for each team member.

The ownership report proves that the code split is balanced. This module adds a
human-readable study guide: which files each member should open, which
functions/classes matter, which demo commands to run, and which questions to
practice.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import ast
import json
import time

from mpot.benchmarks.artifacts import write_json
from mpot.benchmarks.ownership import DEFAULT_MEMBER_FILES, count_file_lines


DEFAULT_MAX_SYMBOLS_PER_FILE = 12

MEMBER_DEMO_COMMANDS: dict[str, list[str]] = {
    "Member A": [
        "python scripts/run_serial.py --config configs/local_smoke.json",
    ],
    "Member B": [
        "python scripts/run_serial.py --config configs/local_smoke.json",
        "python scripts/compare_serial_mpi.py --serial results/serial-mini_sweep-N2 --mpi results/mpi-mini_sweep-N2-P2",
    ],
    "Member C": [
        "mpirun -np 4 python scripts/run_mpi.py --config configs/local_smoke.json",
        "python scripts/analyze_communication.py --run-dir results/mpi-mini_sweep-N2-P2 --output results/communication-mini_sweep-N2-P2.json --markdown report/COMMUNICATION_mini_sweep.md --label mini_sweep",
    ],
    "Member D": [
        "python scripts/generate_ownership_report.py",
        "python scripts/analyze_granularity.py --run-dir results/mpi-mini_sweep-N2-P2 --output results/granularity-mini_sweep-N2-P2.json --markdown report/GRANULARITY_mini_sweep.md --label mini_sweep",
        "python scripts/plot_results.py --results results --output report/figures --label mini_sweep --input-size 2",
    ],
}


MEMBER_DEFENSE_QUESTIONS: dict[str, list[str]] = {
    "Member A": [
        "What is the robot state in this benchmark?",
        "How are circular obstacles represented?",
        "Which terms are included in the trajectory cost?",
        "Why is a 2D point robot acceptable for this parallel-programming demo?",
    ],
    "Member B": [
        "What is one planning task?",
        "Why do we need a serial baseline?",
        "How does deterministic best-result reduction work?",
        "What does task_comparison.csv prove?",
    ],
    "Member C": [
        "What level of parallelism does the project use?",
        "How does task i -> rank i mod P work?",
        "Which blocking MPI collectives are used?",
        "What do comm_events.csv and task_assignment.csv prove?",
    ],
    "Member D": [
        "How is speedup calculated?",
        "How do we separate runtime with and without communication?",
        "How is the 25 percent load-imbalance threshold checked?",
        "Which tables and figures are generated from real artifacts?",
    ],
}


@dataclass
class SourceSymbol:
    """One top-level Python symbol relevant for code defense."""

    name: str
    kind: str
    line: int
    doc: str

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "line": self.line,
            "doc": self.doc,
        }


def _first_doc_line(node: ast.AST) -> str:
    doc = ast.get_docstring(node) or ""
    return doc.strip().splitlines()[0] if doc.strip() else ""


def _python_symbols(path: Path, max_symbols: int) -> list[SourceSymbol]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []

    symbols: list[SourceSymbol] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append(SourceSymbol(node.name, "class", int(node.lineno), _first_doc_line(node)))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "async function" if isinstance(node, ast.AsyncFunctionDef) else "function"
            symbols.append(SourceSymbol(node.name, kind, int(node.lineno), _first_doc_line(node)))
    return symbols[:max_symbols]


def _json_keys(path: Path, max_keys: int) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, dict):
        return [str(key) for key in list(payload.keys())[:max_keys]]
    return []


def summarize_defense_file(repo_root: str | Path, file_path: str | Path, *, max_symbols: int) -> dict[str, Any]:
    """Summarize one primary defense file."""

    root = Path(repo_root).resolve()
    path = Path(file_path)
    absolute = (path if path.is_absolute() else root / path).resolve()
    count = count_file_lines(root, absolute)
    suffix = absolute.suffix
    symbols = _python_symbols(absolute, max_symbols) if absolute.exists() and suffix == ".py" else []
    config_keys = _json_keys(absolute, max_symbols) if absolute.exists() and suffix == ".json" else []
    return {
        "path": count.path,
        "exists": count.exists,
        "suffix": suffix,
        "meaningful_lines": count.meaningful_lines,
        "symbols": [symbol.to_json() for symbol in symbols],
        "config_keys": config_keys,
    }


def build_defense_guide(
    *,
    repo_root: str | Path = ".",
    member_files: dict[str, dict[str, Any]] | None = None,
    max_symbols_per_file: int = DEFAULT_MAX_SYMBOLS_PER_FILE,
) -> dict[str, Any]:
    """Build a JSON-friendly member defense guide."""

    root = Path(repo_root).resolve()
    spec = member_files or DEFAULT_MEMBER_FILES
    members: list[dict[str, Any]] = []

    for member, details in spec.items():
        files = [
            summarize_defense_file(root, path, max_symbols=max_symbols_per_file)
            for path in details.get("files", [])
        ]
        members.append(
            {
                "member": member,
                "area": str(details.get("area", "")),
                "meaningful_lines": sum(file_row["meaningful_lines"] for file_row in files),
                "files": files,
                "demo_commands": MEMBER_DEMO_COMMANDS.get(member, []),
                "practice_questions": MEMBER_DEFENSE_QUESTIONS.get(member, []),
            }
        )

    missing_files = [
        {"member": member["member"], "path": file_row["path"]}
        for member in members
        for file_row in member["files"]
        if not file_row["exists"]
    ]
    return {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "repo_root": str(root),
        "num_members": len(members),
        "max_symbols_per_file": int(max_symbols_per_file),
        "passed": len(members) == 4 and not missing_files,
        "missing_files": missing_files,
        "members": members,
        "note": "Generated from the compact primary defense set. Shared support modules are intentionally summarized elsewhere.",
    }


def _symbol_text(file_row: dict[str, Any]) -> str:
    if file_row["symbols"]:
        return ", ".join(f"{item['name']}:{item['line']}" for item in file_row["symbols"])
    if file_row["config_keys"]:
        return "keys: " + ", ".join(file_row["config_keys"])
    return ""


def defense_guide_markdown(payload: dict[str, Any]) -> str:
    """Render the member defense guide as Markdown."""

    verdict = "PASS" if payload.get("passed") else "FAIL"
    lines = [
        "# Member Defense Guide",
        "",
        "This generated guide is meant for studying, not for inflating the report.",
        "Each member should focus on their primary defense files and demo commands.",
        "",
        f"- created_at: `{payload['created_at']}`",
        f"- verdict: **{verdict}**",
        f"- members: `{payload['num_members']}`",
        "",
    ]

    for member in payload["members"]:
        lines.extend(
            [
                f"## {member['member']}: {member['area']}",
                "",
                f"- meaningful_lines: `{member['meaningful_lines']}`",
                "",
                "### Files",
                "",
                "| file | meaningful lines | key symbols / config keys |",
                "|---|---:|---|",
            ]
        )
        for file_row in member["files"]:
            lines.append(
                f"| `{file_row['path']}` | {file_row['meaningful_lines']} | {_symbol_text(file_row)} |"
            )
        lines.extend(["", "### Demo Commands", ""])
        for command in member["demo_commands"]:
            lines.extend(["```bash", command, "```", ""])
        lines.extend(["### Practice Questions", ""])
        for index, question in enumerate(member["practice_questions"], start=1):
            lines.append(f"{index}. {question}")
        lines.append("")

    lines.extend([payload["note"], ""])
    return "\n".join(lines)


def write_defense_guide(
    *,
    payload: dict[str, Any],
    json_path: str | Path,
    markdown_path: str | Path,
) -> tuple[Path, Path]:
    """Write member defense guide JSON and Markdown artifacts."""

    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    write_json(json_out, payload)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(defense_guide_markdown(payload), encoding="utf-8")
    return json_out, markdown_out
