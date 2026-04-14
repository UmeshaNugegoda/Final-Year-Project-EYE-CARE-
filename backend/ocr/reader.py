"""
EasyOCR reader singleton and main run_ocr orchestration function.
"""
import re

from .preprocessing import _preprocess_pachymetry_for_ocr, _preprocess_topography_for_ocr
from .utils import (
    infer_eye_from_text,
    _normalize_k_diopters,
    _normalize_astig_diopters,
    _normalize_cct_um,
    _split_ocr_by_column,
    _spatially_sorted_chunks,
    _extract_value_after_exact_label,
    extract_value_for_eye,
    extract_first_cct_in_eye_section,
    extract_row_value_from_chunks,
    extract_two_column_row_value,
    extract_value_near_label,
    extract_value_in_eye_section,
)
from .keratometry import (
    _extract_keratometry_separate,
    _extract_keratometry_spherical,
    _collect_cyl_candidates_from_text,
    _best_corneal_cyl_diopter,
    _reconcile_k_values,
)
from .cct import (
    _extract_cct_from_pachymetry_chunks_v3,
    extract_cct_explicit_labeled_eyes,
    extract_cct_from_chunk_eye_pairs,
    _extract_pachy_from_chunks,
)

# ── EasyOCR singleton ─────────────────────────────────────────────────────────

_reader = None


def get_reader():
    global _reader
    if _reader is None:
        import easyocr
        print("Loading EasyOCR...")
        _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _reader


# ── Main OCR function ─────────────────────────────────────────────────────────

def run_ocr(image_path, image_type, eye):
    reader = get_reader()
    extracted = {}
    try:
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

        primary_src = pre_src if pre_src is not None else raw_src
        primary_results = reader.readtext(primary_src, detail=1)

        # Pachymetry reports (Zeiss CIRRUS etc.) print OD and OS tables
        # side-by-side. Without column splitting, the spatial sort interleaves
        # both tables row-by-row, making eye section detection unreliable.
        if image_type == "pachymetry":
            import cv2 as _cv2
            _src_arr = primary_src if isinstance(primary_src, str) else None
            if _src_arr is not None:
                _im = _cv2.imread(_src_arr)
                _img_w = _im.shape[1] if _im is not None else 0
            else:
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

        k1v = extracted.get("K1_diopters")
        k2v = extracted.get("K2_diopters")
        derived_astig = None
        if k1v is not None and k2v is not None:
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
                    if explicit_val <= 2.0:
                        pass
                    elif abs(explicit_val - derived_astig) > 1.0:
                        extracted["astigmatism_diopters"] = derived_astig
                        print(f"  Corneal Astigmatism (Cyl)(reconciled) OCR={explicit_val} derived={derived_astig}")
                except Exception:
                    pass

        # Corneal thickness only from pachymetry images.
        if image_type == "pachymetry":
            if "corneal_thickness_um" not in extracted:
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

            if "corneal_thickness_um" not in extracted:
                cth_m  = re.search(r"corneal\s*thick", text, re.IGNORECASE)
                cen_m  = re.search(r"\bcentr\w*\b",    text, re.IGNORECASE)
                if cth_m and cen_m:
                    pos_cth = cth_m.start()
                    pos_cen = cen_m.start()
                    _found = None
                    if pos_cen < pos_cth:
                        for nm in re.finditer(r"\b(\d{3,4})\b", text[pos_cth:]):
                            v = float(nm.group(1))
                            if 150 <= v <= 1000:
                                _found = v
                                break
                    else:
                        for nm in re.finditer(r"\b(\d{3,4})\b", text[pos_cth:pos_cen]):
                            v = float(nm.group(1))
                            if 150 <= v <= 1000:
                                _found = v
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
