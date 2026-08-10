from __future__ import annotations

import unittest

from scripts.normalize_metrics import normalize_rows, parse_metric_value


class ParseMetricValueTests(unittest.TestCase):
    def test_parses_chinese_and_latin_units(self) -> None:
        cases = {
            "999": 999,
            "1,234": 1234,
            "3.3万": 33000,
            "1.2亿": 120000000,
            "2.5w": 25000,
            "8k赞": 8000,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_metric_value(raw), expected)

    def test_rejects_missing_or_ambiguous_values(self) -> None:
        for raw in (None, "", "很多", True):
            with self.subTest(raw=raw):
                self.assertIsNone(parse_metric_value(raw))


class NormalizeRowsTests(unittest.TestCase):
    def test_percentiles_deduplicate_content_across_lists(self) -> None:
        rows = [
            self.row("liked", "a", "100", "like"),
            self.row("favorited", "a", "100", "like"),
            self.row("liked", "b", "1000", "like"),
            self.row("liked", "c", "1万", "like"),
        ]
        output = normalize_rows(rows)
        by_content = {row["content_id"]: row for row in output}
        self.assertEqual(by_content["a"]["platform_metric_percentile"], 16.67)
        self.assertEqual(by_content["b"]["platform_metric_percentile"], 50.0)
        self.assertEqual(by_content["c"]["platform_metric_percentile"], 83.33)
        self.assertTrue(all(row["performance_weight_status"] == "eligible" for row in output))

    def test_unknown_metric_type_stays_low_confidence(self) -> None:
        row = self.row("liked", "a", "3.3万", None)
        output = normalize_rows([row])[0]
        self.assertEqual(output["metric_type"], "unknown_visible_interaction")
        self.assertEqual(output["metric_value_numeric"], 33000)
        self.assertEqual(output["metric_confidence"], "low")
        self.assertEqual(output["performance_weight_status"], "low_confidence")

    @staticmethod
    def row(list_type: str, content_id: str, value: str, metric_type: str | None) -> dict:
        row = {
            "platform": "douyin",
            "list_type": list_type,
            "content_id": content_id,
            "visible_interaction": value,
            "observed_at": "2026-08-11T12:00:00+08:00",
            "media_type": "video",
        }
        if metric_type:
            row["metric_type"] = metric_type
        return row


if __name__ == "__main__":
    unittest.main()
