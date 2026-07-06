#!/usr/bin/env python3
"""Render every SVG asset for the BOREHOLE MKS-01 profile README.

Single source of truth: both themes (light "field log", dark "night survey")
are generated from one palette dict and one set of drawing functions, so the
two modes can never drift. Hand-editing the SVGs in assets/ is forbidden —
edit this script and re-run it.

Usage:
    python3 scripts/render_assets.py            # render everything
    python3 scripts/render_assets.py --surface  # surface-conditions panel only
"""

import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

MONO = "Courier New, Courier, monospace"

PALETTES = {
    "light": {
        "bg": "#FAF6EF",       # field-log paper
        "ink": "#22303A",
        "water": "#1272B6",
        "laterite": "#C4552D",  # Sierra Leone soil
        "green": "#3E7C4F",
        "rule": "#D8D2C4",
        "faint": "#68757F",
        "plate": "#F3EDE0",     # label-plate fill, slightly deeper than paper
    },
    "dark": {
        "bg": "#0D141C",        # night monitoring station
        "ink": "#D7E3E0",
        "water": "#52C7EA",
        "laterite": "#E58B5B",
        "green": "#74C48F",
        "rule": "#2A3A47",
        "faint": "#748896",
        "plate": "#131E29",
    },
}

STRATA = [
    {
        "n": 1,
        "depth": "0.0 – 1.5 m",
        "label": "TOPSOIL — CURRENT WORK",
        "sub": "SUSTAINABLE AI · 2025–26 · ACTIVELY FORMING",
        "zone": "SAMPLE ZONE I",
        "texture": "stipple",
        "tint": "green",
    },
    {
        "n": 2,
        "depth": "1.5 – 3.0 m",
        "label": "ALLUVIUM — WATER & WEST AFRICA",
        "sub": "WATER-LAIN DEPOSITS",
        "zone": "SAMPLE ZONE II",
        "texture": "waves",
        "tint": "water",
    },
    {
        "n": 3,
        "depth": "3.0 – 5.0 m",
        "label": "CONSOLIDATED STRATA — DATA ANALYTICS",
        "sub": "2023–24 · TIGHTLY LAMINATED",
        "zone": "SAMPLE ZONE III",
        "texture": "laminae",
        "tint": "ink",
    },
    {
        "n": 4,
        "depth": "5 – 12 m",
        "label": "AQUIFER — EDUCATION",
        "sub": "RECHARGED ON THREE CONTINENTS",
        "zone": "SAMPLE ZONE IV",
        "texture": "porous",
        "tint": "water",
    },
    {
        "n": 5,
        "depth": "12 m +",
        "label": "BEDROCK — SIERRA LEONE",
        "sub": "CRYSTALLINE BASEMENT · REFUSAL",
        "zone": "END OF HOLE",
        "texture": "crosshatch",
        "tint": "laterite",
    },
]


def svg_open(w, h, title):
    attr_title = escape(title, {'"': "&quot;"})
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{attr_title}">\n'
        f"<title>{escape(title)}</title>\n"
    )


def text(x, y, s, size, p, color="ink", weight="normal", spacing=None,
         anchor="start", opacity=None, text_length=None):
    attrs = (
        f'x="{x}" y="{y}" font-family="{MONO}" font-size="{size}" '
        f'fill="{p[color]}" font-weight="{weight}" text-anchor="{anchor}"'
    )
    if spacing is not None:
        attrs += f' letter-spacing="{spacing}"'
    if opacity is not None:
        attrs += f' opacity="{opacity}"'
    if text_length is not None:
        attrs += f' textLength="{text_length}" lengthAdjust="spacingAndGlyphs"'
    return f"<text {attrs}>{escape(s)}</text>\n"


def frame(w, h, p):
    """Double hairline border, instrument-plate style."""
    return (
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{p["bg"]}"/>\n'
        f'<rect x="6.5" y="6.5" width="{w - 13}" height="{h - 13}" fill="none" '
        f'stroke="{p["ink"]}" stroke-width="1.5"/>\n'
        f'<rect x="12.5" y="12.5" width="{w - 25}" height="{h - 25}" fill="none" '
        f'stroke="{p["rule"]}" stroke-width="1"/>\n'
    )


# --------------------------------------------------------------------------
# 1. Masthead header
# --------------------------------------------------------------------------

def render_header(p, theme):
    w, h = 1200, 260
    s = svg_open(w, h, "Borehole log MKS-01 — Moses Kolleh Sesay. Site: Arnhem, "
                       "the Netherlands. Logged across Freetown, Changsha, "
                       "Wageningen and Arnhem. Purpose: water, climate, data.")
    s += frame(w, h, p)

    # Wordmark block, left
    s += text(48, 78, "BOREHOLE LOG · MKS-01", 28, p, color="laterite",
              weight="bold", spacing=5)
    s += text(48, 142, "MOSES KOLLEH SESAY", 56, p, weight="bold",
              text_length=640)
    s += text(48, 178, "HYDROGEOLOGIST → CLIMATE-TECH BUILDER", 19, p,
              color="faint", spacing=2)

    # Metadata rows
    s += f'<line x1="48" y1="198" x2="740" y2="198" stroke="{p["rule"]}" stroke-width="1"/>\n'
    s += text(48, 221, "SITE: ARNHEM NL · 51.98° N 5.91° E · NEDERRIJN KM 884", 17,
              p, color="faint")
    s += text(48, 243, "LOGGED ACROSS: FREETOWN → CHANGSHA → WAGENINGEN → ARNHEM",
              17, p, color="faint")

    # Drill derrick over the Nederrijn, right — the page's only looping motion
    ink, water = p["ink"], p["water"]
    s += f'<g stroke="{ink}" stroke-width="2" fill="none" stroke-linecap="round">\n'
    s += '<path d="M905 190 L965 58 L1025 190"/>\n'                    # legs
    s += '<path d="M921 155 L1009 155 M934 126 L996 126 M947 97 L983 97"/>\n'
    s += '<path d="M921 155 L996 126 M1009 155 L934 126"/>\n'          # braces
    s += f'<rect x="953" y="46" width="24" height="14" stroke="{ink}"/>\n'  # crown
    s += '<path d="M965 60 L965 190"/>\n'                              # string
    s += f'<path d="M782 190 L1148 190" stroke-width="2.5"/>\n'        # ground
    s += "</g>\n"
    # drill bit below ground
    s += f'<path d="M958 190 L972 190 L965 206 Z" fill="{ink}"/>\n'
    # water lines, animated drift
    s += '<g>\n'
    for i, y in enumerate((216, 228, 240)):
        s += (
            f'<path d="M800 {y} q 22 -7 44 0 t 44 0 t 44 0 t 44 0 t 44 0 t 44 0 t 44 0" '
            f'fill="none" stroke="{water}" stroke-width="2" opacity="{0.9 - i * 0.25}"/>\n'
        )
    s += ('<animateTransform attributeName="transform" type="translate" '
          'values="0 0; -8 0; 0 0; 8 0; 0 0" dur="8s" repeatCount="indefinite"/>\n')
    s += "</g>\n"

    s += text(w - 24, 34, "FIG. 1 — MASTHEAD · SHEET 1 OF 1", 13, p,
              color="faint", anchor="end", spacing=1.5)
    s += "</svg>\n"
    return s


# --------------------------------------------------------------------------
# 2. Surface conditions — de dagelijkse peiling
# --------------------------------------------------------------------------

def _month_label(iso):
    """'2026-07' or '2026-07-06' -> 'JUL 2026'."""
    from datetime import datetime
    fmt = "%Y-%m" if len(iso) == 7 else "%Y-%m-%d"
    return datetime.strptime(iso, fmt).strftime("%b %Y").upper()


def render_surface(p, theme, data):
    w, h = 1200, 180
    rhine = data["rhine"]
    co2 = data["co2"]
    archival = data.get("archival", True)
    date_label = data["peiling_date"]

    def source_line(default, sounded):
        """A field log never lies — a value not refreshed on peiling day is
        labelled with the date it was actually sounded."""
        if archival or not sounded or sounded == date_label:
            return default, "faint"
        return f"CARRIED FORWARD · {sounded}", "laterite"

    s = svg_open(w, h, f"Surface conditions panel. Rhine discharge at Lobith "
                       f"{rhine['latest']:,.0f} cubic metres per second; "
                       f"atmospheric CO2 {co2['latest']:.1f} ppm (NOAA global "
                       f"trend); reading dated {date_label}.")
    s += frame(w, h, p)

    # cell separators
    for x in (400, 800):
        s += f'<line x1="{x}" y1="20" x2="{x}" y2="{h - 20}" stroke="{p["rule"]}" stroke-width="1"/>\n'

    # ---- Left cell: Rhine discharge at Lobith -----------------------------
    s += text(36, 48, "RIJN @ LOBITH — AFVOER", 16, p, color="faint", spacing=2)
    s += text(36, 92, f"{rhine['latest']:,.0f}".replace(",", " ") + " m³/s", 46,
              p, color="water", weight="bold")

    series = [float(v) for v in rhine["series"][-30:]]
    # fixed reference band, auto-expanded so a flood never renders as a clamp
    lo = min(800.0, min(series) * 0.95)
    hi = max(4200.0, max(series) * 1.06)
    bx0, bx1, by0, by1 = 36, 376, 106, 150   # sparkline box
    def sy(v):
        return by1 - (float(v) - lo) / (hi - lo) * (by1 - by0)
    # normal-range guides (≈1 100 – 4 000 m³/s)
    for guide, glabel in ((4000, "4 000"), (1100, "1 100")):
        gy = sy(guide)
        s += (f'<line x1="{bx0}" y1="{gy:.1f}" x2="{bx1}" y2="{gy:.1f}" '
              f'stroke="{p["rule"]}" stroke-width="1" stroke-dasharray="3 4"/>\n')
        s += text(396, round(gy + 4, 1), glabel, 11, p, color="faint",
                  anchor="end")
    if len(series) > 1:
        step = (bx1 - bx0) / (len(series) - 1)
        pts = " ".join(f"{bx0 + i * step:.1f},{sy(v):.1f}" for i, v in enumerate(series))
        s += (f'<polyline points="{pts}" fill="none" stroke="{p["water"]}" '
              f'stroke-width="2.5" stroke-linejoin="round"/>\n')
        lx = bx0 + (len(series) - 1) * step
        s += f'<circle cx="{lx:.1f}" cy="{sy(series[-1]):.1f}" r="4" fill="{p["water"]}"/>\n'
    r_line, r_color = source_line("30-DAY SOUNDING · RIJKSWATERSTAAT",
                                  rhine.get("sounded"))
    s += text(36, 166, r_line, 12, p, color=r_color, spacing=1.5)

    # ---- Middle cell: atmospheric CO2 -------------------------------------
    s += text(436, 48, "ATMOSPHERE — CO₂", 16, p, color="faint", spacing=2)
    s += text(436, 92, f"{co2['latest']:.1f} ppm", 46, p, color="green",
              weight="bold")
    monthly = co2["monthly"][-12:]
    if monthly:
        mlo, mhi = min(monthly), max(monthly)
        span = (mhi - mlo) or 1.0
        for i, v in enumerate(monthly):
            bar_h = 8 + (v - mlo) / span * 34
            bx = 436 + i * 28
            s += (f'<rect x="{bx}" y="{150 - bar_h:.1f}" width="14" '
                  f'height="{bar_h:.1f}" fill="{p["green"]}" opacity="{0.35 + 0.5 * i / 11:.2f}"/>\n')
    c_line, c_color = source_line("NOAA GLOBAL TREND · TRAILING 12 MO",
                                  co2.get("sounded"))
    s += text(436, 166, c_line, 12, p, color=c_color, spacing=1.5)

    # ---- Right cell: the date stamp ---------------------------------------
    s += text(836, 48, "PEILING", 16, p, color="faint", spacing=2)
    s += text(836, 92, date_label, 40, p, weight="bold")
    if archival:
        s += text(836, 130, f"ARCHIVAL READING — {_month_label(date_label)}",
                  20, p, color="laterite", weight="bold", spacing=1)
        s += text(836, 154, "AWAITING FIRST AUTOMATED SOUNDING", 13, p,
                  color="faint", spacing=1)
    else:
        s += text(836, 126, "CONDITIONS AT TIME OF LOGGING", 15, p,
                  color="faint", spacing=1)
        s += text(836, 150, "TAKEN DAILY · 05:15 UTC", 13, p, color="faint",
                  spacing=1)

    s += text(w - 24, 34, "FIG. 2 — SURFACE CONDITIONS", 13, p, color="faint",
              anchor="end", spacing=1.5)
    s += "</svg>\n"
    return s


# --------------------------------------------------------------------------
# 3. Strata dividers
# --------------------------------------------------------------------------

def _texture_defs(kind, uid, p, tint):
    c = p[tint]
    if kind == "stipple":
        return (
            f'<pattern id="{uid}" width="26" height="18" patternUnits="userSpaceOnUse">'
            f'<circle cx="5" cy="5" r="1.7" fill="{c}"/>'
            f'<circle cx="17" cy="12" r="1.4" fill="{c}"/>'
            f'<circle cx="23" cy="4" r="1.2" fill="{c}"/>'
            f"</pattern>"
        )
    if kind == "waves":
        return (
            f'<pattern id="{uid}" width="64" height="16" patternUnits="userSpaceOnUse">'
            f'<path d="M0 8 Q 16 2 32 8 T 64 8" fill="none" stroke="{c}" stroke-width="1.4"/>'
            f"</pattern>"
        )
    if kind == "laminae":
        return (
            f'<pattern id="{uid}" width="10" height="7" patternUnits="userSpaceOnUse">'
            f'<line x1="0" y1="3.5" x2="10" y2="3.5" stroke="{c}" stroke-width="1"/>'
            f"</pattern>"
        )
    if kind == "porous":
        return (
            f'<pattern id="{uid}" width="34" height="24" patternUnits="userSpaceOnUse">'
            f'<circle cx="8" cy="7" r="2.6" fill="none" stroke="{c}" stroke-width="1.2"/>'
            f'<circle cx="25" cy="17" r="2.2" fill="none" stroke="{c}" stroke-width="1.2"/>'
            f"</pattern>"
        )
    # crosshatch
    return (
        f'<pattern id="{uid}" width="14" height="14" patternUnits="userSpaceOnUse">'
        f'<path d="M0 14 L14 0 M-3 3 L3 -3 M11 17 L17 11" stroke="{c}" stroke-width="1"/>'
        f'<path d="M0 0 L14 14 M11 -3 L17 3 M-3 11 L3 17" stroke="{c}" stroke-width="0.7" opacity="0.6"/>'
        f"</pattern>"
    )


def render_stratum(p, theme, spec):
    w, h = 1200, 110
    uid = f"tx{spec['n']}{theme[0]}"
    title = f"Stratum {spec['n']} divider: {spec['label']}, depth {spec['depth']}."
    s = svg_open(w, h, title)
    s += f"<defs>{_texture_defs(spec['texture'], uid, p, spec['tint'])}</defs>\n"
    s += frame(w, h, p)

    # texture band
    s += f'<rect x="90" y="13" width="{w - 103}" height="{h - 26}" fill="url(#{uid})" opacity="0.5"/>\n'

    # depth ruler, left
    s += f'<line x1="90" y1="13" x2="90" y2="{h - 13}" stroke="{p["ink"]}" stroke-width="1.5"/>\n'
    for i in range(0, 11):
        y = 13 + i * (h - 26) / 10
        tick = 12 if i % 5 == 0 else 7
        s += (f'<line x1="{90 - tick}" y1="{y:.1f}" x2="90" y2="{y:.1f}" '
              f'stroke="{p["ink"]}" stroke-width="1"/>\n')
    s += text(24, 34, "DEPTH", 11, p, color="faint", spacing=1)
    s += text(24, 52, spec["depth"].split("–")[0].strip() if "–" in spec["depth"] else spec["depth"],
              13, p, weight="bold")
    s += text(24, 92, spec["depth"].split("–")[1].strip() if "–" in spec["depth"] else "",
              13, p, weight="bold")

    # label plate
    label_w = 30 + len(spec["label"]) * 20
    s += (f'<rect x="118" y="26" width="{label_w}" height="58" fill="{p["plate"]}" '
          f'stroke="{p["rule"]}" stroke-width="1"/>\n')
    s += text(134, 58, spec["label"], 32, p, weight="bold")
    s += text(134, 76, spec["sub"], 14, p, color="faint", spacing=1.5)

    # zone tag, right
    s += text(w - 28, 62, spec["zone"], 15, p, color=spec["tint"], anchor="end",
              weight="bold", spacing=2)

    # water table marker on the aquifer stratum
    if spec["texture"] == "porous":
        s += (f'<line x1="90" y1="90" x2="{w - 13}" y2="90" stroke="{p["water"]}" '
              f'stroke-width="1.6" stroke-dasharray="10 5"/>\n')
        s += (f'<path d="M1022 76 L1040 76 L1031 89 Z" fill="none" '
              f'stroke="{p["water"]}" stroke-width="2"/>\n')
        s += text(1050, 86, "WATER TABLE", 12, p, color="water", spacing=1.5)

    s += "</svg>\n"
    return s


# --------------------------------------------------------------------------
# 4. Drill path — recharge route across three continents
# --------------------------------------------------------------------------

def render_drill_path(p, theme):
    w, h = 1200, 420
    s = svg_open(w, h, "Recharge path, source to delta: Freetown, Sierra Leone "
                       "(Bintumani massif, 1945 m) to Changsha, China, to "
                       "Wageningen and Arnhem, the Netherlands (Nederrijn "
                       "floodplain, around NAP 0 m).")
    s += frame(w, h, p)

    def ey(elev):  # elevation (m) -> y
        return 340 - elev / 2000.0 * 250

    # elevation gridlines
    for elev in (2000, 1500, 1000, 500):
        y = ey(elev)
        s += (f'<line x1="80" y1="{y:.0f}" x2="{w - 40}" y2="{y:.0f}" '
              f'stroke="{p["rule"]}" stroke-width="1" stroke-dasharray="2 6"/>\n')
        s += text(72, y + 4, f"{elev}", 12, p, color="faint", anchor="end")
    # sea level / NAP line
    s += (f'<line x1="80" y1="340" x2="{w - 40}" y2="340" stroke="{p["water"]}" '
          f'stroke-width="1.6" stroke-dasharray="10 5"/>\n')
    s += text(w - 40, 358, "NAP · SEA LEVEL", 13, p, color="water", anchor="end",
              spacing=1.5)
    s += text(72, 344, "0 m", 12, p, color="faint", anchor="end")

    fx, fy = 190, ey(1945)
    cx, cy = 620, ey(44)
    ax, ay = 1030, ey(13)

    # the descending path
    s += (f'<path d="M{fx} {fy:.0f} C 290 210, 470 300, {cx} {cy:.0f} '
          f'S 900 {ay:.0f}, {ax} {ay:.0f}" fill="none" stroke="{p["ink"]}" '
          f'stroke-width="2" stroke-dasharray="8 7"/>\n')

    # Source: the Bintumani massif — Sierra Leone's roof, where the rivers rise
    s += f'<circle cx="{fx}" cy="{fy:.0f}" r="8" fill="{p["laterite"]}"/>\n'
    s += text(fx + 22, fy - 14, "SOURCE — BINTUMANI MASSIF · 1 945 m", 20, p,
              weight="bold")
    s += text(fx + 22, fy + 10, "SIERRA LEONE · FREETOWN 8.48° N", 15, p,
              color="laterite", spacing=1)
    s += text(fx + 22, fy + 32, "BSc HONS GEOLOGY & HYDROGEOLOGY", 13, p,
              color="faint", spacing=1)

    # Changsha — labels below the point (it sits near sea level)
    s += f'<circle cx="{cx}" cy="{cy:.0f}" r="7" fill="{p["ink"]}"/>\n'
    s += text(cx, cy + 34, "CHANGSHA · 28.2° N", 20, p, weight="bold",
              anchor="middle")
    s += text(cx, cy + 56, "MSc INDUSTRIAL ENGINEERING · HUNAN UNIVERSITY",
              13, p, color="faint", spacing=1, anchor="middle")

    # Wageningen / Arnhem — stacked well above the floodplain point
    s += f'<circle cx="{ax}" cy="{ay:.0f}" r="8" fill="{p["water"]}"/>\n'
    s += text(ax + 60, ay - 110, "WAGENINGEN / ARNHEM · 51.98° N", 20, p,
              weight="bold", anchor="end")
    s += text(ax + 60, ay - 88, "NEDERRIJN FLOODPLAIN · ≈ NAP", 15, p,
              color="water", anchor="end", spacing=1)
    s += text(ax + 60, ay - 68, "MSc ENVIRONMENTAL SCIENCES · WAGENINGEN UR",
              13, p, color="faint", anchor="end", spacing=1)
    s += (f'<line x1="{ax}" y1="{ay - 58:.0f}" x2="{ax}" y2="{ay - 14:.0f}" '
          f'stroke="{p["rule"]}" stroke-width="1"/>\n')

    s += text(w - 24, 34, "FIG. 3 — RECHARGE PATH · SOURCE TO DELTA", 13, p,
              color="faint", anchor="end", spacing=1.5)
    s += "</svg>\n"
    return s


# --------------------------------------------------------------------------

def load_soundings():
    with open(ASSETS / "soundings.json", encoding="utf-8") as f:
        return json.load(f)


def write(name, content):
    ASSETS.mkdir(exist_ok=True)
    path = ASSETS / name
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def render_surface_pair():
    data = load_soundings()
    for theme, p in PALETTES.items():
        write(f"surface-conditions-{theme}.svg", render_surface(p, theme, data))


def render_all():
    for theme, p in PALETTES.items():
        write(f"header-{theme}.svg", render_header(p, theme))
        for spec in STRATA:
            write(f"stratum-{spec['n']}-{theme}.svg", render_stratum(p, theme, spec))
        write(f"drill-path-{theme}.svg", render_drill_path(p, theme))
    render_surface_pair()


if __name__ == "__main__":
    if "--surface" in sys.argv:
        render_surface_pair()
    else:
        render_all()
