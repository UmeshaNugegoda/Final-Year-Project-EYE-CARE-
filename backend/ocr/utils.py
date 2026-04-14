"""
OCR text-parsing utilities.

Normalization helpers, eye-section scoping, spatial chunk sorting,
and generic value-extraction primitives used by keratometry.py, cct.py,
and reader.py.
"""
import re
import math


# ── Eye-column regex (used by _assign_od_os_thickness_pair) ──────────────────
_EYE_COL_RE = re.compile(
    r"(?:(?:^|\W)(OD|OS|O\.?\s*D\.?|O\.?\s*S\.?)(?:\W|$)|Right\s*Eye|Left\s*Eye)",
    re.I,
)


# ── Basic helpers ─────────────────────────────────────────────────────────────

def calculate_k2(k1, astig):
    if k1 is None or astig is None:
        return None
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

    for m in re.finditer(r"(-?\d+(?:\.\d+)?)", section):
        try:
            v = abs(float(m.group(1)))
        except Exception:
            continue
        if v < 20:
            v *= 1000
        if 150 <= v <= 1000:
            return v
    return None


# ── Normalization helpers ─────────────────────────────────────────────────────

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
        return None
    if len(candidates) == 1:
        return round(candidates[0], 2)
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
    if v < 0.5:
        return round(v, 2)
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
    if v < 20:
        v *= 1000
    return v


def _normalize_token(s):
    return re.sub(r"[^a-z0-9]+", "", _norm(s))


# ── Chunk-index helpers ───────────────────────────────────────────────────────

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


# ── Eye-column assignment ─────────────────────────────────────────────────────

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


# ── Spatial / column sorting ──────────────────────────────────────────────────

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
    predictable top-to-bottom, left-to-right reading order.
    """
    if not ocr_results:
        return []

    annotated = []
    for bbox, text, _conf in ocr_results:
        token = str(text).strip()
        if not token:
            continue
        y_center = (bbox[0][1] + bbox[2][1]) / 2
        x_center = (bbox[0][0] + bbox[2][0]) / 2
        annotated.append((y_center, x_center, token))

    annotated.sort(key=lambda t: t[0])
    rows = []
    for item in annotated:
        y = item[0]
        if rows and abs(y - rows[-1][-1][0]) <= row_tolerance:
            rows[-1].append(item)
        else:
            rows.append([item])

    chunks = []
    for row in rows:
        row.sort(key=lambda t: t[1])
        chunks.extend(t[2] for t in row)

    return chunks


# ── Generic value-extraction from text/chunks ─────────────────────────────────

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

    After _split_ocr_by_column the chunks may already be filtered to a
    single eye, so a bilateral row now has only one value cell instead of
    two. We pick by eye_idx when two cells exist and fall back to the
    single cell otherwise.
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
                if re.search(r"\d", raw) or re.fullmatch(r"[-_–—\s]+", raw):
                    cells.append(raw)
                if len(cells) >= 2:
                    break
            if len(cells) == 2:
                return _cell_to_number(cells[eye_idx])
            elif len(cells) == 1:
                return _cell_to_number(cells[0])
    return None


def extract_two_column_row_value(text, row_label_regex, eye, min_val=None, max_val=None):
    """
    Extract a row that contains OD and OS values in sequence, e.g.:
    'Central Corneal Thickness 424 um 566 um'
    and return value based on selected eye.

    Column order is not standardized (OS-left / OD-right is common); we infer
    OD vs OS from header tokens or from labels immediately before each number.
    """
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
    m = re.search(rf"{label_regex}.{{0,100}}?([-\d.]+)", text, re.IGNORECASE)
    if not m:
        return None
    try:
        v = abs(float(m.group(1)))
        if min_val is not None and max_val is not None and max_val > 200 and v < 20:
            v *= 1000
        if min_val is not None and v < min_val:
            return None
        if max_val is not None and v > max_val:
            return None
        return v
    except Exception:
        return None
