"""
test_ocr.py
===========
Runs the OCR pipeline on every image in test_images/ and prints what
was extracted vs what is expected.

Usage:
    cd backend
    python3 scripts/test_ocr.py

Requires:
    - scripts/generate_test_images.py has already been run  (produces test_images/)
    - Flask service is NOT required — this calls the OCR functions directly
"""

import os, sys, json

# Resolve paths relative to this script's location
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR  = os.path.join(_SCRIPTS_DIR, "..")
sys.path.insert(0, _SCRIPTS_DIR)   # allows: from generate_test_images import ...
sys.path.insert(0, _BACKEND_DIR)   # allows: from app import run_ocr

from generate_test_images import ZEISS_VALUES, TOMEY_OS_VALUES, TOMEY_OD_VALUES

# ── import OCR entry point from app ───────────────────────────────────────
from app import run_ocr as _extract_values_from_image

IMG_DIR = os.path.join(_BACKEND_DIR, "test_images")

PASS = "\033[92m PASS\033[0m"
FAIL = "\033[91m FAIL\033[0m"
WARN = "\033[93m WARN\033[0m"

def check(label, got, expected, tolerance=1.5):
    """Compare extracted value against expected, with tolerance for floats."""
    if got is None:
        status = FAIL
        note   = f"got None,  expected {expected}"
    else:
        try:
            diff = abs(float(got) - float(expected))
            status = PASS if diff <= tolerance else FAIL
            note   = f"got {got},  expected {expected}  (diff={diff:.2f})"
        except (TypeError, ValueError):
            status = WARN
            note   = f"got {got!r},  expected {expected}"
    print(f"  [{status} ] {label:40s}  {note}")
    return status == PASS


def run_test(image_path, image_type, eye, expected_values):
    """Run OCR on one image and compare results."""
    short = os.path.basename(image_path)
    print(f"\n{'─'*65}")
    print(f"  Image : {short}")
    print(f"  Type  : {image_type}  Eye: {eye}")
    print(f"{'─'*65}")

    if not os.path.exists(image_path):
        print(f"  [SKIP] File not found: {image_path}")
        return

    try:
        result = _extract_values_from_image(image_path, image_type, eye)
    except Exception as e:
        print(f"  [ERROR] OCR crashed: {e}")
        return

    print(f"  Raw extracted: {json.dumps(result, indent=4, default=str)}\n")

    passes = 0
    total  = 0

    for key, exp_val in expected_values.items():
        got = result.get(key)
        ok  = check(key, got, exp_val)
        passes += int(ok)
        total  += 1

    print(f"\n  Score: {passes}/{total} checks passed")
    return passes, total


def main():
    print("=" * 65)
    print("  OCR TEST RUNNER")
    print("=" * 65)

    total_pass = 0
    total_all  = 0

    # ── Test 1: Zeiss clean — OD ─────────────────────────────────────
    p, t = run_test(
        os.path.join(IMG_DIR, "zeiss_pachymetry_clean.png"),
        image_type="pachymetry",
        eye="OD",
        expected_values={"corneal_thickness_um": ZEISS_VALUES["OD"]["cct"]},
    ) or (0, 1)
    total_pass += p; total_all += t

    # ── Test 2: Zeiss clean — OS ─────────────────────────────────────
    p, t = run_test(
        os.path.join(IMG_DIR, "zeiss_pachymetry_clean.png"),
        image_type="pachymetry",
        eye="OS",
        expected_values={"corneal_thickness_um": ZEISS_VALUES["OS"]["cct"]},
    ) or (0, 1)
    total_pass += p; total_all += t

    # ── Test 3: Zeiss degraded — OD ──────────────────────────────────
    p, t = run_test(
        os.path.join(IMG_DIR, "zeiss_pachymetry_degraded.png"),
        image_type="pachymetry",
        eye="OD",
        expected_values={"corneal_thickness_um": ZEISS_VALUES["OD"]["cct"]},
    ) or (0, 1)
    total_pass += p; total_all += t

    # ── Test 4: Tomey OS clean ────────────────────────────────────────
    p, t = run_test(
        os.path.join(IMG_DIR, "tomey_topography_os_clean.png"),
        image_type="topography",
        eye="OS",
        expected_values={
            "K1_diopters"          : TOMEY_OS_VALUES["SK2"],   # flat K
            "K2_diopters"          : TOMEY_OS_VALUES["SK1"],   # steep K
            "astigmatism_diopters" : TOMEY_OS_VALUES["CYL"],
        },
    ) or (0, 3)
    total_pass += p; total_all += t

    # ── Test 5: Tomey OD clean ────────────────────────────────────────
    p, t = run_test(
        os.path.join(IMG_DIR, "tomey_topography_od_clean.png"),
        image_type="topography",
        eye="OD",
        expected_values={
            "K1_diopters"          : TOMEY_OD_VALUES["SK2"],
            "K2_diopters"          : TOMEY_OD_VALUES["SK1"],
            "astigmatism_diopters" : TOMEY_OD_VALUES["CYL"],
        },
    ) or (0, 3)
    total_pass += p; total_all += t

    # ── Test 6: Tomey OS degraded ─────────────────────────────────────
    p, t = run_test(
        os.path.join(IMG_DIR, "tomey_topography_os_degraded.png"),
        image_type="topography",
        eye="OS",
        expected_values={
            "K1_diopters"          : TOMEY_OS_VALUES["SK2"],
            "K2_diopters"          : TOMEY_OS_VALUES["SK1"],
            "astigmatism_diopters" : TOMEY_OS_VALUES["CYL"],
        },
    ) or (0, 3)
    total_pass += p; total_all += t

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  TOTAL: {total_pass}/{total_all} checks passed")
    if total_pass == total_all:
        print("  \033[92mAll tests passed!\033[0m")
    else:
        print(f"  \033[91m{total_all - total_pass} check(s) failed — see above\033[0m")
    print("=" * 65)


if __name__ == "__main__":
    main()
