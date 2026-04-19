"""API cost tracking and budget enforcement."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.utils.logging_setup import get_logger

log = get_logger(__name__)


class CostTracker:
    """Tracks API costs per project and enforces budget limits."""

    def __init__(self, project_dir: Path, max_per_video: float = 12.0):
        self.project_dir = project_dir
        self.max_per_video = max_per_video
        self.cost_file = project_dir / "costs.json"
        self.costs: list[dict] = []
        if self.cost_file.exists():
            self.costs = json.loads(self.cost_file.read_text(encoding="utf-8"))

    @property
    def total(self) -> float:
        return sum(c["amount"] for c in self.costs)

    def add(self, service: str, operation: str, amount: float) -> None:
        entry = {
            "service": service,
            "operation": operation,
            "amount": round(amount, 4),
            "timestamp": datetime.now().isoformat(),
        }
        self.costs.append(entry)
        self._save()
        log.info("cost_recorded", service=service, operation=operation, amount=amount, total=self.total)

    def check_budget(self) -> bool:
        if self.total >= self.max_per_video:
            log.warning("budget_exceeded", total=self.total, limit=self.max_per_video)
            return False
        return True

    def _save(self) -> None:
        self.cost_file.write_text(
            json.dumps(self.costs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
