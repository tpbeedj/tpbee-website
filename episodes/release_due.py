"""Is a scheduled episode due on the site? Used by .github/workflows/release-episode.yml.

episodes/release.json is written by the Promo Studio publisher when an episode is
scheduled on SoundCloud:

    {"episode": "S03E13", "at": "2026-10-27T07:30:00+00:00"}

Prints "due" once that time has passed and the episode isn't in episodes.json yet,
otherwise "wait" (with the reason). Gives up 2 days after the release time, so a
missed or renamed upload doesn't keep the job busy.
"""
import json
import os
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))


def check():
    try:
        with open(os.path.join(HERE, "release.json"), encoding="utf-8") as f:
            rel = json.load(f)
        code, at = rel["episode"].strip().upper(), datetime.fromisoformat(rel["at"])
    except (OSError, ValueError, KeyError) as exc:
        return "wait", f"no release scheduled ({exc})"
    with open(os.path.join(HERE, "episodes.json"), encoding="utf-8") as f:
        if any(f"[{code}]" in e.get("title", "").upper() for e in json.load(f)):
            return "wait", f"{code} is already listed"
    now = datetime.now(timezone.utc)
    if now < at:
        return "wait", f"{code} is due at {at.isoformat()}"
    if now > at + timedelta(days=2):
        return "wait", f"{code} was due at {at.isoformat()} - over 2 days ago, giving up"
    return "due", code


if __name__ == "__main__":
    state, detail = check()
    print(f"{state} {detail}")
