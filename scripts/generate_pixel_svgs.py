import argparse
import os
import re
import struct
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import palettes  # noqa: E402

_parser = argparse.ArgumentParser(description="Regenerate the profile SVGs and README.")
_parser.add_argument(
    "--palette",
    choices=list(palettes.PALETTES),
    help="color palette to use (saved to scripts/palette.txt for next time)",
)
_args = _parser.parse_args()
PALETTE_NAME = _args.palette or palettes.read_active()
PALETTE = palettes.get(PALETTE_NAME)
if _args.palette:
    palettes.write_active(PALETTE_NAME)
_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")

# ---------------------------------------------------------------------------
# CONTENT: every word comes from profile.toml at the repo root.
# ---------------------------------------------------------------------------
_REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(_REPO_DIR, "profile.toml"), "rb") as _f:
    C = tomllib.load(_f)

COLOR_NAMES = {
    "cyan": "#7dcfff",
    "blue": "#7aa2f7",
    "purple": "#bb9af7",
    "green": "#9ece6a",
    "pink": "#f7768e",
    "yellow": "#e0af68",
    "text": "#c0caf5",
    "muted": "#787c99",
}


def color(name: str) -> str:
    key = str(name).strip().lower()
    if key not in COLOR_NAMES:
        sys.exit(f"profile.toml: unknown color '{name}'. Use one of: {', '.join(COLOR_NAMES)}")
    return COLOR_NAMES[key]


def limit(items: list, n: int, what: str) -> list:
    if len(items) > n:
        print(f"WARNING: {what} has {len(items)} entries but only {n} fit; extra ones are left out.")
    return items[:n]

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(REPO_DIR, "assets")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
PROJECTS_DIR = os.path.join(ASSETS_DIR, "projects")
HEADERS_DIR = os.path.join(ASSETS_DIR, "headers")
BADGES_DIR = os.path.join(ASSETS_DIR, "badges")

os.makedirs(FONTS_DIR, exist_ok=True)
os.makedirs(PROJECTS_DIR, exist_ok=True)
os.makedirs(HEADERS_DIR, exist_ok=True)
os.makedirs(BADGES_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# PARSE PIXELTYPE.TTF BINARY TABLES (CMAP, HMTX, LOCA, GLYF)
# ---------------------------------------------------------------------------
with open(os.path.join(FONTS_DIR, "Pixeltype.ttf"), "rb") as f:
    TTF = f.read()

num_tables = struct.unpack(">H", TTF[4:6])[0]
TABLES = {}
for i in range(num_tables):
    off = 12 + i * 16
    tag, _, toff, tlen = struct.unpack(">4sIII", TTF[off : off + 16])
    TABLES[tag.decode("latin1")] = (toff, tlen)

hhea_off, _ = TABLES["hhea"]
num_hmetrics = struct.unpack(">H", TTF[hhea_off + 34 : hhea_off + 36])[0]
moff, _ = TABLES["maxp"]
num_glyphs = struct.unpack(">H", TTF[moff + 4 : moff + 6])[0]

hmtx_off, _ = TABLES["hmtx"]
ADVANCES = [
    struct.unpack(">Hh", TTF[hmtx_off + i * 4 : hmtx_off + i * 4 + 4])[0]
    for i in range(num_hmetrics)
]
while len(ADVANCES) < num_glyphs:
    ADVANCES.append(ADVANCES[-1])

loff, _ = TABLES["loca"]
LOCS = struct.unpack(f">{num_glyphs + 1}I", TTF[loff : loff + (num_glyphs + 1) * 4])
goff, _ = TABLES["glyf"]


def parse_glyph_contours(gid: int):
    s, e = LOCS[gid], LOCS[gid + 1]
    if s == e:
        return []
    g = TTF[goff + s : goff + e]
    num_contours = struct.unpack(">h", g[0:2])[0]
    if num_contours <= 0:
        return []
    end_pts = struct.unpack(f">{num_contours}H", g[10 : 10 + 2 * num_contours])
    num_pts = end_pts[-1] + 1
    ins_len = struct.unpack(">H", g[10 + 2 * num_contours : 12 + 2 * num_contours])[0]
    pos = 12 + 2 * num_contours + ins_len
    flags = []
    while len(flags) < num_pts:
        fl = g[pos]
        pos += 1
        flags.append(fl)
        if fl & 8:
            rep = g[pos]
            pos += 1
            flags.extend([fl] * rep)
    xs = []
    x = 0
    for fl in flags:
        if fl & 2:
            dx = g[pos]
            pos += 1
            x += dx if (fl & 16) else -dx
        elif not (fl & 16):
            dx = struct.unpack(">h", g[pos : pos + 2])[0]
            pos += 2
            x += dx
        xs.append(x)
    ys = []
    y = 0
    for fl in flags:
        if fl & 4:
            dy = g[pos]
            pos += 1
            y += dy if (fl & 32) else -dy
        elif not (fl & 32):
            dy = struct.unpack(">h", g[pos : pos + 2])[0]
            pos += 2
            y += dy
        ys.append(y)
    contours = []
    start = 0
    for ep in end_pts:
        contours.append(
            [(px // 64, py // 64) for px, py in zip(xs[start : ep + 1], ys[start : ep + 1])]
        )
        start = ep + 1
    return contours


GLYPH_CONTOURS = [parse_glyph_contours(gid) for gid in range(num_glyphs)]
GLYPH_ADV_PX = [adv // 64 for adv in ADVANCES]

coff, _ = TABLES["cmap"]
cdata = TTF[coff:]
soff = struct.unpack(">HHI", cdata[4:12])[2]
segCountX2 = struct.unpack(">H", cdata[soff + 6 : soff + 8])[0]
segCount = segCountX2 // 2
endCodes = struct.unpack(f">{segCount}H", cdata[soff + 14 : soff + 14 + segCountX2])
startCodes = struct.unpack(
    f">{segCount}H", cdata[soff + 16 + segCountX2 : soff + 16 + 2 * segCountX2]
)
idDeltas = struct.unpack(
    f">{segCount}h", cdata[soff + 16 + 2 * segCountX2 : soff + 16 + 3 * segCountX2]
)
idRangeOffsetsPos = soff + 16 + 3 * segCountX2
idRangeOffsets = struct.unpack(
    f">{segCount}H", cdata[idRangeOffsetsPos : idRangeOffsetsPos + segCountX2]
)

CMAP = {}
for i in range(segCount):
    s, e, d, ro = startCodes[i], endCodes[i], idDeltas[i], idRangeOffsets[i]
    if s == 0xFFFF:
        continue
    for c in range(s, e + 1):
        if ro == 0:
            gid = (c + d) & 0xFFFF
        else:
            idx = idRangeOffsetsPos + i * 2 + ro + (c - s) * 2
            gid = struct.unpack(">H", cdata[idx : idx + 2])[0]
            if gid != 0:
                gid = (gid + d) & 0xFFFF
        CMAP[chr(c)] = gid


def measure_px(text: str, scale: float, extra_tracking: float = 0.0) -> float:
    if not text:
        return 0.0
    total = 0.0
    for idx, ch in enumerate(text):
        gid = CMAP.get(ch, CMAP.get(" ", 3))
        total += GLYPH_ADV_PX[gid] * scale
        if idx < len(text) - 1:
            total += extra_tracking
    return total


def fit_px(text: str, scale: float, extra_tracking: float, max_width: float = 0.0):
    """Shrink scale/tracking so text fits max_width. Returns (scale, tracking, width)."""
    w = measure_px(text, scale, extra_tracking)
    if max_width > 0 and w > max_width:
        ratio = max_width / w
        if ratio < 0.85:
            print(f"WARNING: text shrunk to {ratio:.0%} to fit its box, consider shortening: {text!r}")
        scale = round(scale * ratio, 3)
        extra_tracking = round(extra_tracking * ratio, 3)
        w = measure_px(text, scale, extra_tracking)
    return scale, extra_tracking, w


def px_text(
    text: str,
    x: float,
    y: float,
    scale: float,
    fill: str,
    align: str = "left",
    extra_tracking: float = 0.0,
    max_width: float = 0.0,
) -> str:
    scale, extra_tracking, w = fit_px(text, scale, extra_tracking, max_width)
    if align == "center":
        cur_x = x - w / 2.0
    elif align == "right":
        cur_x = x - w
    else:
        cur_x = x

    subpaths = []
    for ch in text:
        gid = CMAP.get(ch, CMAP.get(" ", 3))
        contours = GLYPH_CONTOURS[gid]
        for contour in contours:
            pts = []
            for gx, gy in contour:
                sx = round(cur_x + gx * scale, 2)
                sy = round(y - gy * scale, 2)
                pts.append(f"{sx:g} {sy:g}")
            if pts:
                subpaths.append("M" + "L".join(pts) + "Z")
        cur_x += GLYPH_ADV_PX[gid] * scale + extra_tracking

    if not subpaths:
        return ""
    d_str = "".join(subpaths)
    return f'<path d="{d_str}" fill="{fill}" shape-rendering="crispEdges" />'


def write_svg(path: str, content: str) -> None:
    if PALETTE and path.endswith(".svg"):
        content = _HEX.sub(lambda m: PALETTE.get(m.group(0).lower(), m.group(0)), content)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")


# ---------------------------------------------------------------------------
# 1. HERO-BANNER.SVG (8-Bit Night Scene + RPG HUD with Pixeltype Vector Paths)
# ---------------------------------------------------------------------------
banner_sub = C["banner"]["subtitle"]
BANNER_SUB_MAX = 620
banner_sub_w = fit_px(banner_sub, 2.0, 1.2, BANNER_SUB_MAX)[2]
banner_cursor_x = int(500 + banner_sub_w / 2 + 8)

banner_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 250" width="1000" height="250">
  <g shape-rendering="crispEdges">
    <rect x="0" y="0" width="1000" height="250" fill="#13141f" />
    <rect x="0" y="48" width="1000" height="202" fill="#16161e" />
    <rect x="0" y="96" width="1000" height="154" fill="#1a1b26" />
    <rect x="0" y="144" width="1000" height="106" fill="#1f2335" />
    <rect x="0" y="188" width="1000" height="62" fill="#24283b" />

    <g fill="#16161e">
      <rect x="40" y="44" width="8" height="4" /><rect x="148" y="44" width="8" height="4" />
      <rect x="852" y="44" width="8" height="4" /><rect x="940" y="44" width="8" height="4" />
    </g>
    <g fill="#1a1b26">
      <rect x="76" y="92" width="8" height="4" /><rect x="912" y="92" width="8" height="4" />
    </g>

    <!-- 8-Bit Pixel Crescent Moon -->
    <g fill="#e0af68">
      <rect x="904" y="20" width="24" height="4" />
      <rect x="896" y="24" width="36" height="4" />
      <rect x="892" y="28" width="24" height="4" />
      <rect x="888" y="32" width="20" height="12" />
      <rect x="892" y="44" width="24" height="4" />
      <rect x="896" y="48" width="36" height="4" />
      <rect x="904" y="52" width="24" height="4" />
    </g>

    <!-- Static Pixel Stars -->
    <g fill="#c0caf5">
      <rect x="48" y="24" width="4" height="4" />
      <rect x="128" y="60" width="4" height="4" />
      <rect x="856" y="68" width="4" height="4" />
      <rect x="956" y="80" width="4" height="4" />
      <rect x="40" y="108" width="4" height="4" />
      <rect x="944" y="120" width="4" height="4" />
    </g>

    <!-- Animated Cross-Stars -->
    <g fill="#7dcfff">
      <animate attributeName="opacity" values="1;0.25;1" dur="1.6s" calcMode="discrete" repeatCount="indefinite" />
      <rect x="92" y="32" width="4" height="12" />
      <rect x="88" y="36" width="12" height="4" />
    </g>
    <g fill="#bb9af7">
      <animate attributeName="opacity" values="0.3;1;0.3" dur="2.0s" calcMode="discrete" repeatCount="indefinite" />
      <rect x="144" y="84" width="4" height="12" />
      <rect x="140" y="88" width="12" height="4" />
    </g>
    <g fill="#e0af68">
      <animate attributeName="opacity" values="1;0.2;1" dur="1.8s" calcMode="discrete" repeatCount="indefinite" />
      <rect x="844" y="28" width="4" height="12" />
      <rect x="840" y="32" width="12" height="4" />
    </g>

    <!-- Distant Stepped Pixel Mountains -->
    <g fill="#1b1e2e">
      <rect x="0" y="176" width="180" height="40" />
      <rect x="16" y="164" width="148" height="12" />
      <rect x="36" y="152" width="108" height="12" />
      <rect x="56" y="140" width="68" height="12" />
      <rect x="76" y="128" width="28" height="12" />

      <rect x="820" y="176" width="180" height="40" />
      <rect x="836" y="164" width="148" height="12" />
      <rect x="856" y="152" width="108" height="12" />
      <rect x="876" y="140" width="68" height="12" />
      <rect x="896" y="128" width="28" height="12" />
    </g>

    <!-- Left Pixel Pine Trees -->
    <rect x="32" y="196" width="8" height="16" fill="#563e2e" />
    <g fill="#41a6b5">
      <rect x="32" y="156" width="8" height="8" />
      <rect x="24" y="164" width="24" height="8" />
      <rect x="28" y="172" width="16" height="8" />
      <rect x="20" y="180" width="32" height="8" />
      <rect x="16" y="188" width="40" height="8" />
    </g>
    <rect x="76" y="200" width="8" height="12" fill="#563e2e" />
    <g fill="#73daca">
      <rect x="76" y="168" width="8" height="8" />
      <rect x="68" y="176" width="24" height="8" />
      <rect x="64" y="184" width="32" height="8" />
      <rect x="60" y="192" width="40" height="8" />
    </g>

    <!-- Right Pixel Pine Tree -->
    <rect x="948" y="196" width="8" height="16" fill="#563e2e" />
    <g fill="#41a6b5">
      <rect x="948" y="160" width="8" height="8" />
      <rect x="940" y="168" width="24" height="8" />
      <rect x="936" y="176" width="32" height="8" />
      <rect x="932" y="184" width="40" height="12" />
    </g>

    <!-- Pixel Campfire (Left Foreground) -->
    <rect x="120" y="206" width="24" height="6" fill="#8c5a3c" />
    <rect x="124" y="202" width="16" height="4" fill="#563e2e" />
    <g>
      <animate attributeName="opacity" values="1;0.65;1" dur="0.5s" calcMode="discrete" repeatCount="indefinite" />
      <rect x="124" y="194" width="16" height="8" fill="#f7768e" />
      <rect x="128" y="186" width="8" height="8" fill="#ff9e64" />
      <rect x="128" y="194" width="8" height="6" fill="#e0af68" />
    </g>
    <rect x="130" y="178" width="4" height="4" fill="#ff9e64">
      <animate attributeName="y" values="180;170;162" dur="1.1s" calcMode="discrete" repeatCount="indefinite" />
      <animate attributeName="opacity" values="1;0.7;0" dur="1.1s" calcMode="discrete" repeatCount="indefinite" />
    </rect>

    <!-- Bobbing Pixel Slime Sprite (Right Foreground) -->
    <g>
      <animateTransform attributeName="transform" type="translate" values="0,0; 0,-4; 0,0" dur="0.8s" calcMode="discrete" repeatCount="indefinite" />
      <rect x="876" y="192" width="16" height="4" fill="#7aa2f7" />
      <rect x="872" y="196" width="24" height="12" fill="#7aa2f7" />
      <rect x="868" y="200" width="32" height="8" fill="#7aa2f7" />
      <rect x="876" y="196" width="8" height="4" fill="#7dcfff" />
      <rect x="876" y="202" width="4" height="4" fill="#16161e" />
      <rect x="888" y="202" width="4" height="4" fill="#16161e" />
    </g>

    <!-- Ground Terrain & Dungeon Brick Layer -->
    <rect x="0" y="212" width="1000" height="8" fill="#41a6b5" />
    <rect x="0" y="220" width="1000" height="30" fill="#1f2335" />
    <g fill="#73daca">
      <rect x="0" y="212" width="48" height="4" />
      <rect x="64" y="212" width="52" height="4" />
      <rect x="836" y="212" width="52" height="4" />
      <rect x="904" y="212" width="80" height="4" />
    </g>
    <g fill="#292e42">
      <rect x="16" y="226" width="28" height="8" />
      <rect x="52" y="226" width="28" height="8" />
      <rect x="108" y="226" width="28" height="8" />
      <rect x="34" y="238" width="28" height="8" />
      <rect x="852" y="226" width="28" height="8" />
      <rect x="888" y="226" width="28" height="8" />
      <rect x="944" y="226" width="28" height="8" />
      <rect x="870" y="238" width="28" height="8" />
    </g>

    <!-- CENTER RETRO RPG HUD DIALOGUE BOX -->
    <rect x="160" y="26" width="688" height="176" fill="#0d0e17" />
    <rect x="156" y="18" width="688" height="176" fill="#7aa2f7" />
    <rect x="152" y="22" width="696" height="168" fill="#7aa2f7" />
    <rect x="160" y="22" width="680" height="168" fill="#16161e" />
    <rect x="156" y="26" width="688" height="160" fill="#16161e" />
    <rect x="164" y="26" width="672" height="160" fill="#292e42" />
    <rect x="168" y="30" width="664" height="152" fill="#1a1b26" />

    <!-- Top HUD Status Bar -->
    <rect x="168" y="30" width="664" height="30" fill="#1f2335" />
    <rect x="168" y="60" width="664" height="2" fill="#292e42" />

    <!-- Corner Pixel Rivets -->
    <rect x="174" y="36" width="4" height="4" fill="#7dcfff" />
    <rect x="822" y="36" width="4" height="4" fill="#7dcfff" />
    <rect x="174" y="172" width="4" height="4" fill="#7dcfff" />
    <rect x="822" y="172" width="4" height="4" fill="#7dcfff" />

    <!-- 3 Pixel Hearts in HUD Bar -->
    <g fill="#f7768e">
      <rect x="748" y="38" width="4" height="4" /><rect x="756" y="38" width="4" height="4" />
      <rect x="746" y="42" width="16" height="4" />
      <rect x="748" y="46" width="12" height="4" />
      <rect x="752" y="50" width="4" height="2" />

      <rect x="770" y="38" width="4" height="4" /><rect x="778" y="38" width="4" height="4" />
      <rect x="768" y="42" width="16" height="4" />
      <rect x="770" y="46" width="12" height="4" />
      <rect x="774" y="50" width="4" height="2" />

      <rect x="792" y="38" width="4" height="4" /><rect x="800" y="38" width="4" height="4" />
      <rect x="790" y="42" width="16" height="4" />
      <rect x="792" y="46" width="12" height="4" />
      <rect x="796" y="50" width="4" height="2" />
    </g>

    <!-- Bottom HUD XP Bar -->
    <rect x="310" y="162" width="380" height="8" fill="#13141f" />
    <rect x="312" y="164" width="280" height="4" fill="#9ece6a" />
    <rect x="592" y="164" width="68" height="4" fill="#7dcfff">
      <animate attributeName="opacity" values="1;0.35;1" dur="1.2s" calcMode="discrete" repeatCount="indefinite" />
    </rect>
  </g>

  {px_text(C["banner"]["player_tag"], 190, 51, 2.0, "#7dcfff", "left", 1.0, 420)}
  {px_text(C["banner"]["level"], 726, 51, 2.0, "#9ece6a", "right", 1.0, 110)}

  {px_text(C["banner"]["name"], 504, 114, 5.0, "#0d0e17", "center", 3.0, 640)}
  {px_text(C["banner"]["name"], 500, 110, 5.0, "#c0caf5", "center", 3.0, 640)}

  {px_text(banner_sub, 500, 146, 2.0, "#bb9af7", "center", 1.2, BANNER_SUB_MAX)}
  <rect x="{banner_cursor_x}" y="131" width="9" height="16" fill="#7dcfff" shape-rendering="crispEdges">
    <animate attributeName="opacity" values="1;0;1" dur="1.0s" calcMode="discrete" repeatCount="indefinite" />
  </rect>

  <rect x="2" y="2" width="996" height="246" rx="8" fill="none" stroke="#292e42" stroke-width="4" shape-rendering="crispEdges" />
</svg>"""
write_svg(os.path.join(ASSETS_DIR, "pixel-banner.svg"), banner_svg)


# ---------------------------------------------------------------------------
# 1B. PIXEL-DIVIDER-V2.SVG (44px Tall Section Spacer + Retro Diamond Divider)
# ---------------------------------------------------------------------------
divider_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 44" width="1000" height="44">
  <g shape-rendering="crispEdges">
    <rect x="40" y="21" width="400" height="2" fill="#24283b" />
    <rect x="560" y="21" width="400" height="2" fill="#24283b" />
    <rect x="456" y="19" width="6" height="6" fill="#7aa2f7" />
    <rect x="476" y="18" width="8" height="8" fill="#bb9af7" />
    <rect x="496" y="16" width="8" height="12" fill="#7dcfff" />
    <rect x="494" y="18" width="12" height="8" fill="#7dcfff" />
    <rect x="516" y="18" width="8" height="8" fill="#bb9af7" />
    <rect x="538" y="19" width="6" height="6" fill="#7aa2f7" />
  </g>
</svg>"""
write_svg(os.path.join(ASSETS_DIR, "pixel-divider-v2.svg"), divider_svg)


# ---------------------------------------------------------------------------
# 2. TYPING-STATUS.SVG (1000x68 ViewBox with Vertical Breathing Room)
# ---------------------------------------------------------------------------
typing_entries = [(t["text"], color(t["color"])) for t in C["typing"]]
if not typing_entries:
    sys.exit("profile.toml: add at least one [[typing]] line.")
TYPING_MAX = 920
typing_step = 1 / len(typing_entries)  # each line gets an equal slice of the loop
typing_dur = f"{4 * len(typing_entries)}s"  # 4 seconds per line

line_groups = []
for idx, (text_str, line_color) in enumerate(typing_entries):
    t_start = idx * typing_step
    t_end = (idx + 1) * typing_step
    if len(typing_entries) == 1:
        vals = "1;1"
        kt = "0;1"
    elif idx == 0:
        vals = "1;1;0;0"
        kt = f"0;{t_end - 0.001:.4f};{t_end:.4f};1"
    elif idx == len(typing_entries) - 1:
        vals = "0;0;1;1"
        kt = f"0;{t_start:.4f};{t_start + 0.001:.4f};1"
    else:
        vals = "0;0;1;1;0;0"
        kt = f"0;{t_start:.4f};{t_start + 0.001:.4f};{t_end - 0.001:.4f};{t_end:.4f};1"

    scale, tracking, line_w = fit_px(text_str, 2.4, 1.2, TYPING_MAX)
    x0 = 500.0 - line_w / 2.0

    char_xs = [int(round(x0))]
    cur = x0
    for ch in text_str:
        gid = CMAP.get(ch, CMAP.get(" ", 3))
        cur += GLYPH_ADV_PX[gid] * scale + tracking
        char_xs.append(int(round(cur)))

    x_end = char_xs[-1]
    n_hold = 24
    xs_type = char_xs
    xs_hold = [x_end] * n_hold
    xs_erase = char_xs[::-2]
    if xs_erase[-1] != char_xs[0]:
        xs_erase.append(char_xs[0])

    all_xs = xs_type + xs_hold + xs_erase

    blink_pattern = ([1, 1, 1, 1, 0, 0, 0, 0] * 3)[:n_hold]
    cursor_opacities = [1] * len(xs_type) + blink_pattern + [1] * len(xs_erase)

    mask_x_vals = ";".join(str(x) for x in all_xs)
    mask_w_vals = ";".join(str(max(0, x_end + 24 - x)) for x in all_xs)
    cursor_x_vals = ";".join(str(x) for x in all_xs)
    cursor_op_vals = ";".join(str(op) for op in cursor_opacities)

    path_el = px_text(text_str, 500, 43, scale, line_color, "center", tracking)
    line_groups.append(
        f'  <g opacity="0" shape-rendering="crispEdges">\n'
        f'    <animate attributeName="opacity" values="{vals}" keyTimes="{kt}" dur="{typing_dur}" repeatCount="indefinite" />\n'
        f"    {path_el}\n"
        f'    <rect x="{char_xs[0]}" y="20" width="{x_end + 24 - char_xs[0]}" height="28" fill="#16161e">\n'
        f'      <animate attributeName="x" values="{mask_x_vals}" dur="4s" calcMode="discrete" repeatCount="indefinite" />\n'
        f'      <animate attributeName="width" values="{mask_w_vals}" dur="4s" calcMode="discrete" repeatCount="indefinite" />\n'
        f"    </rect>\n"
        f'    <rect x="{char_xs[0]}" y="25" width="10" height="18" fill="#c0caf5">\n'
        f'      <animate attributeName="x" values="{cursor_x_vals}" dur="4s" calcMode="discrete" repeatCount="indefinite" />\n'
        f'      <animate attributeName="opacity" values="{cursor_op_vals}" dur="4s" calcMode="discrete" repeatCount="indefinite" />\n'
        f"    </rect>\n"
        f'    <rect x="{char_xs[0]}" y="41" width="10" height="3" fill="{line_color}">\n'
        f'      <animate attributeName="x" values="{cursor_x_vals}" dur="4s" calcMode="discrete" repeatCount="indefinite" />\n'
        f'      <animate attributeName="opacity" values="{cursor_op_vals}" dur="4s" calcMode="discrete" repeatCount="indefinite" />\n'
        f"    </rect>\n"
        f"  </g>"
    )

typing_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 68" width="1000" height="68">
  <g shape-rendering="crispEdges">
    <rect x="2" y="14" width="996" height="40" fill="#16161e" stroke="#2f3549" stroke-width="2" />
    <rect x="2" y="14" width="8" height="40" fill="#7aa2f7" />
    <rect x="990" y="14" width="8" height="40" fill="#7aa2f7" />
    <rect x="18" y="28" width="12" height="12" fill="#7aa2f7" />
    <rect x="22" y="32" width="4" height="4" fill="#16161e" />
    <rect x="970" y="28" width="12" height="12" fill="#7aa2f7" />
    <rect x="974" y="32" width="4" height="4" fill="#16161e" />
  </g>
{chr(10).join(line_groups)}
</svg>"""
write_svg(os.path.join(ASSETS_DIR, "typing-status.svg"), typing_svg)


# ---------------------------------------------------------------------------
# 3. PIXEL BADGES (3 Uniform 324x40 Badges)
# ---------------------------------------------------------------------------
def make_pixel_badge(filename: str, label: str, value: str, accent: str) -> None:
    width = 324
    height = 40
    lw = 96
    vw = width - lw - 8
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <g shape-rendering="crispEdges">
    <rect x="2" y="2" width="{width-4}" height="{height-4}" fill="#16161e" stroke="#2f3549" stroke-width="2" />
    <rect x="4" y="4" width="{lw}" height="{height-8}" fill="#1f2335" />
    <rect x="{lw+4}" y="4" width="{vw}" height="{height-8}" fill="{accent}" fill-opacity="0.16" />
    <rect x="{lw+4}" y="4" width="2" height="{height-8}" fill="{accent}" />
    <rect x="2" y="2" width="4" height="4" fill="{accent}" />
    <rect x="{width-6}" y="2" width="4" height="4" fill="{accent}" />
    <rect x="2" y="{height-6}" width="4" height="4" fill="{accent}" />
    <rect x="{width-6}" y="{height-6}" width="4" height="4" fill="{accent}" />
  </g>
  {px_text(label, 4 + lw / 2.0, 27, 2.0, accent, "center", 0.8, lw - 12)}
  {px_text(value, lw + 4 + vw / 2.0, 27, 2.0, "#c0caf5", "center", 0.8, vw - 16)}
</svg>"""
    write_svg(os.path.join(BADGES_DIR, filename), svg)


for _b in C["badges"]:
    make_pixel_badge(_b["file"], _b["label"], _b["value"], color(_b["color"]))


# ---------------------------------------------------------------------------
# 4. PIXEL SECTION HEADERS (Clean, Natural Titles — No 01. or // Subtitles)
# ---------------------------------------------------------------------------
def make_section_header(filename: str, title: str, right_tag: str, accent: str) -> None:
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 62" width="1000" height="62">
  <g shape-rendering="crispEdges">
    <rect x="2" y="6" width="996" height="40" fill="#16161e" stroke="#292e42" stroke-width="2" />
    <rect x="2" y="6" width="8" height="40" fill="{accent}" />
    <rect x="18" y="20" width="12" height="12" fill="{accent}" />
    <rect x="22" y="24" width="4" height="4" fill="#16161e" />
    <rect x="2" y="44" width="996" height="2" fill="{accent}" fill-opacity="0.35" />

    <rect x="920" y="23" width="16" height="6" fill="{accent}" />
    <rect x="944" y="23" width="16" height="6" fill="{accent}" fill-opacity="0.5" />
    <rect x="968" y="23" width="16" height="6" fill="{accent}" fill-opacity="0.2" />
  </g>
  {px_text(title, 42, 34, 2.4, accent, "left", 1.2, 480)}
  {px_text(right_tag, 902, 33, 2.0, "#787c99", "right", 0.8, 360)}
</svg>"""
    write_svg(os.path.join(HEADERS_DIR, filename), svg)


for _key in ("about", "stack", "projects", "snake"):
    _h = C["headers"][_key]
    make_section_header(f"{_key}-header.svg", _h["title"], _h["tag"], color(_h["color"]))


# ---------------------------------------------------------------------------
# 5. PLAYER-SHEET.SVG (Spacious Layout + CTF Trophy + Pygame Domain)
# ---------------------------------------------------------------------------
PS = C["player_sheet"]
prompt_w = measure_px("> ", 2.0, 0.8)
cmd_x = round(28 + prompt_w, 2)
STATUS_MAX = 520
cmd2_w = fit_px(PS["status_command"], 2.0, 0.8, STATUS_MAX)[2]

_rows = limit(PS["rows"], 4, "player_sheet.rows")
sheet_rows = []
for _i, _r in enumerate(_rows):
    _y = 114 + 34 * _i
    _label = (_r["label"][:11]).ljust(11) + ":"
    sheet_rows.append(
        f'  {px_text(_label, 28, _y, 2.0, "#bb9af7", "left", 0.6, 140)}\n'
        f'  {px_text(_r["value"], 172, _y, 2.0, color(_r["color"]), "left", 0.6, 410)}\n'
    )
sheet_rows_svg = "\n".join(sheet_rows)

_core = limit(PS["core_areas"], 4, "player_sheet.core_areas")
_core_pos = [(722, 215), (896, 215), (722, 259), (896, 259)]
core_svg = "\n".join(
    f'  {px_text(a["label"], x, y, 2.0, color(a["color"]), "center", 0.0, 156)}'
    for a, (x, y) in zip(_core, _core_pos)
)
_build = limit(PS["build_lines"], 2, "player_sheet.build_lines") + ["", ""]
cursor_x = int(round(cmd_x + cmd2_w + 3))

about_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 288" width="1000" height="288">
  <g shape-rendering="crispEdges">
    <rect x="4" y="4" width="596" height="280" fill="#16161e" stroke="#2f3549" stroke-width="2" />
    <rect x="4" y="4" width="596" height="40" fill="#1f2335" />
    <rect x="4" y="44" width="596" height="2" fill="#2f3549" />

    <rect x="20" y="18" width="12" height="12" fill="#f7768e" />
    <rect x="40" y="18" width="12" height="12" fill="#e0af68" />
    <rect x="60" y="18" width="12" height="12" fill="#9ece6a" />

    <rect x="622" y="4" width="374" height="128" fill="#16161e" stroke="#2f3549" stroke-width="2" />
    <rect x="622" y="4" width="374" height="4" fill="#9ece6a" />
    <rect x="642" y="25" width="10" height="10" fill="#9ece6a">
      <animate attributeName="opacity" values="1;0.25;1" dur="1.4s" calcMode="discrete" repeatCount="indefinite" />
    </rect>

    <rect x="622" y="150" width="374" height="134" fill="#16161e" stroke="#2f3549" stroke-width="2" />
    <rect x="622" y="150" width="374" height="4" fill="#7aa2f7" />

    <rect x="642" y="192" width="160" height="34" fill="#1f2335" stroke="#3b4261" stroke-width="2" />
    <rect x="816" y="192" width="160" height="34" fill="#1f2335" stroke="#3b4261" stroke-width="2" />
    <rect x="642" y="236" width="160" height="34" fill="#1f2335" stroke="#3b4261" stroke-width="2" />
    <rect x="816" y="236" width="160" height="34" fill="#1f2335" stroke="#3b4261" stroke-width="2" />
  </g>

  {px_text(PS["window_title"], 334, 31, 2.0, "#7dcfff", "center", 0.8, 500)}
  {px_text(">", 28, 78, 2.0, "#7aa2f7", "left", 0.8)}
  {px_text(PS["command"], cmd_x, 78, 2.0, "#c0caf5", "left", 0.8, 540)}

{sheet_rows_svg}
  {px_text(">", 28, 256, 2.0, "#7aa2f7", "left", 0.8)}
  {px_text(PS["status_command"], cmd_x, 256, 2.0, "#a9b1d6", "left", 0.8, STATUS_MAX)}
  <rect x="{cursor_x}" y="242" width="8" height="14" fill="#7dcfff" shape-rendering="crispEdges">
    <animate attributeName="opacity" values="1;0;1" dur="1.0s" calcMode="discrete" repeatCount="indefinite" />
  </rect>

  {px_text(PS["build_title"], 662, 36, 2.0, "#9ece6a", "left", 0.8, 310)}
  {px_text(_build[0], 642, 74, 2.0, "#c0caf5", "left", 0.0, 350)}
  {px_text(_build[1], 642, 104, 2.0, "#a9b1d6", "left", 0.0, 350)}

  {px_text(PS["core_title"], 642, 178, 2.0, "#7aa2f7", "left", 1.0, 336)}
{core_svg}
</svg>"""
write_svg(os.path.join(ASSETS_DIR, "player-sheet.svg"), about_svg)


# ---------------------------------------------------------------------------
# 6. TECH-STACK.SVG (Spacious 3-Line Columns — No // Headers)
# ---------------------------------------------------------------------------
_tech_cols = limit(C["tech_stack"], 3, "tech_stack")
_tech_parts = []
for _col, _x in zip(_tech_cols, (24, 360, 696)):
    _part = [f'  {px_text(_col["title"], _x, 31, 2.0, color(_col["color"]), "left", 0.6, 290)}']
    for _item, _y in zip(limit(_col["items"], 3, f"tech_stack '{_col['title']}' items"), (74, 108, 142)):
        _part.append(f'  {px_text("* " + _item, _x, _y, 2.0, "#c0caf5", "left", 0.0, 290)}')
    _tech_parts.append("\n".join(_part))
tech_text_svg = "\n\n".join(_tech_parts)

tech_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 164" width="1000" height="164">
  <g shape-rendering="crispEdges">
    <rect x="4" y="4" width="320" height="156" fill="#16161e" stroke="#2f3549" stroke-width="2" />
    <rect x="4" y="4" width="320" height="4" fill="#7aa2f7" />
    <rect x="4" y="42" width="320" height="2" fill="#292e42" />

    <rect x="340" y="4" width="320" height="156" fill="#16161e" stroke="#2f3549" stroke-width="2" />
    <rect x="340" y="4" width="320" height="4" fill="#9ece6a" />
    <rect x="340" y="42" width="320" height="2" fill="#292e42" />

    <rect x="676" y="4" width="320" height="156" fill="#16161e" stroke="#2f3549" stroke-width="2" />
    <rect x="676" y="4" width="320" height="4" fill="#bb9af7" />
    <rect x="676" y="42" width="320" height="2" fill="#292e42" />
  </g>

{tech_text_svg}
</svg>"""
write_svg(os.path.join(ASSETS_DIR, "tech-stack.svg"), tech_svg)


# ---------------------------------------------------------------------------
# 7. FOUR PROJECT QUEST CARDS (2x2 Grid, 2-Line Summary + 3 Tags)
# ---------------------------------------------------------------------------
def make_quest_card(
    filename: str,
    title: str,
    badge: str,
    accent1: str,
    accent2: str,
    line1: str,
    line2: str,
    tags: list[str],
) -> None:
    tag_scale = 2.0
    tag_elements = []
    cur_x = 28
    for t in limit(tags, 3, f"tags for '{title}'"):
        tw = int(measure_px(t, tag_scale, 0.4)) + 24
        tag_elements.append(
            f'    <rect x="{cur_x}" y="138" width="{tw}" height="30" fill="#1f2335" stroke="#2f3549" stroke-width="2" shape-rendering="crispEdges" />\n'
            f"    {px_text(t, cur_x + tw / 2.0, 159, tag_scale, '#7dcfff', 'center', 0.4)}"
        )
        cur_x += tw + 12

    badge_w = int(fit_px(badge, 2.0, 0.0, 180)[2]) + 20
    badge_x = 472 - badge_w

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 192" width="500" height="192">
  <g shape-rendering="crispEdges">
    <rect x="6" y="6" width="488" height="180" fill="#16161e" stroke="#2f3549" stroke-width="2" />
    <rect x="6" y="6" width="488" height="6" fill="{accent1}" />
    <rect x="250" y="6" width="244" height="6" fill="{accent2}" />

    <rect x="14" y="18" width="4" height="4" fill="{accent1}" />
    <rect x="482" y="18" width="4" height="4" fill="{accent2}" />
    <rect x="14" y="174" width="4" height="4" fill="{accent1}" />
    <rect x="482" y="174" width="4" height="4" fill="{accent2}" />

    <rect x="{badge_x}" y="22" width="{badge_w}" height="28" fill="#1f2335" stroke="{accent1}" stroke-width="2" />
    <rect x="28" y="62" width="444" height="2" fill="#24283b" />
  </g>

  {px_text(title, 28, 44, 2.3, accent1, "left", 0.0, badge_x - 40)}
  {px_text(badge, badge_x + badge_w / 2.0, 42, 2.0, accent2, "center", 0.0, 180)}

  {px_text(line1, 28, 92, 2.0, "#c0caf5", "left", 0.0, 456)}
  {px_text(line2, 28, 120, 2.0, "#a9b1d6", "left", 0.0, 456)}

{chr(10).join(tag_elements)}
</svg>"""
    write_svg(os.path.join(PROJECTS_DIR, filename), svg)


for _p in C["projects"]:
    make_quest_card(
        _p["file"],
        _p["title"],
        _p["badge"],
        color(_p["accent1"]),
        color(_p["accent2"]),
        _p["line1"],
        _p["line2"],
        _p["tags"],
    )


# ---------------------------------------------------------------------------
# 8. ARCADE-FOOTER.SVG ("CONTINUE? 9... 8... 7... [ INSERT COIN ]" Banner)
# ---------------------------------------------------------------------------
footer_sub = C["footer"]["subline"]
FOOTER_SUB_MAX = 840  # keeps text clear of the coins (x 32-52 and 948-968)
footer_sub_w = fit_px(footer_sub, 2.0, 0.6, FOOTER_SUB_MAX)[2]
footer_cursor_x = int(round(500 + footer_sub_w / 2.0 + 6))

# Vertical layout (viewBox 1000x100): panel y 6-94, accent bar 6-10, base line 90-92.
# Headline caps span y 28-44, subline caps y 60-74, so both gaps to the panel
# edges are 18px and the coins are centered on the text block (y 51).
footer_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 100" width="1000" height="100">
  <g shape-rendering="crispEdges">
    <rect x="2" y="6" width="996" height="88" fill="#16161e" stroke="#2f3549" stroke-width="2" />
    <rect x="2" y="6" width="996" height="4" fill="#bb9af7" />
    <rect x="500" y="6" width="498" height="4" fill="#7dcfff" />
    <rect x="2" y="90" width="996" height="2" fill="#292e42" />

    <!-- Corner Pixel Rivets -->
    <rect x="10" y="16" width="4" height="4" fill="#bb9af7" />
    <rect x="986" y="16" width="4" height="4" fill="#7dcfff" />
    <rect x="10" y="80" width="4" height="4" fill="#bb9af7" />
    <rect x="986" y="80" width="4" height="4" fill="#7dcfff" />

    <!-- Left Animated 8-Bit Gold Coin -->
    <g>
      <animate attributeName="opacity" values="1;0.45;1" dur="1.2s" calcMode="discrete" repeatCount="indefinite" />
      <rect x="36" y="39" width="12" height="24" fill="#e0af68" />
      <rect x="32" y="43" width="20" height="16" fill="#e0af68" />
      <rect x="40" y="45" width="4" height="12" fill="#16161e" />
    </g>

    <!-- Right Animated 8-Bit Gold Coin -->
    <g>
      <animate attributeName="opacity" values="1;0.45;1" dur="1.2s" calcMode="discrete" repeatCount="indefinite" />
      <rect x="952" y="39" width="12" height="24" fill="#e0af68" />
      <rect x="948" y="43" width="20" height="16" fill="#e0af68" />
      <rect x="956" y="45" width="4" height="12" fill="#16161e" />
    </g>
  </g>

  {px_text(C["footer"]["headline"], 500, 44, 2.3, "#e0af68", "center", 1.0, 840)}
  {px_text(footer_sub, 500, 74, 2.0, "#7dcfff", "center", 0.6, FOOTER_SUB_MAX)}
  <rect x="{footer_cursor_x}" y="60" width="8" height="14" fill="#9ece6a" shape-rendering="crispEdges">
    <animate attributeName="opacity" values="1;0;1" dur="1.0s" calcMode="discrete" repeatCount="indefinite" />
  </rect>
</svg>"""
write_svg(os.path.join(ASSETS_DIR, "arcade-footer.svg"), footer_svg)


# ---------------------------------------------------------------------------
# 9. WRITE README.MD
# ---------------------------------------------------------------------------
USER = C["profile"]["username"]
H = C["headers"]

_badge_links = "\n".join(
    f'  <a href="{b["link"]}"><img width="32%" src="./assets/badges/{b["file"]}" alt="{b["alt"]}" /></a>'
    for b in C["badges"]
)

_project_rows = []
_projects = C["projects"]
for _i in range(0, len(_projects), 2):
    _cells = "\n".join(
        f'    <a href="{p["link"]}"><img width="49%" src="./assets/projects/{p["file"]}" alt="{p["alt"]}" /></a>'
        for p in _projects[_i : _i + 2]
    )
    _project_rows.append(f'  <p align="center">\n{_cells}\n  </p>')
_project_rows_md = "\n".join(_project_rows)

_icons = ",".join(C["skill_icons"]["icons"])
_snake_base = f"https://raw.githubusercontent.com/{USER}/{USER}/output"

readme_md = f"""<!-- Generated from profile.toml. Edit that file, not this one. -->
<div align="center">

<img width="100%" src="./assets/pixel-banner.svg" alt="{C["banner"]["alt"]}" />

<img width="100%" src="./assets/typing-status.svg" alt="Animated Pixel Typing Status" />

<p align="center">
{_badge_links}
</p>

</div>

<img width="100%" src="./assets/pixel-divider-v2.svg" alt="" />

<div align="center">
  <img width="100%" src="./assets/headers/about-header.svg" alt="{H["about"]["alt"]}" />
  <img width="100%" src="./assets/player-sheet.svg" alt="{C["player_sheet"]["alt"]}" />
</div>

<img width="100%" src="./assets/pixel-divider-v2.svg" alt="" />

<div align="center">
  <img width="100%" src="./assets/headers/stack-header.svg" alt="{H["stack"]["alt"]}" />
  <img width="100%" src="./assets/tech-stack.svg" alt="{H["stack"]["alt"]}" />
  <br/><br/>
  <img src="https://skillicons.dev/icons?i={_icons}&theme=dark" alt="Tech Stack Icons" />
</div>

<img width="100%" src="./assets/pixel-divider-v2.svg" alt="" />

<div align="center">
  <img width="100%" src="./assets/headers/projects-header.svg" alt="{H["projects"]["alt"]}" />
{_project_rows_md}
</div>

<img width="100%" src="./assets/pixel-divider-v2.svg" alt="" />

<div align="center">
  <img width="100%" src="./assets/headers/snake-header.svg" alt="{H["snake"]["alt"]}" />
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="{_snake_base}/github-contribution-grid-snake-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="{_snake_base}/github-contribution-grid-snake.svg" />
    <img alt="github-contribution-grid-snake" src="{_snake_base}/github-contribution-grid-snake-dark.svg" width="100%" />
  </picture>
</div>

<img width="100%" src="./assets/pixel-divider-v2.svg" alt="" />

<div align="center">
  <a href="{C["footer"]["link"]}"><img width="100%" src="./assets/arcade-footer.svg" alt="{C["footer"]["alt"]}" /></a>
</div>
"""
write_svg(os.path.join(REPO_DIR, "README.md"), readme_md)
print(f"Successfully regenerated all SVGs and README.md with the '{PALETTE_NAME}' palette!")
