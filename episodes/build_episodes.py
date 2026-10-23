"""Build episodes/episodes.json from tpbee's SoundCloud podcast RSS feed.

Run at release time (after the new episode is live on SoundCloud), then commit and push
tpbee-website as usual. If the fetch or parse fails, the existing episodes.json is left alone.

    python episodes/build_episodes.py

Episodes the feed doesn't carry (season 1 and older) can be added by hand to
episodes/episodes_extra.json - same fields as the output, merged in by date.
"""
import json
import os
import re
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

FEED_URL = "https://feeds.soundcloud.com/users/soundcloud:users:425586462/sounds.rss"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "episodes.json")
EXTRA_PATH = os.path.join(HERE, "episodes_extra.json")
NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}

# "Artist - Title" or "Artist – Title", optionally numbered ("3. ") - an older-style tracklist line.
TRACK_LINE = re.compile(r"^\s*(?:\d+[.)]\s*)?\S.*\s[-–—]\s\S")


def fetch_feed():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "tpbee-website episode builder"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def split_description(desc, title):
    """Return (intro, tracklist lines) from a SoundCloud description."""
    lines = [l.rstrip() for l in desc.replace("\r", "").split("\n")]
    if lines and lines[0].strip() == title.strip():
        lines = lines[1:]  # newer descriptions repeat the title as their first line
    text = "\n".join(lines)
    marker = re.search(r"^\s*Tracklist:?\s*$", text, re.M | re.I)
    if marker:
        intro = text[:marker.start()]
        tracks = [l.strip() for l in text[marker.end():].split("\n") if l.strip()]
    else:
        # older episodes: the tracklist is the run of "Artist - Title" lines after the intro
        tracks, intro_lines = [], []
        for l in lines:
            if TRACK_LINE.match(l) and len(l) < 160:
                tracks.append(l.strip())
            elif not tracks:
                intro_lines.append(l)
        intro = "\n".join(intro_lines)
    tracks = [re.sub(r"^\d+[.)]\s*", "", t) for t in tracks]
    intro = re.sub(r"\n{3,}", "\n\n", intro).strip()
    return intro, tracks


def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    show_image = root.find("channel/itunes:image", NS)
    show_image = show_image.get("href") if show_image is not None else ""
    episodes = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        guid = item.findtext("guid") or ""
        m = re.search(r"tracks/(\d+)", guid)
        img = item.find("itunes:image", NS)
        desc = item.findtext("description") or ""
        intro, tracks = split_description(desc, title)
        episodes.append({
            "title": title,
            "date": parsedate_to_datetime(item.findtext("pubDate")).date().isoformat(),
            "duration": item.findtext("itunes:duration", default="", namespaces=NS),
            "url": (item.findtext("link") or "").strip(),
            "track_id": m.group(1) if m else "",
            "image": img.get("href") if img is not None else show_image,
            "intro": intro,
            "tracklist": tracks,
        })
    return episodes


def main():
    try:
        episodes = parse(fetch_feed())
    except Exception as exc:  # keep the last good file rather than breaking the page
        print(f"Feed fetch/parse failed, episodes.json left unchanged: {exc}")
        return 1
    if not episodes:
        print("Feed returned no episodes, episodes.json left unchanged")
        return 1
    if os.path.exists(EXTRA_PATH):
        with open(EXTRA_PATH, encoding="utf-8") as f:
            known = {e["url"] for e in episodes}
            episodes += [e for e in json.load(f) if e.get("url") not in known]
    episodes.sort(key=lambda e: e["date"], reverse=True)
    fd, tmp = tempfile.mkstemp(dir=HERE, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(episodes, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT_PATH)
    no_tracks = [e["title"] for e in episodes if not e["tracklist"]]
    print(f"Wrote {len(episodes)} episodes to episodes.json ({len(no_tracks)} without a tracklist)")
    for t in no_tracks:
        print("  no tracklist:", t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
