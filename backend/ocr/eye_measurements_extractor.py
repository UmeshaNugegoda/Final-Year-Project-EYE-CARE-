"""
Eye Measurements OCR Extractor
================================
Extracts refractive data from a standard ophthalmology refraction form
(tested against the Asiri Hospital / Vision Care Opticals form).

Target fields per eye:
  ucva_snellen       — Unaided VA, Distance row
  bcva_snellen       — DVA from Rx table
  sphere_diopters    — SPH from Rx table   (signed float, e.g. -1.50)
  cylinder_diopters  — CYL from Rx table   (signed float, e.g. -1.50)
  axis_degrees       — AXIS from Rx table  (int 0-180)
"""

import re
import io
import json
import tempfile
import os

import numpy as np

from .reader import _run_ocr_subprocess
from .preprocessing import _preprocess_pachymetry_for_ocr   # reuse similar pipeline


# ── Snellen regex ──────────────────────────────────────────────────
_SNELLEN_RE = re.compile(
    r'\b(?:6/[0-9]+(?:[+-])?|20/[0-9]+|1/[0-9]+|N/[0-9]+|CF|HM|PL|NPL|FC)\b',
    re.IGNORECASE
)

# ── Signed diopter regex (e.g. -1.50, +0.25, -.50) ───────────────
_DIOP_RE = re.compile(r'[+\-]?\s*\d{1,2}(?:[.,]\d{1,2})?')

# ── Eye row markers ───────────────────────────────────────────────
_EYE_MARKER = {'OD': re.compile(r'\bR\b', re.IGNORECASE),
               'OS': re.compile(r'\bL\b', re.IGNORECASE)}

# ── Column headers to look for ────────────────────────────────────
_COL_HEADERS = {
    'sph' : re.compile(r'\bSPH\b', re.IGNORECASE),
    'cyl' : re.compile(r'\bCYL\b', re.IGNORECASE),
    'axis': re.compile(r'\bAXIS?\b', re.IGNORECASE),
    'dva' : re.compile(r'\bDVA\b', re.IGNORECASE),
}

_VA_SECTION = re.compile(r'unaided\s*va?|unaid', re.IGNORECASE)
_RX_SECTION = re.compile(r'\bRx\b', re.IGNORECASE)


def _centroid_x(bbox):
    xs = [pt[0] for pt in bbox]
    return sum(xs) / len(xs)


def _centroid_y(bbox):
    ys = [pt[1] for pt in bbox]
    return sum(ys) / len(ys)


def _parse_diopter(text):
    """Parse a signed diopter value from OCR text, handling OCR noise."""
    text = text.strip()
    # Replace comma with period, remove spaces between sign and digits
    text = text.replace(',', '.').replace(' ', '')
    # Handle common OCR errors: 'O' → '0', 'I' → '1'
    text = text.replace('O', '0').replace('o', '0')
    m = re.search(r'([+\-]?\d{1,2}(?:\.\d{1,2})?)', text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _parse_axis(text):
    """Parse axis degrees (0-180) from OCR text."""
    text = text.strip().replace("'", "").replace('"', '').replace(' ', '')
    m = re.search(r'(\d{1,3})', text)
    if m:
        v = int(m.group(1))
        return v if 0 <= v <= 180 else None
    return None


def _parse_snellen(text):
    """Return a normalised Snellen string or None."""
    text = text.strip()
    # Normalise OCR noise
    text = re.sub(r'\s+', '', text)
    m = _SNELLEN_RE.search(text)
    if m:
        return m.group(0).upper()
    # Accept bare integers as N/X (near VA)
    if re.fullmatch(r'N\d+', text, re.IGNORECASE):
        return text.upper()
    return None


def _find_closest_chunk(chunks, target_x, target_y, x_tol=50, y_range=(0, 80)):
    """Return text of the chunk closest to (target_x, target_y) within tolerances."""
    candidates = []
    for bbox, text, conf in chunks:
        cx = _centroid_x(bbox)
        cy = _centroid_y(bbox)
        if abs(cx - target_x) <= x_tol and y_range[0] <= (cy - target_y) <= y_range[1]:
            candidates.append((cy - target_y, text, conf))
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
    return None


def extract_eye_measurements(image_bytes, eye='OD'):
    """
    Extract refractive data from an eye measurements report image.

    Parameters
    ----------
    image_bytes : bytes
        Raw image file bytes (JPEG or PNG).
    eye : str
        'OD' (right eye / R row) or 'OS' (left eye / L row).

    Returns
    -------
    dict with keys:
        ucva_snellen, bcva_snellen,
        sphere_diopters, cylinder_diopters, axis_degrees,
        eye_extraction_status  (per-field 'extracted' | 'not_found')
    """
    result = {
        'ucva_snellen'      : None,
        'bcva_snellen'      : None,
        'sphere_diopters'   : None,
        'cylinder_diopters' : None,
        'axis_degrees'      : None,
    }
    status = {k: 'not_found' for k in result}

    # ── Save to temp file ─────────────────────────────────────────
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
    tmp.write(image_bytes)
    tmp.close()
    tmp_path = tmp.name

    preproc_path = None
    try:
        # ── Preprocess ───────────────────────────────────────────
        import cv2
        img = cv2.imread(tmp_path)
        if img is None:
            return {**result, 'eye_extraction_status': status}

        gray = _preprocess_pachymetry_for_ocr(img)
        preproc_tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        preproc_path = preproc_tmp.name
        preproc_tmp.close()
        cv2.imwrite(preproc_path, gray)

        # ── OCR ──────────────────────────────────────────────────
        raw = _run_ocr_subprocess(preproc_path)

        # Parse into (bbox, text, conf) and sort by y then x
        chunks = [(item[0], str(item[1]).strip(), float(item[2])) for item in raw]
        chunks.sort(key=lambda c: (_centroid_y(c[0]), _centroid_x(c[0])))

        # ── Find Rx section ──────────────────────────────────────
        rx_y = None
        for bbox, text, conf in chunks:
            if _RX_SECTION.search(text):
                rx_y = _centroid_y(bbox)
                break

        # ── Find column header row (SPH CYL AXIS DVA) ────────────
        col_x = {}  # 'sph'->cx, 'cyl'->cx, 'axis'->cx, 'dva'->cx
        header_y = None
        for bbox, text, conf in chunks:
            cy = _centroid_y(bbox)
            # Look near and below Rx label
            if rx_y is not None and not (-10 < cy - rx_y < 120):
                continue
            for col_name, pattern in _COL_HEADERS.items():
                if pattern.search(text) and col_name not in col_x:
                    col_x[col_name] = _centroid_x(bbox)
                    if header_y is None or cy < header_y:
                        header_y = cy

        # ── Find target eye row ──────────────────────────────────
        eye_marker_re = _EYE_MARKER.get(eye, _EYE_MARKER['OD'])
        eye_row_y = None
        eye_row_x = None

        if header_y is not None:
            for bbox, text, conf in chunks:
                cy = _centroid_y(bbox)
                cx = _centroid_x(bbox)
                # Row should be below header, leftmost column
                if not (5 < cy - header_y < 100):
                    continue
                if eye_marker_re.fullmatch(text.strip()):
                    eye_row_y = cy
                    eye_row_x = cx
                    break

        # Fallback: search whole document if header not found
        if eye_row_y is None:
            for bbox, text, conf in chunks:
                if eye_marker_re.fullmatch(text.strip()):
                    eye_row_y = _centroid_y(bbox)
                    eye_row_x = _centroid_x(bbox)
                    break

        # ── Extract values from eye row ──────────────────────────
        if eye_row_y is not None:
            # For each column with known x, find the chunk closest to
            # (col_x, eye_row_y) within ±40px x-tolerance, ±25px y
            def get_value_at_col(col_name):
                if col_name not in col_x:
                    return None
                target_x = col_x[col_name]
                best = None
                best_dist = float('inf')
                for bbox, text, conf in chunks:
                    cy = _centroid_y(bbox)
                    cx = _centroid_x(bbox)
                    if abs(cy - eye_row_y) > 25:
                        continue
                    if abs(cx - target_x) < best_dist:
                        best_dist = abs(cx - target_x)
                        best = text
                return best if best_dist <= 60 else None

            sph_text  = get_value_at_col('sph')
            cyl_text  = get_value_at_col('cyl')
            axis_text = get_value_at_col('axis')
            dva_text  = get_value_at_col('dva')

            if sph_text:
                v = _parse_diopter(sph_text)
                if v is not None and -30.0 <= v <= 20.0:
                    result['sphere_diopters'] = round(v, 2)
                    status['sphere_diopters'] = 'extracted'

            if cyl_text:
                v = _parse_diopter(cyl_text)
                if v is not None and -10.0 <= v <= 0.0:
                    result['cylinder_diopters'] = round(v, 2)
                    status['cylinder_diopters'] = 'extracted'
                elif v is not None and 0.0 < v <= 10.0:
                    # Some reports write positive CYL — negate for convention
                    result['cylinder_diopters'] = round(-abs(v), 2)
                    status['cylinder_diopters'] = 'extracted'

            if axis_text:
                v = _parse_axis(axis_text)
                if v is not None:
                    result['axis_degrees'] = v
                    status['axis_degrees'] = 'extracted'

            if dva_text:
                v = _parse_snellen(dva_text)
                if v:
                    result['bcva_snellen'] = v
                    status['bcva_snellen'] = 'extracted'

        # ── Extract UCVA from Unaided VA section ──────────────────
        ua_y = None
        for bbox, text, conf in chunks:
            if _VA_SECTION.search(text):
                ua_y = _centroid_y(bbox)
                break

        if ua_y is not None:
            # Find R/L row in unaided VA section (within 120px below section header)
            ua_eye_y = None
            for bbox, text, conf in chunks:
                cy = _centroid_y(bbox)
                if not (5 < cy - ua_y < 120):
                    continue
                if eye_marker_re.fullmatch(text.strip()):
                    ua_eye_y = cy
                    break

            if ua_eye_y is not None:
                # Grab next Snellen-like chunk on same row
                for bbox, text, conf in chunks:
                    cy = _centroid_y(bbox)
                    if abs(cy - ua_eye_y) > 20:
                        continue
                    v = _parse_snellen(text)
                    if v:
                        result['ucva_snellen'] = v
                        status['ucva_snellen'] = 'extracted'
                        break

    except Exception as e:
        print(f'[eye_measurements_extractor] error: {e}')
    finally:
        for p in [tmp_path, preproc_path]:
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass

    return {**result, 'eye_extraction_status': status}
