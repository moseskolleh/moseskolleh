#!/usr/bin/env python3
"""Daily readings — refresh the surface-conditions panel.

Fetches three open datasets and re-renders assets/surface-conditions-*.svg:

  1. Rhine discharge (Q, m3/s) at Lobith, from Rijkswaterstaat
     WaterWebservices (ddapi20) — where the Rhine enters the Netherlands.
  2. Daily rainfall at Monza, from ARPA Lombardia's rain gauges on the
     Open Data Lombardia portal — the province the PhD studies.
  3. Atmospheric CO2, from the NOAA GML global daily trend file.

FAIL-SOFT CONTRACT: a field log never lies — it just gets older. On ANY
fetch, parse, or schema error this script exits 0 WITHOUT writing, so the
previous dated reading stands. A partial success (some sources up, some
down) keeps the fresh sources and carries the stale values forward.

Stdlib only. Run from anywhere: paths resolve relative to this file.
"""

import csv
import io
import json
import sys
import urllib.parse
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

# The _DBO endpoints were retired in 2025 (they now answer 404); ddapi20 is
# their successor, with locations addressed by Code alone.
RWS_BASE = "https://ddapi20-waterwebservices.rijkswaterstaat.nl"
RWS_CATALOG = RWS_BASE + "/METADATASERVICES/OphalenCatalogus"
RWS_OBSERVATIONS = RWS_BASE + "/ONLINEWAARNEMINGENSERVICES/OphalenWaarnemingen"
# ARPA Lombardia on Socrata: the sensor register, then the recent readings.
# Which of the two reading datasets covers a given 30-day window shifts at
# month and year boundaries, so both are asked and merged.
LOMBARDIA = "https://www.dati.lombardia.it/resource"
ARPA_SENSORS = "nf78-nj6b"
ARPA_READINGS = ("i95f-5avh", "647i-nhxk")
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
        raw = resp.read().decode()
    if not raw.strip():   # ddapi20 answers 204 No Content when it has no data
        raise ValueError(f"empty response from {url}")
    return json.loads(raw)


def get_text(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode()


def find_lobith():
    """Look the station up in the catalogue rather than hardcoding a code
    that Rijkswaterstaat has already reshuffled once. Returns the request's
    Locatie and AquoMetadata, preferring a Lobith location the catalogue
    says carries measured discharge."""
    cat = post_json(RWS_CATALOG, {"CatalogusFilter": {
        "Grootheden": True, "Compartimenten": True, "Eenheden": True,
        "Hoedanigheden": True, "ProcesTypes": True,
    }})
    locs = [loc for loc in cat.get("LocatieLijst", [])
            if "lobith" in (loc.get("Naam") or "").strip().lower()]
    if not locs:
        raise LookupError("no Lobith station in RWS catalogue")

    q_meta = {m.get("AquoMetadata_MessageID"): m
              for m in cat.get("AquoMetadataLijst", [])
              if (m.get("Grootheid") or {}).get("Code") == "Q"}
    q_at = {}
    for link in cat.get("AquoMetadataLocatieLijst", []):
        # the catalogue spells this key two ways
        mid = link.get("AquoMetaData_MessageID", link.get("AquoMetadata_MessageID"))
        if mid in q_meta:
            q_at.setdefault(link.get("Locatie_MessageID"), []).append(q_meta[mid])

    def rank(loc):
        has_q = loc.get("Locatie_MessageID") in q_at
        exact = (loc.get("Naam") or "").strip().lower() == "lobith"
        return (not has_q, not exact)

    loc = sorted(locs, key=rank)[0]
    metas = q_at.get(loc.get("Locatie_MessageID"), [])
    # measured values, not forecasts, when the catalogue offers both
    metas.sort(key=lambda m: str(m.get("ProcesType", "meting")).lower() != "meting")
    aquo = {"Compartiment": {"Code": "OW"}, "Grootheid": {"Code": "Q"}}
    if metas:
        for key in ("Compartiment", "Eenheid", "Grootheid", "Hoedanigheid"):
            code = (metas[0].get(key) or {}).get("Code")
            if code:
                aquo[key] = {"Code": code}
        if metas[0].get("ProcesType"):
            aquo["ProcesType"] = metas[0]["ProcesType"]
    return {"Code": loc["Code"]}, aquo


def fetch_rhine():
    """Return (latest_value, series_of_daily_means) for discharge at Lobith."""
    loc, aquo = find_lobith()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    body = {
        "Locatie": loc,
        "AquoPlusWaarnemingMetadata": {"AquoMetadata": aquo},
        "Periode": {
            "Begindatumtijd": start.strftime("%Y-%m-%dT%H:%M:%S.000+00:00"),
            "Einddatumtijd": end.strftime("%Y-%m-%dT%H:%M:%S.000+00:00"),
        },
    }
    data = post_json(RWS_OBSERVATIONS, body)
    per_day = {}
    for wl in data.get("WaarnemingenLijst", []):
        for m in wl.get("MetingenLijst", []):
            if (m.get("WaarnemingMetadata") or {}).get("Kwaliteitswaardecode") == "99":
                continue   # flagged invalid
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


def socrata(dataset, params):
    query = urllib.parse.urlencode(params)
    return json.loads(get_text(f"{LOMBARDIA}/{dataset}.json?{query}"))


def find_monza_gauge():
    """The active ARPA Lombardia rain gauge in Monza, from the sensor
    register — looked up, not hardcoded, because gauges get replaced."""
    rows = socrata(ARPA_SENSORS, {"tipologia": "Precipitazione",
                                  "provincia": "MB", "$limit": 500})
    monza = [r for r in rows
             if "monza" in (r.get("nomestazione") or "").lower()
             and r.get("idsensore")]
    if not monza:
        raise LookupError("no Monza rain gauge in the ARPA sensor register")
    # active gauges first (storico "N"), then the longest-running
    monza.sort(key=lambda r: (r.get("storico", "N") != "N",
                              r.get("datastart") or "9999"))
    return str(monza[0]["idsensore"]), monza[0].get("nomestazione", "Monza")


def fetch_rain():
    """Return (station_name, 30_day_total_mm, daily_totals_mm) for Monza."""
    sensor, name = find_monza_gauge()
    since = (datetime.now(timezone.utc) - timedelta(days=31)).strftime(
        "%Y-%m-%dT00:00:00.000")
    readings, failures = {}, []
    for dataset in ARPA_READINGS:
        try:
            rows = socrata(dataset, {"idsensore": sensor,
                                     "$where": f"data >= '{since}'",
                                     "$limit": 50000})
        except Exception as exc:  # noqa: BLE001 — the other dataset may hold it
            failures.append(f"{dataset}: {exc}")
            continue
        for r in rows:
            try:
                v = float(r["valore"])
            except (KeyError, TypeError, ValueError):
                continue
            # -9999 is ARPA's missing-data code; rain is mm per 10 minutes
            if 0 <= v < 500:
                readings[r.get("data", "")[:19]] = v
    if not readings:
        raise ValueError("no Monza rain readings" +
                         (f" ({'; '.join(failures)})" if failures else ""))
    per_day = {}
    for t, v in readings.items():
        per_day[t[:10]] = per_day.get(t[:10], 0.0) + v
    days = sorted(per_day)[-30:]
    if len(days) < 7:
        raise ValueError(f"only {len(days)} days of Monza rain readings")
    daily = [round(per_day[d], 1) for d in days]
    return name, round(sum(daily), 1), daily


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
        rain = data.get("rain")
        rain_alt = (f"rain at Monza {rain['total_30d']:.0f} mm over 30 days; "
                    if rain else "")
        alt = (f"Surface conditions {data['reading_date']}: Rhine discharge at "
               f"Lobith {data['rhine']['latest']:,.0f} m3/s, 30-day sounding; "
               f"{rain_alt}atmospheric CO2 {data['co2']['latest']:.1f} ppm, "
               f"NOAA global trend.")
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

    fresh = {"rhine": None, "rain": None, "co2": None}
    for key, fetch in (("rhine", fetch_rhine), ("rain", fetch_rain),
                       ("co2", fetch_co2)):
        try:
            fresh[key] = fetch()
        except Exception as exc:  # noqa: BLE001 — fail-soft by contract
            print(f"reading: {key} source unavailable ({exc}); carrying prior value")

    if all(v is None for v in fresh.values()):
        print("reading: every source down; prior dated reading stands")
        return 0

    today = date.today().isoformat()
    try:
        data = dict(prior)
        if fresh["rhine"] is not None:
            latest, series = fresh["rhine"]
            data["rhine"] = {"latest": latest, "series": series,
                             "station": "Lobith", "quantity": "Q",
                             "unit": "m3/s", "sounded": today}
        if fresh["rain"] is not None:
            station, total, daily = fresh["rain"]
            data["rain"] = {"station": station, "total_30d": total,
                            "daily": daily, "unit": "mm",
                            "source": "ARPA Lombardia", "sounded": today}
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
