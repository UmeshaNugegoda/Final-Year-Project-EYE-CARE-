"""
generate_test_images.py
=======================
Generates synthetic ophthalmology report images that mimic real Zeiss pachymetry,
Tomey topography, and prescription card layouts.

Usage:
    cd backend
    python3 scripts/generate_test_images.py

Output:
    test_images/
        patient_1/  patient_2/  patient_3/  patient_4/
            topography_od.png
            topography_os.png
            pachymetry.png
            prescription_card.png

    (Legacy single-patient images also regenerated for test_ocr.py)
    zeiss_pachymetry_clean.png
    zeiss_pachymetry_degraded.png
    tomey_topography_os_clean.png
    tomey_topography_od_clean.png
    tomey_topography_os_degraded.png
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

# ══════════════════════════════════════════════════════════════════════════
# LEGACY KNOWN VALUES  (kept for test_ocr.py backward-compatibility)
# ══════════════════════════════════════════════════════════════════════════
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
# 4-PATIENT TEST DATASET
# Each patient has OD + OS entries for topography, pachymetry, and refraction.
# ══════════════════════════════════════════════════════════════════════════
PATIENTS = [
    {
        "id": "PAT-001",
        "name": "Ahmed, R.M.",
        "dob": "14/03/1996",
        "exam_date": "02/04/2026",
        "months_post_dalk": 8,
        "note": "Likely → Spectacles",
        "topo": {
            "OD": {"SK1": 44.80, "SK2": 43.25, "CYL": 1.55, "Ks_axis": 90, "SK2_axis": 0,
                   "MinK": 43.10, "MinK_axis": 5, "AvgK": 44.03},
            "OS": {"SK1": 45.20, "SK2": 44.10, "CYL": 1.10, "Ks_axis": 88, "SK2_axis": 178,
                   "MinK": 44.02, "MinK_axis": 172, "AvgK": 44.65},
        },
        "pachy": {
            "OD": {"cct": 498, "min_thickness": 489, "pachy_min_median": -42},
            "OS": {"cct": 512, "min_thickness": 505, "pachy_min_median": -31},
        },
        "rx": {
            "OD": {"ucva": "6/36", "bcva": "6/9",  "sphere": -1.00, "cylinder": -1.50, "axis": 85},
            "OS": {"ucva": "6/24", "bcva": "6/9",  "sphere": -0.75, "cylinder": -1.00, "axis": 95},
        },
    },
    {
        "id": "PAT-002",
        "name": "Fernando, S.K.",
        "dob": "07/11/1989",
        "exam_date": "02/04/2026",
        "months_post_dalk": 18,
        "note": "Likely → Contact Lenses",
        "topo": {
            "OD": {"SK1": 48.30, "SK2": 46.50, "CYL": 1.80, "Ks_axis": 70, "SK2_axis": 160,
                   "MinK": 46.30, "MinK_axis": 155, "AvgK": 47.40},
            "OS": {"SK1": 49.10, "SK2": 47.20, "CYL": 1.90, "Ks_axis": 110, "SK2_axis": 20,
                   "MinK": 47.00, "MinK_axis": 18, "AvgK": 48.15},
        },
        "pachy": {
            "OD": {"cct": 462, "min_thickness": 451, "pachy_min_median": -68},
            "OS": {"cct": 471, "min_thickness": 462, "pachy_min_median": -57},
        },
        "rx": {
            "OD": {"ucva": "6/60", "bcva": "6/12", "sphere": -2.50, "cylinder": -2.00, "axis": 70},
            "OS": {"ucva": "6/60", "bcva": "6/12", "sphere": -2.25, "cylinder": -2.25, "axis": 110},
        },
    },
    {
        "id": "PAT-003",
        "name": "Perera, K.J.",
        "dob": "22/06/1982",
        "exam_date": "02/04/2026",
        "months_post_dalk": 24,
        "note": "Likely → No Correction",
        "topo": {
            "OD": {"SK1": 43.40, "SK2": 42.80, "CYL": 0.60, "Ks_axis": 92, "SK2_axis": 2,
                   "MinK": 42.70, "MinK_axis": 8, "AvgK": 43.10},
            "OS": {"SK1": 43.90, "SK2": 43.20, "CYL": 0.70, "Ks_axis": 87, "SK2_axis": 177,
                   "MinK": 43.10, "MinK_axis": 175, "AvgK": 43.55},
        },
        "pachy": {
            "OD": {"cct": 535, "min_thickness": 528, "pachy_min_median": -18},
            "OS": {"cct": 542, "min_thickness": 536, "pachy_min_median": -12},
        },
        "rx": {
            "OD": {"ucva": "6/9",  "bcva": "6/6",  "sphere": +0.25, "cylinder": -0.50, "axis": 180},
            "OS": {"ucva": "6/7.5","bcva": "6/6",  "sphere": +0.25, "cylinder": -0.25, "axis": 175},
        },
    },
    {
        "id": "PAT-004",
        "name": "Nishantha, D.P.",
        "dob": "19/09/1993",
        "exam_date": "02/04/2026",
        "months_post_dalk": 12,
        "note": "Likely → Spectacles",
        "topo": {
            "OD": {"SK1": 46.80, "SK2": 45.00, "CYL": 1.80, "Ks_axis": 60, "SK2_axis": 150,
                   "MinK": 44.85, "MinK_axis": 145, "AvgK": 45.90},
            "OS": {"SK1": 46.20, "SK2": 44.75, "CYL": 1.45, "Ks_axis": 120, "SK2_axis": 30,
                   "MinK": 44.60, "MinK_axis": 28, "AvgK": 45.48},
        },
        "pachy": {
            "OD": {"cct": 480, "min_thickness": 471, "pachy_min_median": -55},
            "OS": {"cct": 488, "min_thickness": 479, "pachy_min_median": -48},
        },
        "rx": {
            "OD": {"ucva": "6/24", "bcva": "6/12", "sphere": -1.75, "cylinder": -1.75, "axis": 60},
            "OS": {"ucva": "6/18", "bcva": "6/9",  "sphere": -1.50, "cylinder": -1.50, "axis": 120},
        },
    },
]


# ══════════════════════════════════════════════════════════════════════════
# ZEISS PACHYMETRY
# ══════════════════════════════════════════════════════════════════════════
def generate_zeiss_pachymetry(values, patient_name="", patient_id="",
                               dob="", exam_date="", output_path=None, degraded=False):
    """Generates a Zeiss CIRRUS-style pachymetry report image."""
    W, H = 1100, 620
    img = Image.new("RGB", (W, H), color=(255, 255, 255))
    d   = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 38], fill=(230, 230, 230))
    d.text((W//2, 10), "Pachymetry Analysis : Pachymetry",
           font=_font(16, bold=True), fill=(0, 0, 0), anchor="mt")
    d.text((W - 60, 10), "OD", font=_font(14, bold=True), fill=(0, 0, 0), anchor="mt")
    d.text((W - 20, 10), "OS", font=_font(14, bold=True), fill=(0, 0, 0), anchor="mt")

    d.text((10, 48), f"Name:  {patient_name}",  font=_font(11), fill=(40, 40, 40))
    d.text((10, 63), f"ID:    {patient_id}",    font=_font(11), fill=(40, 40, 40))
    d.text((10, 78), f"DOB:   {dob}",           font=_font(11), fill=(40, 40, 40))
    d.text((400, 48), f"Exam Date:  {exam_date}", font=_font(11), fill=(40, 40, 40))
    d.text((750, 48), "Vasan Hospital",          font=_font(11, bold=True), fill=(0, 0, 128))
    d.line([(0, 100), (W, 100)], fill=(180, 180, 180), width=1)

    def draw_pachy_table(x_start, eye_label, eye_vals):
        col_w   = [90, 65, 65, 65, 60, 70]
        headers = ["Range (mm)", "Min. (µm)", "Avg. (µm)", "Max. (µm)", "S-I (µm)", "SN-IT (µm)"]
        min_t = eye_vals["min_thickness"]
        cct   = eye_vals["cct"]

        if eye_label == "OD":
            rows = [
                ["0.0-2.0", str(min_t), str(min_t+25), str(min_t+68), "-", "-"],
                ["2.0-5.0", str(min_t+4), str(min_t+88), str(min_t+169), "37", "58"],
                ["5.0-7.0", str(min_t+81), str(min_t+165), str(min_t+237), "45", "67"],
            ]
        else:
            rows = [
                ["0.0-2.0", str(min_t), str(min_t+7), str(min_t+23), "-", "-"],
                ["2.0-5.0", str(min_t), str(min_t+28), str(min_t+69), "-21", "-2"],
                ["5.0-7.0", str(min_t+25), str(min_t+62), str(min_t+107), "-6", "14"],
            ]

        y = 110
        d.text((x_start, y), f"Pachymetry {eye_label}",
               font=_font(12, bold=True), fill=(0, 0, 0))
        y += 22

        x = x_start
        d.rectangle([x, y, x + sum(col_w), y + 20], fill=(210, 210, 210))
        for h, w in zip(headers, col_w):
            d.text((x + 4, y + 3), h, font=_font(9, bold=True), fill=(0, 0, 0))
            x += w
        y += 20

        for ri, row in enumerate(rows):
            x = x_start
            bg = (248, 248, 248) if ri % 2 == 0 else (255, 255, 255)
            d.rectangle([x_start, y, x_start + sum(col_w), y + 18], fill=bg)
            for val, w in zip(row, col_w):
                d.text((x + 4, y + 2), val, font=_font(10), fill=(0, 0, 0))
                x += w
            y += 18

        d.rectangle([x_start, 132, x_start + sum(col_w), y],
                    outline=(140, 140, 140), width=1)
        y += 4

        pmm = eye_vals["pachy_min_median"]
        d.rectangle([x_start, y, x_start + sum(col_w), y + 18], fill=(240, 245, 240))
        d.text((x_start + 4,   y + 2), "Minimum Thickness (µm)",  font=_font(9, bold=True), fill=(0,0,0))
        d.text((x_start + 180, y + 2), str(min_t),                 font=_font(10, bold=True), fill=(0,0,0))
        d.text((x_start + 260, y + 2), "Y Min (µm)",               font=_font(9, bold=True), fill=(0,0,0))
        d.text((x_start + 360, y + 2), "-221" if eye_label == "OD" else "661", font=_font(10), fill=(0,0,0))
        y += 18

        d.rectangle([x_start, y, x_start + sum(col_w), y + 18], fill=(220, 240, 220))
        d.text((x_start + 4,   y + 2), "Pachy Min-Median (µm)",            font=_font(9, bold=True), fill=(0,0,0))
        d.text((x_start + 180, y + 2), str(pmm),                            font=_font(10, bold=True), fill=(0,0,0))
        d.text((x_start + 260, y + 2), "Central Corneal Thickness (µm)",   font=_font(9, bold=True), fill=(0,0,0))
        d.text((x_start + 460, y + 2), str(cct),                            font=_font(11, bold=True), fill=(0, 0, 180))
        d.rectangle([x_start, y, x_start + sum(col_w), y + 18],
                    outline=(100, 140, 100), width=1)

    draw_pachy_table(10,  "OD", values["OD"])
    draw_pachy_table(580, "OS", values["OS"])
    d.text((10, H - 20), "ZEISS  |  CIRRUS 6000  |  Serial: 6000-11921",
           font=_font(9), fill=(120, 120, 120))

    if degraded:
        img = _apply_degradation(img, blur=2.5, noise=18, rotate=2.5, crop_right=60)

    img.save(output_path, dpi=(150, 150))
    print(f"[GEN] Saved: {output_path}")
    return output_path


# ══════════════════════════════════════════════════════════════════════════
# TOMEY TOPOGRAPHY
# ══════════════════════════════════════════════════════════════════════════
def generate_tomey_topography(eye, values, patient_name="", patient_id="",
                               dob="", exam_date="", output_path=None, degraded=False):
    """Generates a Tomey RT-7000 style topography report with colored K labels."""
    W, H = 900, 800
    img = Image.new("RGB", (W, H), color=(255, 255, 255))
    d   = ImageDraw.Draw(img)

    d.text((10, 10),  patient_name,              font=_font(11, bold=True), fill=(0,0,0))
    d.text((300, 10), f"ID#: {patient_id}",      font=_font(11), fill=(0,0,0))
    d.text((500, 10), "Sex: M",                  font=_font(11), fill=(0,0,0))
    d.text((W - 50, 6), eye,                    font=_font(20, bold=True), fill=(0,0,0), anchor="rt")
    d.text((10, 26),  f"DOB: {dob}",             font=_font(11), fill=(0,0,0))
    d.text((10, 42),  f"Date: {exam_date}  17:10:24", font=_font(11), fill=(0,0,0))
    d.line([(0, 58), (W, 58)], fill=(180, 180, 180), width=1)

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

    d.text((10,  66), "Ks:",                       font=_font(11, bold=True), fill=(0,0,0))
    d.text((32,  66), f"{SK1:.2f} @ {Ks_a}°",     font=_font(11, bold=True), fill=RED)
    d.text((175, 66), "SK2:",                      font=_font(11, bold=True), fill=(0,0,0))
    d.text((205, 66), f"{SK2_v:.2f} @ {SK2_a}°",  font=_font(11, bold=True), fill=RED)
    d.text((350, 66), "MinK:",                     font=_font(11, bold=True), fill=(0,0,0))
    d.text((385, 66), f"{MinK:.2f} @ {MinK_a}°",  font=_font(11, bold=True), fill=GREEN)
    d.text((530, 66), "AvgK:",                     font=_font(11, bold=True), fill=(0,0,0))
    d.text((568, 66), f"{AvgK:.2f}",              font=_font(11, bold=True), fill=GREEN)
    d.text((660, 66), "Cyl:",                      font=_font(11, bold=True), fill=(0,0,0))
    d.text((690, 66), f"{CYL:.2f}",               font=_font(11, bold=True), fill=RED)
    d.line([(0, 90), (W, 90)], fill=(160, 160, 160), width=1)

    d.rectangle([20,  100, 320, 400], fill=(240, 240, 255), outline=(180, 180, 200))
    d.text((170, 245), "Standard", font=_font(13), fill=(100, 100, 130), anchor="mm")
    d.rectangle([360, 100, 660, 400], fill=(255, 240, 230), outline=(200, 180, 180))
    d.text((510, 245), "Absolute", font=_font(13), fill=(130, 100, 100), anchor="mm")

    for i in range(300):
        h_val = int(240 - (i / 300) * 240)
        r, g, b = _hsv_to_rgb(h_val, 255, 200)
        d.line([(700 + i, 350), (700 + i, 395)], fill=(r, g, b))
    d.line([(0, 420), (W, 420)], fill=(160, 160, 160), width=1)

    d.text((20, 430),  "Klyce / Maeda",       font=_font(11, bold=True), fill=(0,0,0))
    d.text((280, 430), "Smolek / Klyce",       font=_font(11, bold=True), fill=(0,0,0))
    d.text((540, 430), "Keratoconus",          font=_font(11, bold=True), fill=(0,0,0))
    d.text((540, 444), "Screening System",     font=_font(11, bold=True), fill=(0,0,0))
    d.text((20, 464),  "0.0% Similarity",      font=_font(11), fill=GREEN)
    d.text((280, 464), "16.1% Severity",       font=_font(11), fill=RED)
    d.text((20, 482),  "Keratoconus Pattern",  font=_font(10), fill=GREEN)
    d.text((20, 497),  "not Detected",         font=_font(10), fill=GREEN)
    d.text((540, 462), f"SK1: {SK1:.2f} @{Ks_a}°", font=_font(10, bold=True), fill=RED)
    d.line([(0, 530), (W, 530)], fill=(160, 160, 160), width=1)

    d.text((20, 538), "Related Indices", font=_font(12, bold=True), fill=(0, 0, 0))
    d.line([(20, 554), (W - 20, 554)], fill=(180, 180, 180), width=1)

    indices_left  = [("SK1", f"{SK1:.2f}",  RED),  ("SAI", "0.56", RED),  ("OSI", "1.77", RED),  ("IAI", "0.41", RED)]
    indices_mid   = [("SK2", f"{SK2_v:.2f}", RED),  ("DSI", "2.97", RED),  ("CSI", "-0.30", GREEN), ("KPI", "0.23", RED)]
    indices_right = [("CYL", f"{CYL:.2f}",  RED),  ("SRI", "0.34", GREEN), ("SDP", "1.00", GREEN), ("AA",  "88.15%", GREEN)]

    def draw_index_col(x, items, y_start=560):
        y = y_start
        for label, val, color in items:
            d.text((x,      y), f"{label} :", font=_font(11, bold=True), fill=(0, 0, 0))
            d.text((x + 55, y), val,          font=_font(11, bold=True), fill=color)
            y += 22

    draw_index_col(20,  indices_left)
    draw_index_col(200, indices_mid)
    draw_index_col(380, indices_right)

    d.line([(0, H - 30), (W, H - 30)], fill=(180, 180, 180), width=1)
    d.text((10, H - 22), "TOMEY  RT-7000  |  22C-200S-2D1", font=_font(9), fill=(120, 120, 120))

    if degraded:
        img = _apply_degradation(img, blur=1.8, noise=12, rotate=1.5, crop_right=30, crop_top=0)

    img.save(output_path, dpi=(150, 150))
    print(f"[GEN] Saved: {output_path}")
    return output_path


# ══════════════════════════════════════════════════════════════════════════
# PRESCRIPTION CARD
# ══════════════════════════════════════════════════════════════════════════
def generate_prescription_card(patient, output_path):
    """
    Generates a prescription / refraction card showing UCVA, BCVA,
    Sphere, Cylinder, and Axis for both eyes.
    This image is a visual reference — manually type these values into the form.
    """
    W, H = 780, 480
    img = Image.new("RGB", (W, H), color=(255, 255, 255))
    d   = ImageDraw.Draw(img)

    # ── Header bar ───────────────────────────────────────────────────────
    d.rectangle([0, 0, W, 50], fill=(30, 80, 160))
    d.text((W // 2, 25), "Post-DALK Refraction Record",
           font=_font(17, bold=True), fill=(255, 255, 255), anchor="mm")

    # ── Patient info strip ───────────────────────────────────────────────
    d.rectangle([0, 50, W, 90], fill=(235, 242, 255))
    d.text((15,  60), f"Patient : {patient['name']}",     font=_font(11, bold=True), fill=(0,0,0))
    d.text((15,  75), f"ID      : {patient['id']}",       font=_font(11), fill=(40,40,40))
    d.text((350, 60), f"DOB     : {patient['dob']}",      font=_font(11), fill=(40,40,40))
    d.text((350, 75), f"Date    : {patient['exam_date']}", font=_font(11), fill=(40,40,40))
    d.text((620, 60), f"Months post-DALK:", font=_font(11), fill=(40,40,40))
    d.text((620, 75), f"{patient['months_post_dalk']} months",
           font=_font(11, bold=True), fill=(30, 80, 160))

    # ── Table setup ──────────────────────────────────────────────────────
    TABLE_TOP   = 105
    COL_LABEL   = 15
    COL_OD      = 220
    COL_OS      = 490
    COL_WIDTH   = 250
    ROW_H       = 36

    # Column headers
    d.rectangle([COL_OD - 10, TABLE_TOP, COL_OD + COL_WIDTH, TABLE_TOP + ROW_H],
                fill=(50, 120, 200))
    d.rectangle([COL_OS - 10, TABLE_TOP, COL_OS + COL_WIDTH, TABLE_TOP + ROW_H],
                fill=(50, 120, 200))
    d.text((COL_OD + COL_WIDTH // 2, TABLE_TOP + ROW_H // 2),
           "OD  (Right Eye)", font=_font(13, bold=True), fill=(255,255,255), anchor="mm")
    d.text((COL_OS + COL_WIDTH // 2, TABLE_TOP + ROW_H // 2),
           "OS  (Left Eye)", font=_font(13, bold=True), fill=(255,255,255), anchor="mm")

    ROWS = [
        ("UCVA  (Snellen)",  "ucva",     str),
        ("BCVA  (Snellen)",  "bcva",     str),
        ("Sphere (D)",       "sphere",   lambda v: f"{v:+.2f}"),
        ("Cylinder (D)",     "cylinder", lambda v: f"{v:+.2f}"),
        ("Axis (°)",         "axis",     lambda v: str(int(v))),
    ]

    rx = patient["rx"]
    for i, (label, key, fmt) in enumerate(ROWS):
        y = TABLE_TOP + ROW_H + i * ROW_H
        bg = (248, 248, 255) if i % 2 == 0 else (255, 255, 255)

        # Row background
        d.rectangle([COL_LABEL, y, W - 15, y + ROW_H], fill=bg)

        # Row label
        d.text((COL_LABEL + 5, y + ROW_H // 2),
               label, font=_font(12, bold=True), fill=(30, 30, 30), anchor="lm")

        # OD value
        od_val = fmt(rx["OD"][key])
        d.text((COL_OD + COL_WIDTH // 2, y + ROW_H // 2),
               od_val, font=_font(14, bold=True), fill=(0, 0, 160), anchor="mm")

        # OS value
        os_val = fmt(rx["OS"][key])
        d.text((COL_OS + COL_WIDTH // 2, y + ROW_H // 2),
               os_val, font=_font(14, bold=True), fill=(0, 0, 160), anchor="mm")

        # Horizontal divider
        d.line([(COL_LABEL, y + ROW_H), (W - 15, y + ROW_H)],
               fill=(200, 210, 230), width=1)

    # Outer table border
    total_h = ROW_H + len(ROWS) * ROW_H
    d.rectangle([COL_LABEL, TABLE_TOP + ROW_H, W - 15, TABLE_TOP + total_h],
                outline=(150, 170, 210), width=1)

    # Vertical dividers
    for cx in [COL_OD - 10, COL_OS - 10]:
        d.line([(cx, TABLE_TOP + ROW_H), (cx, TABLE_TOP + total_h)],
               fill=(150, 170, 210), width=1)

    # ── Note banner ──────────────────────────────────────────────────────
    note_y = TABLE_TOP + total_h + 14
    d.rectangle([COL_LABEL, note_y, W - 15, note_y + 28], fill=(255, 248, 220))
    d.text((COL_LABEL + 8, note_y + 14),
           f"Clinical note: {patient['note']}  |  Enter logMAR = -log10(Snellen fraction) in the prediction form",
           font=_font(10), fill=(100, 80, 0), anchor="lm")

    # ── Footer ───────────────────────────────────────────────────────────
    d.line([(0, H - 28), (W, H - 28)], fill=(180, 180, 180), width=1)
    d.text((15, H - 16), "Vasan Hospital  |  Post-DALK Rehabilitation Unit",
           font=_font(9), fill=(120, 120, 120))
    d.text((W - 15, H - 16), patient["exam_date"],
           font=_font(9), fill=(120, 120, 120), anchor="rs")

    img.save(output_path, dpi=(150, 150))
    print(f"[GEN] Saved: {output_path}")
    return output_path


# ══════════════════════════════════════════════════════════════════════════
# DEGRADATION helpers
# ══════════════════════════════════════════════════════════════════════════
def _apply_degradation(img, blur=2.0, noise=15, rotate=2.0, crop_right=0, crop_top=0):
    arr = np.array(img)
    if blur > 0:
        k = int(blur * 2) | 1
        arr = cv2.GaussianBlur(arr, (k, k), blur)
    if noise > 0:
        gauss = np.random.normal(0, noise, arr.shape).astype(np.int16)
        arr = np.clip(arr.astype(np.int16) + gauss, 0, 255).astype(np.uint8)
    if rotate != 0:
        h, w = arr.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), rotate, 1.0)
        arr = cv2.warpAffine(arr, M, (w, h), borderValue=(255, 255, 255))
    h, w = arr.shape[:2]
    arr = arr[crop_top:, :w - crop_right]
    return Image.fromarray(arr)


def _hsv_to_rgb(h, s, v):
    h = h / 255 * 360; s = s / 255; v = v / 255
    c = v * s; x = c * (1 - abs((h / 60) % 2 - 1)); m = v - c
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
    print("=" * 65)
    print("  Generating test images for 4 patients...")
    print("=" * 65)

    # ── Per-patient images ────────────────────────────────────────────
    for i, p in enumerate(PATIENTS, start=1):
        folder = os.path.join(OUT_DIR, f"patient_{i}")
        os.makedirs(folder, exist_ok=True)
        print(f"\n── Patient {i}: {p['id']} ({p['name']}) ─────────────────")

        # Build Tomey-style topo dicts
        def _topo_vals(eye):
            t = p["topo"][eye]
            return {
                "SK1": t["SK1"], "SK2": t["SK2"], "CYL": t["CYL"],
                "Ks_val": t["SK1"], "Ks_axis": t["Ks_axis"],
                "SK2_val": t["SK2"], "SK2_axis": t["SK2_axis"],
                "MinK": t["MinK"], "MinK_axis": t["MinK_axis"],
                "AvgK": t["AvgK"],
            }

        generate_tomey_topography(
            eye="OD", values=_topo_vals("OD"),
            patient_name=p["name"], patient_id=p["id"],
            dob=p["dob"], exam_date=p["exam_date"],
            output_path=os.path.join(folder, "topography_od.png"),
        )
        generate_tomey_topography(
            eye="OS", values=_topo_vals("OS"),
            patient_name=p["name"], patient_id=p["id"],
            dob=p["dob"], exam_date=p["exam_date"],
            output_path=os.path.join(folder, "topography_os.png"),
        )
        generate_zeiss_pachymetry(
            values=p["pachy"],
            patient_name=p["name"], patient_id=p["id"],
            dob=p["dob"], exam_date=p["exam_date"],
            output_path=os.path.join(folder, "pachymetry.png"),
        )
        generate_prescription_card(
            patient=p,
            output_path=os.path.join(folder, "prescription_card.png"),
        )

    # ── Legacy images (for test_ocr.py) ──────────────────────────────
    print("\n── Legacy images (for test_ocr.py) ───────────────────────────")

    def _legacy_topo(vals_dict):
        return {
            "SK1": vals_dict["SK1"], "SK2": vals_dict["SK2"], "CYL": vals_dict["CYL"],
            "Ks_val": vals_dict["SK1"], "Ks_axis": vals_dict.get("Ks_axis", 90),
            "SK2_val": vals_dict["SK2"], "SK2_axis": vals_dict.get("SK2_axis", 0),
            "MinK": vals_dict.get("MinK", vals_dict["SK2"] - 0.08),
            "MinK_axis": vals_dict.get("MinK_axis", 5),
            "AvgK": vals_dict.get("AvgK", round((vals_dict["SK1"] + vals_dict["SK2"]) / 2, 2)),
        }

    generate_zeiss_pachymetry(
        values=ZEISS_VALUES,
        patient_name="Faris, M.S.Mr", patient_id="150317",
        dob="6/8/2004", exam_date="10/31/2025",
        output_path=os.path.join(OUT_DIR, "zeiss_pachymetry_clean.png"),
    )
    generate_zeiss_pachymetry(
        values=ZEISS_VALUES,
        patient_name="Faris, M.S.Mr", patient_id="150317",
        dob="6/8/2004", exam_date="10/31/2025",
        output_path=os.path.join(OUT_DIR, "zeiss_pachymetry_degraded.png"),
        degraded=True,
    )
    generate_tomey_topography(
        eye="OS", values=_legacy_topo(TOMEY_OS_VALUES),
        patient_name="Faris.,Mr.M.S.", patient_id="150317",
        dob="6/8/2004", exam_date="10/31/2025",
        output_path=os.path.join(OUT_DIR, "tomey_topography_os_clean.png"),
    )
    generate_tomey_topography(
        eye="OD", values=_legacy_topo(TOMEY_OD_VALUES),
        patient_name="Faris.,Mr.M.S.", patient_id="150317",
        dob="6/8/2004", exam_date="10/31/2025",
        output_path=os.path.join(OUT_DIR, "tomey_topography_od_clean.png"),
    )
    generate_tomey_topography(
        eye="OS", values=_legacy_topo(TOMEY_OS_VALUES),
        patient_name="Faris.,Mr.M.S.", patient_id="150317",
        dob="6/8/2004", exam_date="10/31/2025",
        output_path=os.path.join(OUT_DIR, "tomey_topography_os_degraded.png"),
        degraded=True,
    )

    # ── Summary table ─────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print("  PATIENT SUMMARY — use prescription_card.png for form values")
    print(f"{'='*65}")
    hdr = f"  {'ID':<10} {'Name':<20} {'Eye':<4} {'UCVA':<7} {'BCVA':<7} {'Sph':>6} {'Cyl':>6} {'Ax':>4}  CCT"
    print(hdr)
    print("  " + "-" * 63)
    for p in PATIENTS:
        for eye in ("OD", "OS"):
            rx  = p["rx"][eye]
            cct = p["pachy"][eye]["cct"]
            print(f"  {p['id']:<10} {p['name']:<20} {eye:<4} "
                  f"{rx['ucva']:<7} {rx['bcva']:<7} "
                  f"{rx['sphere']:>+6.2f} {rx['cylinder']:>+6.2f} {rx['axis']:>4}  {cct} µm")
    print(f"{'='*65}")
    print(f"\nImages saved to: {OUT_DIR}/")


if __name__ == "__main__":
    main()
