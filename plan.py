#!/usr/bin/env python3
"""Print the signed-in Proton VPN plan as one parseable line.

`protonvpn info` only prints the account name, but the CLI's own API core
exposes VPNAccount.max_tier (0 = Free, 2 = Plus, 3 = Proton employee) plus
plan_name/plan_title. That is the authoritative signal, so the widget does not
have to infer a tier from the absence of text.

Output: tier=<int>\tname=<plan name>\ttitle=<plan title>
        tier=-1 when unknown (not signed in, or the core is unavailable).

The proton packages are installed for the system interpreter, so re-exec there
when the interpreter that runs this file cannot import them.
"""
import os
import sys

try:
    from proton.vpn.core.api import ProtonVPNAPI
    from proton.vpn.core.session_holder import ClientTypeMetadata
except ImportError:
    if os.path.realpath(sys.executable) != "/usr/bin/python" and os.path.exists("/usr/bin/python"):
        os.execv("/usr/bin/python", ["/usr/bin/python", os.path.abspath(__file__)] + sys.argv[1:])
    print("tier=-1")
    raise SystemExit(0)


def main() -> int:
    try:
        api = ProtonVPNAPI(ClientTypeMetadata(type="cli"))
        account = api.account_data
        tier = account.max_tier
        if not api.is_user_logged_in():
            tier = -1
        print(f"tier={tier}\tname={account.plan_name}\ttitle={account.plan_title}")
    except Exception:
        print("tier=-1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
