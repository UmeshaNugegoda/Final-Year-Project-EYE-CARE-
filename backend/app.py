import math
import statistics
import re, joblib, numpy as np, pandas as pd
import easyocr, tempfile, os
from flask import Flask, request, jsonify
from flask_cors import CORS
 
app = Flask(__name__)
CORS(app)
 
MODEL    = joblib.load("eye_correction_model.pkl")
LE       = joblib.load("label_encoder.pkl")
SCALER   = joblib.load("scaler.pkl")
IMPUTER  = joblib.load("imputer.pkl")
FEATURES = joblib.load("feature_names.pkl")
print(f"Model loaded | Features: {FEATURES} | Classes: {list(LE.classes_)}")

# Compatibility shim for models pickled with older scikit-learn versions.
if not hasattr(IMPUTER, "_fill_dtype"):
    try:
        IMPUTER._fill_dtype = np.asarray(IMPUTER.statistics_).dtype
    except Exception:
        IMPUTER._fill_dtype = object
 
_reader = None
def get_reader():
    global _reader
    if _reader is None:
        print("Loading EasyOCR...")
        _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _reader
 
def calculate_k2(k1, astig):
    if k1 is None or astig is None: return None
    return round(float(k1) + abs(float(astig)), 2)

def infer_eye_from_text(_text, requested_eye="OD"):
    """
    Use the eye chosen in the app (OD/OS). Do not override from OCR.

    Bilateral reports almost always mention OD before OS in reading order; using
    the first OD/OS hit in the OCR prefix incorrectly forced OD even when the
    user selected OS, which swapped central corneal thickness and other
    eye-specific values.
    """
    base_eye = (requested_eye or "OD").upper()
    if base_eye not in ("OD", "OS"):
        base_eye = "OD"
    return base_eye
 
def extract_value_for_eye(text, pattern, eye):
    od_m = re.search(r"(?:(?:^|\W)(?:OD|O\.?\s*D\.?)(?:\W|$)|Right\s*Eye)", text, re.IGNORECASE)
    os_m = re.search(r"(?:(?:^|\W)(?:OS|O\.?\s*S\.?)(?:\W|$)|Left\s*Eye)",  text, re.IGNORECASE)
    if od_m and os_m:
        od_s, os_s = od_m.start(), os_m.start()
        section = (text[od_s:os_s] if od_s < os_s else text[od_s:]) if eye == "OD" \
             else (text[os_s:od_s] if os_s < od_s else text[os_s:])
        m = re.search(pattern, section, re.IGNORECASE)
        if m: return abs(float(m.group(1)))
    elif od_m or os_m:
        # If only one eye section exists, avoid assigning opposite-eye values.
        marker_eye = "OD" if od_m else "OS"
        if marker_eye == eye:
            start = od_m.start() if od_m else os_m.start()
            section = text[start:]
            m = re.search(pattern, section, re.IGNORECASE)
            if m:
                return abs(float(m.group(1)))
        else:
            return None
    all_m = list(re.finditer(pattern, text, re.IGNORECASE))
    if len(all_m) == 2: return abs(float(all_m[0 if eye=="OD" else 1].group(1)))
    if len(all_m) == 1: return abs(float(all_m[0].group(1)))
    return None

def extract_first_cct_in_eye_section(text, eye):
    """
    Last-chance CCT extraction:
    take the OD/OS section from the OCR text and pick the first number that
    looks like corneal thickness in um (or mm that we can convert).
    """
    od_m = re.search(r"(?:(?:^|\W)(?:OD|O\.?\s*D\.?)(?:\W|$)|Right\s*Eye)", text, re.IGNORECASE)
    os_m = re.search(r"(?:(?:^|\W)(?:OS|O\.?\s*S\.?)(?:\W|$)|Left\s*Eye)", text, re.IGNORECASE)
    if od_m and os_m:
        od_s, os_s = od_m.start(), os_m.start()
        section = (text[od_s:os_s] if od_s < os_s else text[od_s:]) if eye == "OD" \
            else (text[os_s:od_s] if os_s < od_s else text[os_s:])
    else:
        section = text

    # Pull numbers in the order they appear.
    for m in re.finditer(r"(-?\d+(?:\.\d+)?)", section):
        try:
            v = abs(float(m.group(1)))
        except Exception:
            continue
        # If OCR likely read mm (0.42) instead of um (420).
        if v < 20:
            v *= 1000
        if 150 <= v <= 1000:
            return v
    return None

def _pad_image(img, pad=40):
    """Add white border so edge text isn't clipped during OCR."""
    import cv2
    return cv2.copyMakeBorder(img, pad, pad, pad, pad,
                               cv2.BORDER_CONSTANT, value=(255, 255, 255))


def _sharpen(gray):
    """Unsharp-mask pass — helps blurry photographed images."""
    import cv2
    import numpy as np
    blurred = cv2.GaussianBlur(gray, (0, 0), 3)
    return cv2.addWeighted(gray, 1.5, blurred, -0.5, 0)


def _deskew(gray):
    """Detect and correct small rotations (≤15°) in photographed images."""
    import cv2
    import numpy as np
    # Threshold to find text pixels
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(th > 0))
    if len(coords) < 50:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5 or abs(angle) > 15:
        return gray
    h, w = gray.shape
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h),
                          flags=cv2.INTER_CUBIC,
                          borderValue=255)


def _extract_colored_text_layer(bgr, scale=2.5):
    """
    Isolate red + green text (Tomey K-value rows) onto a white background
    and return a high-contrast grayscale image optimised for OCR.

    Strategy:
    - Convert to HSV.
    - Mask red pixels (hue 0-15 and 160-180) and green pixels (hue 35-85).
    - Dilate slightly so thin strokes are not lost.
    - Composite the colored pixels onto white; everything else becomes white.
    - Return the result upscaled and CLAHE-enhanced.
    """
    import cv2
    import numpy as np

    upscaled = cv2.resize(bgr, None, fx=scale, fy=scale,
                          interpolation=cv2.INTER_CUBIC)
    hsv = cv2.cvtColor(upscaled, cv2.COLOR_BGR2HSV)

    # Red mask (wraps around 0° in HSV)
    red_lo1 = cv2.inRange(hsv, np.array([0,   80,  60]), np.array([12,  255, 255]))
    red_lo2 = cv2.inRange(hsv, np.array([158, 80,  60]), np.array([180, 255, 255]))
    red_mask = cv2.bitwise_or(red_lo1, red_lo2)

    # Green mask
    green_mask = cv2.inRange(hsv, np.array([35, 60, 60]), np.array([90, 255, 255]))

    combined = cv2.bitwise_or(red_mask, green_mask)

    # Dilate to thicken thin strokes
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    combined = cv2.dilate(combined, kernel, iterations=1)

    # White canvas; paint colored pixels black
    result = np.full(upscaled.shape[:2], 255, dtype=np.uint8)
    result[combined > 0] = 0

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return clahe.apply(result)


def _is_blurry(gray, threshold=80.0):
    """Return True if the image appears blurry (low Laplacian variance)."""
    import cv2
    return cv2.Laplacian(gray, cv2.CV_64F).var() < threshold


def _preprocess_pachymetry_for_ocr(image_path):
    """
    Pachymetry tables are dense and OCR often misses micron values.
    Pipeline: pad → upscale → deskew → sharpen → CLAHE → threshold.
    Uses softer thresholding for blurry/photographed images.
    """
    import cv2

    bgr = cv2.imread(image_path)
    if bgr is None:
        return image_path

    bgr  = _pad_image(bgr, pad=30)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
    gray = _deskew(gray)

    blurry = _is_blurry(gray)

    if blurry:
        # Soft path for photographed/degraded images:
        # bilateral filter preserves edges better than NL-means on noisy photos
        gray = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
        gray = _sharpen(gray)
        clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
        gray  = clahe.apply(gray)
        # Larger block + higher C = softer, less noise-sensitive threshold
        th = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            51, 8,
        )
    else:
        # Sharp path for clean digital scans
        gray = cv2.fastNlMeansDenoising(gray, None, h=8,
                                         templateWindowSize=7, searchWindowSize=21)
        gray = _sharpen(gray)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        gray  = clahe.apply(gray)
        th = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31, 2,
        )

    return cv2.cvtColor(th, cv2.COLOR_GRAY2RGB)


def _preprocess_topography_for_ocr(image_path):
    """
    Topography reports (Tomey/axvam) contain K-values in red or green text
    which grayscale conversion washes out.

    Pipeline:
    1. Run standard grayscale preprocessing (full page, good for labels/numbers).
    2. Run color-channel extraction (isolates red/green K-value rows).
    Both results are returned stacked vertically so EasyOCR sees both passes
    in a single read call.
    """
    import cv2
    import numpy as np

    bgr = cv2.imread(image_path)
    if bgr is None:
        return image_path

    bgr = _pad_image(bgr, pad=30)

    # ── Pass 1: standard grayscale + CLAHE + threshold ──────────────
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
    gray = _deskew(gray)

    blurry = _is_blurry(gray)

    if blurry:
        gray = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
        gray = _sharpen(gray)
        clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
        gray  = clahe.apply(gray)
        th1 = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            51, 8,
        )
    else:
        gray = _sharpen(gray)
        gray = cv2.fastNlMeansDenoising(gray, None, h=10,
                                         templateWindowSize=7, searchWindowSize=21)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        gray  = clahe.apply(gray)
        th1 = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            35, 3,
        )

    # ── Pass 2: color-channel extraction (red/green text) ───────────
    colored_layer = _extract_colored_text_layer(bgr, scale=2.5)

    # Make both the same width before stacking
    w_target = max(th1.shape[1], colored_layer.shape[1])

    def pad_to_width(img, w):
        if img.shape[1] < w:
            pad = w - img.shape[1]
            return cv2.copyMakeBorder(img, 0, 0, 0, pad,
                                      cv2.BORDER_CONSTANT, value=255)
        return img

    th1_pad   = pad_to_width(th1, w_target)
    color_pad = pad_to_width(colored_layer, w_target)

    # Add a visible separator row so OCR doesn't merge text across passes
    sep = np.full((40, w_target), 255, dtype=np.uint8)

    combined = np.vstack([th1_pad, sep, color_pad])
    return cv2.cvtColor(combined, cv2.COLOR_GRAY2RGB)

def _extract_cct_from_pachymetry_chunks_v3(chunks, eye):
    """
    Very robust pachymetry CCT extraction from OCR chunks.
    Works even when OCR misspells the row label by:
      1) slicing to the correct OD/OS pachymetry section
      2) preferring a "central thickness"-like label nearby
      3) falling back to the smallest plausible thickness number in that section
         (central thickness is typically the smallest thickness-like value around ~400-600).
    """
    if not chunks:
        return None

    lower = [str(c).lower() for c in chunks]
    eye = (eye or "OD").upper()

    # Find section start for selected eye.
    start_pat = "pach"  # catches "Pachymatry", "Pachymetry", etc.
    if eye == "OD":
        start_idx = next((i for i, t in enumerate(lower) if start_pat in t and "od" in t), None)
        other_eye_idx = next((i for i, t in enumerate(lower) if start_pat in t and "os" in t), None)
    else:
        start_idx = next((i for i, t in enumerate(lower) if start_pat in t and "os" in t), None)
        other_eye_idx = next((i for i, t in enumerate(lower) if start_pat in t and "od" in t), None)

    if start_idx is None:
        return None

    # End at the next eye table (if present) or at epithelial thickness header.
    epithelial_idx = next((i for i, t in enumerate(lower) if "epithelial" in t or "epitholl" in t), None)
    end_idx_candidates = [x for x in (other_eye_idx, epithelial_idx) if x is not None and x > start_idx]
    end_idx = min(end_idx_candidates) if end_idx_candidates else min(len(chunks), start_idx + 120)

    section_chunks = chunks[start_idx:end_idx]
    section_lower = lower[start_idx:end_idx]

    def _first_number_in(s):
        m = re.search(r"[-]?[0-9]+(?:\.[0-9]+)?", str(s))
        if not m:
            return None
        try:
            return abs(float(m.group(0)))
        except Exception:
            return None

    # ── Strategy A: scan joined section text for CCT label + number ────
    # This handles the common case where OCR splits "Central Corneal Thickness (µm)"
    # across multiple chunks, so per-chunk matching misses it.
    section_text = " ".join(section_chunks)
    for pat in (
        r"central\s*corneal\s*thick\w*\s*[\(\[]?[^0-9]{0,12}(\d{3,4})",
        r"centr\w*\s+corn\w*\s+thick\w*[^0-9]{0,15}(\d{3,4})",
        r"corneal\s+thick\w*[^0-9]{0,12}(\d{3,4})",
        r"c\.?c\.?t\.?\s*[:\s]\s*(\d{3,4})",
        r"central\s*thick\w*[^0-9]{0,12}(\d{3,4})",
    ):
        m = re.search(pat, section_text, re.IGNORECASE)
        if m:
            v = abs(float(m.group(1)))
            if 150 <= v <= 1000:
                print(f"  CCT(regex-section-text)={v}")
                return v

    # ── Strategy B: per-chunk label detection (handles fused OCR tokens) ─
    # Also checks if "central"/"thick" appear in adjacent tokens, not just one.
    central_label_markers = (
        "cantre",
        "cettl",
        "central",
        "cewlcomeal",
        "comeal",
        "comral",
        "ceni",
    )
    thickness_like_markers = (
        "thck",
        "thick",
        "thckn",
        "thcknau",
        "mkrese",
        "inican",
        "inicaness",
        "thic",
        "thicin",
        "thicinare",
    )

    for i, tok in enumerate(section_lower):
        has_central   = any(cm in tok for cm in central_label_markers)
        has_thickness = any(tm in tok for tm in thickness_like_markers)

        # Single fused token: "CentralCornealThickness" type
        if has_central and has_thickness:
            for j in range(i + 1, min(i + 8, len(section_chunks))):
                v = _first_number_in(section_chunks[j])
                if v is not None and 150 <= v <= 1000:
                    return v

        # Split label: "Central" ... "Thickness" across adjacent chunks
        elif has_central:
            # Look for "thick" in the next 3 tokens
            for k in range(i + 1, min(i + 4, len(section_chunks))):
                nearby = section_lower[k]
                if any(tm in nearby for tm in thickness_like_markers):
                    # Found split label — now find the number
                    for j in range(k + 1, min(k + 6, len(section_chunks))):
                        v = _first_number_in(section_chunks[j])
                        if v is not None and 150 <= v <= 1000:
                            return v
                    break

    # Fallback: smallest plausible micron-like number in the OD/OS section.
    candidates = []
    for tok in section_chunks:
        v = _first_number_in(tok)
        if v is not None and 300 <= v <= 650:
            candidates.append(v)
    if not candidates:
        # Broader fallback (still keeps results clinically plausible).
        for tok in section_chunks:
            v = _first_number_in(tok)
            if v is not None and 150 <= v <= 1000:
                candidates.append(v)

    if not candidates:
        return None

    # Do not assume the thinner value is "central" when two plausible CCTs
    # appear in the same slice (common when OD/OS both leak into one section).
    uniq = sorted(set(round(c, 1) for c in candidates))
    if len(uniq) == 2 and abs(uniq[0] - uniq[1]) < 120:
        return None

    return round(min(candidates), 2)


_EYE_COL_RE = re.compile(
    r"(?:(?:^|\W)(OD|OS|O\.?\s*D\.?|O\.?\s*S\.?)(?:\W|$)|Right\s*Eye|Left\s*Eye)",
    re.I,
)


def _eye_symbol_from_col_label(m):
    s = re.sub(r"\s+", "", m.group(0).lower())
    if "left" in s or s == "os" or s.startswith("os") or "o.s" in s:
        return "OS"
    return "OD"


def _assign_od_os_thickness_pair(text, m, v_left, v_right, min_val, max_val):
    """
    Map two left-to-right OCR numbers after a CCT row to (OD, OS).
    Many devices print OS then OD; we previously assumed OD then OS only.
    """
    try:
        v1 = abs(float(v_left))
        v2 = abs(float(v_right))
    except Exception:
        return None
    for vv in (v1, v2):
        if min_val is not None and vv < min_val:
            return None
        if max_val is not None and vv > max_val:
            return None

    i1, i2 = m.start(1), m.start(2)
    ctx_start = max(0, m.start() - 240)
    ctx = text[ctx_start : m.end()]
    o1 = i1 - ctx_start
    o2 = i2 - ctx_start

    def last_eye_before(pos):
        last = None
        for mm in _EYE_COL_RE.finditer(ctx):
            if mm.start() >= pos:
                break
            last = _eye_symbol_from_col_label(mm)
        return last

    le1 = last_eye_before(o1)
    le2 = last_eye_before(o2)
    if le1 == "OD" and le2 == "OS":
        od_v, os_v = v1, v2
    elif le1 == "OS" and le2 == "OD":
        od_v, os_v = v2, v1
    else:
        wide_s = max(0, m.start() - 400)
        sub = text[wide_s:i1]
        hdr_pair = list(re.finditer(r"(?:^|\W)(OD|OS)(?:\W|$)", sub, re.I))
        if len(hdr_pair) >= 2:
            a, b = hdr_pair[0].group(1).upper(), hdr_pair[1].group(1).upper()
            if a == "OS" and b == "OD":
                od_v, os_v = v2, v1
            elif a == "OD" and b == "OS":
                od_v, os_v = v1, v2
            else:
                od_v, os_v = v1, v2
        else:
            head = ctx[:o1]
            os_m = re.search(r"(?:^|\W)OS(?:\W|$)", head, re.I)
            od_m = re.search(r"(?:^|\W)OD(?:\W|$)", head, re.I)
            if os_m and od_m:
                od_v, os_v = (v1, v2) if od_m.start() < os_m.start() else (v2, v1)
            elif os_m and not od_m:
                od_v, os_v = v2, v1
            elif od_m and not os_m:
                od_v, os_v = v1, v2
            else:
                od_v, os_v = v1, v2

    return od_v, os_v


def extract_cct_explicit_labeled_eyes(text, eye, min_val=150, max_val=1000):
    """
    Prefer values bound to explicit OD/OS tokens after a CCT label (most reliable).
    """
    if not text:
        return None
    eye_u = (eye or "OD").upper()
    # Looser eye/value coupling — OCR often yields "OD503", "O D 503", or "OD : 503".
    od_pat = r"(?:(?:^|\W)(?:OD|O\.?\s*D\.?)(?:\W|$)|Right\s*Eye)\s*\D{0,80}([-\d.]+)"
    os_pat = r"(?:(?:^|\W)(?:OS|O\.?\s*S\.?)(?:\W|$)|Left\s*Eye)\s*\D{0,80}([-\d.]+)"
    for lab in (
        r"central\s*corneal\s*thickness",
        r"corneal\s*thickness(?!\s*map)",
        r"\bcct\b(?!\s*map)",
    ):
        for lm in re.finditer(lab, text, re.I):
            seg = text[lm.end() : lm.end() + 480]
            od_m = re.search(od_pat, seg, re.I)
            os_m = re.search(os_pat, seg, re.I)
            if not (od_m and os_m):
                continue
            try:
                od_v = _normalize_cct_um(abs(float(od_m.group(1))))
                os_v = _normalize_cct_um(abs(float(os_m.group(1))))
            except Exception:
                continue
            if not (min_val <= od_v <= max_val and min_val <= os_v <= max_val):
                continue
            return os_v if eye_u == "OS" else od_v
    return None


def extract_cct_from_chunk_eye_pairs(chunks, eye):
    """
    Table rows where OCR emits ... OD 503 OS 520 (or split tokens).
    """
    if not chunks:
        return None
    eye_u = (eye or "OD").upper()
    normalized = [_norm(c) for c in chunks]
    for i, token in enumerate(normalized):
        if not (
            all(k in token for k in ["corneal", "thickness"])
            or _looks_like_row_label(normalized, i, ["corneal", "thickness"])
            or _looks_like_row_label(normalized, i, ["central", "corneal", "thickness"])
        ):
            continue
        window = " ".join(str(chunks[k]) for k in range(i, min(i + 26, len(chunks))))
        m_od_first = re.search(
            r"OD\D{0,50}([-\d.]+)\D{0,90}OS\D{0,50}([-\d.]+)",
            window,
            re.I,
        )
        m_os_first = re.search(
            r"OS\D{0,50}([-\d.]+)\D{0,90}OD\D{0,50}([-\d.]+)",
            window,
            re.I,
        )
        if m_od_first:
            try:
                od_vw = _normalize_cct_um(abs(float(m_od_first.group(1))))
                os_vw = _normalize_cct_um(abs(float(m_od_first.group(2))))
            except Exception:
                od_vw = os_vw = None
            if (
                od_vw
                and os_vw
                and 150 <= od_vw <= 1000
                and 150 <= os_vw <= 1000
            ):
                return os_vw if eye_u == "OS" else od_vw
        if m_os_first:
            try:
                os_vw = _normalize_cct_um(abs(float(m_os_first.group(1))))
                od_vw = _normalize_cct_um(abs(float(m_os_first.group(2))))
            except Exception:
                od_vw = os_vw = None
            if (
                od_vw
                and os_vw
                and 150 <= od_vw <= 1000
                and 150 <= os_vw <= 1000
            ):
                return os_vw if eye_u == "OS" else od_vw

        od_v = os_v = None
        for j in range(i + 1, min(i + 28, len(chunks))):
            raw = str(chunks[j])
            tok = re.sub(r"[^a-z0-9]+", "", raw.lower())
            m_od = re.search(
                r"(?:(?:^|\W)(?:OD|O\.?\s*D\.?)(?:\W|$)|Right\s*Eye)\D{0,12}([-\d.]+)",
                raw,
                re.I,
            )
            if m_od:
                v = _normalize_cct_um(abs(float(m_od.group(1))))
                if v and 150 <= v <= 1000:
                    od_v = v
            m_os = re.search(
                r"(?:(?:^|\W)(?:OS|O\.?\s*S\.?)(?:\W|$)|Left\s*Eye)\D{0,12}([-\d.]+)",
                raw,
                re.I,
            )
            if m_os:
                v = _normalize_cct_um(abs(float(m_os.group(1))))
                if v and 150 <= v <= 1000:
                    os_v = v
            if tok in ("od", "o0", "0d") and od_v is None:
                v = _normalize_cct_um(_cell_to_number(chunks[j + 1] if j + 1 < len(chunks) else None))
                if v and 150 <= v <= 1000:
                    od_v = v
            elif tok in ("os", "o5", "0s") and os_v is None:
                v = _normalize_cct_um(_cell_to_number(chunks[j + 1] if j + 1 < len(chunks) else None))
                if v and 150 <= v <= 1000:
                    os_v = v
        if od_v and os_v:
            return os_v if eye_u == "OS" else od_v
    return None


def _keratometry_eye_scope(text, eye):
    """
    Slice OCR text to the selected eye when OD and OS blocks are present.
    Keratometry regex then runs inside this slice so we do not read the fellow eye.
    """
    if not text:
        return ""
    eye_u = (eye or "OD").upper()
    od_m = re.search(r"(?:(?:^|\W)(?:OD|O\.?\s*D\.?)(?:\W|$)|Right\s*Eye)", text, re.IGNORECASE)
    os_m = re.search(r"(?:(?:^|\W)(?:OS|O\.?\s*S\.?)(?:\W|$)|Left\s*Eye)", text, re.IGNORECASE)
    if od_m and os_m:
        od_s, os_s = od_m.start(), os_m.start()
        if od_s < os_s:
            od_sec, os_sec = text[od_s:os_s], text[os_s:]
        else:
            os_sec, od_sec = text[os_s:od_s], text[od_s:]
        return od_sec if eye_u == "OD" else os_sec
    return text


def _search_k_pattern_scoped(text, eye, pattern):
    """First match inside the selected-eye scope, then full text as fallback."""
    for probe in (_keratometry_eye_scope(text, eye), text):
        if not probe or not probe.strip():
            continue
        m = re.search(pattern, probe, re.IGNORECASE)
        if not m:
            continue
        try:
            return abs(float(m.group(1)))
        except Exception:
            continue
    return None


def _extract_sim_k_flat_steep_pair(text, eye):
    """
    Sim K flat X steep Y (or steep then flat) on one line — most reliable K1/K2 pair.
    Returns (K1_flatter, K2_steeper) after normalizing each diopter read.
    """
    pair_patterns = (
        r"sim(?:ulated)?\s*k\s*[^\d]{0,40}?flat[^\d]{0,25}([-\d.]+)[^\d]{0,55}?steep[^\d]{0,25}([-\d.]+)",
        r"sim(?:ulated)?\s*k\s*[^\d]{0,40}?steep[^\d]{0,25}([-\d.]+)[^\d]{0,55}?flat[^\d]{0,25}([-\d.]+)",
    )
    for probe in (_keratometry_eye_scope(text, eye), text):
        if not probe or not probe.strip():
            continue
        for pat in pair_patterns:
            m = re.search(pat, probe, re.IGNORECASE)
            if not m:
                continue
            try:
                a = _normalize_k_diopters(abs(float(m.group(1))))
                b = _normalize_k_diopters(abs(float(m.group(2))))
            except Exception:
                continue
            if a is None or b is None:
                continue
            # K1 = flatter (lower D), K2 = steeper (higher D) for Sim K magnitudes
            k1, k2 = (a, b) if a <= b else (b, a)
            if 30 <= k1 <= 65 and 30 <= k2 <= 65:
                return k1, k2
    return None, None


def extract_ks_kf(text, chunks, eye):
    """
    Prefer topography-specific labels:
    - Ks / K steep -> K2
    - Kf / K flat  -> K1
    """
    out = {}

    # Regex pass — scoped to selected eye when bilateral text is present.
    for pat in [
        r"(?:^|\W)k\s*s(?![a-z])[^\d-]{0,25}([-\d.]+)",
        r"(?:^|\W)k\s*2(?![a-z])[^\d-]{0,25}([-\d.]+)",
        r"(?:^|\W)k\s*steep(?![a-z])[^\d-]{0,25}([-\d.]+)",
        r"(?:^|\W)s\s*k\s*1(?![a-z])[^\d-]{0,25}([-\d.]+)",
        r"(?:^|\W)s\s*k\s*[i1l](?![a-z])[^\d-]{0,25}([-\d.]+)",
        r"(?:^|\W)[8s]\s*k\s*[1il](?![a-z])[^\d-]{0,25}([-\d.]+)",
    ]:
        raw = _search_k_pattern_scoped(text, eye, pat)
        v = _normalize_k_diopters(raw)
        if v is not None:
            out["K2_diopters"] = v
            break

    for pat in [
        r"(?:^|\W)min\s*k(?![a-z])[^\d-]{0,25}([-\d.]+)",
        r"(?:^|\W)k\s*f(?![a-z])[^\d-]{0,25}([-\d.]+)",
        r"(?:^|\W)k\s*1(?![a-z])[^\d-]{0,25}([-\d.]+)",
        r"(?:^|\W)k\s*flat(?![a-z])[^\d-]{0,25}([-\d.]+)",
        r"(?:^|\W)s\s*k\s*2(?![a-z])[^\d-]{0,25}([-\d.]+)",
        r"(?:^|\W)[8s]\s*k\s*[2z](?![a-z])[^\d-]{0,25}([-\d.]+)",
    ]:
        raw = _search_k_pattern_scoped(text, eye, pat)
        v = _normalize_k_diopters(raw)
        if v is not None:
            out["K1_diopters"] = v
            break

    # Strict chunk fallback using exact labels only.
    if "K2_diopters" not in out:
        v = _extract_value_after_exact_k_label(chunks, ["ks", "k2"])
        if v is None:
            v = extract_row_value_from_chunks(chunks, ["k2", "steep"], eye)
        if v is not None:
            out["K2_diopters"] = v
    if "K1_diopters" not in out:
        v = _extract_value_after_exact_k_label(chunks, ["kf", "k1"])
        if v is None:
            v = extract_row_value_from_chunks(chunks, ["k1", "flat"], eye)
        if v is not None:
            out["K1_diopters"] = v

    return out


def _extract_keratometry_separate(text, chunks, eye):
    """
    K1 and K2 from distinct report fields (Kf/Ks, K1 flat, K2 steep, table columns).
    Never sets K1 == K2 unless the source only provides one distinct value.

    Order: Sim K pair (same line) → OD/OS table rows → Ks/Kf labels → scoped regex.
    """
    out = {}

    sk1, sk2 = _extract_sim_k_flat_steep_pair(text, eye)
    if sk1 is not None and sk2 is not None:
        out["K1_diopters"] = sk1
        out["K2_diopters"] = sk2
        return out

    v = _normalize_k_diopters(extract_row_value_from_chunks(chunks, ["k1", "flat"], eye))
    if v is not None:
        out["K1_diopters"] = v
    v = _normalize_k_diopters(extract_row_value_from_chunks(chunks, ["k2", "steep"], eye))
    if v is not None:
        out["K2_diopters"] = v

    ks_kf = extract_ks_kf(text, chunks, eye)
    if out.get("K1_diopters") is None and ks_kf.get("K1_diopters") is not None:
        out["K1_diopters"] = ks_kf["K1_diopters"]
    if out.get("K2_diopters") is None and ks_kf.get("K2_diopters") is not None:
        out["K2_diopters"] = ks_kf["K2_diopters"]

    if out.get("K1_diopters") is None:
        for pat in [
            r"Sim\s*K\s*flat[\s:=-]*(-?[\d.]+)",
            r"(?:^|\W)K\s*1(?:\s*\([^)]*flat[^)]*\))?[^\d-]{0,25}([-\d.]+)(?:\s*@\s*\d+)?",
            r"(?:^|\W)min\s*k(?![a-z])[^\d-]{0,25}([-\d.]+)",
            r"(?:^|\W)k\s*f(?![a-z])[^\d-]{0,25}([-\d.]+)",
            r"(?:^|\W)K\s*flat(?![a-z])[^\d-]{0,25}([-\d.]+)",
            r"(?:^|\W)s\s*k\s*2(?![a-z])[^\d-]{0,25}([-\d.]+)",
            r"(?:^|\W)[8s]\s*k\s*[2z](?![a-z])[^\d-]{0,25}([-\d.]+)",
        ]:
            raw = _search_k_pattern_scoped(text, eye, pat)
            v = _normalize_k_diopters(raw)
            if v is not None:
                out["K1_diopters"] = v
                break

    if out.get("K2_diopters") is None:
        for pat in [
            r"Sim\s*K\s*steep[\s:=-]*(-?[\d.]+)",
            r"(?:^|\W)K\s*2(?:\s*\([^)]*steep[^)]*\))?[^\d-]{0,25}([-\d.]+)(?:\s*@\s*\d+)?",
            r"(?:^|\W)k\s*s(?![a-z])[^\d-]{0,25}([-\d.]+)",
            r"(?:^|\W)K\s*steep(?![a-z])[^\d-]{0,25}([-\d.]+)",
            r"(?:^|\W)s\s*k\s*1(?![a-z])[^\d-]{0,25}([-\d.]+)",
            r"(?:^|\W)s\s*k\s*[i1l](?![a-z])[^\d-]{0,25}([-\d.]+)",
            r"(?:^|\W)[8s]\s*k\s*[1il](?![a-z])[^\d-]{0,25}([-\d.]+)",
        ]:
            raw = _search_k_pattern_scoped(text, eye, pat)
            v = _normalize_k_diopters(raw)
            if v is not None:
                out["K2_diopters"] = v
                break

    return out


def _extract_keratometry_spherical(text, chunks, eye):
    """
    Single spherical keratometry (SK1 / Related Indices / K with Spherical label).
    Returns one diopter to apply to both K1 and K2 when separate K1/K2 are absent.
    """
    sk1_val = _best_keratometry_diopter(_collect_sk1_candidates_from_text(text, eye))
    if sk1_val is None:
        for pat in [
            r"(?:^|\W)K(?![a-z])[^\d-]{0,20}([-\d.]+)\s*\((?:spherical|sphere|sph)\)",
            r"(?:^|\W)spherical\s*k[^\d-]{0,25}([-\d.]+)",
        ]:
            raw = _search_k_pattern_scoped(text, eye, pat)
            if raw is None:
                continue
            sk1_val = _normalize_k_diopters(raw)
            if sk1_val is not None:
                break
    if sk1_val is None:
        v = _extract_value_after_exact_label(chunks, ["sk1", "ski", "skl", "8k1"], lookahead=5)
        sk1_val = _normalize_k_diopters(v) if v is not None else None
    if sk1_val is not None:
        return sk1_val

    if not re.search(r"\b(spherical|sk1|ski|skl|8k1)\b", text, re.IGNORECASE):
        return None

    spherical_k = None
    for pat in [
        r"(?:^|\W)K(?![a-z])[^\d-]{0,20}([-\d.]+)\s*\((?:spherical|sphere|sph)\)",
        r"(?:^|\W)spherical\s*k[^\d-]{0,25}([-\d.]+)",
    ]:
        raw = _search_k_pattern_scoped(text, eye, pat)
        if raw is not None:
            spherical_k = raw
            break
    return _normalize_k_diopters(spherical_k)


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower())

def _cell_to_number(cell):
    if cell is None:
        return None
    c = _norm(cell).replace("µ", "u")
    if re.fullmatch(r"[-_–—\s]+", c):
        return None
    m = re.search(r"(-?\d+(?:\.\d+)?)", c)
    if not m:
        return None
    v = abs(float(m.group(1)))
    # If OCR captured mm (e.g. "0.42 mm"), normalize to um for CCT.
    # (CCT should typically be ~250-800 um.)
    if "mm" in c and v < 10:
        v *= 1000
    return v

def _normalize_k_diopters(v):
    """
    Keratometry K values are typically around ~20..80 diopters.
    OCR can drop/misplace the decimal (e.g. 4.4 instead of 44),
    so we try scaling by powers of 10 and select the closest plausible value.
    """
    if v is None:
        return None
    try:
        v = abs(float(v))
    except Exception:
        return None
    candidates = []
    for pow10 in (-2, -1, 0, 1, 2, 3):
        vv = v * (10 ** pow10)
        if 30 <= vv <= 65:
            candidates.append(vv)
    if not candidates:
        # Reject clearly implausible K values instead of returning bad OCR.
        return None
    if len(candidates) == 1:
        return round(candidates[0], 2)
    # Prefer the scale closest to the raw OCR number (avoids biasing toward ~50 D).
    v0 = max(float(v), 1e-6)
    best = min(
        candidates,
        key=lambda x: (abs(math.log10((x + 1e-9) / v0)), abs(x - 41.0)),
    )
    return round(best, 2)

def _normalize_astig_diopters(v):
    """
    Astigmatism magnitude is usually ~0..10 diopters.
    If OCR returns a value like 18 (meaning 1.8), shift down.
    """
    if v is None:
        return None
    try:
        v = abs(float(v))
    except Exception:
        return None
    # Sub-diopter corneal cylinder (e.g. 0.12 D on topography) — do not upscale.
    if v < 0.5:
        return round(v, 2)
    # If OCR misses decimal (e.g. 1.8 read as 18), bring back.
    while v > 10:
        v /= 10
    return round(v, 2)

def _normalize_cct_um(v):
    """If CCT looks like mm from OCR, convert to um."""
    if v is None:
        return None
    try:
        v = float(v)
    except Exception:
        return None
    # Common OCR value for CCT in mm is ~0.4-0.8.
    if v < 20:
        v *= 1000
    return v

def _normalize_token(s):
    return re.sub(r"[^a-z0-9]+", "", _norm(s))

def _looks_like_row_label(normalized_chunks, start_idx, row_keywords):
    """
    Return True if row keywords are found in order across a short token window.
    This handles OCR where labels are split into separate chunks, e.g.
    ['Corneal', 'Thickness', 'OD', 'OS', ...].
    """
    words = [_normalize_token(w) for w in row_keywords if _normalize_token(w)]
    if not words:
        return False
    window = normalized_chunks[start_idx:min(start_idx + 6, len(normalized_chunks))]
    wi = 0
    for token in window:
        if words[wi] in _normalize_token(token):
            wi += 1
            if wi == len(words):
                return True
    return False

def _extract_value_after_exact_k_label(chunks, labels):
    """
    Extract number after exact short K label token (Kf/Ks/K1/K2).
    Avoids false positives from words like KSI or Similarity blocks.
    """
    if not chunks:
        return None
    exact = {str(x).lower() for x in (labels or [])}
    for i, raw in enumerate(chunks):
        tok = re.sub(r"[^a-z0-9]+", "", str(raw).lower())
        if tok not in exact:
            continue
        for j in range(i + 1, min(i + 5, len(chunks))):
            v = _cell_to_number(chunks[j])
            if v is not None:
                return v
    return None

def _extract_value_after_exact_label(chunks, labels, lookahead=6):
    """Extract first numeric value that appears after an exact label token."""
    if not chunks:
        return None
    exact = {re.sub(r"[^a-z0-9]+", "", str(x).lower()) for x in (labels or [])}
    if not exact:
        return None
    for i, raw in enumerate(chunks):
        tok = re.sub(r"[^a-z0-9]+", "", str(raw).lower())
        if tok not in exact:
            continue
        for j in range(i + 1, min(i + 1 + lookahead, len(chunks))):
            v = _cell_to_number(chunks[j])
            if v is not None:
                return v
    return None

def _collect_sk1_candidates_from_text(text, eye=None):
    """
    OCR often merges two passes; first block may misread SK1 (e.g. 8k1 29.80)
    while a later 'Related Indices' line has SKI 39.80. Collect all SK1-like
    tokens and let _best_keratometry_diopter choose the plausible value.
    When ``eye`` is set, search the selected-eye slice first, then full text.
    """
    if not text:
        return []
    texts = []
    if eye is not None:
        scoped = _keratometry_eye_scope(text, eye)
        if scoped and scoped.strip() and scoped != text:
            texts.append(scoped)
    texts.append(text)
    candidates = []
    for t in texts:
        for m in re.finditer(
            r"(?:Related\s+Indices|Indices[_:\s])[\s\S]{0,320}?(?:SK[1Iil]|8k1)\s*[:.]?\s*(-?[\d.]+)",
            t,
            re.IGNORECASE,
        ):
            try:
                candidates.append(abs(float(m.group(1))))
            except Exception:
                pass
        for m in re.finditer(
            r"(?:^|\s)(?:SK[1Iil]|8k1)\s*[:.]?\s*(-?[\d.]+)",
            t,
            re.IGNORECASE,
        ):
            try:
                candidates.append(abs(float(m.group(1))))
            except Exception:
                pass
    return candidates

def _best_keratometry_diopter(candidates):
    """Pick best plausible K (D) when OCR returns duplicate/noisy reads."""
    if not candidates:
        return None
    normed = []
    for c in candidates:
        n = _normalize_k_diopters(c)
        if n is not None:
            normed.append(n)
    if not normed:
        return None
    narrow = [x for x in normed if 35 <= x <= 45]
    if narrow:
        return round(statistics.median(narrow), 2)
    wider = [x for x in normed if 30 <= x <= 50]
    if wider:
        return round(statistics.median(wider), 2)
    return round(statistics.median(normed), 2)

def _collect_cyl_candidates_from_text(text):
    """Corneal CYL / CA near Related Indices (Tomey-style reports)."""
    if not text:
        return []
    candidates = []
    for m in re.finditer(
        r"(?:Related\s+Indices|Indices[_:\s])[\s\S]{0,320}?(?:\bCY\b|\bCYL\b|\bCA\b)\s*[:.]?\s*(-?[\d.]+)",
        text,
        re.IGNORECASE,
    ):
        try:
            candidates.append(abs(float(m.group(1))))
        except Exception:
            pass
    for m in re.finditer(
        r"(?:Related\s+Indices|Indices[_:\s])[\s\S]{0,320}?corneal\s*cyl[^\d-]{0,24}(-?[\d.]+)",
        text,
        re.IGNORECASE,
    ):
        try:
            candidates.append(abs(float(m.group(1))))
        except Exception:
            pass
    return candidates

def _best_corneal_cyl_diopter(candidates):
    if not candidates:
        return None
    normed = []
    for c in candidates:
        n = _normalize_astig_diopters(c)
        if n is not None and 0 <= n <= 10:
            normed.append(n)
    if not normed:
        return None
    # Prefer small values typical of topography CYL (often < 2 D)
    small = [x for x in normed if x <= 5]
    return min(small if small else normed, key=lambda x: abs(x - 0.5))

def _reconcile_k_values(extracted):
    """
    Keep clinically consistent K ordering:
    K1 is flatter (lower), K2 is steeper (higher).
    """
    k1 = extracted.get("K1_diopters")
    k2 = extracted.get("K2_diopters")
    if k1 is None or k2 is None:
        return
    try:
        k1f = float(k1)
        k2f = float(k2)
    except Exception:
        return
    if k1f > k2f and abs(k1f - k2f) >= 0.2:
        extracted["K1_diopters"] = round(k2f, 2)
        extracted["K2_diopters"] = round(k1f, 2)

def _extract_pachy_from_chunks(chunks, eye):
    """
    Robust pachymetry fallback for noisy OCR chunk streams.
    Looks for thickness-related labels (including common OCR misspellings),
    then picks OD/OS or nearest plausible thickness value.
    """
    if not chunks:
        return None

    normalized = [_norm(c) for c in chunks]
    eye_idx = 0 if eye == "OD" else 1
    # Conservative label roots to catch OCR variations:
    # thickness/thicknes/thikness, pachy/pachymetry, cct, thinnest/minimum.
    label_markers = ("thick", "pach", "cct", "thinn", "minim")

    for i, token in enumerate(normalized):
        token_compact = _normalize_token(token)
        if not any(m in token_compact for m in label_markers):
            continue

        # Prefer OD/OS style row extraction first.
        cells = []
        for j in range(i + 1, min(i + 14, len(chunks))):
            raw = str(chunks[j]).strip()
            if not raw:
                continue
            if re.search(r"\d", raw) or re.fullmatch(r"[-_–—\s]+", raw):
                cells.append(raw)
            if len(cells) >= 2:
                break
        if len(cells) >= 2:
            v = _normalize_cct_um(_cell_to_number(cells[eye_idx]))
            if v and 150 <= v <= 1000:
                return v

        # If not a two-column row, take nearest plausible single value.
        for j in range(i + 1, min(i + 18, len(chunks))):
            v = _normalize_cct_um(_cell_to_number(chunks[j]))
            if v and 150 <= v <= 1000:
                return v
    return None

def extract_value_in_eye_section(text, eye, value_label_regex, min_val=None, max_val=None):
    """
    Extract a labeled numeric value from the eye-specific pachymetry section.
    Example row:
      Pachymetry OD ... Central Corneal Thickness (um) 424
    """
    if not text:
        return None

    eye_u = (eye or "OD").upper()
    if eye_u == "OD":
        start_patterns = (
            r"pachymetry\s*od",
            r"pachym\w*\s+od\b",
            r"pachy\w*\s+od\b",
            r"(?:^|\W)od(?:\W|$)(?=[\s\S]{0,300}(?:central\s*corneal|corneal\s*thickness|\bcct\b))",
        )
        end_pat = (
            r"pachymetry\s*os|pachym\w*\s+os\b|pachy\w*\s+os\b|"
            r"(?:^|\W)os(?:\W|$)(?=[\s\S]{0,120}(?:central\s*corneal|corneal\s*thickness|\bcct\b))|"
            r"epithelial\s*thickness"
        )
    else:
        start_patterns = (
            r"pachymetry\s*os",
            r"pachym\w*\s+os\b",
            r"pachy\w*\s+os\b",
            r"(?:^|\W)os(?:\W|$)(?=[\s\S]{0,300}(?:central\s*corneal|corneal\s*thickness|\bcct\b))",
        )
        end_pat = (
            r"epithelial\s*thickness|epith\w*|"
            r"pachymetry\s*od|pachym\w*\s+od\b|pachy\w*\s+od\b"
        )

    start_m = None
    for sp in start_patterns:
        start_m = re.search(sp, text, re.IGNORECASE)
        if start_m:
            break
    if not start_m:
        return None

    tail = text[start_m.end() :]
    end_m = re.search(end_pat, tail, re.IGNORECASE)
    if end_m and end_m.start() > 0:
        section = tail[: end_m.start()]
    else:
        section = tail[:800]
    if len(section) > 900:
        section = section[:900]

    m = re.search(rf"{value_label_regex}.{{0,80}}?([-\d.]+)", section, re.IGNORECASE)
    if not m:
        return None
    try:
        v = _normalize_cct_um(abs(float(m.group(1))))
        if min_val is not None and v < min_val:
            return None
        if max_val is not None and v > max_val:
            return None
        return v
    except Exception:
        return None

def extract_row_value_from_chunks(chunks, row_keywords, eye):
    """
    Extracts value from OCR table rows like:
    'K1 (Flat K)' | OD cell | OS cell
    using the selected eye to choose the correct column.
    """
    if not chunks:
        return None

    eye_idx = 0 if eye == "OD" else 1
    normalized = [_norm(c) for c in chunks]

    for i, token in enumerate(normalized):
        if all(k in token for k in row_keywords) or _looks_like_row_label(normalized, i, row_keywords):
            cells = []
            for j in range(i + 1, min(i + 8, len(chunks))):
                raw = str(chunks[j]).strip()
                if not raw:
                    continue
                # Candidate OD/OS row cells: number-containing value or dash placeholder.
                if re.search(r"\d", raw) or re.fullmatch(r"[-_–—\s]+", raw):
                    cells.append(raw)
                if len(cells) >= 2:
                    break
            if len(cells) >= 2:
                return _cell_to_number(cells[eye_idx])
    return None

def extract_two_column_row_value(text, row_label_regex, eye, min_val=None, max_val=None):
    """
    Extract a row that contains OD and OS values in sequence, e.g.:
    'Central Corneal Thickness 424 um 566 um'
    and return value based on selected eye.

    Column order is not standardized (OS-left / OD-right is common); we infer
    OD vs OS from header tokens or from labels immediately before each number.
    """
    # OCR output can vary a lot (extra punctuation, units, line breaks).
    # Keep this tolerant but still require two numeric values.
    m = re.search(
        rf"{row_label_regex}\s*[:\-]?\s*([-\d.]+)\s*(?:u|p|um|pm|µm|mm)?\s*[^0-9\-]*\s*([-\d.]+)\s*(?:u|p|um|pm|µm|mm)?",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    try:
        v1 = abs(float(m.group(1)))
        v2 = abs(float(m.group(2)))
        matched = m.group(0).lower()
        # If OCR captured mm (e.g. "0.42 mm ... 0.56 mm"), convert to um.
        if re.search(r"\bmm\b", matched):
            v1 *= 1000
            v2 *= 1000
        v1 = _normalize_cct_um(v1)
        v2 = _normalize_cct_um(v2)
        pair = _assign_od_os_thickness_pair(text, m, v1, v2, min_val, max_val)
        if not pair:
            return None
        od_val, os_val = pair
        value = os_val if (eye or "OD").upper() == "OS" else od_val
        if min_val is not None and value < min_val:
            return None
        if max_val is not None and value > max_val:
            return None
        return value
    except Exception:
        return None

def extract_value_near_label(text, label_regex, min_val=None, max_val=None):
    """
    Finds first numeric value shortly after a label. Useful for noisy OCR where
    table structure is lost but label + value still appear in sequence.
    """
    # OCR tables/labels often break across whitespace and punctuation;
    # allow a wider window so we can still capture the number.
    m = re.search(rf"{label_regex}.{{0,100}}?([-\d.]+)", text, re.IGNORECASE)
    if not m:
        return None
    try:
        v = abs(float(m.group(1)))
        # For CCT, OCR can capture mm (e.g. 0.42) without unit context.
        # Convert early so range checks work in um.
        if min_val is not None and max_val is not None and max_val > 200 and v < 20:
            v *= 1000
        if min_val is not None and v < min_val:
            return None
        if max_val is not None and v > max_val:
            return None
        return v
    except Exception:
        return None
 
def _split_ocr_by_column(ocr_results, image_width, eye):
    """
    For side-by-side reports (Zeiss pachymetry has OD left / OS right),
    filter OCR results to only those whose x-centre falls in the correct half.
    This prevents OD and OS values from interleaving in the chunk list.

    eye='OD' → keep tokens with x_centre < midpoint
    eye='OS' → keep tokens with x_centre >= midpoint
    """
    if not ocr_results or not image_width:
        return ocr_results
    mid = image_width / 2
    filtered = []
    for item in ocr_results:
        bbox, text, conf = item
        x_center = (bbox[0][0] + bbox[2][0]) / 2
        if eye == "OD" and x_center < mid:
            filtered.append(item)
        elif eye == "OS" and x_center >= mid:
            filtered.append(item)
    # If filtering removed everything (single-eye report), return all results
    return filtered if filtered else ocr_results


def _spatially_sorted_chunks(ocr_results, row_tolerance=15):
    """
    Convert EasyOCR detail=1 results into a spatially ordered chunk list.

    EasyOCR does not guarantee strict left-to-right order within a row when
    reading tabular reports. Without bounding boxes the code had no way to
    tell which column (OD vs OS) a value belonged to.

    This function groups detected tokens into rows by their vertical centre
    coordinate (within ``row_tolerance`` pixels), then sorts each row left-to-
    right by horizontal centre so the returned chunk list always follows a
    predictable top-to-bottom, left-to-right reading order.  The existing
    chunk-index logic (eye_idx = 0 for OD, 1 for OS) therefore works reliably.
    """
    if not ocr_results:
        return []

    annotated = []
    for bbox, text, _conf in ocr_results:
        token = str(text).strip()
        if not token:
            continue
        # bbox: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
        y_center = (bbox[0][1] + bbox[2][1]) / 2
        x_center = (bbox[0][0] + bbox[2][0]) / 2
        annotated.append((y_center, x_center, token))

    # Sort by y first, then group into rows with tolerance for slight height variation.
    annotated.sort(key=lambda t: t[0])
    rows = []
    for item in annotated:
        y = item[0]
        if rows and abs(y - rows[-1][-1][0]) <= row_tolerance:
            rows[-1].append(item)
        else:
            rows.append([item])

    # Within each row sort left → right.
    chunks = []
    for row in rows:
        row.sort(key=lambda t: t[1])
        chunks.extend(t[2] for t in row)

    return chunks


def run_ocr(image_path, image_type, eye):
    reader = get_reader()
    extracted = {}
    try:
        # Determine OCR sources (preprocessed images give better recognition).
        raw_src = image_path
        pre_src = None

        if image_type == "pachymetry":
            try:
                pre_src = _preprocess_pachymetry_for_ocr(image_path)
            except Exception as e:
                print(f"Preprocess OCR failed ({image_type}): {e}")
        elif image_type == "topography":
            try:
                pre_src = _preprocess_topography_for_ocr(image_path)
            except Exception as e:
                print(f"Preprocess OCR failed ({image_type}): {e}")

        # Read with bounding boxes (detail=1) so tokens can be spatially sorted.
        primary_src = pre_src if pre_src is not None else raw_src
        primary_results = reader.readtext(primary_src, detail=1)

        # Pachymetry reports (Zeiss CIRRUS etc.) print OD and OS tables
        # side-by-side. Without column splitting, the spatial sort interleaves
        # both tables row-by-row, making eye section detection unreliable.
        # Split by x-midpoint so each eye's chunks are processed in isolation.
        if image_type == "pachymetry":
            import cv2 as _cv2
            _src_arr = primary_src if isinstance(primary_src, str) else None
            if _src_arr is not None:
                _im = _cv2.imread(_src_arr)
                _img_w = _im.shape[1] if _im is not None else 0
            else:
                # pre_src is a numpy array — get its width directly
                _img_w = primary_src.shape[1] if hasattr(primary_src, 'shape') else 0
            eye_results = _split_ocr_by_column(primary_results, _img_w, (eye or "OD").upper())
            chunks = _spatially_sorted_chunks(eye_results)
        else:
            chunks = _spatially_sorted_chunks(primary_results)

        # For topography also run OCR on the original image and append its text
        # to improve regex coverage, but do NOT mix its chunks into the index-
        # based chunk list (that would double every value and break column logic).
        extra_text = ""
        if image_type == "topography" and pre_src is not None:
            try:
                raw_results = reader.readtext(raw_src, detail=1)
                raw_chunks = _spatially_sorted_chunks(raw_results)
                extra_text = " " + " ".join(raw_chunks)
            except Exception as e:
                print(f"Secondary OCR pass failed: {e}")

        text = " ".join(chunks) + extra_text
        effective_eye = infer_eye_from_text(text, eye)
        safe_preview = text[:250].encode("ascii", errors="ignore").decode("ascii", errors="ignore")
        print(f"[OCR/{image_type}/{eye}->{effective_eye}] {safe_preview}")

        if image_type == "topography":
            cyl_val = _best_corneal_cyl_diopter(_collect_cyl_candidates_from_text(text))
            if cyl_val is None:
                for pat in [
                    r"corneal\s*cyl[^\d-]{0,20}(-?[\d.]+)",
                    r"\bcyl(?:inder)?\b[^\d-]{0,20}(-?[\d.]+)",
                    r"\bcy\b[^\d-]{0,20}(-?[\d.]+)",
                    r"\bca\b[^\d-]{0,20}(-?[\d.]+)",
                ]:
                    raw = extract_value_for_eye(text, pat, effective_eye)
                    if raw is None:
                        continue
                    cyl_val = _normalize_astig_diopters(raw)
                    if cyl_val is not None:
                        break
            if cyl_val is None:
                v = _extract_value_after_exact_label(chunks, ["cyl", "cy", "ca"], lookahead=5)
                cyl_val = _normalize_astig_diopters(v) if v is not None else None
            if cyl_val is not None:
                extracted["astigmatism_diopters"] = cyl_val
                print(f"  Corneal Astigmatism (Cyl)(from CYL)={cyl_val}")

        # Keratometry: (1) separate K1 / K2, then (2) spherical single-K if both still missing.
        sep = _extract_keratometry_separate(text, chunks, effective_eye)
        if sep.get("K1_diopters") is not None:
            extracted["K1_diopters"] = sep["K1_diopters"]
            print(f"  K1(separate)={sep['K1_diopters']}")
        if sep.get("K2_diopters") is not None:
            extracted["K2_diopters"] = sep["K2_diopters"]
            print(f"  K2(separate)={sep['K2_diopters']}")

        if extracted.get("K1_diopters") is None and extracted.get("K2_diopters") is None:
            sph = _extract_keratometry_spherical(text, chunks, effective_eye)
            if sph is not None:
                extracted["K1_diopters"] = sph
                extracted["K2_diopters"] = sph
                print(f"  K1/K2(explicitly spherical)={sph}")

        # Astigmatism (Corneal Cyl) — do not overwrite topography Related Indices CYL.
        if "astigmatism_diopters" not in extracted:
            for pat in [
                r"(?:^|\W)astigmatism[^\d-]{0,30}([-\d.]+)",
                r"(?:^|\W)corneal\s*cyl[^\d-]{0,25}([-\d.]+)",
                r"(?:^|\W)cyl(?:inder)?(?![a-z])[^\d-]{0,25}([-\d.]+)",
                r"(?:^|\W)cy(?![a-z])[^\d-]{0,25}([-\d.]+)",
                r"(?:^|\W)ca(?![a-z])[^\d-]{0,25}([-\d.]+)",
                r"(?:^|\W)delta\s*K[\s:=-]*([-\d.]+)",
            ]:
                v = extract_value_for_eye(text, pat, effective_eye)
                if v:
                    extracted["astigmatism_diopters"] = v
                    print(f"  Corneal Astigmatism (Cyl)={v}")
                    break

        # Normalize K values before deriving/reconciling astigmatism.
        if "K1_diopters" in extracted:
            extracted["K1_diopters"] = _normalize_k_diopters(extracted.get("K1_diopters"))
        if "K2_diopters" in extracted:
            extracted["K2_diopters"] = _normalize_k_diopters(extracted.get("K2_diopters"))
        if extracted.get("K1_diopters") is None:
            extracted.pop("K1_diopters", None)
        if extracted.get("K2_diopters") is None:
            extracted.pop("K2_diopters", None)
        if "astigmatism_diopters" in extracted:
            extracted["astigmatism_diopters"] = _normalize_astig_diopters(extracted.get("astigmatism_diopters"))
        _reconcile_k_values(extracted)

        # Reconcile astig: prefer the derived value from K1/K2 when it looks
        # more consistent than the explicitly OCR'd astig value.
        k1v = extracted.get("K1_diopters")
        k2v = extracted.get("K2_diopters")
        derived_astig = None
        if k1v is not None and k2v is not None:
            # Use absolute difference regardless of OCR ordering (K2 can be < K1).
            derived_astig = round(abs(float(k2v) - float(k1v)), 2)
            if not (0 <= derived_astig <= 10):
                derived_astig = None

        explicit_astig = extracted.get("astigmatism_diopters")
        if derived_astig is not None:
            if explicit_astig is None:
                extracted["astigmatism_diopters"] = derived_astig
                print(f"  Corneal Astigmatism (Cyl)(derived)={derived_astig}")
            else:
                try:
                    explicit_val = float(explicit_astig)
                    # Keep OCR / Related Indices cylinder when it is small and plausible;
                    # |K1−K2| is often wrong when K1 or K2 OCR fails and must not wipe 0.12–2 D cyl.
                    if explicit_val <= 2.0:
                        pass
                    elif abs(explicit_val - derived_astig) > 1.0:
                        extracted["astigmatism_diopters"] = derived_astig
                        print(f"  Corneal Astigmatism (Cyl)(reconciled) OCR={explicit_val} derived={derived_astig}")
                except Exception:
                    pass

        # Corneal thickness only from pachymetry images. Topography OCR often contains
        # unrelated "thickness"/CCT tokens that were overwriting or blocking correct values.
        if image_type == "pachymetry":
            # ── Single-column path (column-split result only has one eye) ──
            # Must run before the dual-column functions which require both eyes.
            if "corneal_thickness_um" not in extracted:
                # Strategy 1: strict label + value (works when OCR reads label cleanly)
                for pat in (
                    r"central\s*corneal\s*thick\w*.{0,50}?(\d{3,4})",
                    r"centr\w*\s+corn\w*\s+thick\w*.{0,50}?(\d{3,4})",
                    r"\bcct\b.{0,20}?(\d{3,4})",
                ):
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        v = _normalize_cct_um(abs(float(m.group(1))))
                        if v and 150 <= v <= 1000:
                            extracted["corneal_thickness_um"] = v
                            print(f"  CCT(single-col-regex)={v}")
                            break

            # Strategy 2: two-anchor approach.
            # OCR often splits "Central Corneal Thickness" across two separate
            # detections. Find both anchors ("Central" and "Corneal Thickness")
            # and extract the value that sits between or immediately after them.
            if "corneal_thickness_um" not in extracted:
                cth_m  = re.search(r"corneal\s*thick", text, re.IGNORECASE)
                cen_m  = re.search(r"\bcentr\w*\b",    text, re.IGNORECASE)
                if cth_m and cen_m:
                    pos_cth = cth_m.start()
                    pos_cen = cen_m.start()
                    _found = None
                    if pos_cen < pos_cth:
                        # "Central" comes before "Corneal Thickness"
                        # → CCT value is AFTER the "Corneal Thickness" label
                        for nm in re.finditer(r"\b(\d{3,4})\b", text[pos_cth:]):
                            v = float(nm.group(1))
                            if 150 <= v <= 1000:
                                _found = v
                                break
                    else:
                        # "Corneal Thickness" comes before "Central"
                        # → CCT value is the LAST valid number before "Central"
                        for nm in re.finditer(r"\b(\d{3,4})\b", text[pos_cth:pos_cen]):
                            v = float(nm.group(1))
                            if 150 <= v <= 1000:
                                _found = v   # keep overwriting → takes the last one
                    if _found is not None:
                        v = _normalize_cct_um(_found)
                        if v and 150 <= v <= 1000:
                            extracted["corneal_thickness_um"] = v
                            print(f"  CCT(two-anchor)={v}")

            if "corneal_thickness_um" not in extracted:
                v = extract_cct_explicit_labeled_eyes(text, effective_eye)
                if v:
                    extracted["corneal_thickness_um"] = v
                    print(f"  CCT(explicit-OD-OS)={v}")
            if "corneal_thickness_um" not in extracted:
                v = extract_cct_from_chunk_eye_pairs(chunks, effective_eye)
                if v:
                    extracted["corneal_thickness_um"] = v
                    print(f"  CCT(chunk OD/OS pair)={v}")

            if "corneal_thickness_um" not in extracted:
                v = extract_value_in_eye_section(
                    text,
                    effective_eye,
                    r"central\s*corneal\s*thickness",
                    min_val=150,
                    max_val=1000,
                )
                if v:
                    extracted["corneal_thickness_um"] = v
                    print(f"  CCT(pachy-eye-section-central)={v}")

            if "corneal_thickness_um" not in extracted:
                v = _extract_cct_from_pachymetry_chunks_v3(chunks, effective_eye)
                if v:
                    extracted["corneal_thickness_um"] = v
                    print(f"  CCT(pachy-chunk-section-fallback)={v}")

            if "corneal_thickness_um" not in extracted:
                cct_dual = extract_two_column_row_value(
                    text,
                    r"central\s*corneal\s*thickness",
                    effective_eye,
                    min_val=150,
                    max_val=1000,
                )
                if cct_dual:
                    extracted["corneal_thickness_um"] = _normalize_cct_um(cct_dual)
                    print(f"  CCT(dual-row)={cct_dual}")

            if "corneal_thickness_um" not in extracted:
                cct_dual_plain = extract_two_column_row_value(
                    text,
                    r"corneal\s*thickness",
                    effective_eye,
                    min_val=150,
                    max_val=1000,
                )
                if cct_dual_plain:
                    extracted["corneal_thickness_um"] = _normalize_cct_um(cct_dual_plain)
                    print(f"  CCT(corneal-thickness-dual-row)={cct_dual_plain}")

            if "corneal_thickness_um" not in extracted:
                cct_row = extract_row_value_from_chunks(chunks, ["corneal", "thickness"], effective_eye)
                cct_row = _normalize_cct_um(cct_row)
                if cct_row and 150 < cct_row < 1000:
                    extracted["corneal_thickness_um"] = cct_row
                    print(f"  CCT(corneal-thickness-row)={cct_row}")

            for pat in [
                r"(?:CCT|central\s*corneal\s*thickness)[\s:=-]*([\d.]+)",
                r"(?:pachymetry|thickness)[\s:=-]*([\d.]+)",
                r"apex[\s:=-]*([\d.]+)",
            ]:
                if "corneal_thickness_um" in extracted:
                    break
                v = extract_value_for_eye(text, pat, effective_eye)
                v = _normalize_cct_um(v)
                if v and 150 < v < 1000:
                    extracted["corneal_thickness_um"] = v
                    print(f"  CCT={v}")
                    break
            if "corneal_thickness_um" not in extracted:
                v = extract_row_value_from_chunks(chunks, ["central", "thickness"], effective_eye)
                v = _normalize_cct_um(v)
                if v and 150 < v < 1000:
                    extracted["corneal_thickness_um"] = v
                    print(f"  CCT(table)={v}")
            if "corneal_thickness_um" not in extracted:
                v = extract_two_column_row_value(
                    text,
                    r"minimum\s*thickness",
                    effective_eye,
                    min_val=150,
                    max_val=1000,
                )
                if v:
                    extracted["corneal_thickness_um"] = _normalize_cct_um(v)
                    print(f"  MinThickness(dual-row-fallback)={v}")
            if "corneal_thickness_um" not in extracted:
                v = extract_row_value_from_chunks(chunks, ["minimum", "thickness"], effective_eye)
                v = _normalize_cct_um(v)
                if v and 150 < v < 1000:
                    extracted["corneal_thickness_um"] = v
                    print(f"  MinThickness(table-fallback)={v}")

            if "corneal_thickness_um" not in extracted:
                for label in [
                    r"central\s*corneal\s*thickness",
                    r"\bcct\b",
                    r"minimum\s*thickness",
                    r"thinnest\s*thickness",
                    r"pachymetry",
                    r"corneal\s*thickness",
                ]:
                    v = extract_value_near_label(text, label, min_val=150, max_val=1000)
                    if v:
                        extracted["corneal_thickness_um"] = _normalize_cct_um(v)
                        print(f"  CCT(label-near)={v}")
                        break

            if "corneal_thickness_um" not in extracted:
                v = _extract_pachy_from_chunks(chunks, effective_eye)
                if v:
                    extracted["corneal_thickness_um"] = v
                    print(f"  CCT(pachy-chunk-fallback)={v}")

            if "corneal_thickness_um" not in extracted:
                v = extract_first_cct_in_eye_section(text, effective_eye)
                if v:
                    extracted["corneal_thickness_um"] = v
                    print(f"  CCT(eye-section-first)={v}")
    except Exception as e:
        print(f"OCR error: {e}")
    return extracted
 
@app.route("/api/extract", methods=["POST"])
def extract():
    eye = request.form.get("eye", "OD").upper()
    extracted, temps = {}, []
    try:
        for img_key, img_type in [("topography","topography"), ("pachymetry","pachymetry")]:
            if img_key in request.files:
                f = request.files[img_key]
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(f.filename)[1] or ".jpg")
                tmp_path = tmp.name
                tmp.close()  # Required on Windows before saving/opening the file again.
                f.save(tmp_path); temps.append(tmp_path)
                part = run_ocr(tmp_path, img_type, eye)

                # Merge with source priority:
                # - topography owns K values + astigmatism
                # - pachymetry owns corneal thickness
                if img_type == "topography":
                    for key in ["K1_diopters", "K2_diopters", "astigmatism_diopters"]:
                        if key in part and part[key] is not None:
                            extracted[key] = part[key]
                    if "corneal_thickness_um" in part and part["corneal_thickness_um"] is not None and "corneal_thickness_um" not in extracted:
                        extracted["corneal_thickness_um"] = part["corneal_thickness_um"]
                else:  # pachymetry
                    if "corneal_thickness_um" in part and part["corneal_thickness_um"] is not None:
                        extracted["corneal_thickness_um"] = part["corneal_thickness_um"]
                    for key in ["K1_diopters", "K2_diopters", "astigmatism_diopters"]:
                        if key in part and part[key] is not None and key not in extracted:
                            extracted[key] = part[key]
        if (
            extracted.get("K2_diopters") is None
            and extracted.get("K1_diopters") is not None
            and extracted.get("astigmatism_diopters") is not None
        ):
            extracted["K2_diopters"] = calculate_k2(extracted["K1_diopters"], extracted["astigmatism_diopters"])
        return jsonify({"extracted": extracted, "eye": eye})
    except Exception as e:
        return jsonify({"error": str(e), "extracted": {}}), 500
    finally:
        for p in temps:
            if os.path.exists(p):
                try:
                    os.unlink(p)
                except PermissionError:
                    pass
 
@app.route("/api/predict", methods=["POST"])
def predict():
    data = request.get_json()
    if not data: return jsonify({"error": "No data"}), 400
    try:
        if data.get("K2_diopters") is None:
            data["K2_diopters"] = calculate_k2(data.get("K1_diopters"), data.get("astigmatism_diopters"))
        row     = pd.DataFrame([{f: data.get(f, np.nan) for f in FEATURES}])
        row_imp = IMPUTER.transform(row)
        row_sc  = SCALER.transform(row_imp)
        idx     = MODEL.predict(row_sc)[0]
        probs   = MODEL.predict_proba(row_sc)[0]
        label   = LE.inverse_transform([idx])[0]
        return jsonify({
            "prediction"   : label,
            "confidence"   : round(float(max(probs))*100, 1),
            "probabilities": {c: round(float(p)*100,1) for c,p in zip(LE.classes_, probs)}
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
 
@app.route("/api/health")
def health():
    return jsonify({"status":"ok","features":FEATURES,"classes":list(LE.classes_)})

@app.route("/api/debug", methods=["POST"])
def debug():
    """Temporary route — shows raw OCR text from uploaded images"""
    eye    = request.form.get("eye", "OD").upper()
    reader = get_reader()
    result = {}
    for img_key in ["topography", "pachymetry"]:
        if img_key in request.files:
            f   = request.files[img_key]
            tmp = tempfile.NamedTemporaryFile(
                delete=False, suffix=os.path.splitext(f.filename)[1] or ".jpg"
            )
            tmp_path = tmp.name
            tmp.close()
            f.save(tmp_path)
            try:
                chunks = reader.readtext(tmp_path, detail=0)
                result[img_key] = {
                    "full_text": " ".join(chunks),
                    "chunks"   : chunks          # each item OCR read separately
                }
            finally:
                try: os.unlink(tmp_path)
                except: pass
    return jsonify(result)
 
if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5001)