#!/usr/bin/env python3
"""Regenerates commands/index.html's embedded command list from
streaming-automation's commands.json.

Run this locally whenever commands.json changes:

    python export_commands.py [path/to/commands.json]

With no argument, defaults to ../../streaming-automation/commands.json,
matching the sibling-folder layout under K:\\Dev\\. Only commands with
enabled: true are included.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE.parent.parent / "streaming-automation" / "commands.json"
PAGE = HERE / "index.html"

START_MARKER = "/* COMMANDS:START */"
END_MARKER = "/* COMMANDS:END */"

# Fallback for commands with no explicit "public_useful" field set (older
# entries from before that field existed, or ones nobody's touched yet).
# Mark a command explicitly via the dashboard's Command Manager tab
# ("Mark useful" button) instead of editing this list where possible.
USEFUL_KEYS = {
    "id", "lastid", "kit", "mic", "controller", "camera", "pc", "decks",
    "monitors", "headphones", "schedule", "weather", "time", "add", "so",
    "raid",
}


def is_useful(key, cmd):
    if "public_useful" in cmd:
        return bool(cmd["public_useful"])
    response = cmd.get("response", "")
    return key in USEFUL_KEYS or "http://" in response or "https://" in response


def build_records(commands):
    useful, other = [], []
    for key, cmd in commands.items():
        if not cmd.get("enabled", False):
            continue
        response = cmd.get("response", "")
        record = {
            "trigger": key,
            "response": response,
            "kind": cmd.get("response_type", "static"),
            "bot": cmd.get("bot", "hostvoice"),
        }
        access = cmd.get("access", "everyone")
        if access != "everyone":
            record["access"] = access
        (useful if is_useful(key, cmd) else other).append(record)

    key_fn = lambda r: r["trigger"].lower()
    useful.sort(key=key_fn)
    other.sort(key=key_fn)
    return {"useful": useful, "other": other}


# Publishing pushes straight to the live site, so a publish that looks wrong
# stops before anything is written: lots of commands vanishing at once (a
# damaged commands.json), an empty reply, garbled text, or something that
# looks private. The caller can then publish anyway.
MAX_REMOVED = 3
_GARBLED = re.compile(r"\ufffd|\u00e2\u20ac|\u00c3[\x80-\xbf]")  # U+FFFD, or UTF-8 read as cp1252
_PRIVATE = re.compile(r"localhost|(?<![\w.])(?:127|10|192\.168)(?:\.\d{1,3}){2,3}(?![\w.])|oauth:|access_token|refresh_token|"
                      r"client_secret|password|api[_ -]?key", re.I)


def current_records(html):
    """The command list the page (as last published) carries."""
    m = re.search(re.escape(START_MARKER) + r"\s*var COMMANDS = (.*?);\s*" + re.escape(END_MARKER), html, re.DOTALL)
    return json.loads(m.group(1)) if m else {"useful": [], "other": []}


def _by_trigger(records):
    return {r["trigger"]: r for group in ("useful", "other") for r in records.get(group, [])}


def changes(old, new):
    o, n = _by_trigger(old), _by_trigger(new)
    return {
        "added": sorted(set(n) - set(o), key=str.lower),
        "removed": sorted(set(o) - set(n), key=str.lower),
        "changed": sorted((t for t in n if t in o and n[t] != o[t]), key=str.lower),
    }


def anomalies(old, new, diff):
    warnings = []
    n = _by_trigger(new)
    if not n:
        warnings.append("No commands at all - commands.json may be damaged")
    elif len(diff["removed"]) >= MAX_REMOVED:
        shown = ", ".join("!" + t for t in diff["removed"][:10])
        more = f" and {len(diff['removed']) - 10} more" if len(diff["removed"]) > 10 else ""
        warnings.append(f"{len(diff['removed'])} commands would disappear: {shown}{more}")
    for trigger, r in n.items():
        response = r.get("response", "")
        if not response.strip():
            warnings.append(f"!{trigger} has an empty reply")
        elif _GARBLED.search(response):
            warnings.append(f"!{trigger} has garbled characters: {response[:60]}")
        elif _PRIVATE.search(response):
            warnings.append(f"!{trigger} looks like it has something private in it: {response[:60]}")
    return warnings


def regenerate(source=None, force=False):
    """Rewrite index.html's embedded data from commands.json. Returns counts
    (useful, other, hidden = disabled commands not published), what changed
    against the page as last published, and any warnings. With warnings and
    no force, nothing is written and "blocked" is True."""
    source = Path(source) if source else DEFAULT_SOURCE
    if not source.exists():
        raise FileNotFoundError(f"commands.json not found at {source}")

    data = json.loads(source.read_text(encoding="utf-8"))
    commands = data.get("commands", {})
    records = build_records(commands)

    html = PAGE.read_text(encoding="utf-8")
    if START_MARKER not in html or END_MARKER not in html:
        raise RuntimeError(f"Markers not found in {PAGE} - page template may have changed.")

    old = current_records(html)
    diff = changes(old, records)
    warnings = anomalies(old, records, diff)
    if warnings and not force:
        return {"blocked": True, "warnings": warnings, "changes": diff}

    payload = "var COMMANDS = " + json.dumps(records, ensure_ascii=False, indent=2) + ";"
    replacement = f"{START_MARKER}\n  {payload}\n  {END_MARKER}"
    pattern = re.compile(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL)
    # Use a function repl, not a string one - re.sub treats backslashes (\n, \1, ...)
    # in a string repl as template escapes, which mangles the \n already escaped
    # inside JSON string values by json.dumps.
    new_html = pattern.sub(lambda _m: replacement, html, count=1)
    PAGE.write_text(new_html, encoding="utf-8")

    useful, other = len(records["useful"]), len(records["other"])
    return {
        "useful": useful,
        "other": other,
        "hidden": len(commands) - (useful + other),
        "changes": diff,
        "warnings": warnings,
    }


def main():
    args = [a for a in sys.argv[1:] if a != "--force"]
    source = args[0] if args else None
    try:
        counts = regenerate(source, force="--force" in sys.argv)
    except (FileNotFoundError, RuntimeError) as e:
        raise SystemExit(str(e))
    if counts.get("blocked"):
        raise SystemExit("Not written - check these, then run again with --force:\n  "
                         + "\n  ".join(counts["warnings"]))
    print(f"Wrote {counts['useful']} useful + {counts['other']} other commands to {PAGE} "
          f"({counts['hidden']} disabled, not published)")


if __name__ == "__main__":
    main()
