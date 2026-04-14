"""
generate_test_images.py
=======================
Generates synthetic ophthalmology report images that mimic real Zeiss pachymetry
and Tomey topography layouts. Use these to test the OCR pipeline without needing
real patient images.

Usage:
    cd backend
    python3 scripts/generate_test_images.py

Output:
    test_images/
        zeiss_pachymetry_clean.png      — clean digital scan, both eyes
        tomey_topography_os_clean.png   — clean Tomey report (OS)
        tomey_topography_od_clean.png   — clean Tomey report (OD)
        zeiss_pachymetry_degraded.png   — blurry/low-contrast version
        tomey_topography_degraded.png   — partial crop + rotation

KNOWN VALUES baked into each image are printed at the end so you can
compare against what test_ocr.py extracts.
"""

import os
import math
import random
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2

# ── Paths ──────────────────────────────────────────────────────────────────
FONT_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD    = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
OUT_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "test_images")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Font helpers ───────────────────────────────────────────────────────────
def _font(size, bold=False):
    try:
        return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)
    except Exception:
        return ImageFont.load_default()

def _text_w(draw, text, font):
    try:
        return draw.textlength(text, font=font)
    except Exception:
        return len(text) * font.size * 0.6

# ── Known test values ──────────────────────────────────────────────────────
ZEISS_VALUES = {
    "OD": {"cct": 424, "min_thickness": 414, "pachy_min_median": -81},
    "OS": {"cct": 566, "min_thickness": 561, "pachy_min_median": -26},
}

TOMEY_OS_VALUES = {
    "SK1": 46.40, "SK2": 45.43, "CYL": 0.97,
    "Ks_val": 46.40, "Ks_axis": 125,
    "SK2_val": 45.43, "SK2_axis": 35,
    "MinK": 45.37, "MinK_axis": 27,
    "AvgK": 45.91,
}

TOMEY_OD_VALUES = {
    "SK1": 44.21, "SK2": 42.18, "CYL": 2.03,
    "Ks_val": 44.21, "Ks_axis": 85,
    "SK2_val": 42.18, "SK2_axis": 175,
    "MinK": 42.10, "MinK_axis": 170,
    "AvgK": 43.20,
}

# ══════════════════════════════════════════════════════════════════════════
# ZEISS PACHYMETRY
# ══════════════════════════════════════════════════════════════════════════

def generate_zeiss_pachymetry(values=None, output_path=None, degraded=False):
    """Generates a Zeiss CIRRUS-style pachymetry report image."""
    if values is None:
        values = ZEISS_VALUES
    if output_path is None:
        tag = "degraded" if degraded else "clean"
        output_path = os.path.join(OUT_DIR, f"zeiss_pachymetry_{tag}.png")

    W, H = 1100, 620
    img = Image.new("RGB", (W, H), color=(255, 255, 255))
    d   = ImageDraw.Draw(img)

    # ── Header ──────────────────────────────────────────────────────────
    d.rectangle([0, 0, W, 38], fill=(230, 230, 230))
    d.text((W//2, 10), "Pachymetry Analysis : Pachymetry",
           font=_font(16, bold=True), fill=(0, 0, 0), anchor="mt")
    d.text((W - 60, 10), "OD", font=_font(14, bold=True), fill=(0, 0, 0), anchor="mt")
    d.text((W - 20, 10), "OS", font=_font(14, bold=True), fill=(0, 0, 0), anchor="mt")

    # Patient info row
    d.text((10, 48), "Name:  Faris, M.S.Mr",        font=_font(11), fill=(40, 40, 40))
    d.text((10, 63), "ID:    150317",                font=_font(11), fill=(40, 40, 40))
    d.text((10, 78), "DOB:   6/8/2004",              font=_font(11), fill=(40, 40, 40))
    d.text((400, 48), "Exam Date:  10/31/2025",      font=_font(11), fill=(40, 40, 40))
    d.text((400, 63), "Exam Time:  5:08 PM",         font=_font(11), fill=(40, 40, 40))
    d.text((750, 48), "Vasan Hospital",              font=_font(11, bold=True), fill=(0, 0, 128))

    # ── Divider ─────────────────────────────────────────────────────────
    d.line([(0, 100), (W, 100)], fill=(180, 180, 180), width=1)

    # ── Draw one pachymetry table (OD or OS) ────────────────────────────
    def draw_pachy_table(x_start, eye_label, eye_vals):
        col_w   = [90, 65, 65, 65, 60, 70]
        headers = ["Range (mm)", "Min. (µm)", "Avg. (µm)", "Max. (µm)", "S-I (µm)", "SN-IT (µm)"]
        rows    = [
            ["0.0-2.0", "414", "439", "482", "-", "-"],
            ["2.0-5.0", "418", "502", "583", "37", "58"],
            ["5.0-7.0", "495", "579", "651", "45", "67"],
        ]
        if eye_label == "OS":
            rows = [
                ["0.0-2.0", "561", "568", "584", "-", "-"],
                ["2.0-5.0", "561", "589", "630", "-21", "-2"],
                ["5.0-7.0", "586", "623", "668", "-6", "14"],
            ]

        # Section title
        y = 110
        d.text((x_start, y), f"Pachymetry {eye_label}",
               font=_font(12, bold=True), fill=(0, 0, 0))
        y += 22

        # Header row
        x = x_start
        d.rectangle([x, y, x + sum(col_w), y + 20], fill=(210, 210, 210))
        for i, (h, w) in enumerate(zip(headers, col_w)):
            d.text((x + 4, y + 3), h, font=_font(9, bold=True), fill=(0, 0, 0))
            x += w
        y += 20

        # Data rows
        for ri, row in enumerate(rows):
            x = x_start
            bg = (248, 248, 248) if ri % 2 == 0 else (255, 255, 255)
            d.rectangle([x_start, y, x_start + sum(col_w), y + 18], fill=bg)
            for val, w in zip(row, col_w):
                d.text((x + 4, y + 2), val, font=_font(10), fill=(0, 0, 0))
                x += w
            y += 18

        # Borders
        d.rectangle([x_start, 132, x_start + sum(col_w), y],
                    outline=(140, 140, 140), width=1)

        # Footer rows (min thickness + CCT)
        y += 4
        min_t = eye_vals["min_thickness"]
        pmm   = eye_vals["pachy_min_median"]
        cct   = eye_vals["cct"]

        d.rectangle([x_start, y, x_start + sum(col_w), y + 18], fill=(240, 245, 240))
        d.text((x_start + 4,  y + 2), f"Minimum Thickness (µm)",  font=_font(9, bold=True), fill=(0,0,0))
        d.text((x_start + 180, y + 2), str(min_t),                 font=_font(10, bold=True), fill=(0,0,0))
        d.text((x_start + 260, y + 2), "Y Min (µm)",              font=_font(9, bold=True), fill=(0,0,0))
        d.text((x_start + 360, y + 2), "-221" if eye_label == "OD" else "661", font=_font(10), fill=(0,0,0))
        y += 18

        d.rectangle([x_start, y, x_start + sum(col_w), y + 18], fill=(220, 240, 220))
        d.text((x_start + 4,  y + 2), f"Pachy Min-Median (µm)",   font=_font(9, bold=True), fill=(0,0,0))
        d.text((x_start + 180, y + 2), str(pmm),                   font=_font(10, bold=True), fill=(0,0,0))
        d.text((x_start + 260, y + 2), "Central Corneal Thickness (µm)", font=_font(9, bold=True), fill=(0,0,0))
        # CCT value — make it slightly larger so OCR has a better shot
        d.text((x_start + 460, y + 2), str(cct),
               font=_font(11, bold=True), fill=(0, 0, 180))
        d.rectangle([x_start, y, x_start + sum(col_w), y + 18],
                    outline=(100, 140, 100), width=1)

    draw_pachy_table(10,  "OD", values["OD"])
    draw_pachy_table(580, "OS", values["OS"])

    # ── Footer label ────────────────────────────────────────────────────
    d.text((10, H - 20), "ZEISS  |  CIRRUS 6000  |  Serial: 6000-11921",
           font=_font(9), fill=(120, 120, 120))

    if degraded:
        img = _apply_degradation(img, blur=2.5, noise=18, rotate=2.5, crop_right=60)

    img.save(output_path, dpi=(150, 150))
    print(f"[GEN] Saved: {output_path}")
    return output_path, values


# ══════════════════════════════════════════════════════════════════════════
# TOMEY TOPOGRAPHY
# ══════════════════════════════════════════════════════════════════════════

def generate_tomey_topography(eye="OS", values=None, output_path=None, degraded=False):
    """Generates a Tomey RT-7000 style topography report with colored K labels."""
    if values is None:
        values = TOMEY_OS_VALUES if eye == "OS" else TOMEY_OD_VALUES
    if output_path is None:
        tag = "degraded" if degraded else "clean"
        output_path = os.path.join(OUT_DIR, f"tomey_topography_{eye.lower()}_{tag}.png")

    W, H = 900, 800
    img = Image.new("RGB", (W, H), color=(255, 255, 255))
    d   = ImageDraw.Draw(img)

    # ── Patient header ───────────────────────────────────────────────────
    d.text((10, 10), f"Faris.,Mr.M.S.",     font=_font(11, bold=True), fill=(0,0,0))
    d.text((300, 10), f"ID#: 150317",       font=_font(11), fill=(0,0,0))
    d.text((500, 10), "Sex: M",             font=_font(11), fill=(0,0,0))
    d.text((W - 50, 6), eye,               font=_font(20, bold=True), fill=(0,0,0), anchor="rt")
    d.text((10, 26), "DOB: 6/8/2004",      font=_font(11), fill=(0,0,0))
    d.text((10, 42), "Date: 10/31/2025  17:10:24", font=_font(11), fill=(0,0,0))
    d.line([(0, 58), (W, 58)], fill=(180, 180, 180), width=1)

    # ── Colored K-values header bar ──────────────────────────────────────
    # This is the critical row — OCR must read the red values
    d.rectangle([0, 62, W, 90], fill=(245, 245, 245))

    SK1   = values["SK1"]
    SK2_v = values["SK2"]
    CYL   = values["CYL"]
    Ks_a  = values["Ks_axis"]
    SK2_a = values["SK2_axis"]
    MinK  = values["MinK"]
    MinK_a= values["MinK_axis"]
    AvgK  = values["AvgK"]

    RED   = (200, 0, 0)
    GREEN = (0, 140, 0)

    # Ks (steep K = SK1)
    d.text((10,  66), "Ks:",                      font=_font(11, bold=True), fill=(0,0,0))
    d.text((32,  66), f"{SK1:.2f} @ {Ks_a}°",    font=_font(11, bold=True), fill=RED)

    # SK2
    d.text((175, 66), "SK2:",                     font=_font(11, bold=True), fill=(0,0,0))
    d.text((205, 66), f"{SK2_v:.2f} @ {SK2_a}°", font=_font(11, bold=True), fill=RED)

    # MinK
    d.text((350, 66), "MinK:",                    font=_font(11, bold=True), fill=(0,0,0))
    d.text((385, 66), f"{MinK:.2f} @ {MinK_a}°", font=_font(11, bold=True), fill=GREEN)

    # AvgK
    d.text((530, 66), "AvgK:",                    font=_font(11, bold=True), fill=(0,0,0))
    d.text((568, 66), f"{AvgK:.2f}",             font=_font(11, bold=True), fill=GREEN)

    # CYL
    d.text((660, 66), "Cyl:",                     font=_font(11, bold=True), fill=(0,0,0))
    d.text((690, 66), f"{CYL:.2f}",              font=_font(11, bold=True), fill=RED)

    d.line([(0, 90), (W, 90)], fill=(160, 160, 160), width=1)

    # ── Map placeholders ─────────────────────────────────────────────────
    # Left map (Standard) — filled circle placeholder
    d.rectangle([20, 100, 320, 400], fill=(240, 240, 255), outline=(180, 180, 200))
    d.text((170, 245), "Standard", font=_font(13), fill=(100, 100, 130), anchor="mm")

    # Right map (Absolute)
    d.rectangle([360, 100, 660, 400], fill=(255, 240, 230), outline=(200, 180, 180))
    d.text((510, 245), "Absolute", font=_font(13), fill=(130, 100, 100), anchor="mm")

    d.text((20,  405), "Standard",  font=_font(10), fill=(80, 80, 80))
    d.text((360, 405), "Absolute",  font=_font(10), fill=(80, 80, 80))
    d.text((700, 405), "Diopters",  font=_font(10), fill=(80, 80, 80))

    # Color scale bar
    for i in range(300):
        h_val = int(240 - (i / 300) * 240)
        r, g, b = _hsv_to_rgb(h_val, 255, 200)
        d.line([(700 + i, 350), (700 + i, 395)], fill=(r, g, b))
    d.text((700, 400), "9.0", font=_font(8), fill=(60,60,60))
    d.text((990, 400), "101.6", font=_font(8), fill=(60,60,60))

    d.line([(0, 420), (W, 420)], fill=(160, 160, 160), width=1)

    # ── Keratoconus screening section ────────────────────────────────────
    d.text((20,  430), "Klyce / Maeda",           font=_font(11, bold=True), fill=(0,0,0))
    d.text((280, 430), "Smolek / Klyce",           font=_font(11, bold=True), fill=(0,0,0))
    d.text((540, 430), "Keratoconus",              font=_font(11, bold=True), fill=(0,0,0))
    d.text((540, 444), "Screening System",         font=_font(11, bold=True), fill=(0,0,0))
    d.text((20,  448), "KCI",                      font=_font(11), fill=(0,0,0))
    d.text((280, 448), "KSI",                      font=_font(11), fill=(0,0,0))
    d.text((20,  464), "0.0% Similarity",          font=_font(11), fill=GREEN)
    d.text((280, 464), "16.1% Severity",           font=_font(11), fill=RED)
    d.text((20,  482), "Keratoconus Pattern",      font=_font(10), fill=GREEN)
    d.text((20,  497), "not Detected",             font=_font(10), fill=GREEN)
    d.text((280, 482), "Keratoconus",              font=_font(10), fill=(180, 120, 0))
    d.text((280, 497), "Suspect Interpreted",      font=_font(10), fill=(180, 120, 0))

    # SK1 screening bar
    d.text((540, 462), f"SK1: {SK1:.2f} @{Ks_a}°", font=_font(10, bold=True), fill=RED)

    d.line([(0, 530), (W, 530)], fill=(160, 160, 160), width=1)

    # ── Related Indices section ───────────────────────────────────────────
    d.text((20, 538), "Related Indices",           font=_font(12, bold=True), fill=(0, 0, 0))
    d.line([(20, 554), (W - 20, 554)], fill=(180, 180, 180), width=1)

    # Three-column layout
    indices_left = [
        ("SK1",  f"{SK1:.2f}",  RED),
        ("SAI",  "0.56",        RED),
        ("OSI",  "1.77",        RED),
        ("IAI",  "0.41",        RED),
    ]
    indices_mid = [
        ("SK2",  f"{SK2_v:.2f}", RED),
        ("DSI",  "2.97",         RED),
        ("CSI",  "-0.30",        GREEN),
        ("KPI",  "0.23",         RED),
    ]
    indices_right = [
        ("CYL",  f"{CYL:.2f}",  RED),
        ("SRI",  "0.34",         GREEN),
        ("SDP",  "1.00",         GREEN),
        ("AA",   "88.15%",       GREEN),
    ]

    def draw_index_col(x, items, y_start=560):
        y = y_start
        for label, val, color in items:
            d.text((x,     y), f"{label} :",    font=_font(11, bold=True), fill=(0, 0, 0))
            d.text((x + 55, y), val,            font=_font(11, bold=True), fill=color)
            y += 22

    draw_index_col(20,  indices_left)
    draw_index_col(200, indices_mid)
    draw_index_col(380, indices_right)

    # ── Footer ───────────────────────────────────────────────────────────
    d.line([(0, H - 30), (W, H - 30)], fill=(180, 180, 180), width=1)
    d.text((10, H - 22), "TOMEY  RT-7000  |  22C-200S-2D1",
           font=_font(9), fill=(120, 120, 120))

    if degraded:
        img = _apply_degradation(img, blur=1.8, noise=12, rotate=1.5, crop_right=30, crop_top=0)

    img.save(output_path, dpi=(150, 150))
    print(f"[GEN] Saved: {output_path}")
    return output_path, values


# ══════════════════════════════════════════════════════════════════════════
# DEGRADATION helpers
# ══════════════════════════════════════════════════════════════════════════

def _apply_degradation(img, blur=2.0, noise=15, rotate=2.0, crop_right=0, crop_top=0):
    """Simulate a badly photographed / scanned image."""
    arr = np.array(img)

    # Gaussian blur
    if blur > 0:
        k = int(blur * 2) | 1          # odd kernel size
        arr = cv2.GaussianBlur(arr, (k, k), blur)

    # Gaussian noise
    if noise > 0:
        gauss = np.random.normal(0, noise, arr.shape).astype(np.int16)
        arr = np.clip(arr.astype(np.int16) + gauss, 0, 255).astype(np.uint8)

    # Slight rotation
    if rotate != 0:
        h, w = arr.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), rotate, 1.0)
        arr = cv2.warpAffine(arr, M, (w, h), borderValue=(255, 255, 255))

    # Crop right/top edges to simulate partial framing
    h, w = arr.shape[:2]
    arr = arr[crop_top:, :w - crop_right]

    return Image.fromarray(arr)


def _hsv_to_rgb(h, s, v):
    h = h / 255 * 360
    s = s / 255
    v = v / 255
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c
    if   h < 60:  r, g, b = c, x, 0
    elif h < 120: r, g, b = x, c, 0
    elif h < 180: r, g, b = 0, c, x
    elif h < 240: r, g, b = 0, x, c
    elif h < 300: r, g, b = x, 0, c
    else:          r, g, b = c, 0, x
    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("Generating synthetic test images...")
    print("=" * 60)

    generate_zeiss_pachymetry(degraded=False)
    generate_zeiss_pachymetry(degraded=True)
    generate_tomey_topography(eye="OS", degraded=False)
    generate_tomey_topography(eye="OD", degraded=False)
    generate_tomey_topography(eye="OS", degraded=True)

    print()
    print("=" * 60)
    print("KNOWN VALUES — compare against test_ocr.py output")
    print("=" * 60)
    print("\nZeiss Pachymetry:")
    print(f"  OD Central Corneal Thickness : {ZEISS_VALUES['OD']['cct']} µm")
    print(f"  OS Central Corneal Thickness : {ZEISS_VALUES['OS']['cct']} µm")
    print("\nTomey OS:")
    print(f"  K1 (flat)  : {TOMEY_OS_VALUES['SK2']:.2f} D  (SK2 = flatter)")
    print(f"  K2 (steep) : {TOMEY_OS_VALUES['SK1']:.2f} D  (SK1 = steeper)")
    print(f"  CYL        : {TOMEY_OS_VALUES['CYL']:.2f} D")
    print("\nTomey OD:")
    print(f"  K1 (flat)  : {TOMEY_OD_VALUES['SK2']:.2f} D")
    print(f"  K2 (steep) : {TOMEY_OD_VALUES['SK1']:.2f} D")
    print(f"  CYL        : {TOMEY_OD_VALUES['CYL']:.2f} D")
    print()
    print(f"Images saved to: {OUT_DIR}/")
    print("Run:  python3 scripts/test_ocr.py")


if __name__ == "__main__":
    main()
