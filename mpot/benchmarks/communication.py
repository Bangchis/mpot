"""Communication strategy analysis from MPI communication event artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import csv

from mpot.benchmarks.artifacts import read_json, write_json


EXPECTED_COLLECTIVES = {"bcast", "scatter", "gather"}


def _read_comm_events(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _as_float(value: Any) -> float:
    text = str(value).strip()
    return 0.0 if text == "" else float(text)


def _as_int_or_none(value: Any) -> int | None:
    text = str(value).strip()
    return None if text == "" else int(text)


def analyze_communication(run_dir: str | Path) -> dict[str, Any]:
    """Analyze blocking collectives recorded by one MPI run."""

    root = Path(run_dir)
    summary = read_json(root / "summary.json")
    events_path = root / "comm_events.csv"
    raw_events = _read_comm_events(events_path)
    if not raw_events:
        raise ValueError(f"No communication rows found in {events_path}.")

    rank_totals: dict[int, dict[str, Any]] = {}
    event_groups: dict[str, list[dict[str, str]]] = {}
    collective_groups: dict[str, list[dict[str, str]]] = {}
    for row in raw_events:
        rank = int(row["rank"])
        duration = _as_float(row["duration_s"])
        rank_totals.setdefault(rank, {"rank": rank, "num_events": 0, "total_duration_s": 0.0})
        rank_totals[rank]["num_events"] += 1
        rank_totals[rank]["total_duration_s"] += duration
        event_groups.setdefault(row["event"], []).append(row)
        collective_groups.setdefault(row["collective"], []).append(row)

    event_rows = []
    for event, rows in sorted(event_groups.items()):
        durations = [_as_float(row["duration_s"]) for row in rows]
        payloads = [_as_int_or_none(row.get("payload_count", "")) for row in rows]
        event_rows.append(
            {
                "event": event,
                "collective": rows[0]["collective"],
                "root": int(rows[0]["root"]),
                "blocking": all(_as_bool(row["blocking"]) for row in rows),
                "num_rank_rows": len(rows),
                "max_duration_s": max(durations),
                "sum_duration_s": sum(durations),
                "max_payload_count": max([value for value in payloads if value is not None], default=None),
            }
        )

    collective_rows = []
    for collective, rows in sorted(collective_groups.items()):
        durations = [_as_float(row["duration_s"]) for row in rows]
        collective_rows.append(
            {
                "collective": collective,
                "num_events": len(rows),
                "total_duration_s": sum(durations),
                "max_event_duration_s": max(durations),
            }
        )

    observed_collectives = set(collective_groups)
    return {
        "run_dir": str(root),
        "comm_events_csv": str(events_path),
        "run_id": summary.get("run_id", root.name),
        "input_size_n": int(summary["total_tasks"]),
        "processes": int(summary["size"]),
        "topology": "SPMD with rank 0 coordinator, logical star topology",
        "communication_strategy": "blocking collectives: bcast, scatter, gather",
        "all_events_blocking": all(_as_bool(row["blocking"]) for row in raw_events),
        "observed_collectives": sorted(observed_collectives),
        "has_expected_collectives": EXPECTED_COLLECTIVES.issubset(observed_collectives),
        "num_event_rows": len(raw_events),
        "rank_rows": [rank_totals[rank] for rank in sorted(rank_totals)],
        "event_rows": event_rows,
        "collective_rows": collective_rows,
        "note": "Derived only from real comm_events.csv and summary.json artifacts.",
    }


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def communication_markdown(payload: dict[str, Any]) -> str:
    """Render communication analysis as Markdown."""

    lines = [
        "# Communication Strategy Analysis",
        "",
        "This analysis is generated from real MPI communication event artifacts.",
        "",
        "## Summary",
        "",
        f"- run_id: `{payload['run_id']}`",
        f"- input_size_n: `{payload['input_size_n']}`",
        f"- processes: `{payload['processes']}`",
        f"- topology: `{payload['topology']}`",
        f"- strategy: `{payload['communication_strategy']}`",
        f"- all_events_blocking: `{_fmt(payload['all_events_blocking'])}`",
        f"- observed_collectives: `{', '.join(payload['observed_collectives'])}`",
        f"- has_expected_collectives: `{_fmt(payload['has_expected_collectives'])}`",
        "",
        "## Event Groups",
        "",
        "| event | collective | root | blocking | rank_rows | max_duration_s | sum_duration_s | max_payload_count |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["event_rows"]:
        lines.append(
            "| {event} | {collective} | {root} | {blocking} | {rows} | {max_d} | {sum_d} | {payload} |".format(
                event=row["event"],
                collective=row["collective"],
                root=row["root"],
                blocking=_fmt(row["blocking"]),
                rows=row["num_rank_rows"],
                max_d=_fmt(row["max_duration_s"]),
                sum_d=_fmt(row["sum_duration_s"]),
                payload=_fmt(row["max_payload_count"]),
            )
        )

    lines.extend(
        [
            "",
            "## Per-Rank Communication Totals",
            "",
            "| rank | num_events | total_duration_s |",
            "|---:|---:|---:|",
        ]
    )
    for row in payload["rank_rows"]:
        lines.append(f"| {row['rank']} | {row['num_events']} | {_fmt(row['total_duration_s'])} |")
    lines.extend(["", payload["note"], ""])
    return "\n".join(lines)


def write_communication_analysis(
    *,
    payload: dict[str, Any],
    json_path: str | Path,
    markdown_path: str | Path,
) -> tuple[Path, Path]:
    """Write communication analysis JSON and Markdown files."""

    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    write_json(json_out, payload)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(communication_markdown(payload), encoding="utf-8")
    return json_out, markdown_out
