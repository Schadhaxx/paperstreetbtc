#!/usr/bin/env python3
"""Composite sim PPM frames into video frames (960x1020 canvas).

Layout: device screen scaled 3x nearest-neighbour, centred in a 960x960
area; a 60px caption strip at the bottom. Tap indicators (cyan rings)
are drawn at the recorded canvas coords, fading over 0.5s.
"""
import json, sys, os, math
from PIL import Image, ImageDraw, ImageFont

SIM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANVAS_W, CANVAS_H = 960, 1020
DEV_AREA_H = 960
BG = (11, 17, 32)          # canvas background (slightly lighter than device bg)
BORDER = (30, 41, 59)      # device border
CAPTION_COLOR = (154, 166, 188)
RING_COLOR = (34, 211, 238)  # cyan
SCALE = 3

def device_rect(w, h):
    dw, dh = w * SCALE, h * SCALE
    x = (CANVAS_W - dw) // 2
    y = (DEV_AREA_H - dh) // 2
    return x, y, dw, dh

def main():
    manifest = json.load(open(os.path.join(SIM_DIR, "frames", "manifest.json")))
    outdir = os.path.join(SIM_DIR, "video_frames")
    os.makedirs(outdir, exist_ok=True)
    try:
        capfont = ImageFont.truetype(
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 30)
    except Exception:
        capfont = ImageFont.load_default()
    taps = manifest["taps"]
    for i, fr in enumerate(manifest["frames"]):
        ppm = Image.open(os.path.join(SIM_DIR, "frames", fr["file"])).convert("RGB")
        w, h = ppm.size
        # Smooth upscale (LANCZOS) — the device is anti-aliased now,
        # so the video must not re-pixelate it with nearest-neighbour.
        big = ppm.resize((w * SCALE, h * SCALE), Image.LANCZOS)
        canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
        x, y, dw, dh = device_rect(w, h)
        canvas.paste(big, (x, y))
        overlay = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rectangle([x - 2, y - 2, x + dw + 1, y + dh + 1], outline=BORDER + (255,), width=2)
        # tap indicators: white ring + dot (visible on dark bg and on
        # cyan active buttons), fading over 0.7s after the tap
        t = fr["t"]
        for tap in taps:
            dt = t - tap["t"]
            if 0 <= dt <= 0.7:
                a = int(255 * (1 - dt / 0.7))
                cx, cy = tap["x"], tap["y"]
                od.ellipse([cx - 33, cy - 33, cx + 33, cy + 33],
                           outline=(0, 0, 0, int(a * 0.7)), width=9)
                od.ellipse([cx - 28, cy - 28, cx + 28, cy + 28],
                           outline=(255, 255, 255, a), width=5)
                od.ellipse([cx - 6, cy - 6, cx + 6, cy + 6],
                           fill=(255, 255, 255, a))
        # swipe indicators: cyan arrow from finger-down to lift,
        # fading over 0.7s after the swipe (same window as taps)
        t = fr["t"]
        for sw in manifest.get("swipes", []):
            dt = t - sw["t"]
            if 0 <= dt <= 0.7:
                a = int(255 * (1 - dt / 0.7))
                x0, y0, x1, y1 = sw["x0"], sw["y0"], sw["x1"], sw["y1"]
                od.line([x0, y0, x1, y1], fill=(34, 211, 238, a), width=5)
                od.ellipse([x0 - 6, y0 - 6, x0 + 6, y0 + 6],
                           fill=(34, 211, 238, a))
                ang = math.atan2(y1 - y0, x1 - x0)
                for da in (2.6, -2.6):
                    ex = x1 - 18 * math.cos(ang + da)
                    ey = y1 - 18 * math.sin(ang + da)
                    od.line([x1, y1, ex, ey], fill=(34, 211, 238, a), width=5)
        canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
        d = ImageDraw.Draw(canvas)
        cap = fr["caption"]
        bbox = d.textbbox((0, 0), cap, font=capfont)
        cw = bbox[2] - bbox[0]
        d.text(((CANVAS_W - cw) // 2, 972), cap, font=capfont, fill=CAPTION_COLOR)
        canvas.save(os.path.join(outdir, f"comp_{i:04d}.png"))
    print(f"composited {len(manifest['frames'])} frames -> {outdir}")

if __name__ == "__main__":
    main()
