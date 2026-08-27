#!/usr/bin/env python3
"""Norma plugin telemetry — record a skill-invocation event.

Usage:
    scripts/track.py <event>

Where <event> is one of:
    analyze_invoked   — fired by /normativa-analyze at the end of a successful run
    informe_rendered  — fired by /normativa-informe after the printable HTML is written

What gets sent (and only this):
    - schema: 'estudio-local.norma_event.v1'
    - event: the argv[1] value
    - machine_id: anonymous UUID stored in ~/.config/estudio-local/machine-id
                  (created on first run; opaque to the user)
    - skill_version: the version field from .claude-plugin/plugin.json
    - ts: ISO-8601 UTC timestamp

What does NOT get sent (deliberately):
    - padron numbers, envelope JSON, locality, zone codes
    - file paths, project paths, any conversation content
    - hostname, user, IP (CF strips the source IP from the function's view)

Disclosed in README.md → "Telemetry" section. Opt out with
ESTUDIO_LOCAL_TELEMETRY=0 (or any value other than '1' / 'true' / unset).

Fire-and-forget: 1-second timeout, all errors swallowed. Telemetry must
never block or surface in the user's flow.
"""

import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ENDPOINT = "https://estudio-local.com/api/telemetry"
SCHEMA_ID = "estudio-local.norma_event.v1"
ALLOWED_EVENTS = {"analyze_invoked", "informe_rendered"}
TIMEOUT_S = 1.0


def opted_out() -> bool:
    val = os.environ.get("ESTUDIO_LOCAL_TELEMETRY", "1").strip().lower()
    return val in {"0", "false", "no", "off"}


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "estudio-local"


def machine_id() -> str:
    path = config_dir() / "machine-id"
    if path.exists():
        try:
            mid = path.read_text().strip()
            if mid:
                return mid
        except OSError:
            pass
    mid = str(uuid.uuid4())
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(mid + "\n")
    except OSError:
        pass
    return mid


def skill_version() -> str:
    plugin_json = Path(__file__).parent.parent / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(plugin_json.read_text()).get("version", "")
    except Exception:
        return ""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: track.py <event>", file=sys.stderr)
        return 2
    event = sys.argv[1]
    if event not in ALLOWED_EVENTS:
        print(f"track.py: unknown event '{event}'", file=sys.stderr)
        return 2
    if opted_out():
        return 0

    body = json.dumps({
        "schema": SCHEMA_ID,
        "event": event,
        "machine_id": machine_id(),
        "skill_version": skill_version(),
    }).encode("utf-8")

    # CF Bot Fight Mode 403s the default Python-urllib User-Agent. A
    # plugin-identifying UA both passes the bot check and makes server-side
    # logs intelligible. The UA is not security; the schema/event whitelist
    # at /api/telemetry is.
    user_agent = f"Norma/{skill_version() or 'unknown'} (estudio-local plugin)"
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as _:
            pass
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
