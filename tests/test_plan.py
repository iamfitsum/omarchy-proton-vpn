#!/usr/bin/env python3
"""Tests for plan.py payload shaping (no Proton session required)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plan import UNKNOWN, plan_payload  # noqa: E402


class PlanPayloadTests(unittest.TestCase):
    def test_plus_account(self) -> None:
        acc = SimpleNamespace(max_tier=2, plan_name="vpn2024", plan_title="VPN Plus")
        self.assertEqual(
            plan_payload(acc, True),
            {"tier": 2, "name": "vpn2024", "title": "VPN Plus"},
        )

    def test_free_account_with_none_title(self) -> None:
        acc = SimpleNamespace(max_tier=0, plan_name="free", plan_title=None)
        self.assertEqual(
            plan_payload(acc, True),
            {"tier": 0, "name": "free", "title": ""},
        )

    def test_signed_out_does_not_leak_cached_plus(self) -> None:
        acc = SimpleNamespace(max_tier=2, plan_name="vpn2024", plan_title="VPN Plus")
        self.assertEqual(plan_payload(acc, False), UNKNOWN)

    def test_missing_account_is_unknown(self) -> None:
        self.assertEqual(plan_payload(None, True), UNKNOWN)

    def test_bad_tier_is_unknown(self) -> None:
        acc = SimpleNamespace(max_tier="nope", plan_name="free", plan_title="Free")
        self.assertEqual(plan_payload(acc, True), UNKNOWN)

    def test_payload_is_json_safe(self) -> None:
        acc = SimpleNamespace(max_tier=3, plan_name="employee", plan_title="Proton")
        json.dumps(plan_payload(acc, True))


if __name__ == "__main__":
    unittest.main()
