#!/usr/bin/env python3
"""Daily readings — refresh the surface-conditions panel.

Fetches two open datasets and re-renders assets/surface-conditions-*.svg:

  1. Rhine discharge (Q, m3/s) at Lobith, from Rijkswaterstaat
     WaterWebservices — the station where the Rhine enters the Netherlands.
  2. Atmospheric CO2, from the NOAA GML global daily trend file.

FAIL-SOFT CONTRACT: a field log never lies — it just gets older. On ANY
fetch, parse, or schema error this script exits 0 WITHOUT writing, so the
previous dated reading stands. A partial success (one source up, one down)
keeps the fresh source and carries the stale value forward unchanged.

Stdlib only. Run from anywhere: paths resolve relative to this file.
"""

import csv
import io
import json
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_assets  # noqa: E402  (shared templates — themes can never drift)

ROOT = Path(__file__).resolve().parent.parent
SOUNDINGS = ROOT / "assets" / "soundings.json"
README = ROOT / "README.md"
ARCHIVAL_CAVEAT = ("\n<sub>Day-one panel shows an archival estimate; "
                   "the first automated sounding replaces it.</sub>\n")

RWS_BASE = "https://waterwebservices.rijkswaterstaat.nl"
RWS_CATALOG = RWS_BASE + "/METADATASERVICES_DBO/OphalenCatalogus"
RWS_OBSERVATIONS = RWS_BASE + "/ONLINEWAARNEMINGENSERVICES_DBO/OphalenWaarnemingen"
NOAA_CO2_TREND = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_trend_gl.csv"
NOAA_CO2_MONTHLY = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_gl.csv"

TIMEOUT = 30
UA = {"User-Agent": "moseskolleh-profile-readings/1.0 (github.com/moseskolleh)"}


def post_json(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **UA},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def get_text(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode()


def find_lobith():
    """Look the station up in the catalogue rather than hardcoding metadata
    that Rijkswaterstaat has been known to reshuffle."""
    cat = post_json(RWS_CATALOG, {
        "CatalogusFilter": {"Grootheden": True, "Compartimenten": True}
    })
    candidates = []
    for loc in cat.get("LocatieLijst", []):
        naam = (loc.get("Naam") or "").strip().lower()
        if naam == "lobith":
            candidates.insert(0, loc)   # exact name wins over e.g. "Lobith haven"
        elif "lobith" in naam:
            candidates.append(loc)
    if not candidates:
        raise LookupError("no Lobith station in RWS catalogue")
    loc = candidates[0]
    return {"Code": loc["Code"], "X": loc["X"], "Y": loc["Y"]}


def fetch_rhine():
    """Return (latest_value, series_of_daily_means) for discharge at Lobith."""
    loc = find_lobith()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    body = {
        "Locatie": loc,
        "AquoPlusWaarnemingMetadata": {
            "AquoMetadata": {
                "Compartiment": {"Code": "OW"},
                "Grootheid": {"Code": "Q"},
            }
        },
        "Periode": {
            "Begindatumtijd": start.strftime("%Y-%m-%dT%H:%M:%S.000+00:00"),
            "Einddatumtijd": end.strftime("%Y-%m-%dT%H:%M:%S.000+00:00"),
        },
    }
    data = post_json(RWS_OBSERVATIONS, body)
    per_day = {}
    for wl in data.get("WaarnemingenLijst", []):
        for m in wl.get("MetingenLijst", []):
            v = m.get("Meetwaarde", {}).get("Waarde_Numeriek")
            t = m.get("Tijdstip", "")
            # RWS flags missing data as extreme sentinel values
            if v is None or v > 1e8 or v < 0:
                continue
            per_day.setdefault(t[:10], []).append(float(v))
    if not per_day:
        raise ValueError("RWS returned no usable Q measurements")
    days = sorted(per_day)[-30:]
    series = [round(sum(per_day[d]) / len(per_day[d])) for d in days]
    return series[-1], series


def fetch_co2():
    """Return (latest_daily_trend_ppm, last_12_monthly_means)."""
    trend_rows = [r for r in csv.reader(io.StringIO(get_text(NOAA_CO2_TREND)))
                  if r and not r[0].startswith("#")]
    # columns: year, month, day, smoothed, trend — walk back past any
    # trailing fill rows (NOAA uses sentinels like -999.99 elsewhere)
    latest = None
    for row in reversed(trend_rows):
        try:
            v = float(row[4])
        except (IndexError, ValueError):
            continue
        if 300 < v < 700:
            latest = v
            break
    if latest is None:
        raise ValueError("no plausible CO2 trend value in NOAA file")

    monthly_rows = [r for r in csv.reader(io.StringIO(get_text(NOAA_CO2_MONTHLY)))
                    if r and not r[0].startswith("#")]
    # columns: year, month, decimal date, average, ...
    monthly = []
    for row in monthly_rows:
        try:
            v = float(row[3])
            if 300 < v < 700:
                monthly.append(round(v, 2))
        except (IndexError, ValueError):
            continue
    if len(monthly) < 12:
        raise ValueError("fewer than 12 monthly CO2 means in NOAA file")
    return round(latest, 1), monthly[-12:]


def sync_readme(data):
    """Best-effort: keep the README's alt text truthful under total image
    failure, and drop the day-one archival caveat once real data flows.
    Never raises; a failed sync only means slightly staler prose."""
    try:
        import re
        md = README.read_text(encoding="utf-8")
        alt = (f"Surface conditions {data['reading_date']}: Rhine discharge at "
               f"Lobith {data['rhine']['latest']:,.0f} m3/s, 30-day sounding; "
               f"atmospheric CO2 {data['co2']['latest']:.1f} ppm, NOAA global "
               f"trend.")
        new_md, n = re.subn(r'(alt=")Surface conditions [^"]*(")',
                            lambda m: m.group(1) + alt + m.group(2), md)
        if n == 1:
            md = new_md
        md = md.replace(ARCHIVAL_CAVEAT, "\n")
        README.write_text(md, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 — cosmetic sync only
        print(f"reading: README sync skipped ({exc})")


def main():
    try:
        prior = json.loads(SOUNDINGS.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — fail-soft by contract
        print(f"reading: cannot read prior soundings ({exc}); leaving log as-is")
        return 0

    fresh = {"rhine": None, "co2": None}
    for key, fetch in (("rhine", fetch_rhine), ("co2", fetch_co2)):
        try:
            fresh[key] = fetch()
        except Exception as exc:  # noqa: BLE001 — fail-soft by contract
            print(f"reading: {key} source unavailable ({exc}); carrying prior value")

    if fresh["rhine"] is None and fresh["co2"] is None:
        print("reading: both sources down; prior dated reading stands")
        return 0

    today = date.today().isoformat()
    try:
        data = dict(prior)
        if fresh["rhine"] is not None:
            latest, series = fresh["rhine"]
            data["rhine"] = {"latest": latest, "series": series,
                             "station": "Lobith", "quantity": "Q",
                             "unit": "m3/s", "sounded": today}
        if fresh["co2"] is not None:
            latest, monthly = fresh["co2"]
            data["co2"] = {"latest": latest, "monthly": monthly,
                           "source": "NOAA GML global trend", "sounded": today}
        data["archival"] = False
        data["reading_date"] = today

        # Render FIRST — if the merged data can't produce valid SVGs
        # (e.g. a hand-mangled prior file), nothing is written at all.
        svgs = {theme: render_assets.render_surface(p, theme, data)
                for theme, p in render_assets.PALETTES.items()}
    except Exception as exc:  # noqa: BLE001 — fail-soft by contract
        print(f"reading: could not compose reading ({exc}); prior log stands")
        return 0

    SOUNDINGS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    for theme, svg in svgs.items():
        (ROOT / "assets" / f"surface-conditions-{theme}.svg").write_text(
            svg, encoding="utf-8")
    sync_readme(data)
    print(f"reading: logged {data['reading_date']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
