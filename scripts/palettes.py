"""Color palettes for the profile SVGs.

The generator draws everything in the base (Tokyo Night) colors. When a
palette other than "original" is active, every base color is swapped for its
counterpart below as each SVG is written.

Switch palettes (the words themselves live in profile.toml):
    python3 scripts/generate_pixel_svgs.py --palette ember
or edit scripts/palette.txt and rerun the generator. On GitHub, use
Actions -> "Change Palette" -> Run workflow.

To add a palette, copy one of the dicts below, change the right-hand values,
and add it to PALETTES. Any base color you leave out stays as it is.
"""

import os
import sys

# Warm darks and neutrals shared by the warm palettes.
_WARM_BASE = {
    "#0d0e17": "#070403",  # drop shadows
    "#13141f": "#0f0806",  # outer sky / deepest bg
    "#16161e": "#150b08",
    "#1a1b26": "#1b0f0a",
    "#1b1e2e": "#22120c",  # distant mountains
    "#1f2335": "#24140d",  # panels
    "#24283b": "#2d1910",
    "#292e42": "#3d2216",  # inner borders
    "#2f3549": "#4d2b1b",  # outer borders
    "#3b4261": "#5e3621",
    "#563e2e": "#6e3b1f",  # tree trunks / wood
    "#8c5a3c": "#a95e2c",
    "#787c99": "#b08a6e",  # muted text
    "#a9b1d6": "#f0d6b4",  # secondary text
    "#c0caf5": "#fff2dc",  # main text
}

PALETTES = {
    # Tokyo Night, the colors the generator is written in.
    "original": {},

    # All warm: amber hero, blaze-orange frames, rose labels, lime XP.
    "ember": {
        **_WARM_BASE,
        "#7dcfff": "#ffb627",  # cyan   -> amber (name glow, cursor, rivets)
        "#7aa2f7": "#ff6a1a",  # blue   -> blaze orange (frames, slime)
        "#bb9af7": "#ff4f7b",  # purple -> hot rose (labels)
        "#9ece6a": "#d9ec3c",  # green  -> electric lime (XP, success)
        "#f7768e": "#ff3a2e",  # pink   -> fire red (hearts, flame)
        "#e0af68": "#ffd27a",  # yellow -> moon gold
        "#ff9e64": "#ff8a2a",  # orange -> ember
        "#41a6b5": "#4e9a3a",  # teal trees  -> forest
        "#73daca": "#8fd14f",  # light trees -> leaf
    },

    # Warm base with one cool pop of neon teal.
    "sunset": {
        **_WARM_BASE,
        "#7dcfff": "#ffbf2e",
        "#7aa2f7": "#ff5a3c",
        "#bb9af7": "#ff5fa8",
        "#9ece6a": "#2ee6c5",
        "#f7768e": "#ff3355",
        "#e0af68": "#ffd98a",
        "#ff9e64": "#ff8c3a",
        "#41a6b5": "#1fa38e",
        "#73daca": "#4ff0d0",
    },
}

DEFAULT_PALETTE = "original"
PALETTE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "palette.txt")

# The contribution snake uses the "blue" frame color.
_SNAKE_BASE = "#7aa2f7"


def read_active() -> str:
    try:
        with open(PALETTE_FILE, encoding="utf-8") as f:
            name = f.read().strip()
    except FileNotFoundError:
        return DEFAULT_PALETTE
    return name or DEFAULT_PALETTE


def write_active(name: str) -> None:
    with open(PALETTE_FILE, "w", encoding="utf-8") as f:
        f.write(name + "\n")


def get(name: str) -> dict:
    if name not in PALETTES:
        sys.exit(f"Unknown palette '{name}'. Choose one of: {', '.join(PALETTES)}")
    return {k.lower(): v for k, v in PALETTES[name].items()}


def snake_color(name: str) -> str:
    return get(name).get(_SNAKE_BASE, _SNAKE_BASE)


if __name__ == "__main__":
    # `python3 scripts/palettes.py snake-color` prints the snake color for the
    # active palette (used by the snake workflow).
    if sys.argv[1:] == ["snake-color"]:
        print(snake_color(read_active()))
    else:
        print("Palettes:", ", ".join(PALETTES))
        print("Active:", read_active())
