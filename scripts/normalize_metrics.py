#!/usr/bin/env python3
"""Normalize visible engagement metrics without comparing unlike cohorts.

The input remains one row per platform/list relationship. Percentiles are
computed from independent content IDs within cohorts that share platform and
metric type. Unknown metric types stay explicitly low confidence.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


UNIT_MULTIPLIERS = {
    "": 1,
    "千": 1_000,
    "k": 1_000,
    "K": 1_000,
    "万": 10_000,
    "w": 10_000,
    "W": 10_000,
    "亿": 100_000_000,
}

METRIC_PATTERN = re.compile(
    r"^\s*(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>千|万|亿|[kKwW])?"
    r"\s*(?:点赞|赞|收藏|评论|互动)?\s*\+?\s*$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Snapshot JSONL")
    parser.add_argument("--output", required=True, type=Path, help="Normalized JSONL")
    return parser.parse_args()


def parse_metric_value(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0, int(round(value)))
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    match = METRIC_PATTERN.fullmatch(text)
    if not match:
        return None
    number = float(match.group("number"))
    multiplier = UNIT_MULTIPLIERS[match.group("unit") or ""]
    return max(0, int(round(number * multiplier)))


def read_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"line {line_number}: expected JSON object")
            required = ("platform", "list_type", "content_id")
            if any(not row.get(field) for field in required):
                raise ValueError(f"line {line_number}: platform/list_type/content_id are required")
            rows.append(row)
    return rows


def metric_identity(row: dict[str, Any]) -> tuple[str, str]:
    explicit = row.get("metric_type") or row.get("visible_interaction_type")
    if explicit:
        return str(explicit), "high"
    return "unknown_visible_interaction", "low"


def raw_metric_value(row: dict[str, Any]) -> Any:
    if row.get("metric_value_raw") not in (None, ""):
        return row.get("metric_value_raw")
    return row.get("visible_interaction")


def midpoint_percentile(value: int, cohort: Iterable[int]) -> float | None:
    values = sorted(cohort)
    if not values:
        return None
    lower = sum(item < value for item in values)
    equal = sum(item == value for item in values)
    return round(100 * (lower + 0.5 * equal) / len(values), 2)


def unique_cohort_values(
    rows: list[dict[str, Any]],
    key_fields: tuple[str, ...],
) -> dict[tuple[str, ...], list[int]]:
    content_values: dict[tuple[tuple[str, ...], str], int] = {}
    for row in rows:
        value = row.get("metric_value_numeric")
        if value is None:
            continue
        cohort = tuple(str(row.get(field) or "unknown") for field in key_fields)
        content_key = (cohort, str(row["content_id"]))
        content_values[content_key] = max(value, content_values.get(content_key, value))
    grouped: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for (cohort, _content_id), value in content_values.items():
        grouped[cohort].append(value)
    return dict(grouped)


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        metric_type, confidence = metric_identity(row)
        raw_value = raw_metric_value(row)
        numeric = parse_metric_value(raw_value)
        row.update(
            {
                "metric_type": metric_type,
                "metric_value_raw": raw_value,
                "metric_value_numeric": numeric,
                "metric_observed_at": row.get("metric_observed_at") or row.get("observed_at"),
                "metric_confidence": confidence,
            }
        )
        if raw_value in (None, ""):
            status = "unavailable"
        elif numeric is None:
            status = "unparseable"
        elif confidence == "low":
            status = "low_confidence"
        else:
            status = "eligible"
        row["performance_weight_status"] = status
        normalized.append(row)

    platform_groups = unique_cohort_values(normalized, ("platform", "metric_type"))
    media_groups = unique_cohort_values(normalized, ("platform", "media_type", "metric_type"))
    list_groups = unique_cohort_values(normalized, ("platform", "list_type", "metric_type"))

    for row in normalized:
        value = row.get("metric_value_numeric")
        if value is None:
            row["platform_metric_percentile"] = None
            row["media_metric_percentile"] = None
            row["list_metric_percentile"] = None
            continue
        platform_key = (str(row["platform"]), str(row["metric_type"]))
        media_key = (
            str(row["platform"]),
            str(row.get("media_type") or "unknown"),
            str(row["metric_type"]),
        )
        list_key = (str(row["platform"]), str(row["list_type"]), str(row["metric_type"]))
        row["platform_metric_percentile"] = midpoint_percentile(value, platform_groups[platform_key])
        row["media_metric_percentile"] = midpoint_percentile(value, media_groups[media_key])
        row["list_metric_percentile"] = midpoint_percentile(value, list_groups[list_key])
    return normalized


def main() -> int:
    args = parse_args()
    normalized = normalize_rows(read_rows(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in normalized:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    summary = {
        "input": str(args.input),
        "output": str(args.output),
        "rows": len(normalized),
        "eligible": sum(row["performance_weight_status"] == "eligible" for row in normalized),
        "low_confidence": sum(row["performance_weight_status"] == "low_confidence" for row in normalized),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
