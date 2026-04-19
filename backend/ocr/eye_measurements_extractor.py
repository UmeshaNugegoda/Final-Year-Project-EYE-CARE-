"""
Eye Measurements OCR Extractor
================================
Extracts refractive data from a standard ophthalmology refraction form.
Tested against Asiri Hospital / Vision Care Opticals and Vasan Eye Care Hospital forms.

Target fields per eye:
  ucva_snellen       — Unaided VA, Distance row
  bcva_snellen       — DVA from Rx table
  sphere_diopters    — SPH from Rx table   (signed float, e.g. -1.50)
  cylinder_diopters  — CYL from Rx table   (signed float, e.g. -1.50)
  axis_degrees       — AXIS from Rx table  (int 0-180)
"""

import re
import tempfile
import os

from .reader import _run_ocr_subprocess
from .preprocessing import _preprocess_eye_measurements_for_ocr

_EYE_MIN_CONF = 0.25   # handwritten OCR is lower confidence

# Exact Snellen numerators: 6, 20, 4, 3, 2, 1 (metric + imperial variants)
_SNELLEN_RE = re.compile(
    r'\b(?:6/[0-9]+(?:[+-])?|20/[0-9]+|4/[0-9]+|3/[0-9]+|2/[0-9]+|1/[0-9]+|CF|HM|PL|NPL|FC)\b',
    re.IGNORECASE
)

# Column headers — broadened for common OCR misreads
# SPH often read as GPH, 5PH; CYL as CIL; AXIS as AXS, AX1S
_COL_HEADERS = {
    'sph' : re.compile(r'\b[Ss5cCG][Pp][Hh]\b'),
    'cyl' : re.compile(r'\bCY[Ll1I]\b', re.IGNORECASE),
    'axis': re.compile(r'\bAX[I1]?S\b', re.IGNORECASE),
    'dva' : re.compile(r'\bDVA\b', re.IGNORECASE),
}

_VA_SECTION = re.compile(r'unaided\s*va?|unaid', re.IGNORECASE)
_RX_SECTION = re.compile(r'\bRx\b', re.IGNORECASE)
_EYE_MARKER = {
    'OD': re.compile(r'^R$', re.IGNORECASE),
    'OS': re.compile(r'^L$', re.IGNORECASE),
}

def _cx(bbox): return sum(p[0] for p in bbox) / len(bbox)
def _cy(bbox): return sum(p[1] for p in bbox) / len(bbox)


def _parse_diopter(text):
    """Parse a signed diopter value, handling common OCR noise from handwriting."""
    text = text.strip()
    text = text.replace(',', '.').replace(' ', '')
    text = text.replace('O', '0').replace('o', '0')
    text = text.replace('I', '1').replace('l', '1')  # I/l look like 1
    # Tilde and backtick commonly substitute for minus in handwriting OCR
    text = re.sub(r'[~`]', '-', text)
    # Apostrophe commonly substitutes for decimal point, e.g. "9'00" → "9.00"
    text = re.sub(r"'(\d)", r'.\1', text)
    # Strip OCR bracket between sign and digit: "-(1.50" → "-1.50"
    text = re.sub(r'([+\-])\s*[\(\[]\s*(\d)', r'\1\2', text)
    # Digit-minus-digit → digit.digit: "-1-50" → "-1.50" (handwriting decimal as dash)
    text = re.sub(r'(\d)-(\d)', r'\1.\2', text)
    m = re.search(r'([+\-]?\d{1,2}(?:\.\d{1,2})?)', text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _parse_axis(text):
    """Parse axis degrees (0-180) from OCR text, preferring the last valid candidate."""
    text = text.strip().replace("'", "").replace('"', '').replace('°', '').replace(' ', '')
    candidates = [int(m.group()) for m in re.finditer(r'\d+', text) if 0 <= int(m.group()) <= 180]
    return candidates[-1] if candidates else None


def _parse_snellen(text):
    """Return a normalised Snellen string or None, handling common OCR noise."""
    text = re.sub(r'\s+', '', text.strip())
    text = text.replace('O', '0').replace('o', '0')  # O/o confused with 0
    # Direct match
    m = _SNELLEN_RE.search(text)
    if m:
        return m.group(0).upper()
    # Strip single leading OCR noise character: "16/12" → "6/12"
    if len(text) >= 4:
        m2 = _SNELLEN_RE.match(text[1:])
        if m2:
            return m2.group(0).upper()
    # Near VA format "N6", "N6+"
    if re.fullmatch(r'N\d+[+-]?', text, re.IGNORECASE):
        return text.upper()
    return None


def _run_ocr_on(path):
    raw = _run_ocr_subprocess(path, min_conf=_EYE_MIN_CONF)
    chunks = [(item[0], str(item[1]).strip(), float(item[2])) for item in raw]
    chunks.sort(key=lambda c: (_cy(c[0]), _cx(c[0])))
    return chunks


def extract_eye_measurements(image_bytes, eye='OD'):
    """
    Extract refractive data from an eye measurements report image.

    Parameters
    ----------
    image_bytes : bytes  — raw JPEG or PNG file bytes
    eye : str           — 'OD' (right) or 'OS' (left)

    Returns
    -------
    dict with keys: ucva_snellen, bcva_snellen, sphere_diopters,
                    cylinder_diopters, axis_degrees, eye_extraction_status
    """
    result = {
        'ucva_snellen'      : None,
        'bcva_snellen'      : None,
        'sphere_diopters'   : None,
        'cylinder_diopters' : None,
        'axis_degrees'      : None,
    }
    status = {k: 'not_found' for k in result}

    tmp_path     = None
    preproc_path = None
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        tmp.write(image_bytes)
        tmp.close()
        tmp_path = tmp.name

        import cv2

        preproc = _preprocess_eye_measurements_for_ocr(tmp_path)
        preproc_tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        preproc_path = preproc_tmp.name
        preproc_tmp.close()
        cv2.imwrite(preproc_path, preproc)

        chunks = _run_ocr_on(preproc_path)

        # Sparse fallback: retry on raw image if preprocessing destroyed content
        if len(chunks) < 20:
            print(f'[eye_meas] sparse ({len(chunks)}) — retrying raw image')
            raw_chunks = _run_ocr_on(tmp_path)
            if len(raw_chunks) > len(chunks):
                chunks = raw_chunks

        # ── Locate Rx section ────────────────────────────────────────
        rx_y = None
        for bbox, text, conf in chunks:
            if _RX_SECTION.search(text):
                rx_y = _cy(bbox)
                break

        # ── Locate column headers ────────────────────────────────────
        col_x        = {}
        header_y     = None   # topmost header y
        header_y_max = None   # bottommost header y — data rows must be BELOW this

        for bbox, text, conf in chunks:
            cy = _cy(bbox)
            if rx_y is not None and not (-10 < cy - rx_y < 250):
                continue
            for col_name, pattern in _COL_HEADERS.items():
                if pattern.search(text) and col_name not in col_x:
                    col_x[col_name] = _cx(bbox)
                    if header_y is None     or cy < header_y:     header_y     = cy
                    if header_y_max is None or cy > header_y_max: header_y_max = cy

        # ── Locate target eye row ────────────────────────────────────
        eye_marker_re = _EYE_MARKER.get(eye, _EYE_MARKER['OD'])
        eye_row_y     = None

        if header_y is not None:
            for bbox, text, conf in chunks:
                cy = _cy(bbox)
                if not (5 < cy - header_y < 160): continue
                if eye_marker_re.fullmatch(text.strip()):
                    eye_row_y = cy
                    break

        # Full-document fallback for the eye marker
        if eye_row_y is None:
            for bbox, text, conf in chunks:
                if eye_marker_re.fullmatch(text.strip()):
                    eye_row_y = _cy(bbox)
                    break

        # Position-based fallback: if still no marker, estimate from header position
        # The R row is typically ~35-45 px below the last header on these forms
        if eye_row_y is None and header_y_max is not None:
            eye_row_y = header_y_max + 40
            if eye == 'OS':
                eye_row_y += 45  # L row is one row below R row

        # ── Extract values from the eye row ─────────────────────────
        # CRITICAL: only look at chunks BELOW the header row (header_y_max)
        # so that the column headers themselves never win the distance race.
        if eye_row_y is not None and col_x:
            cutoff_y = header_y_max if header_y_max is not None else (header_y or 0)
            # If a stray header pushed cutoff_y past the eye row, fall back to the
            # topmost header y so data rows between headers and eye_row_y are visible.
            if cutoff_y >= eye_row_y:
                cutoff_y = header_y if header_y is not None else 0

            def get_col(col_name):
                if col_name not in col_x: return None
                tx = col_x[col_name]
                best, best_dist = None, float('inf')
                for bbox, text, conf in chunks:
                    cy = _cy(bbox)
                    if cy <= cutoff_y: continue        # skip header row and above
                    if abs(cy - eye_row_y) > 60: continue
                    # Weight y-proximity heavily so a 2px x-advantage doesn't pick the wrong row
                    d = abs(_cx(bbox) - tx) + abs(cy - eye_row_y) * 2
                    if d < best_dist:
                        best_dist, best = d, text
                return best if best_dist <= 250 else None

            def get_snellen_col(col_name, y_tol=70):
                """Like get_col but requires the result to parse as a distance Snellen VA."""
                if col_name not in col_x: return None
                tx = col_x[col_name]
                best, best_dist = None, float('inf')
                for bbox, text, conf in chunks:
                    cy = _cy(bbox)
                    if cy <= cutoff_y: continue
                    if abs(cy - eye_row_y) > y_tol: continue
                    v = _parse_snellen(text)
                    if not v or re.fullmatch(r'N\d+[+-]?', v, re.IGNORECASE):
                        continue
                    d = abs(_cx(bbox) - tx) + abs(cy - eye_row_y) * 2
                    if d < best_dist:
                        best_dist, best = d, v
                return best if best_dist <= 350 else None

            sph_text  = get_col('sph')
            cyl_text  = get_col('cyl')
            axis_text = get_col('axis')

            if sph_text:
                v = _parse_diopter(sph_text)
                if v is not None and -30.0 <= v <= 20.0:
                    result['sphere_diopters'] = round(v, 2)
                    status['sphere_diopters'] = 'extracted'

            if cyl_text:
                v = _parse_diopter(cyl_text)
                if v is not None and -15.0 <= v <= 15.0:
                    result['cylinder_diopters'] = round(-abs(v), 2)
                    status['cylinder_diopters'] = 'extracted'

            if axis_text:
                v = _parse_axis(axis_text)
                if v is not None:
                    result['axis_degrees'] = v
                    status['axis_degrees'] = 'extracted'

            bcva = get_snellen_col('dva')
            if bcva:
                result['bcva_snellen'] = bcva
                status['bcva_snellen'] = 'extracted'

        # ── UCVA from Unaided VA section ─────────────────────────────
        ua_y = None
        for bbox, text, conf in chunks:
            if _VA_SECTION.search(text):
                ua_y = _cy(bbox)
                break

        if ua_y is not None:
            ua_eye_y = None
            for bbox, text, conf in chunks:
                cy = _cy(bbox)
                if not (5 < cy - ua_y < 200): continue
                if eye_marker_re.fullmatch(text.strip()):
                    ua_eye_y = cy
                    break

            if ua_eye_y is not None:
                for bbox, text, conf in chunks:
                    if abs(_cy(bbox) - ua_eye_y) > 40: continue
                    v = _parse_snellen(text)
                    if v:
                        result['ucva_snellen'] = v
                        status['ucva_snellen'] = 'extracted'
                        break

        # ── Text-based fallback for SPH / CYL / AXIS ─────────────────
        if any(result[k] is None for k in ('sphere_diopters', 'cylinder_diopters', 'axis_degrees')):
            eye_letter = 'R' if eye == 'OD' else 'L'
            joined = ' '.join(t for _, t, _ in chunks)
            pat = (
                rf'(?<![A-Za-z]){eye_letter}(?![A-Za-z])\s*'
                r'([+\-~]?\s*\d{1,2}[.,\'\u2019]\d{1,2})'
                r'\s+'
                r'([+\-~]?\s*\d{1,2}[.,\'\u2019]\d{1,2})'
                r'\s+'
                r'(\d{1,3})[\'°]?'
            )
            m = re.search(pat, joined)
            if m:
                if result['sphere_diopters'] is None:
                    v = _parse_diopter(m.group(1))
                    if v is not None and -30.0 <= v <= 20.0:
                        result['sphere_diopters'] = round(v, 2)
                        status['sphere_diopters'] = 'extracted'
                if result['cylinder_diopters'] is None:
                    v = _parse_diopter(m.group(2))
                    if v is not None and -15.0 <= v <= 15.0:
                        result['cylinder_diopters'] = round(-abs(v), 2)
                        status['cylinder_diopters'] = 'extracted'
                if result['axis_degrees'] is None:
                    v = _parse_axis(m.group(3))
                    if v is not None:
                        result['axis_degrees'] = v
                        status['axis_degrees'] = 'extracted'

        # ── BCVA fallback: y-closest distance Snellen on the eye row ────
        if result['bcva_snellen'] is None and eye_row_y is not None:
            cutoff_y = header_y_max if header_y_max is not None else 0
            if cutoff_y >= eye_row_y:
                cutoff_y = header_y if header_y is not None else 0
            best_v, best_dy = None, float('inf')
            for bbox, text, conf in chunks:
                cy = _cy(bbox)
                if cy <= cutoff_y: continue
                if abs(cy - eye_row_y) > 70: continue
                v = _parse_snellen(text)
                if v and not re.fullmatch(r'N\d+[+-]?', v, re.IGNORECASE):
                    dy = abs(cy - eye_row_y)
                    if dy < best_dy:
                        best_dy, best_v = dy, v
            if best_v:
                result['bcva_snellen'] = best_v
                status['bcva_snellen'] = 'extracted'

        # ── UCVA fallback: Snellen near any R/L marker ────────────────
        if result['ucva_snellen'] is None:
            found_markers = []
            for bbox, text, conf in chunks:
                if eye_marker_re.fullmatch(text.strip()):
                    found_markers.append(_cy(bbox))

            for marker_y in found_markers:
                for bbox, text, conf in chunks:
                    if abs(_cy(bbox) - marker_y) > 40: continue
                    v = _parse_snellen(text)
                    if (v and v != result.get('bcva_snellen')
                            and not re.fullmatch(r'N\d+[+-]?', v, re.IGNORECASE)):
                        result['ucva_snellen'] = v
                        status['ucva_snellen'] = 'extracted'
                        break
                if result['ucva_snellen']:
                    break

    except Exception as e:
        print(f'[eye_meas] error: {e}')
    finally:
        for p in [tmp_path, preproc_path]:
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass

    return {**result, 'eye_extraction_status': status}
