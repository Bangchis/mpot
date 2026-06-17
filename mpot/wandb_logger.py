"""Optional W&B logger used by rank 0 only.

The course demo must work without W&B, so this module catches import/login/runtime
failures and falls back to a no-op logger.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class OptionalWandbLogger:
    """Small wrapper that keeps W&B optional."""

    def __init__(self, enabled: bool, project: str, config: dict[str, Any]):
        self.enabled = bool(enabled)
        self._wandb = None
        self._run = None
        if not self.enabled:
            return
        try:
            import wandb

            self._wandb = wandb
            self._run = wandb.init(project=project, config=config)
        except Exception as exc:
            print(f"[wandb] disabled: {exc}")
            self.enabled = False
            self._wandb = None
            self._run = None

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        if not self.enabled or self._wandb is None:
            return
        try:
            self._wandb.log(metrics, step=step)
        except Exception as exc:
            print(f"[wandb] metric logging skipped: {exc}")
            self.enabled = False

    def log_artifact(self, path: str, name: str | None = None) -> None:
        if not self.enabled or self._wandb is None:
            return
        artifact_path = Path(path)
        if not artifact_path.exists():
            print(f"[wandb] artifact missing, skipped: {artifact_path}")
            return
        try:
            artifact = self._wandb.Artifact(name or artifact_path.stem, type="result")
            artifact.add_file(str(artifact_path))
            self._wandb.log_artifact(artifact)
        except Exception as exc:
            print(f"[wandb] artifact logging skipped: {exc}")
            self.enabled = False

    def finish(self) -> None:
        if not self.enabled or self._wandb is None:
            return
        try:
            self._wandb.finish()
        except Exception as exc:
            print(f"[wandb] finish skipped: {exc}")
        finally:
            self.enabled = False

