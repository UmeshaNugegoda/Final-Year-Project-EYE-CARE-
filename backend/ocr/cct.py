"""
Central Corneal Thickness (CCT) extraction from OCR text.

Handles pachymetry chunk streams, explicit OD/OS-labeled rows,
bilateral table layouts, and fallback heuristics for noisy OCR output.
"""
import re

from .utils import (
    _norm,
    _normalize_token,
    _looks_like_row_label,
    _normalize_cct_um,
    _cell_to_number,
)


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

    start_pat = "pach"  # catches "Pachymatry", "Pachymetry", etc.
    if eye == "OD":
        start_idx = next((i for i, t in enumerate(lower) if start_pat in t and "od" in t), None)
        other_eye_idx = next((i for i, t in enumerate(lower) if start_pat in t and "os" in t), None)
    else:
        start_idx = next((i for i, t in enumerate(lower) if start_pat in t and "os" in t), None)
        other_eye_idx = next((i for i, t in enumerate(lower) if start_pat in t and "od" in t), None)

    if start_idx is None:
        return None

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

        if has_central and has_thickness:
            for j in range(i + 1, min(i + 8, len(section_chunks))):
                v = _first_number_in(section_chunks[j])
                if v is not None and 150 <= v <= 1000:
                    return v

        if has_central and not has_thickness:
            window = section_lower[i:min(i + 5, len(section_lower))]
            if any(tm in " ".join(window) for tm in thickness_like_markers):
                for j in range(i + 1, min(i + 8, len(section_chunks))):
                    v = _first_number_in(section_chunks[j])
                    if v is not None and 150 <= v <= 1000:
                        return v

    return None


def extract_cct_explicit_labeled_eyes(text, eye, min_val=150, max_val=1000):
    """
    Prefer values bound to explicit OD/OS tokens after a CCT label (most reliable).
    """
    if not text:
        return None
    eye_u = (eye or "OD").upper()
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


def _extract_pachy_from_chunks(chunks, eye):
    """
    Robust pachymetry fallback for noisy OCR chunk streams.
    Looks for thickness-related labels (including common OCR misspellings),
    then picks OD/OS or nearest plausible thickness value.

    After _split_ocr_by_column the chunk list is already filtered to a
    single eye, so a row that previously had two cells (OD | OS) now has
    only one. We handle both cases:
      - two cells  → use eye_idx to pick the correct column (bilateral report)
      - one cell   → take it directly (chunks were pre-filtered to one eye)
    """
    if not chunks:
        return None

    normalized = [_norm(c) for c in chunks]
    eye_idx = 0 if eye == "OD" else 1
    label_markers = ("thick", "pach", "cct", "thinn", "minim")

    for i, token in enumerate(normalized):
        token_compact = _normalize_token(token)
        if not any(m in token_compact for m in label_markers):
            continue

        cells = []
        for j in range(i + 1, min(i + 14, len(chunks))):
            raw = str(chunks[j]).strip()
            if not raw:
                continue
            if re.search(r"\d", raw) or re.fullmatch(r"[-_–—\s]+", raw):
                cells.append(raw)
            if len(cells) >= 2:
                break
        if len(cells) == 2:
            v = _normalize_cct_um(_cell_to_number(cells[eye_idx]))
            if v and 150 <= v <= 1000:
                return v
        elif len(cells) == 1:
            v = _normalize_cct_um(_cell_to_number(cells[0]))
            if v and 150 <= v <= 1000:
                return v

        for j in range(i + 1, min(i + 18, len(chunks))):
            v = _normalize_cct_um(_cell_to_number(chunks[j]))
            if v and 150 <= v <= 1000:
                return v
    return None
