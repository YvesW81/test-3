#!/usr/bin/env python3
"""File-monitor: haalt actuele filedata op bij Rijkswaterstaat en logt naar CSV."""

import csv
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

API_URL = "https://api.rwsverkeersinfo.nl/api/traffic/"
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

TOTALEN_HEADER = [
    "tijdstip", "aantal_files", "totale_lengte_km",
    "totale_vertraging_min", "aantal_incidenten", "aantal_wegwerkzaamheden",
]
FILES_HEADER = [
    "tijdstip", "weg", "titel", "richting", "traject", "oorzaak",
    "vertraging_min", "lengte_m", "lat", "lon", "start_tijd", "file_id",
]


def local_time(iso_utc: str) -> str:
    """Zet ISO UTC-tijd ('2026-07-10T07:32:28.536Z') om naar lokale tijd."""
    if not iso_utc:
        return ""
    try:
        dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
        return dt.astimezone(ZoneInfo("Europe/Amsterdam")).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso_utc


def fetch(input_file: str | None) -> dict:
    if input_file:
        return json.loads(Path(input_file).read_text(encoding="utf-8"))
    req = urllib.request.Request(API_URL, headers={"User-Agent": "file-monitor (github)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def append_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(header)
        w.writerows(rows)


def main() -> None:
    input_file = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--input" else None
    data = fetch(input_file)

    now = datetime.now(ZoneInfo("Europe/Amsterdam"))
    ts = now.strftime("%Y-%m-%d %H:%M")

    jams = [o for o in data.get("obstructions", []) if o.get("obstructionType") == 4]
    total_delay = round(sum(o.get("delay") or 0 for o in jams))

    append_csv(DATA_DIR / "totalen.csv", TOTALEN_HEADER, [[
        ts,
        data.get("numberOfJams", len(jams)),
        round(data.get("totalLengthOfJams", 0) / 1000, 1),
        total_delay,
        data.get("numberOfIncidents", 0),
        data.get("numberOfRoadWorks", 0),
    ]])

    file_rows = [[
        ts,
        o.get("roadNumber", ""),
        o.get("title", ""),
        o.get("directionText", ""),
        o.get("locationText", ""),
        o.get("cause", ""),
        o.get("delay") or 0,
        o.get("length") or 0,
        o.get("latitude", ""),
        o.get("longitude", ""),
        local_time(o.get("timeStart", "")),
        o.get("id", ""),
    ] for o in jams]

    if file_rows:
        append_csv(DATA_DIR / "files" / f"{now:%Y-%m}.csv", FILES_HEADER, file_rows)

    print(f"{ts}: {len(jams)} files gelogd, totaal {total_delay} min vertraging")


if __name__ == "__main__":
    main()
