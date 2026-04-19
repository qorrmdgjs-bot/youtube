"""Abstract base class for all pipeline stages."""

from __future__ import annotations

import abc
from pathlib import Path

from src.models import ProjectManifest
from src.utils.logging_setup import get_logger


class BaseStage(abc.ABC):
    """Base class for pipeline stages.

    Each stage reads from and writes to the project directory.
    The orchestrator handles manifest updates and error recovery.
    """

    # Subclasses must define these
    name: str = ""
    dependencies: list[str] = []

    def __init__(self) -> None:
        self.log = get_logger(f"stage.{self.name}")

    @abc.abstractmethod
    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        """Execute the stage.

        Args:
            project_dir: Path to the project directory.
            manifest: Current project manifest.

        Returns:
            Cost in USD for this stage's API calls.
        """
        ...

    def can_run(self, manifest: ProjectManifest) -> bool:
        """Check if all dependencies are satisfied."""
        for dep in self.dependencies:
            if not manifest.is_stage_completed(dep):
                return False
        return True

    def is_completed(self, manifest: ProjectManifest) -> bool:
        """Check if this stage is already completed."""
        return manifest.is_stage_completed(self.name)
