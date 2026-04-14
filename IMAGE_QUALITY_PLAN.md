# Image Quality Handling — Implementation Plan

## Problem Statement

The OCR extraction pipeline works correctly on clean digital exports (validated with Tomey RT-7000 clean PNG, extracting K1/K2/CYL with exact match). However, real-world clinic images introduce problems the current preprocessing cannot fully solve:

| Problem | Root cause |
|---|---|
| Blurry images | Photos taken with a phone rather than digital export |
| Hole-punched pages | Filing holes appear as `O`, `0`, `C` to OCR, shifting column positions |
| Content cut off at edges | Report not fully in frame when photographed |
| Angled / perspective distortion | Camera not held parallel to the printout |
| Low resolution | Phone camera in low-light or distance |

**The goal is not to block bad images — it is to detect every problem, fix it automatically where possible, and tell the clinician exactly what went wrong so they can act on it. The prediction always runs.**

---

## What the system already does

- `_is_blurry()` — Laplacian variance detects blur and switches to a bilateral filter soft path
- `_deskew()` — corrects rotations up to 15°
- `_sharpen()` — unsharp mask after preprocessing
- `_pad_image()` — adds white border to avoid edge clipping
- CLAHE — adaptive contrast enhancement
- 2.5× upscaling — improves OCR on low-resolution inputs
- HSV colour masking — extracts red/green text on Tomey reports
- `_split_ocr_by_column()` — prevents OD/OS value mixing on side-by-side Zeiss reports
- `_reconcile_k_values()` — ensures K1 < K2 regardless of machine naming convention
- CCT manual fallback field — clinician can enter CCT manually if OCR fails

---

## What is missing

1. No warnings surfaced to the user — failures are silent
2. No hole-punch detection or masking
3. No instant feedback on upload — quality check only happens after full OCR is triggered
4. K1, K2, CYL have no manual override (only CCT does)
5. Result panel does not indicate which values were extracted vs estimated by the model imputer

---

## Proposed Solution — Three Phases

---

### Phase 1 — Instant Image Quality Check on Upload

**When:** Immediately after the clinician selects an image file, before OCR runs.  
**How:** The frontend POSTs the image to a new lightweight endpoint `/api/analyze-quality`.  
**Speed:** Sub-second — computer vision only, no EasyOCR.  
**Result:** Warnings appear on the upload card so the clinician can retake the photo before filling out the rest of the form.

#### Checks performed

| Check | Detection method | Auto-fix | Warning shown |
|---|---|---|---|
| Blur | Laplacian variance < 80 | Bilateral filter (already done in OCR pipeline) | `"Image appears blurry — extracted values may be inaccurate"` |
| Low resolution | Width or height < 800 px | 2.5× upscaling (already done) | `"Image resolution is low — higher quality gives better OCR results"` |
| Hole-punch marks | OpenCV circular contour filter (radius 20–120 px) | **Fill holes white before OCR** (new fix) | `"Punch-hole marks detected and masked — check extracted values near the left margin"` |
| Severe angle | Skew angle from deskew exceeds 10° | Correction up to 15° (already done) | `"Image appears angled — photograph straight overhead for best results"` |
| Edge clipping risk | Content within 30 px of border after padding | Padding (already done) | `"Content may be cut off at the image edge — ensure the full page is visible"` |

#### UI on upload card after quality check

```
┌──────────────────────────────────────────────────────┐
│  Topography Report                [uploads K1/K2]   │
│                                                      │
│  [image preview]                         [Remove]   │
│                                                      │
│  ⚠  Image appears blurry                            │
│  ⚠  Punch-hole marks detected — masked before scan  │
│                                                      │
│  Warnings do not block submission. Verify results.  │
└──────────────────────────────────────────────────────┘
```

Warnings are **advisory**, not blocking. The clinician can still submit.

#### Files changed

| File | Change |
|---|---|
| `backend/app.py` | Add `_analyze_image_quality()` function + `/api/analyze-quality` Flask route |
| `backend/app.py` | Add hole-masking step inside `_preprocess_topography_for_ocr` and `_preprocess_pachymetry_for_ocr` |
| `backend/src/server.js` | Add `POST /api/analyze-quality` proxy route (same pattern as `/api/extract`) |
| `Frontend/src/components/ImageUpload/ImageUpload.jsx` | Call `/api/analyze-quality` on file select; show warnings on card |
| `Frontend/src/components/ImageUpload/ImageUpload.css` | Styles for warning banners, spinner |

---

### Phase 2 — Per-field Extraction Status in Results

**When:** After OCR runs and the prediction is returned.  
**What:** Each extracted value is tagged so the clinician knows whether it came from the image, from a manual override, or was estimated by the model's imputer.

#### Status badges

| Badge | Meaning |
|---|---|
| ✅ Extracted | Value was read successfully from the uploaded image |
| ⚠ Manual override | Clinician entered this value manually in the fallback field |
| 🔶 Not found — estimated | OCR could not extract this value; model used an imputed estimate |

#### UI in result panel

```
VALUES EXTRACTED FROM REPORT IMAGES

K1 DIOPTERS         K2 DIOPTERS          CYL
42.18 D  ✅         44.21 D  ✅          2.03 D  ✅

CORNEAL THICKNESS
—   🔶  Not extracted — model used an estimated value
        Enter manually below if you have this measurement
```

The extraction status also appears in the **PDF export** so printed reports carry the same transparency.

#### Files changed

| File | Change |
|---|---|
| `backend/app.py` | Return `extraction_status` dict alongside `extracted` from `/api/extract` |
| `backend/src/server.js` | Pass `extractionStatus` through in `/api/predictions` response |
| `Frontend/src/components/ResultPanel/ResultPanel.jsx` | Render status badge next to each extracted value |
| `Frontend/src/components/ResultPanel/ResultPanel.css` | Styles for status badges |

---

### Phase 3 — Manual Override Fields for K1, K2, CYL

**What:** Add optional override fields for K1, K2, and Corneal Astigmatism (CYL) — the same pattern as the existing CCT fallback field.  
**Why:** If OCR returns a wrong value (e.g., 42.10 instead of 42.18 for K1), the clinician can correct it without needing to re-upload or re-run.

#### UI in form (Topography & Pachymetry Values section)

```
 AUTO  K1/Kf, K2/Ks, Cyl, CCT are extracted automatically from the uploaded images...

 ┌─────────────────────────────────────────────────────────────┐
 │  K1 Override (D)           K2 Override (D)    Cyl Override  │
 │  Optional – only if         Optional          Optional      │
 │  OCR is incorrect                                           │
 │  [ _______ ]               [ _______ ]        [ _______ ]  │
 └─────────────────────────────────────────────────────────────┘
 ┌─────────────────────────────────────────────────────────────┐
 │  Central Corneal Thickness Fallback (µm)                    │
 │  Optional, only if OCR fails (e.g. 424 or 566)             │
 │  [ _______ ]                                                │
 └─────────────────────────────────────────────────────────────┘
```

#### Files changed

| File | Change |
|---|---|
| `Frontend/src/components/NumericInputs/NumericInputs.jsx` | Add K1/K2/CYL override input fields |
| `Frontend/src/pages/Prediction/Prediction.jsx` | Add `k1Override`, `k2Override`, `cylOverride` to form state; append to FormData |
| `backend/src/server.js` | Read overrides from request; prefer them over OCR values if present |

---

## Phased delivery order

```
Phase 1 (highest impact)
  └── /api/analyze-quality endpoint (Flask + Node proxy)
  └── Hole-masking in preprocessing
  └── Upload card warnings (React)

Phase 2
  └── extraction_status in /api/extract response
  └── Status badges in ResultPanel

Phase 3
  └── K1/K2/CYL override fields in form
  └── Override handling in server.js
```

Each phase is independently deployable and testable.

---

## Testing plan

### With existing test images

| Image | Expected quality warnings | Expected extraction |
|---|---|---|
| `tomey_topography_od_clean.png` | None | K1 ✅, K2 ✅, CYL ✅ |
| `tomey_topography_os_degraded.png` | Blur warning | K1/K2/CYL — may be partial |
| `zeiss_pachymetry_clean.png` | None | CCT ✅ |
| `zeiss_pachymetry_degraded.png` | Blur warning | CCT — may show 🔶 |

### Manual test steps

1. Upload degraded image → confirm warning appears on upload card immediately
2. Submit prediction → confirm 🔶 badge on any unextracted value in result
3. Enter K1 override → resubmit → confirm override value used in result
4. Export PDF → confirm status badges present in printed report
5. Upload clean image → confirm no warnings, all values show ✅

---

## Supervisor summary

> The system now handles poor-quality report images at every stage:
>
> 1. **Detects** — blur, low resolution, hole-punch marks, angle distortion, and edge clipping are all checked on upload
> 2. **Fixes automatically** — hole masking, deskew, bilateral filtering, CLAHE, and upscaling are all applied before OCR runs
> 3. **Warns specifically** — the clinician sees exactly which problems were found, with targeted advice, before they submit
> 4. **Always predicts** — the model runs regardless of image quality, using imputed estimates for any values that could not be extracted
> 5. **Shows transparency** — every value in the result is tagged as extracted, estimated, or manually overridden
> 6. **Allows correction** — manual override fields for all OCR-extracted values mean a bad scan never permanently corrupts a prediction
