#!/usr/bin/env python3
"""Merge one normalized engagement snapshot into append-only history.

Input is JSONL. The script deliberately does not infer interaction times.
It deduplicates by platform/list_type/content_id and computes a conservative
run diff. Standard library only.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


KEY_FIELDS = ("platform", "list_type", "content_id")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Current run JSONL")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"line {line_number}: expected JSON object")
            missing = [field for field in KEY_FIELDS if not row.get(field)]
            if missing:
                raise ValueError(f"line {line_number}: missing {', '.join(missing)}")
            rows.append(row)
    return rows


def key(row: dict[str, Any]) -> tuple[str, str, str]:
    return tuple(str(row[field]) for field in KEY_FIELDS)  # type: ignore[return-value]


def load_history(path: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    latest: dict[tuple[str, str, str], dict[str, Any]] = {}
    if not path.exists():
        return latest
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                latest[key(row)] = row
    return latest


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    args = parse_args()
    rows = read_rows(args.input)
    history_path = args.output_dir / "history.jsonl"
    previous = load_history(history_path)
    now = utc_now()

    current: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        row["run_id"] = args.run_id
        row.setdefault("observed_at", now)
        row.setdefault("content_publish_at", None)
        row.setdefault("like_at", None)
        row.setdefault("favorite_at", None)
        row["is_new"] = key(row) not in previous
        current[key(row)] = row

    new_keys = [item for item, row in current.items() if row["is_new"]]
    repeat_keys = [item for item, row in current.items() if not row["is_new"]]

    # Append only the current run's observations; old evidence remains intact.
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        for row in current.values():
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    grouped_current: defaultdict[tuple[str, str], set[tuple[str, str, str]]] = defaultdict(set)
    grouped_previous: defaultdict[tuple[str, str], set[tuple[str, str, str]]] = defaultdict(set)
    for item in current:
        grouped_current[item[:2]].add(item)
    for item in previous:
        grouped_previous[item[:2]].add(item)

    groups = sorted(set(grouped_current) | set(grouped_previous))
    diff_groups: dict[str, dict[str, list[str]]] = {}
    for platform, list_type in groups:
        current_keys = grouped_current[(platform, list_type)]
        previous_keys = grouped_previous[(platform, list_type)]
        diff_groups[f"{platform}:{list_type}"] = {
            "new_content_ids": sorted(item[2] for item in current_keys - previous_keys),
            "repeated_content_ids": sorted(item[2] for item in current_keys & previous_keys),
            "not_seen_this_run": sorted(item[2] for item in previous_keys - current_keys),
        }

    diff = {
        "run_id": args.run_id,
        "generated_at": now,
        "rows_in_run": len(current),
        "new_rows": len(new_keys),
        "repeated_rows": len(repeat_keys),
        "groups": diff_groups,
        "interpretation": {
            "not_seen_this_run": "not proof of removal; coverage, sorting, pagination, and access must be checked",
            "interaction_times": "not inferred from observed_at",
        },
    }
    diff_path = args.output_dir / "diffs" / f"{args.run_id}.json"
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    latest_path = args.output_dir / "latest.jsonl"
    write_jsonl(latest_path, sorted(current.values(), key=lambda row: key(row)))
    print(json.dumps({"history": str(history_path), "latest": str(latest_path), "diff": str(diff_path), "new_rows": len(new_keys)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
