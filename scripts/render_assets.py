#!/usr/bin/env python3
"""Render the SVG figures for the profile README.

Two figures, each in a light and a dark version drawn from one palette
dict and one set of functions, so the two themes cannot drift apart:

  banner-{theme}.svg    the name, under a hyetograph of the last 30 days
                        of rain at Monza (bars hang from the top, the way
                        hydrologists draw rainfall)
  readings-{theme}.svg  two stat tiles: Rhine discharge at Lobith and
                        atmospheric CO2, each with a small trend line

Both are drawn from assets/soundings.json, which scripts/update_readings.py
refreshes every morning. Do not edit the SVGs by hand: change this script
and run it again.

Design notes
  - Transparent background, GitHub's own text colours and system font, so
    the figures sit on the page instead of in a box.
  - Type is sized for a README column that scales the 840-unit canvas down
    to about 340 px on a phone: the name and the headline values stay
    legible there; the small labels are also given as plain text in the
    README (see readings_line).
  - Every value shows the date it was actually read. A source that is down
    therefore shows an older date, never a number that only looks fresh.

Usage:
    python3 scripts/render_assets.py
"""

import json
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

W = 840
SANS = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', "
        "Helvetica, Arial, sans-serif")

# Text and rule colours follow GitHub's light and dark themes. The two data
# colours are a validated pair (colour-blind separation and 3:1 contrast on
# both surfaces): blue for water, orange for the atmosphere.
PALETTES = {
    "light": {
        "surface": "#ffffff",
        "fg": "#1f2328",
        "sub": "#59636e",
        "rule": "#d1d9e0",
        "water": "#2a78d6",
        "air": "#eb6834",
    },
    "dark": {
        "surface": "#0d1117",
        "fg": "#f0f6fc",
        "sub": "#9198a1",
        "rule": "#3d444d",
        "water": "#3987e5",
        "air": "#d95926",
    },
}


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def svg_open(w, h, title, style=""):
    attr_title = escape(title, {'"': "&quot;"})
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{attr_title}" '
        f'font-family="{SANS}">\n'
        f"<title>{escape(title)}</title>\n"
        + (f"<style>{style}</style>\n" if style else "")
    )


def text(x, y, s, size, fill, weight=400, anchor="start", spacing=None):
    attrs = (f'x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
             f'font-weight="{weight}" text-anchor="{anchor}"')
    if spacing is not None:
        attrs += f' letter-spacing="{spacing}"'
    return f"<text {attrs}>{s}</text>\n"


def rule(x1, x2, y, p):
    return (f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" '
            f'stroke="{p["rule"]}" stroke-width="1"/>\n')


def nice_date(iso):
    """'2026-11-09' -> '9 Nov 2026'."""
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {d.strftime('%b %Y')}"


def short_date(iso):
    """'2026-10-30' -> '30 Oct'."""
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {d.strftime('%b')}"


def read_on(block, data):
    """The date a value was actually read (falls back to the log's date)."""
    return block.get("sounded") or data["reading_date"]


def num(v, decimals=0):
    return f"{v:,.{decimals}f}"


# --------------------------------------------------------------------------
# 1. Banner: the name, under the last 30 days of rain at Monza
# --------------------------------------------------------------------------

BANNER_STYLE = (
    "@media (prefers-reduced-motion: no-preference){"
    ".b{transform-box:fill-box;transform-origin:50% 0;"
    "animation:fall .8s cubic-bezier(.2,.7,.2,1) both}"
    "@keyframes fall{from{transform:scaleY(0)}}}"
)


def _hanging_bar(x, y0, w, h, fill, delay):
    """A bar hanging from the baseline y0: square where it meets the
    baseline, rounded at the data end."""
    r = min(4.0, w / 2, h)
    d = (f"M{x:.1f} {y0} h{w:.1f} v{h - r:.1f} "
         f"a{r:.1f} {r:.1f} 0 0 1 -{r:.1f} {r:.1f} h-{w - 2 * r:.1f} "
         f"a{r:.1f} {r:.1f} 0 0 1 -{r:.1f} -{r:.1f} Z")
    return (f'<path class="b" style="animation-delay:{delay}ms" d="{d}" '
            f'fill="{fill}"/>\n')


def render_banner(p, theme, data):
    h = 232
    rain = data.get("rain")
    base_y, max_h = 30, 74        # baseline of the hyetograph, tallest bar

    if rain:
        total = rain["total_30d"]
        title = (f"Moses Kolleh Sesay, hydrogeologist turned flood-risk "
                 f"researcher, IUSS Pavia. Above the name, the last 30 days "
                 f"of rain at Monza drawn as bars hanging from the top: "
                 f"{num(total)} mm in total, read "
                 f"{nice_date(read_on(rain, data))}.")
    else:
        title = ("Moses Kolleh Sesay, hydrogeologist turned flood-risk "
                 "researcher, IUSS Pavia.")
    s = svg_open(W, h, title, BANNER_STYLE)

    # ---- hyetograph ------------------------------------------------------
    s += text(0, 17, "Rain over Monza, last 30 days", 13, p["sub"])
    if rain:
        s += text(W, 17,
                  f'<tspan fill="{p["fg"]}" font-weight="600">'
                  f'{num(total)} mm</tspan> · read '
                  f'{nice_date(read_on(rain, data))}',
                  13, p["sub"], anchor="end")
    else:
        s += text(W, 17, "awaiting the first reading", 13, p["sub"],
                  anchor="end")
    s += rule(0, W, base_y - 0.5, p)

    # one tick per day, so the axis reads as 30 days even in a dry month
    slot = W / 30
    for i in range(30):
        x = i * slot + slot / 2
        s += (f'<line x1="{x:.1f}" y1="{base_y}" x2="{x:.1f}" '
              f'y2="{base_y + 4}" stroke="{p["rule"]}" stroke-width="1"/>\n')

    daily = [float(v) for v in (rain["daily"][-30:] if rain else [])]
    if daily and max(daily) > 0:
        # 20 mm/day fills the scale unless a storm needs more, so a month
        # of drizzle is not drawn as a month of downpours
        top = max(20.0, max(daily))
        bar_w = 12
        offset = 30 - len(daily)   # a short series is right-aligned on today
        for i, v in enumerate(daily):
            if v <= 0:
                continue
            bar_h = max(1.5, v / top * max_h)
            x = (i + offset) * slot + (slot - bar_w) / 2
            s += _hanging_bar(x, base_y, bar_w, bar_h, p["water"],
                              (i + offset) * 22)
        # one label only: the wettest day
        peak = max(range(len(daily)), key=lambda i: daily[i])
        px = (peak + offset) * slot + slot / 2
        py = base_y + max(1.5, daily[peak] / top * max_h) + 17
        label = f"{num(daily[peak])} mm"
        days = rain.get("days") or []
        if len(days) == len(rain["daily"]):
            label += f" on {short_date(days[-30:][peak])}"
        anchor = "middle"
        if px < 70:
            px, anchor = (peak + offset) * slot + 8, "start"
        elif px > W - 70:
            px, anchor = (peak + offset + 1) * slot - 8, "end"
        s += text(f"{px:.1f}", f"{py:.1f}", label, 12, p["sub"],
                  anchor=anchor)
    elif rain:
        s += text(0, base_y + 22, "No rain recorded", 12, p["sub"])

    # ---- name ------------------------------------------------------------
    s += text(-2, 182, "Moses Kolleh Sesay", 46, p["fg"], weight=600,
              spacing="-0.6")
    s += text(0, 214,
              "Hydrogeologist turned flood-risk researcher · IUSS Pavia",
              17, p["sub"])
    s += "</svg>\n"
    return s


# --------------------------------------------------------------------------
# 2. Readings: Rhine discharge and atmospheric CO2
# --------------------------------------------------------------------------

def _trend(values, x0, x1, y0, y1, color, p, peak_fmt=None):
    """A 2 px trend line scaled to its own range, with an end marker and,
    when peak_fmt is given, a single label on the highest point (the
    headline value names the end)."""
    vals = [float(v) for v in values]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    step = (x1 - x0) / (len(vals) - 1)

    def xy(i):
        y = (y0 + y1) / 2 if hi == lo else y1 - (vals[i] - lo) / span * (y1 - y0)
        return x0 + i * step, y

    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in map(xy, range(len(vals))))
    out = (f'<polyline points="{pts}" fill="none" stroke="{color}" '
           f'stroke-width="2" stroke-linejoin="round" '
           f'stroke-linecap="round"/>\n')
    ex, ey = xy(len(vals) - 1)
    out += (f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="4.5" fill="{color}" '
            f'stroke="{p["surface"]}" stroke-width="2"/>\n')
    peak = max(range(len(vals)), key=lambda i: vals[i])
    if peak_fmt and hi > lo and peak < len(vals) - 2:
        px, py = xy(peak)
        anchor = "start" if px < x0 + 24 else "middle"
        out += text(f"{px:.1f}", f"{py - 9:.1f}", peak_fmt(hi), 12, p["sub"],
                    anchor=anchor)
    return out


def _tile(x, w, p, label, value, unit, notes, chart):
    s = rule(x, x + w, 0.5, p)
    s += text(x, 27, label, 13, p["sub"])
    s += text(x, 70,
              f'{value}<tspan font-size="15" font-weight="400" '
              f'fill="{p["sub"]}" dx="6">{unit}</tspan>',
              36, p["fg"], weight=600, spacing="-0.4")
    for i, note in enumerate(notes):
        s += text(x, 96 + i * 18, note, 12, p["sub"])
    return s + chart


def render_readings(p, theme, data):
    h = 128
    rhine, co2 = data["rhine"], data["co2"]
    title = (f"Rhine discharge at Lobith {num(rhine['latest'])} cubic metres "
             f"per second, read {nice_date(read_on(rhine, data))}, with its "
             f"30-day trend. Atmospheric CO2 {num(co2['latest'], 1)} parts "
             f"per million, read {nice_date(read_on(co2, data))}, with its "
             f"12-month trend.")
    s = svg_open(W, h, title)
    tile_w, gap = 396, 48
    x2 = tile_w + gap

    s += _tile(
        0, tile_w, p, "Rhine discharge at Lobith", num(rhine["latest"]),
        "m³/s",
        ["30 days · Rijkswaterstaat",
         f"read {nice_date(read_on(rhine, data))}"],
        _trend(rhine["series"][-30:], 250, tile_w - 8, 36, 112, p["water"],
               p, num))
    # The headline is NOAA's deseasonalised trend; the line is the monthly
    # mean, which still carries the seasonal cycle. The line is therefore
    # left unlabelled, so no number on it is read against the headline.
    s += _tile(
        x2, tile_w, p, "Atmospheric CO₂, global trend",
        num(co2["latest"], 1), "ppm",
        ["Line: 12 monthly means · NOAA",
         f"read {nice_date(read_on(co2, data))}"],
        _trend(co2["monthly"][-12:], x2 + 250, x2 + tile_w - 8, 36, 112,
               p["air"], p))
    s += "</svg>\n"
    return s


# --------------------------------------------------------------------------
# 3. The same readings as plain text, for the README
# --------------------------------------------------------------------------

def readings_line(data):
    """One sentence of real text carrying the figures' numbers, so they stay
    readable on a phone, by a screen reader, and if the images fail. A value
    that was not refreshed on the day of the reading says when it was."""
    day = data["reading_date"]

    def stale(block):
        on = read_on(block, data)
        return "" if on == day else f" (last read {nice_date(on)})"

    parts = []
    rain = data.get("rain")
    if rain:
        parts.append(f"**{num(rain['total_30d'])} mm** of rain at Monza over "
                     f"30 days{stale(rain)}")
    rhine, co2 = data["rhine"], data["co2"]
    parts.append(f"the Rhine at Lobith carrying **{num(rhine['latest'])} "
                 f"m³/s**{stale(rhine)}")
    parts.append(f"the global CO₂ trend at **{num(co2['latest'], 1)} ppm**"
                 f"{stale(co2)}")
    return f"Read on {nice_date(day)}: " + " · ".join(parts) + "."


# --------------------------------------------------------------------------

def load_soundings():
    with open(ASSETS / "soundings.json", encoding="utf-8") as f:
        return json.load(f)


def render_all(data):
    """Return {filename: svg} for every figure in both themes."""
    out = {}
    for theme, p in PALETTES.items():
        out[f"banner-{theme}.svg"] = render_banner(p, theme, data)
        out[f"readings-{theme}.svg"] = render_readings(p, theme, data)
    return out


def write_all(svgs):
    ASSETS.mkdir(exist_ok=True)
    for name, content in svgs.items():
        (ASSETS / name).write_text(content, encoding="utf-8")
        print(f"wrote assets/{name}")


if __name__ == "__main__":
    write_all(render_all(load_soundings()))
