"""Generate destination-themed SVG illustrations for the sample hotels.

Run:  python tools/make_hotel_images.py
Writes static/img/hotels/<hotel-id>.svg and fallback.svg. Local files always
load (no hot-linking, no licence issues). Swap in real photos by adding an
"image_url" to a hotel in data/hotels.json - the UI falls back to these SVGs
if a remote image fails to load.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "img" / "hotels"

PAL = {  # sky top, sky bottom, sun, ground, accent
    "beach": ("#5ec8f2", "#ffe3b3", "#ffd166", "#f4d7a1", "#2a9d8f"),
    "fort": ("#f7a072", "#ffe0c2", "#fff1a8", "#d9a066", "#c8553d"),
    "city": ("#6d83f2", "#f5c6ec", "#ffe29a", "#9aa5b1", "#5f4bb6"),
    "sea": ("#1d3557", "#e76f51", "#ffb703", "#2a4d69", "#f4a261"),
    "garden": ("#8ecae6", "#e9f5db", "#fff3b0", "#95d5b2", "#2d6a4f"),
    "backwater": ("#90e0ef", "#fefae0", "#ffd60a", "#52b788", "#1b4332"),
    "lake": ("#ffafcc", "#ffe5d9", "#fff0a5", "#a2d2ff", "#6a4c93"),
    "desert": ("#ffb347", "#ffe8c7", "#fff5b1", "#e9c46a", "#264653"),
    "skyline": ("#3a0ca3", "#f72585", "#ffd166", "#4361ee", "#4cc9f0"),
    "temple": ("#ff9e00", "#ffe8a3", "#fff3b0", "#c9a227", "#9d0208"),
    "london": ("#577590", "#d8e2dc", "#f9e79f", "#6c757d", "#8d0801"),
}


def backdrop(theme, p):
    top, bot, sun, ground, acc = p
    s = []
    if theme in ("beach", "backwater", "lake", "sea", "skyline", "temple", "london"):
        s.append(f'<rect y="150" width="400" height="90" fill="{acc}" opacity=".55"/>')
    if theme == "beach":
        s.append(f'<path d="M0 185 Q200 165 400 185 V240 H0Z" fill="{ground}"/>')
        for x in (40, 350):
            s.append(f'<path d="M{x} 200 q6 -40 2 -80" stroke="#6b4226" stroke-width="5" fill="none"/>'
                     f'<path d="M{x+2} 120 q-30 -5 -40 12 M{x+2} 120 q30 -8 42 8 M{x+2} 120 q-18 -22 -34 -18 M{x+2} 120 q20 -22 36 -14" stroke="#2d6a4f" stroke-width="6" fill="none" stroke-linecap="round"/>')
    elif theme == "fort":
        s.append(f'<path d="M0 160 Q90 110 180 150 T400 140 V240 H0Z" fill="{acc}" opacity=".45"/>')
        s.append(f'<path d="M20 150 h14 v-8 h8 v8 h14 v-8 h8 v8 h14 v-8 h8 v8 h14 v30 h-80z" fill="{acc}" opacity=".8"/>')
        s.append(f'<rect y="178" width="400" height="62" fill="{ground}"/>')
    elif theme == "city":
        for i, h in enumerate((60, 90, 50, 110, 70, 85, 55)):
            s.append(f'<rect x="{10+i*56}" y="{180-h}" width="44" height="{h}" fill="{acc}" opacity=".35"/>')
        s.append(f'<path d="M300 180 v-40 a22 22 0 0 1 44 0 v40 h-10 v-30 a12 12 0 0 0 -24 0 v30z" fill="{acc}" opacity=".6"/>')
        s.append(f'<rect y="178" width="400" height="62" fill="{ground}"/>')
    elif theme == "sea":
        for i, h in enumerate((40, 70, 55, 90, 60, 45)):
            s.append(f'<rect x="{200+i*33}" y="{150-h}" width="26" height="{h}" fill="#0b132b" opacity=".6"/>')
        s.append(f'<path d="M0 205 Q200 150 400 190 V240 H0Z" fill="{ground}"/>')
    elif theme == "garden":
        for x in (30, 90, 330, 370):
            s.append(f'<rect x="{x-3}" y="150" width="6" height="35" fill="#6b4226"/><circle cx="{x}" cy="140" r="24" fill="{acc}" opacity=".85"/><circle cx="{x+8}" cy="132" r="5" fill="#ffafcc"/>')
        s.append(f'<rect y="180" width="400" height="60" fill="{ground}"/>')
    elif theme == "backwater":
        s.append('<path d="M40 185 h120 l-15 16 h-90z" fill="#6b4226"/><path d="M60 185 q40 -30 80 0" fill="#d4a373"/>')
        for x in (320, 360):
            s.append(f'<path d="M{x} 160 q5 -35 0 -70" stroke="#6b4226" stroke-width="5" fill="none"/><path d="M{x} 90 q-26 0 -34 14 M{x} 90 q26 -4 34 10 M{x} 90 q-10 -22 -26 -18 M{x} 90 q12 -22 28 -14" stroke="{acc}" stroke-width="6" fill="none" stroke-linecap="round"/>')
        s.append(f'<rect y="205" width="400" height="35" fill="{ground}"/>')
    elif theme == "lake":
        s.append(f'<rect x="250" y="120" width="110" height="36" fill="#fff" opacity=".85"/>')
        for x in (262, 292, 322, 348):
            s.append(f'<path d="M{x-10} 120 a10 12 0 0 1 20 0z" fill="#fff"/>')
        s.append(f'<rect y="195" width="400" height="45" fill="{acc}" opacity=".35"/>')
    elif theme == "desert":
        s.append(f'<path d="M318 180 L326 40 L334 180Z" fill="{acc}" opacity=".7"/>')
        s.append(f'<path d="M0 185 Q120 150 240 185 T400 175 V240 H0Z" fill="{ground}"/>')
    elif theme == "skyline":
        s.append(f'<circle cx="80" cy="115" r="38" fill="none" stroke="{acc}" stroke-width="4" opacity=".8"/>')
        for x in (260, 300, 340):
            s.append(f'<rect x="{x}" y="80" width="26" height="80" fill="#0b132b" opacity=".6"/>')
        s.append('<rect x="252" y="72" width="122" height="10" rx="5" fill="#0b132b" opacity=".6"/>')
    elif theme == "temple":
        for x, h in ((300, 80), (340, 60), (270, 55)):
            s.append(f'<path d="M{x-18} 160 L{x} {160-h} L{x+18} 160Z" fill="{acc}" opacity=".7"/>')
        s.append(f'<rect y="185" width="400" height="55" fill="{ground}"/>')
    elif theme == "london":
        s.append(f'<rect x="320" y="60" width="22" height="110" fill="#3d405b"/><path d="M320 60 L331 38 L342 60Z" fill="#3d405b"/><circle cx="331" cy="80" r="7" fill="#f2cc8f"/>')
        s.append('<path d="M150 150 q60 -40 120 0" stroke="#3d405b" stroke-width="5" fill="none"/><rect x="140" y="150" width="140" height="8" fill="#3d405b"/>')
        s.append(f'<rect y="185" width="400" height="55" fill="{ground}"/>')
    return "".join(s)


def building(style, p, seed):
    acc = p[4]
    lit = "#ffe8a3"
    s = []
    if style == "resort":
        s.append(f'<rect x="110" y="140" width="180" height="50" rx="6" fill="#fffaf0"/><path d="M100 142 L200 112 L300 142Z" fill="{acc}"/>')
        for i in range(6):
            s.append(f'<rect x="{122+i*27}" y="152" width="16" height="14" rx="2" fill="{lit}"/>')
        s.append('<rect x="130" y="198" width="140" height="18" rx="9" fill="#48cae4"/>')
        s.append(f'<path d="M100 215 l12 -22 l12 22z" fill="{acc}"/><path d="M290 215 l12 -22 l12 22z" fill="{acc}"/>')
    elif style == "boutique":
        s.append(f'<rect x="150" y="100" width="100" height="100" rx="4" fill="#fdf0d5"/><rect x="150" y="96" width="100" height="10" fill="{acc}"/>')
        for r in range(3):
            for c in range(3):
                s.append(f'<path d="M{162+c*28} {140+r*28} v-14 a8 8 0 0 1 16 0 v14z" fill="{lit}"/>')
        s.append(f'<rect x="190" y="178" width="20" height="22" fill="{acc}"/>')
    elif style == "heritage":
        s.append(f'<rect x="120" y="130" width="160" height="70" fill="#fceade"/>')
        for x in (140, 200, 260):
            s.append(f'<path d="M{x-18} 130 a18 20 0 0 1 36 0z" fill="{acc}"/><rect x="{x-2}" y="102" width="4" height="10" fill="{acc}"/>')
        for i in range(5):
            s.append(f'<path d="M{132+i*30} 200 v-30 a9 10 0 0 1 18 0 v30z" fill="{lit}" opacity=".9"/>')
    elif style == "budget":
        s.append('<rect x="160" y="120" width="80" height="80" fill="#f1faee"/>')
        s.append(f'<rect x="170" y="108" width="60" height="14" rx="3" fill="{acc}"/>')
        for r in range(2):
            for c in range(3):
                s.append(f'<rect x="{168+c*24}" y="{132+r*26}" width="14" height="16" fill="{lit}"/>')
        s.append('<rect x="192" y="180" width="16" height="20" fill="#6c757d"/>')
    else:  # business tower
        s.append(f'<rect x="165" y="60" width="70" height="140" fill="#e0fbfc" opacity=".95"/><rect x="165" y="56" width="70" height="6" fill="{acc}"/>')
        for r in range(9):
            for c in range(4):
                on = ((r * 4 + c + seed) % 3) != 0
                s.append(f'<rect x="{172+c*16}" y="{68+r*14}" width="10" height="8" fill="{lit if on else "#98c1d9"}"/>')
    return "".join(s)


def svg(theme, style, seed):
    p = PAL[theme]
    top, bot, sun = p[0], p[1], p[2]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" role="img">'
            f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/>'
            f'<stop offset="1" stop-color="{bot}"/></linearGradient></defs>'
            f'<rect width="400" height="240" fill="url(#g)"/>'
            f'<circle cx="{70 + (seed * 53) % 260}" cy="{50 + (seed * 17) % 30}" r="22" fill="{sun}" opacity=".9"/>'
            f'{backdrop(theme, p)}{building(style, p, seed)}</svg>')


def main():
    data = json.loads((ROOT / "data" / "hotels.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for cid, info in data["cities"].items():
        for i, h in enumerate(info["hotels"]):
            (OUT / f"{h['id']}.svg").write_text(svg(info["theme"], h["style"], i + len(cid)), encoding="utf-8")
            n += 1
    (OUT / "fallback.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240"><rect width="400" height="240" fill="#2b2544"/>'
        '<rect x="160" y="80" width="80" height="100" rx="6" fill="#8b5cf6" opacity=".6"/>'
        '<rect x="176" y="96" width="14" height="14" fill="#e9d5ff"/><rect x="210" y="96" width="14" height="14" fill="#e9d5ff"/>'
        '<rect x="176" y="124" width="14" height="14" fill="#e9d5ff"/><rect x="210" y="124" width="14" height="14" fill="#e9d5ff"/>'
        '<rect x="192" y="152" width="16" height="28" fill="#e9d5ff"/></svg>', encoding="utf-8")
    print(f"wrote {n} hotel images + fallback to {OUT}")


if __name__ == "__main__":
    main()
