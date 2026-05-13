"""
Keratometry (K-value) extraction from OCR text.

Handles K1 (flat), K2 (steep), Sim K pairs, Ks/Kf labels, spherical K,
and corneal cylinder (CYL / CA) for topography reports.
"""
import re
import statistics

from .utils import (
    _normalize_k_diopters,
    _normalize_astig_diopters,
    _extract_value_after_exact_k_label,
    _extract_value_after_exact_label,
    extract_row_value_from_chunks,
)


# ── Eye-scope helpers ─────────────────────────────────────────────────────────

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


# ── Sim K pair ────────────────────────────────────────────────────────────────

def _extract_sim_k_flat_steep_pair(text, eye):
    """
    Sim K flat X steep Y (or steep then flat) on one line — most reliable K1/K2 pair.
    Returns (K1_flatter, K2_steeper) after normalizing each diopter read.
    """
    pair_patterns = (
        r"sim(?:ulated)?\s*k\s*[^\d]{0,40}?flat[^\d]{0,25}([-\d.]+)[^\d]{0,55}?steep[^\d]{0,25}([-\d.]+)",
        r"sim(?:ulated)?\s*k\s*[^\d]{0,40}?steep[^\d]{0,25}([-\d.]+)[^\d]{0,55}?flat[^\d]{0,25}([-\d.]+)",
        # Tomey RT-7000 "Sim K's" compact two-row format (no flat/steep labels):
        # e.g. "Sim K's 47.24 (2.77) 0.68 529 43.45 (Z.14) 0.70 278"
        # K2 steep is the first value, K1 flat is the second.
        # The k1,k2 = min,max swap below handles ordering automatically.
        r"sim\s*k(?:'?s)?\s+([\d.]+)\s*\([^)]{1,12}\)[\s\S]{0,50}?([\d.]+)\s*\([^)]{1,12}\)",
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
            k1, k2 = (a, b) if a <= b else (b, a)
            if 30 <= k1 <= 65 and 30 <= k2 <= 65:
                return k1, k2
    return None, None


# ── Tomey RT-7000 chunk-based extractor ──────────────────────────────────────

def _extract_sim_k_from_chunks(chunks):
    """
    Tomey RT-7000 chunk-based extraction for the "Sim K's" section.

    Two-pass approach:

    Pass 1 — MM validation (handles comparison views where both eyes' data
    is spatially interleaved after sorting):
      Each K value in diopters is printed alongside its radius of curvature in mm.
      The relationship is K_D × R_mm ≈ 337.5. By finding parenthesised mm values
      "(7.28)" and pairing them with K candidates that satisfy this equation, we
      identify the true K readings and reject color-scale and refraction values.

    Pass 2 — Forward scan fallback (handles single-eye or images where mm values
    are OCR-corrupted, e.g. "(7.14)" read as "(Z.14)"):
      Scans forward from the first "Sim K's" label for the first two direct
      K-range values (30–65 D), skipping parenthesised tokens.

    Returns (K1_flat, K2_steep) or (None, None).
    """
    # Locate all "Sim K's" label positions.
    # Use [\W]? to handle both ASCII and Unicode apostrophes returned by OCR.
    sim_k_positions = [
        i for i, c in enumerate(chunks)
        if re.match(r"sim\s*k(?:[\W]?s)?\s*$", c.strip(), re.IGNORECASE)
    ]
    if not sim_k_positions:
        return None, None

    first_pos = sim_k_positions[0]
    last_pos  = sim_k_positions[-1]

    # Wide window covering all Sim K's positions + surrounding context
    win_start = max(0, first_pos - 25)
    win_end   = min(len(chunks), last_pos + 25)
    window    = chunks[win_start : win_end]

    # ── Pass 1: mm-validated K extraction ────────────────────────────────────
    k_candidates  = []  # direct 30-65 D values
    mm_candidates = []  # parenthesised radius values 5.0-9.5 mm

    for c in window:
        clean = re.sub(r'(\d+),\.(\d+)', r'\1.\2', c.strip())  # fix "51,.36"
        if clean.startswith('('):
            # Parenthesised token — only valid as a mm candidate
            m = re.match(r'^\(?([\d.]+)\)?$', clean)
            if m:
                try:
                    mv = float(m.group(1))
                    if 5.0 <= mv <= 9.5:
                        mm_candidates.append(round(mv, 3))
                except ValueError:
                    pass
            continue  # never treat a parenthesised token as a K-diopter value
        # Require a plain decimal number — rejects annotated values like "52.83D"
        # (Central K in diopters) while accepting "47.24" or "51.36" (after comma fix)
        if not re.match(r'^-?[\d]+\.[\d]+$', clean):
            continue
        try:
            v = float(clean)
        except ValueError:
            continue
        if 30.0 <= v <= 65.0:
            k_candidates.append(round(v, 2))

    if mm_candidates:
        validated_k = []
        for k_D in k_candidates:
            expected_mm = 337.5 / k_D
            for mm_val in mm_candidates:
                if abs(mm_val - expected_mm) < 0.15:   # strict < to exclude boundary
                    if k_D not in validated_k:
                        validated_k.append(k_D)
                    break
        if len(validated_k) >= 2:
            k1, k2 = min(validated_k), max(validated_k)
            if 0 < (k2 - k1) <= 20:
                return k1, k2

    # ── Pass 2: forward scan from first "Sim K's" ────────────────────────────
    k_vals = []
    for c in chunks[first_pos + 1 : first_pos + 30]:
        clean = re.sub(r'(\d+),\.(\d+)', r'\1.\2', c.strip())
        if clean.startswith('('):
            continue
        num_str = re.sub(r'[^\d.]', '', clean)
        if not num_str or '.' not in num_str:
            continue
        try:
            v = float(num_str)
        except ValueError:
            continue
        if 30.0 <= v <= 65.0:
            k_vals.append(round(v, 2))
            if len(k_vals) == 2:
                break

    if len(k_vals) >= 2:
        k1, k2 = min(k_vals), max(k_vals)
        if 0 < (k2 - k1) <= 20:
            return k1, k2

    return None, None


def _extract_ret7000_comparison_simk(text, eye):
    """
    Fallback for comparison-style RET-700 reports that print:
    "Right Center ... Sim K's ..." and "Left Center ... Sim K's ...".

    We keep this isolated as an additive parser so existing extraction logic is
    unchanged for all currently supported formats.
    """
    if not text:
        return None, None

    eye_header = "right" if (eye or "OD").upper() == "OD" else "left"
    section_re = re.compile(
        rf"{eye_header}\s*center[\s\S]{{0,800}}?sim\s*k(?:[\W]?s)?([\s\S]{{0,300}}?)(?:kisa%|geometric\s*values|ref\s*\(vd=0\)|other|$)",
        re.IGNORECASE,
    )
    m = section_re.search(text)
    if not m:
        return None, None

    section = m.group(1)
    # Capture two-decimal values and keep clinically plausible keratometry only.
    vals = []
    for n in re.finditer(r"(?<!\d)(\d{2}\.\d{2})(?!\d)", section):
        try:
            fv = float(n.group(1))
        except ValueError:
            continue
        if 30.0 <= fv <= 65.0 and fv not in vals:
            vals.append(round(fv, 2))
        if len(vals) >= 2:
            break

    if len(vals) < 2:
        return None, None
    k1, k2 = min(vals), max(vals)
    if 0 < (k2 - k1) <= 20:
        return k1, k2
    return None, None


# ── Ks / Kf label extraction ──────────────────────────────────────────────────

def extract_ks_kf(text, chunks, eye):
    """
    Prefer topography-specific labels:
    - Ks / K steep -> K2
    - Kf / K flat  -> K1
    """
    out = {}

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
        r"(?:^|\W)k\s*f(?![a-z])[^\d-]{0,25}([-\d.]+)",
        r"(?:^|\W)k\s*1(?![a-z])[^\d-]{0,25}([-\d.]+)",
        r"(?:^|\W)k\s*flat(?![a-z])[^\d-]{0,25}([-\d.]+)",
        r"(?:^|\W)s\s*k\s*2(?![a-z])[^\d-]{0,25}([-\d.]+)",   # Tomey SK2 = flat K = K1
        r"(?:^|\W)[8s]\s*k\s*[2z](?![a-z])[^\d-]{0,25}([-\d.]+)",
        r"(?:^|\W)min\s*k(?![a-z])[^\d-]{0,25}([-\d.]+)",       # MinK is last-resort fallback
    ]:
        raw = _search_k_pattern_scoped(text, eye, pat)
        v = _normalize_k_diopters(raw)
        if v is not None:
            out["K1_diopters"] = v
            break

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


# ── Separate K1 / K2 extraction ───────────────────────────────────────────────

def _extract_keratometry_separate(text, chunks, eye):
    """
    K1 and K2 from distinct report fields (Kf/Ks, K1 flat, K2 steep, table columns).
    Never sets K1 == K2 unless the source only provides one distinct value.

    Order: Sim K pair (same line) → OD/OS table rows → Ks/Kf labels → scoped regex.
    """
    out = {}

    # Dedicated fallback for RET-700 comparison print layout (Right/Left Center).
    rk1, rk2 = _extract_ret7000_comparison_simk(text, eye)
    if rk1 is not None and rk2 is not None:
        out["K1_diopters"] = rk1
        out["K2_diopters"] = rk2
        return out

    # Tomey RT-7000 chunk-based extraction (handles "Sim K's" label-free format)
    ck1, ck2 = _extract_sim_k_from_chunks(chunks)
    if ck1 is not None and ck2 is not None:
        out["K1_diopters"] = ck1
        out["K2_diopters"] = ck2
        return out

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
            r"(?:^|\W)k\s*f(?![a-z])[^\d-]{0,25}([-\d.]+)",
            r"(?:^|\W)K\s*flat(?![a-z])[^\d-]{0,25}([-\d.]+)",
            r"(?:^|\W)s\s*k\s*2(?![a-z])[^\d-]{0,25}([-\d.]+)",   # Tomey SK2 = flat K = K1
            r"(?:^|\W)[8s]\s*k\s*[2z](?![a-z])[^\d-]{0,25}([-\d.]+)",
            r"(?:^|\W)min\s*k(?![a-z])[^\d-]{0,25}([-\d.]+)",       # MinK is last-resort fallback
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


# ── Spherical K extraction ────────────────────────────────────────────────────

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


# ── Corneal cylinder (CYL / CA) ───────────────────────────────────────────────

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
    small = [x for x in normed if x <= 5]
    return min(small if small else normed, key=lambda x: abs(x - 0.5))


# ── K-value reconciliation ────────────────────────────────────────────────────

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
