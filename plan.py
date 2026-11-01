#!/usr/bin/env python3
"""Print the signed-in Proton VPN plan as one JSON object.

`protonvpn info` only prints the account name (CLI 1.0.5). The CLI's API core
still has VPNAccount.max_tier (0 Free, 2 Plus, 3 Proton employee) plus
plan_name / plan_title. That is the source of truth.

Prints {"tier": <int>, "name": <str>, "title": <str>}.
tier is -1 when unknown (signed out, or the core is unavailable).

The proton packages are installed for the system interpreter, so re-exec there
when the interpreter that runs this file cannot import them.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

UNKNOWN = {"tier": -1, "name": "", "title": ""}


def plan_payload(account: Any, logged_in: bool) -> dict[str, Any]:
    """Return a JSON-safe plan dict. Never includes credentials."""
    if not logged_in or account is None:
        return dict(UNKNOWN)
    try:
        tier = int(account.max_tier)
    except (TypeError, ValueError):
        return dict(UNKNOWN)
    name = getattr(account, "plan_name", None)
    title = getattr(account, "plan_title", None)
    return {
        "tier": tier,
        "name": "" if name is None else str(name),
        "title": "" if title is None else str(title),
    }


def _dump(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, separators=(",", ":")))


def _reexec_system_python() -> None:
    here = os.path.abspath(__file__)
    current = os.path.realpath(sys.executable)
    for candidate in ("/usr/bin/python3", "/usr/bin/python"):
        if os.path.exists(candidate) and os.path.realpath(candidate) != current:
            os.execv(candidate, [candidate, here, *sys.argv[1:]])


def main() -> int:
    """Load the CLI session and print the plan payload."""
    try:
        from proton.vpn.core.api import ProtonVPNAPI
        from proton.vpn.core.session_holder import ClientTypeMetadata
    except ImportError:
        _reexec_system_python()
        _dump(UNKNOWN)
        return 0
    try:
        api = ProtonVPNAPI(ClientTypeMetadata(type="cli"))
        logged_in = bool(api.is_user_logged_in())
        account = api.account_data if logged_in else None
        _dump(plan_payload(account, logged_in))
    except Exception:
        _dump(UNKNOWN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
