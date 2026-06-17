"""Optional W&B logging for MPOT benchmark runs.

Local CSV/JSON/PNG artifacts are always the source of truth for the course
project. This module adds a thin optional W&B layer on top so runs can be
compared visually without making W&B a required dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import csv
import json
import time


DEFAULT_WANDB_PROJECT = "distributed-mpot-course"
STANDARD_ARTIFACT_FILENAMES = [
    "summary.json",
    "config.json",
    "task_results.csv",
    "task_results.json",
    "rank_timings.csv",
    "comm_events.csv",
    "task_assignment.csv",
    "best_trajectory.npy",
]
STANDARD_IMAGE_FILENAMES = [
    "best_path.png",
    "cost_by_task.png",
    "rank_time_breakdown.png",
]
STANDARD_ANIMATION_SUFFIXES = {".gif", ".mp4", ".webm"}


@dataclass
class WandbSettings:
    """User-facing W&B settings passed from CLI scripts."""

    enabled: bool = False
    project: str = DEFAULT_WANDB_PROJECT
    entity: str | None = None
    group: str | None = None
    job_type: str | None = None
    mode: str | None = None
    name: str | None = None
    tags: list[str] = field(default_factory=list)
    notes: str | None = None
    max_table_rows: int = 5000
    log_artifact: bool = True
    log_tables: bool = True
    log_media: bool = True


def wandb_settings_from_namespace(args: Any) -> WandbSettings:
    """Build settings from argparse args while tolerating older callers."""

    return WandbSettings(
        enabled=bool(getattr(args, "use_wandb", False)),
        project=getattr(args, "wandb_project", None) or DEFAULT_WANDB_PROJECT,
        entity=getattr(args, "wandb_entity", None),
        group=getattr(args, "wandb_group", None),
        job_type=getattr(args, "wandb_job_type", None),
        mode=getattr(args, "wandb_mode", None),
        name=getattr(args, "wandb_name", None),
        tags=list(getattr(args, "wandb_tag", None) or []),
        notes=getattr(args, "wandb_notes", None),
        max_table_rows=int(getattr(args, "wandb_max_table_rows", 5000) or 5000),
        log_artifact=not bool(getattr(args, "wandb_no_artifact", False)),
        log_tables=not bool(getattr(args, "wandb_no_tables", False)),
        log_media=not bool(getattr(args, "wandb_no_media", False)),
    )


def load_json(path: str | Path) -> dict[str, Any]:
    """Read a JSON object from disk."""

    with Path(path).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def run_summary_from_dir(run_dir: str | Path) -> dict[str, Any]:
    """Load the standard summary for one run directory."""

    return load_json(Path(run_dir) / "summary.json")


def _clean_tag(value: Any) -> str:
    text = str(value).strip().replace(" ", "_")
    return text.replace("/", "_")


def default_group(summary: dict[str, Any]) -> str:
    """Return a useful W&B group name for comparisons."""

    config = summary.get("config") if isinstance(summary.get("config"), dict) else {}
    experiment = summary.get("experiment_name") or config.get("experiment_name")
    if experiment:
        return _clean_tag(experiment)
    return _clean_tag(summary.get("run_id", "mpot"))


def build_wandb_tags(summary: dict[str, Any], extra_tags: list[str] | None = None) -> list[str]:
    """Build stable tags so W&B runs are easy to filter."""

    tags = [
        "mpot",
        "course-project",
        f"mode:{summary.get('mode', 'unknown')}",
        f"N:{summary.get('total_tasks', 'unknown')}",
        f"P:{summary.get('size', 'unknown')}",
    ]
    if summary.get("parallel_backend"):
        tags.append(f"backend:{summary['parallel_backend']}")
    if summary.get("mapping"):
        tags.append(f"mapping:{summary['mapping']}")
    if summary.get("config_hash"):
        tags.append(f"config:{summary['config_hash']}")
    tags.extend(extra_tags or [])
    return list(dict.fromkeys(_clean_tag(tag) for tag in tags if tag))


def summary_to_wandb_config(summary: dict[str, Any]) -> dict[str, Any]:
    """Return compact W&B config fields from a run summary."""

    config = summary.get("config") if isinstance(summary.get("config"), dict) else {}
    optimizer = config.get("optimizer", {}) if isinstance(config.get("optimizer"), dict) else {}
    problem = config.get("problem", {}) if isinstance(config.get("problem"), dict) else {}
    return {
        "run_id": summary.get("run_id"),
        "mode": summary.get("mode"),
        "experiment_name": summary.get("experiment_name") or config.get("experiment_name"),
        "config_hash": summary.get("config_hash"),
        "parallel_backend": summary.get("parallel_backend"),
        "mapping": summary.get("mapping"),
        "total_tasks": summary.get("total_tasks"),
        "processes": summary.get("size"),
        "device": summary.get("device") or config.get("device"),
        "base_seed": config.get("base_seed"),
        "traj_len": problem.get("traj_len"),
        "num_obstacles": len(problem.get("obstacles", [])) if isinstance(problem.get("obstacles"), list) else None,
        "num_particles": optimizer.get("num_particles"),
        "num_probe": optimizer.get("num_probe"),
        "max_outer_iters": optimizer.get("max_outer_iters"),
        "max_inner_iters": optimizer.get("max_inner_iters"),
    }


def summary_to_wandb_metrics(summary: dict[str, Any]) -> dict[str, float | int | bool]:
    """Extract scalar metrics with readable W&B panel names."""

    metrics: dict[str, float | int | bool] = {}
    scalar_keys = {
        "solution/best_cost": "best_cost",
        "solution/best_collision_fraction": "best_collision_fraction",
        "runtime/total_time_s": "total_time_s",
        "runtime/with_communication_s": "runtime_with_communication_s",
        "runtime/without_communication_s": "runtime_without_communication_s",
        "tasks/total": "total_tasks",
        "tasks/results": "num_task_results",
        "mpi/processes": "size",
        "mpi/communication_events_count": "communication_events_count",
    }
    for metric_name, summary_key in scalar_keys.items():
        value = summary.get(summary_key)
        if isinstance(value, (int, float, bool)):
            metrics[metric_name] = value
    if isinstance(summary.get("runtime_with_communication_s"), (int, float)) and isinstance(
        summary.get("runtime_without_communication_s"), (int, float)
    ):
        metrics["runtime/communication_overhead_s"] = float(summary["runtime_with_communication_s"]) - float(
            summary["runtime_without_communication_s"]
        )
    load_balance = summary.get("load_balance")
    if isinstance(load_balance, dict):
        for key, value in load_balance.items():
            if isinstance(value, (int, float, bool)):
                metrics[f"load_balance/{key}"] = value
    problem = summary.get("problem")
    if isinstance(problem, dict):
        obstacles = problem.get("obstacles")
        if isinstance(obstacles, list):
            metrics["problem/num_obstacles"] = len(obstacles)
    return metrics


def discover_run_files(run_dir: str | Path, extra_paths: list[str | Path] | None = None) -> dict[str, list[Path]]:
    """Discover standard files to upload for one run."""

    root = Path(run_dir)
    artifacts = [root / name for name in STANDARD_ARTIFACT_FILENAMES]
    images = [root / name for name in STANDARD_IMAGE_FILENAMES]
    animations = [path for path in root.iterdir() if path.suffix.lower() in STANDARD_ANIMATION_SUFFIXES] if root.exists() else []
    for raw in extra_paths or []:
        path = Path(raw)
        if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            images.append(path)
        elif path.suffix.lower() in STANDARD_ANIMATION_SUFFIXES:
            animations.append(path)
        else:
            artifacts.append(path)
    return {
        "artifacts": sorted({path for path in artifacts if path.exists()}),
        "images": sorted({path for path in images if path.exists()}),
        "animations": sorted({path for path in animations if path.exists()}),
    }


def read_csv_rows(path: str | Path, max_rows: int) -> tuple[list[str], list[list[str]], bool]:
    """Read a bounded number of CSV rows for W&B tables."""

    with Path(path).open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            columns = next(reader)
        except StopIteration:
            return [], [], False
        rows: list[list[str]] = []
        truncated = False
        for index, row in enumerate(reader):
            if index >= max_rows:
                truncated = True
                break
            rows.append(row)
    return columns, rows, truncated


def _normalized_label(value: Any) -> str:
    """Normalize a run label for forgiving command-line filtering."""

    return _clean_tag(value).lower()


def summary_label_values(summary: dict[str, Any], run_dir: str | Path) -> list[str]:
    """Return human-facing labels that can identify a completed run."""

    config = summary.get("config") if isinstance(summary.get("config"), dict) else {}
    values = [
        Path(run_dir).name,
        summary.get("run_id"),
        summary.get("experiment_name"),
        config.get("experiment_name"),
        default_group(summary),
    ]
    return [str(value) for value in values if value]


def summary_matches_label(summary: dict[str, Any], run_dir: str | Path, label: str | None) -> bool:
    """Return True when a run belongs to an experiment label.

    The match is substring-based on run id, experiment name, directory name, and
    default group. This keeps the uploader convenient for labels such as
    ``final_macbook_air_2d`` that appear in several generated run ids.
    """

    if not label:
        return True
    needle = _normalized_label(label)
    return any(needle in _normalized_label(value) for value in summary_label_values(summary, run_dir))


def discover_experiment_run_dirs(
    results_dir: str | Path,
    *,
    label: str | None = None,
    modes: set[str] | None = None,
) -> list[Path]:
    """Find completed run directories that should be logged as one experiment."""

    root = Path(results_dir)
    matches: list[tuple[str, Path]] = []
    if not root.exists():
        return []
    for summary_path in sorted(root.glob("*/summary.json")):
        run_dir = summary_path.parent
        try:
            summary = load_json(summary_path)
        except Exception:
            continue
        mode = str(summary.get("mode", "")).strip()
        if modes and mode not in modes:
            continue
        if summary_matches_label(summary, run_dir, label):
            run_id = str(summary.get("run_id") or run_dir.name)
            matches.append((run_id, run_dir))
    return [run_dir for _, run_dir in sorted(matches)]


def build_experiment_manifest(
    *,
    label: str,
    settings: WandbSettings,
    run_outcomes: list[dict[str, Any]],
    matched_run_dirs: list[str | Path],
    report_paths: list[str | Path] | None = None,
    dry_run: bool = False,
    index_status: str = "skipped",
) -> dict[str, Any]:
    """Build a local manifest for a W&B experiment upload attempt."""

    return {
        "label": label,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "dry_run": bool(dry_run),
        "project": settings.project,
        "entity": settings.entity,
        "group": settings.group or _clean_tag(label),
        "mode": settings.mode,
        "index_status": index_status,
        "num_matched_runs": len(matched_run_dirs),
        "num_logged_runs": sum(1 for outcome in run_outcomes if outcome.get("status") == "logged"),
        "matched_run_dirs": [str(Path(path)) for path in matched_run_dirs],
        "report_paths": [str(Path(path)) for path in (report_paths or [])],
        "run_outcomes": run_outcomes,
        "note": "Local CSV/JSON/PNG artifacts remain the source of truth; W&B is an optional dashboard layer.",
    }


def experiment_manifest_markdown(payload: dict[str, Any]) -> str:
    """Render a W&B experiment manifest as Markdown for quick inspection."""

    lines = [
        "# W&B Experiment Upload Manifest",
        "",
        f"- label: `{payload.get('label', '')}`",
        f"- project: `{payload.get('project', '')}`",
        f"- group: `{payload.get('group', '')}`",
        f"- mode: `{payload.get('mode') or 'default'}`",
        f"- dry run: `{payload.get('dry_run')}`",
        f"- matched runs: `{payload.get('num_matched_runs')}`",
        f"- logged runs: `{payload.get('num_logged_runs')}`",
        f"- index status: `{payload.get('index_status')}`",
        "",
    ]
    report_paths = payload.get("report_paths") or []
    if report_paths:
        lines.extend(["## Report-level Artifacts", "", "| path |", "|---|"])
        for path in report_paths:
            lines.append(f"| `{path}` |")
        lines.append("")
    lines.extend(["## Matched Runs", "", "| run id | status | manifest |", "|---|---|---|"])
    for outcome in payload.get("run_outcomes") or []:
        lines.append(
            f"| `{outcome.get('run_id', '')}` | `{outcome.get('status', '')}` | `{outcome.get('manifest', '')}` |"
        )
    if not payload.get("run_outcomes"):
        for run_dir in payload.get("matched_run_dirs") or []:
            lines.append(f"| `{Path(run_dir).name}` | `matched` |  |")
    lines.append("")
    return "\n".join(lines)


def write_experiment_manifest(
    payload: dict[str, Any],
    *,
    json_path: str | Path,
    markdown_path: str | Path | None = None,
) -> tuple[Path, Path | None]:
    """Write a W&B batch-upload manifest as JSON and optional Markdown."""

    json_out = Path(json_path)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    with json_out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
    markdown_out = None
    if markdown_path is not None:
        markdown_out = Path(markdown_path)
        markdown_out.parent.mkdir(parents=True, exist_ok=True)
        markdown_out.write_text(experiment_manifest_markdown(payload), encoding="utf-8")
    return json_out, markdown_out


class OptionalWandbLogger:
    """Small wrapper that keeps W&B optional and rank-0 friendly."""

    def __init__(self, settings: WandbSettings, summary: dict[str, Any]):
        self.settings = settings
        self.summary = summary
        self.enabled = bool(settings.enabled)
        self._wandb = None
        self._run = None
        if not self.enabled:
            return
        try:
            import wandb

            self._wandb = wandb
            init_kwargs: dict[str, Any] = {
                "project": settings.project,
                "entity": settings.entity,
                "name": settings.name or summary.get("run_id"),
                "group": settings.group or default_group(summary),
                "job_type": settings.job_type or str(summary.get("mode", "benchmark")),
                "tags": build_wandb_tags(summary, settings.tags),
                "notes": settings.notes,
                "config": summary_to_wandb_config(summary),
            }
            if settings.mode:
                init_kwargs["mode"] = settings.mode
            init_kwargs = {key: value for key, value in init_kwargs.items() if value is not None}
            self._run = wandb.init(**init_kwargs)
        except Exception as exc:
            print(f"[wandb] disabled: {exc}")
            self.enabled = False
            self._wandb = None
            self._run = None

    def log_metrics(self, metrics: dict[str, Any], step: int | None = None) -> None:
        if not self.enabled or self._run is None:
            return
        try:
            self._run.log(metrics, step=step)
            for key, value in metrics.items():
                if isinstance(value, (int, float, bool)):
                    self._run.summary[key] = value
        except Exception as exc:
            print(f"[wandb] metric logging skipped: {exc}")
            self.enabled = False

    def log_images(self, images: list[Path]) -> None:
        if not self.enabled or self._wandb is None:
            return
        payload = {}
        for path in images:
            try:
                payload[f"figures/{path.stem}"] = self._wandb.Image(str(path), caption=path.name)
            except Exception as exc:
                print(f"[wandb] image skipped {path}: {exc}")
        if payload:
            self.log_metrics(payload)

    def log_animations(self, animations: list[Path]) -> None:
        if not self.enabled or self._wandb is None:
            return
        payload = {}
        for path in animations:
            try:
                file_format = path.suffix.lower().lstrip(".") or None
                payload[f"animations/{path.stem}"] = self._wandb.Video(
                    str(path),
                    caption=path.name,
                    format=file_format,
                )
            except Exception as exc:
                print(f"[wandb] animation media skipped {path}: {exc}")
        if payload:
            self.log_metrics(payload)

    def log_tables(self, csv_paths: list[Path]) -> None:
        if not self.enabled or self._wandb is None:
            return
        payload = {}
        for path in csv_paths:
            try:
                columns, rows, truncated = read_csv_rows(path, self.settings.max_table_rows)
                if not columns:
                    continue
                table = self._wandb.Table(columns=columns)
                for row in rows:
                    table.add_data(*row)
                key = f"tables/{path.stem}"
                payload[key] = table
                if truncated and self._run is not None:
                    self._run.summary[f"{key}_truncated_at"] = self.settings.max_table_rows
            except Exception as exc:
                print(f"[wandb] table skipped {path}: {exc}")
        if payload:
            self.log_metrics(payload)

    def log_artifact_bundle(self, run_dir: str | Path, files: list[Path]) -> None:
        if not self.enabled or self._wandb is None or self._run is None:
            return
        root = Path(run_dir)
        name = str(self.summary.get("run_id", root.name)).replace("/", "_")
        try:
            artifact = self._wandb.Artifact(name=f"{name}-results", type="mpot-run")
            for path in sorted({p for p in files if p.exists()}):
                try:
                    rel = path.relative_to(root)
                    artifact_name = str(rel)
                except ValueError:
                    artifact_name = path.name
                artifact.add_file(str(path), name=artifact_name)
            artifact.metadata = {
                "run_id": self.summary.get("run_id"),
                "mode": self.summary.get("mode"),
                "total_tasks": self.summary.get("total_tasks"),
                "processes": self.summary.get("size"),
                "config_hash": self.summary.get("config_hash"),
            }
            self._run.log_artifact(artifact)
        except Exception as exc:
            print(f"[wandb] artifact logging skipped: {exc}")
            self.enabled = False

    def finish(self) -> None:
        if not self.enabled or self._run is None:
            return
        try:
            self._run.finish()
        except Exception as exc:
            print(f"[wandb] finish skipped: {exc}")
        finally:
            self.enabled = False


def write_wandb_manifest(
    run_dir: str | Path,
    *,
    enabled: bool,
    project: str,
    group: str | None,
    files: dict[str, list[Path]],
    status: str,
) -> Path:
    """Write a small local manifest recording the W&B logging attempt."""

    path = Path(run_dir) / "wandb_manifest.json"
    payload = {
        "enabled": bool(enabled),
        "project": project,
        "group": group,
        "status": status,
        "artifacts": [str(p) for p in files.get("artifacts", [])],
        "images": [str(p) for p in files.get("images", [])],
        "animations": [str(p) for p in files.get("animations", [])],
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
    return path


def log_run_directory_to_wandb(
    run_dir: str | Path,
    *,
    settings: WandbSettings,
    extra_paths: list[str | Path] | None = None,
) -> dict[str, Any]:
    """Log one completed run directory to W&B, if enabled and available."""

    run_dir = Path(run_dir)
    summary = run_summary_from_dir(run_dir)
    files = discover_run_files(run_dir, extra_paths=extra_paths)
    logger = OptionalWandbLogger(settings=settings, summary=summary)
    status = "disabled"
    if logger.enabled:
        status = "logged"
        logger.log_metrics(summary_to_wandb_metrics(summary))
        if settings.log_media:
            logger.log_images(files["images"])
            logger.log_animations(files["animations"])
        if settings.log_tables:
            table_paths = [path for path in files["artifacts"] if path.suffix.lower() == ".csv"]
            logger.log_tables(table_paths)
        if settings.log_artifact:
            artifact_files = files["artifacts"] + files["images"] + files["animations"]
            logger.log_artifact_bundle(run_dir, artifact_files)
        logger.finish()
    manifest = write_wandb_manifest(
        run_dir,
        enabled=settings.enabled,
        project=settings.project,
        group=settings.group or default_group(summary),
        files=files,
        status=status,
    )
    return {
        "run_id": summary.get("run_id"),
        "status": status,
        "manifest": str(manifest),
        "num_artifact_files": len(files["artifacts"]),
        "num_images": len(files["images"]),
        "num_animations": len(files["animations"]),
    }


def wandb_environment_hint() -> str:
    """Return a short hint for users who want online/offline W&B logging."""

    return (
        "Install optional dependency with `python -m pip install wandb`, then run "
        "`wandb login`. For offline runs use `--wandb-mode offline` or set "
        "`WANDB_MODE=offline` and later run `wandb sync <wandb-run-dir>`."
    )
