#!/usr/bin/env python3
"""Generate API cost report across all projects."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path("projects")


def main():
    if not BASE_DIR.exists():
        print("프로젝트 디렉토리가 없습니다.")
        sys.exit(0)

    total_cost = 0.0
    project_count = 0

    print("=" * 70)
    print("YouTube 자동화 파이프라인 - 비용 리포트")
    print("=" * 70)

    for project_dir in sorted(BASE_DIR.iterdir()):
        if not project_dir.is_dir():
            continue

        manifest_path = project_dir / "manifest.json"
        if not manifest_path.exists():
            continue

        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        project_id = data.get("project_id", "?")
        title = data.get("brief", {}).get("title", "?")
        cost = data.get("total_cost_usd", 0.0)
        stages = data.get("stages", {})

        print(f"\n{project_id} | {title}")

        for stage_name, stage_info in stages.items():
            stage_cost = stage_info.get("cost_usd", 0.0)
            status = stage_info.get("status", "?")
            if stage_cost > 0:
                print(f"  {stage_name}: ${stage_cost:.4f} ({status})")

        print(f"  합계: ${cost:.2f}")
        total_cost += cost
        project_count += 1

        # Also check costs.json if exists
        costs_file = project_dir / "costs.json"
        if costs_file.exists():
            costs = json.loads(costs_file.read_text(encoding="utf-8"))
            by_service: dict[str, float] = {}
            for entry in costs:
                svc = entry.get("service", "unknown")
                by_service[svc] = by_service.get(svc, 0) + entry.get("amount", 0)
            if by_service:
                print("  서비스별:")
                for svc, amt in by_service.items():
                    print(f"    {svc}: ${amt:.4f}")

    print("\n" + "=" * 70)
    print(f"프로젝트 수: {project_count}")
    print(f"전체 비용: ${total_cost:.2f}")

    # Monthly budget check
    monthly_budget = 1000.0
    percent = (total_cost / monthly_budget) * 100 if monthly_budget > 0 else 0
    print(f"월간 예산 사용: {percent:.1f}% (${total_cost:.2f} / ${monthly_budget:.2f})")
    print("=" * 70)


if __name__ == "__main__":
    main()
