#!/usr/bin/env python3
"""Generate TFT_eSPI smooth-font (.vlw) files for the PaperStreet keychain.

Renders glyphs with PIL/FreeType (grayscale 'L' = 8-bit alpha) and writes
the .vlw format documented in TFT_eSPI's Extensions/Smooth_font.cpp
(TFT_eSPI::loadFont / loadMetrics):

  Header: 6 x int32 big-endian:
      [gCount, version=11, font size (points), mboxY=0, ascent, descent]
  Then gCount glyph records, each 7 x int32 big-endian:
      [unicode, bitmap height, bitmap width, gxAdvance,
       gdY (baseline -> TOP of bitmap, +ve = up),
       gdX (cursor -> LEFT edge of bitmap, signed), padding=0]
  Then the bitmaps in glyph-record order, 1 byte/px 8-bit alpha,
  row-major top-to-bottom, starting at byte offset 24 + 28*gCount.
  Trailer (never read by loadFont, written for format completeness):
      1 byte name length, font name zero-terminated,
      1 byte PostScript-name length, PS name zero-terminated,
      1 final byte 0x01 (anti-aliased).

Notes:
  * U+0020 (space) is NEVER in the glyph table: TFT_eSPI handles space
    via spaceWidth = (ascent+descent)*2/7. Printable charsets start at 0x21.
  * ascent/descent come from PIL ImageFont.getmetrics() at the render
    size, consistent with where PIL places the baseline when rendering.
  * loadMetrics() stores gxAdvance as uint8 and gdX as int8, so advances
    must fit in 0..255 and gdX in -128..127; this script asserts that.
  * A glyph with no nonzero pixels keeps width=height=0, gdX=gdY=0 and
    its gxAdvance. A requested character with no glyph in the font is
    skipped and reported (never silently substituted).

Usage:  python3 tools/genvlw.py        (run from ps-keychain-sim/)
Writes the 16 .vlw files to BOTH
  ~/workspace/ps-keychain-firmware/data/   (firmware deliverable)
  ~/workspace/ps-keychain-sim/data/        (sim harness)
and instantiates the two static Outfit weights from the variable font
into /tmp/fonts/Outfit-ExtraBold.ttf and /tmp/fonts/Outfit-Bold.ttf.
"""

import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from fontTools import ttLib
from fontTools.varLib.instancer import instantiateVariableFont

# ---------------------------------------------------------------- sources
INTER_BOLD = "/tmp/fonts/Inter-Bold.ttf"      # instantiated wght 700, see below
INTER_XBOLD = "/tmp/fonts/Inter-ExtraBold.ttf"  # instantiated wght 800, see below
INTER_VF = "/tmp/fonts/Inter-VF.ttf"           # google/fonts Inter variable font
OUTFIT_VF = "/tmp/fonts/Outfit-VF.ttf"
OUTFIT_XB = "/tmp/fonts/Outfit-ExtraBold.ttf"   # instantiated, wght 800
OUTFIT_B = "/tmp/fonts/Outfit-Bold.ttf"         # instantiated, wght 700
MONO_SB = "/tmp/fonts/IBMPlexMono-SemiBold.ttf"
MONO_B = "/tmp/fonts/IBMPlexMono-Bold.ttf"

ASCII_PRINTABLE = "".join(chr(c) for c in range(0x21, 0x7F))  # '!'..'~', no space
# Middle dot U+00B7 (·) is used as a separator in the change row, footer and
# candle note, so the Mono fonts carry it alongside ASCII printable.
ASCII_MIDDOT = ASCII_PRINTABLE + "·"
DIGITS = "0123456789"
PRICE = "$0123456789,."

# (output name, source font path, pixel size, charset)
FONTS = [
    ("OutfitXB29", OUTFIT_XB, 29, PRICE),
    ("OutfitXB30", OUTFIT_XB, 30, PRICE),
    ("OutfitXB22", OUTFIT_XB, 22, PRICE),
    ("OutfitB15",  OUTFIT_B,  15, PRICE),
    ("OutfitB11",  OUTFIT_B,  11, PRICE),
    ("OutfitB9",   OUTFIT_B,   9, ASCII_PRINTABLE),
    ("InterB7",    INTER_BOLD, 7, ASCII_PRINTABLE),
    ("InterXB8",   INTER_XBOLD, 8, ASCII_PRINTABLE),
    ("InterB6",    INTER_BOLD, 6, ASCII_PRINTABLE),
    ("MonoSB8",    MONO_SB,    8, ASCII_MIDDOT),
    ("MonoB8",     MONO_B,     8, ASCII_MIDDOT),
    ("MonoSB7",    MONO_SB,    7, ASCII_MIDDOT),
    ("MonoSB6",    MONO_SB,    6, ASCII_MIDDOT),
    ("MonoB9",     MONO_B,     9, ASCII_MIDDOT),
    ("MonoB13",    MONO_B,    13, DIGITS),
    ("MonoB19",    MONO_B,    19, DIGITS),
]

MARGIN = 16  # px of slack around each rendered glyph (covers negative bearings)


# ---------------------------------------------------------------- helpers
def instantiate_outfit():
    """Instantiate static wght=800 / wght=700 instances from Outfit-VF.ttf."""
    for weight, out_path in ((800, OUTFIT_XB), (700, OUTFIT_B)):
        font = ttLib.TTFont(OUTFIT_VF)
        instantiateVariableFont(font, {"wght": weight}, inplace=True)
        font.save(out_path)
        print(f"  instantiated wght {weight} -> {out_path}")


def instantiate_inter():
    """Instantiate static wght=700 / wght=800 instances from Inter-VF.ttf."""
    for weight, out_path in ((700, INTER_BOLD), (800, INTER_XBOLD)):
        font = ttLib.TTFont(INTER_VF)
        instantiateVariableFont(font, {"wght": weight}, inplace=True)
        font.save(out_path)
        print(f"  instantiated wght {weight} -> {out_path}")


def render_glyph(pil_font, ch, ascent, descent):
    """Render one glyph; return (width, height, gxAdvance, gdY, gdX, bitmap bytes).

    Renders with anchor 'la' so the ascender top is at y=MARGIN and the
    baseline is at y=MARGIN+ascent; cursor x is at x=MARGIN.
    """
    advance = int(round(pil_font.getlength(ch)))
    cell_h = ascent + descent
    img = Image.new("L", (advance + 2 * MARGIN, cell_h + 2 * MARGIN), 0)
    draw = ImageDraw.Draw(img)
    draw.text((MARGIN, MARGIN), ch, font=pil_font, fill=255, anchor="la")
    bbox = img.getbbox()  # bounding box of pixels with alpha > 0, or None
    if bbox is None:
        return 0, 0, advance, 0, 0, b""
    left, top, right, bottom = bbox
    width, height = right - left, bottom - top
    baseline_y = MARGIN + ascent
    gdX = left - MARGIN            # bbox left relative to cursor x
    gdY = baseline_y - top         # baseline to TOP of bitmap (+ve = up)
    bitmap = img.crop(bbox).tobytes()
    return width, height, advance, gdY, gdX, bitmap


def build_vlw(name, source_path, size, charset):
    """Render all glyphs and return (file bytes, missing chars, glyph count)."""
    pil_font = ImageFont.truetype(source_path, size)
    ascent, descent = pil_font.getmetrics()
    ttfont = ttLib.TTFont(source_path)
    cmap = ttfont.getBestCmap()

    glyphs = []   # (unicode, height, width, advance, gdY, gdX, bitmap)
    missing = []
    for ch in sorted(set(charset), key=ord):
        code = ord(ch)
        assert code != 0x20, "space must not be in a vlw glyph table"
        if code not in cmap:
            missing.append(ch)
            continue
        w, h, adv, gdY, gdX, bitmap = render_glyph(pil_font, ch, ascent, descent)
        if not 0 <= adv <= 255:
            raise ValueError(f"{name} U+{code:04X}: gxAdvance {adv} out of uint8 range")
        if not -128 <= gdX <= 127:
            raise ValueError(f"{name} U+{code:04X}: gdX {gdX} out of int8 range")
        if not (0 <= w <= 255 and 0 <= h <= 255):
            raise ValueError(f"{name} U+{code:04X}: bitmap {w}x{h} out of uint8 range")
        glyphs.append((code, h, w, adv, gdY, gdX, bitmap))

    out = bytearray()
    out += struct.pack(">6i", len(glyphs), 11, size, 0, ascent, descent)
    for code, h, w, adv, gdY, gdX, _ in glyphs:
        out += struct.pack(">7i", code, h, w, adv, gdY, gdX, 0)
    for _, _, _, _, _, _, bitmap in glyphs:
        out += bitmap
    # Trailer (loadFont never reads it; written for format completeness).
    name_b = name.encode("ascii")
    out += bytes([len(name_b)]) + name_b + b"\x00"
    out += bytes([len(name_b)]) + name_b + b"\x00"
    out += b"\x01"
    return bytes(out), missing, len(glyphs)


# ---------------------------------------------------------------- main
def main():
    sim_root = Path(__file__).resolve().parent.parent
    firmware_data = sim_root.parent / "ps-keychain-firmware" / "data"
    sim_data = sim_root / "data"
    for d in (firmware_data, sim_data):
        d.mkdir(parents=True, exist_ok=True)

    for path in (INTER_VF, OUTFIT_VF, MONO_SB, MONO_B):
        if not Path(path).exists():
            print(f"FATAL: source font missing: {path}", file=sys.stderr)
            return 1

    print("Instantiating static Outfit weights from variable font...")
    instantiate_outfit()
    print("Instantiating static Inter weights from variable font...")
    instantiate_inter()

    total = 0
    print(f"{'font':<12} {'glyphs':>6} {'bytes':>8}")
    for name, source, size, charset in FONTS:
        data, missing, count = build_vlw(name, source, size, charset)
        for d in (firmware_data, sim_data):
            (d / f"{name}.vlw").write_bytes(data)
        total += len(data)
        print(f"{name:<12} {count:>6} {len(data):>8}")
        if missing:
            print(f"  WARNING: missing from font (skipped): "
                  + ", ".join(f"U+{ord(c):04X} {c!r}" for c in missing))

    print(f"Total: {total} bytes across {len(FONTS)} files "
          f"({total / 1024:.1f} KiB)")
    print(f"Wrote to {firmware_data} and {sim_data}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
