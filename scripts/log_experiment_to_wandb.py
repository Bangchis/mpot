#!/usr/bin/env python3
"""Log a whole benchmark label to W&B as a comparable experiment group.

Each completed run under results/<run_id>/ remains a separate W&B run so
runtime, speedup, and quality can be compared naturally. Optional report-level
figures are logged to one extra "experiment index" run.
"""

from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import replace
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.cli import add_wandb_args
from mpot.wandb_logger import (
    OptionalWandbLogger,
    WandbSettings,
    _clean_tag,
    build_experiment_manifest,
    discover_experiment_run_dirs,
    discover_run_files,
    log_run_directory_to_wandb,
    run_summary_from_dir,
    write_experiment_manifest,
    wandb_settings_from_namespace,
)


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="Experiment label to match, e.g. final_macbook_air_2d.")
    parser.add_argument("--results-dir", default="results", help="Directory containing completed run folders.")
    parser.add_argument(
        "--include-mode",
        action="append",
        default=[],
        choices=["serial", "mpi"],
        help="Optional run mode filter. Repeat to include multiple modes. Defaults to all modes.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of matched runs to log.")
    parser.add_argument("--dry-run", action="store_true", help="Only list matched runs and write the batch manifest.")
    parser.add_argument(
        "--extra-path",
        action="append",
        default=[],
        help="Extra file to attach to every matched run. Use sparingly to avoid duplication.",
    )
    parser.add_argument(
        "--report-path",
        action="append",
        default=[],
        help="Report-level PNG/GIF/CSV/JSON file to attach to the experiment index run. Can be repeated.",
    )
    parser.add_argument(
        "--skip-index-run",
        action="store_true",
        help="Do not create the report-level experiment index W&B run.",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Output JSON manifest path. Defaults to report/WANDB_EXPERIMENT_<label>.json.",
    )
    parser.add_argument(
        "--markdown",
        default=None,
        help="Output Markdown manifest path. Defaults to report/WANDB_EXPERIMENT_<label>.md.",
    )
    add_wandb_args(parser)
    return parser.parse_args()


def _default_manifest_paths(label: str) -> tuple[Path, Path]:
    slug = _clean_tag(label)
    return Path("report") / f"WANDB_EXPERIMENT_{slug}.json", Path("report") / f"WANDB_EXPERIMENT_{slug}.md"


def _existing_paths(raw_paths: list[str]) -> list[Path]:
    paths = []
    for raw in raw_paths:
        path = Path(raw)
        if not path.exists():
            print(f"[wandb] warning: extra/report path does not exist and will be skipped: {path}", file=sys.stderr)
            continue
        paths.append(path)
    return paths


def _experiment_index_summary(label: str, run_dirs: list[Path]) -> dict[str, object]:
    summaries = [run_summary_from_dir(run_dir) for run_dir in run_dirs]
    modes = sorted({str(summary.get("mode", "unknown")) for summary in summaries})
    process_counts = sorted({int(summary.get("size", 1) or 1) for summary in summaries})
    input_sizes = sorted({int(summary.get("total_tasks", 0) or 0) for summary in summaries})
    return {
        "run_id": f"wandb-experiment-{_clean_tag(label)}",
        "mode": "experiment-index",
        "experiment_name": label,
        "total_tasks": sum(int(summary.get("total_tasks", 0) or 0) for summary in summaries),
        "size": max(process_counts) if process_counts else 1,
        "num_task_results": len(summaries),
        "parallel_backend": "mixed",
        "mapping": "cyclic",
        "config": {"experiment_name": label, "device": "cpu"},
        "wandb_index": {
            "label": label,
            "num_runs": len(run_dirs),
            "modes": modes,
            "process_counts": process_counts,
            "input_sizes": input_sizes,
        },
    }


def _log_experiment_index(
    *,
    label: str,
    run_dirs: list[Path],
    settings: WandbSettings,
    report_paths: list[Path],
) -> str:
    if not settings.enabled or not report_paths:
        return "skipped"
    summary = _experiment_index_summary(label, run_dirs)
    index_settings = replace(
        settings,
        group=settings.group or _clean_tag(label),
        name=settings.name or str(summary["run_id"]),
        job_type=settings.job_type or "experiment-index",
        tags=list(dict.fromkeys([*settings.tags, f"experiment:{label}", "experiment-index"])),
    )
    files = discover_run_files(ROOT, extra_paths=report_paths)
    logger = OptionalWandbLogger(settings=index_settings, summary=summary)
    if not logger.enabled:
        return "disabled"
    metrics = {
        "experiment/num_runs": len(run_dirs),
        "experiment/num_report_paths": len(report_paths),
    }
    index = summary.get("wandb_index", {})
    if isinstance(index, dict):
        metrics["experiment/num_input_sizes"] = len(index.get("input_sizes", []))
        metrics["experiment/num_process_counts"] = len(index.get("process_counts", []))
    logger.log_metrics(metrics)
    if index_settings.log_media:
        logger.log_images(files["images"])
        logger.log_animations(files["animations"])
    if index_settings.log_tables:
        logger.log_tables([path for path in files["artifacts"] if path.suffix.lower() == ".csv"])
    if index_settings.log_artifact:
        logger.log_artifact_bundle(ROOT, files["artifacts"] + files["images"] + files["animations"])
    logger.finish()
    return "logged"


def main() -> int:
    args = parse_args()
    modes = set(args.include_mode) if args.include_mode else None
    run_dirs = discover_experiment_run_dirs(args.results_dir, label=args.label, modes=modes)
    if args.limit is not None:
        run_dirs = run_dirs[: args.limit]

    manifest_json_default, manifest_md_default = _default_manifest_paths(args.label)
    manifest_json = Path(args.manifest) if args.manifest else manifest_json_default
    manifest_md = Path(args.markdown) if args.markdown else manifest_md_default
    report_paths = _existing_paths(args.report_path)
    extra_paths = _existing_paths(args.extra_path)
    settings = wandb_settings_from_namespace(args)

    print(f"label: {args.label}")
    print(f"matched runs: {len(run_dirs)}")
    for run_dir in run_dirs:
        summary = run_summary_from_dir(run_dir)
        print(
            f"- {summary.get('run_id', run_dir.name)} "
            f"mode={summary.get('mode')} N={summary.get('total_tasks')} P={summary.get('size')}"
        )

    run_outcomes: list[dict[str, object]] = []
    index_status = "skipped"
    if not args.dry_run:
        if not settings.enabled:
            print("W&B disabled. Add --use-wandb, or use --dry-run to inspect matches.", file=sys.stderr)
            return 2
        for run_dir in run_dirs:
            summary = run_summary_from_dir(run_dir)
            per_run_settings = replace(
                settings,
                group=settings.group or _clean_tag(args.label),
                name=settings.name or str(summary.get("run_id") or run_dir.name),
                job_type=settings.job_type or str(summary.get("mode", "benchmark")),
                tags=list(dict.fromkeys([*settings.tags, f"experiment:{args.label}"])),
            )
            run_outcomes.append(
                log_run_directory_to_wandb(
                    run_dir,
                    settings=per_run_settings,
                    extra_paths=extra_paths,
                )
            )
        if not args.skip_index_run:
            index_status = _log_experiment_index(
                label=args.label,
                run_dirs=run_dirs,
                settings=settings,
                report_paths=report_paths,
            )

    payload = build_experiment_manifest(
        label=args.label,
        settings=replace(settings, group=settings.group or _clean_tag(args.label)),
        run_outcomes=run_outcomes,
        matched_run_dirs=run_dirs,
        report_paths=report_paths,
        dry_run=args.dry_run,
        index_status=index_status,
    )
    json_out, markdown_out = write_experiment_manifest(payload, json_path=manifest_json, markdown_path=manifest_md)
    print(f"manifest_json: {json_out}")
    if markdown_out:
        print(f"manifest_markdown: {markdown_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
