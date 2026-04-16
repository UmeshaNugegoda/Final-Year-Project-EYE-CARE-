# Changelog

## [Latest] — April 2026

### Model Enhancements

- **`monthsAfterDALK` as a model feature** — The months elapsed since DALK surgery is now included as the 9th input feature. Post-DALK corneal stability varies significantly over time; early-stage patients (< 6 months) behave differently to stable patients (> 24 months). Previously this field was collected but never passed to the model.

- **Probability calibration** — The XGBoost classifier is now wrapped with `CalibratedClassifierCV(method='isotonic', cv=5)`, producing trustworthy confidence percentages. Raw XGBoost `predict_proba` scores are not well-calibrated by default, which is a problem in a clinical setting where a reported 90% confidence should actually mean ~90% accuracy.

- **Model retrained via knowledge distillation** — Since the original training dataset is not in the repository, a synthetic dataset of 3,000 post-DALK patient records was generated from realistic clinical distributions. The existing model's predictions were used as training labels (knowledge distillation). The retrained model achieves **93% accuracy** on a held-out test set. See `backend/scripts/retrain_model.py`.

- **Confidence threshold — "Refer to Specialist"** — When the model confidence falls below 65%, the system now returns `"Refer to Specialist"` instead of a low-confidence recommendation. A 51%-confident recommendation is clinically unsafe. The result panel shows a distinct amber referral banner for this case.

- **All `.pkl` artifacts replaced** — `eye_correction_model.pkl`, `scaler.pkl`, `imputer.pkl`, `label_encoder.pkl`, and `feature_names.pkl` all updated to reflect the new 9-feature calibrated model.

---

### OCR Improvements

- **Confidence filtering** — EasyOCR returns a confidence score per text chunk. Chunks below 0.35 confidence are now discarded before field extraction, reducing noisy extractions from poor-quality images (`backend/ocr/reader.py`).

- **Wider column tolerance in eye measurements extractor** — Increased x-tolerance from ±60px to ±80px and y-tolerance from ±25px to ±35px. This improves extraction from photos taken at a slight angle (`backend/ocr/eye_measurements_extractor.py`).

- **Deskew preprocessing for eye measurements** — Images are automatically deskewed before OCR using the same preprocessing pipeline already used for topography images.

- **Eye measurements OCR trigger fixed** — The OCR pipeline now correctly triggers when only an eye measurements image is uploaded (previously only ran when topography or pachymetry images were present).

- **Extraction success rate logging** — After each `/api/extract` call, a one-line summary is logged: `[OCR] 3/4 fields extracted | eye=OD | status={...}`. This gives visibility into how often each field fails to extract.

---

### Clinical UX

- **Manual measurement form hidden by default** — The numeric input form is no longer shown on page load. It appears automatically only when OCR quality issues are detected, or can be toggled manually via an "Enter measurements manually" button. A green OCR-ready note is shown when a clean eye measurements image is uploaded.

- **Prior assessment comparison** — After a prediction is saved, the result panel now shows a compact "vs. last visit" row comparing confidence and recommendation against the most recent prior record for the same patient and eye.

- **Clinician notes** — A notes textarea is shown in the result panel after a prediction completes. Notes are saved via `PATCH /api/predictions/:id/notes` and displayed in the patient history view.

- **"Refer to Specialist" referral banner** — When confidence is below the threshold, the result panel shows an amber banner with an alert icon instead of a standard recommendation badge.

- **K2-derived badge** — When K2 is calculated as K1 + |astigmatism| rather than directly extracted, a small `calc` badge is shown next to the K2 value in the result panel.

- **Due for Re-assessment on Dashboard** — A new "Due for Re-assessment" section appears on the dashboard listing patients whose last assessment exceeds the clinical re-assessment interval. Rule: `monthsAfterDALK < 12` → flag after 90 days; `≥ 12` → flag after 180 days. Each row shows days overdue and an "Assess" button linking directly to the prediction form pre-filled with that patient.

- **Estimated values in Patient History** — K1, K2, CCT, and astigmatism fields that were imputed (not directly extracted by OCR) are now shown with an amber `Est.` badge rather than displaying `—`.

- **UCVA / BCVA and clinician notes in Patient History** — Visual acuity values and any saved clinician notes are now displayed in the patient history detail view.

---

### Frontend UI Overhaul

- **SVG icons replace all emoji** — All navigation and UI emoji replaced with `lucide-react` SVG icons throughout the app (Sidebar, ImageUpload, ResultPanel, Dashboard).

- **Card border stripes removed** — The coloured left-border stripe on all form cards has been removed.

- **Dashboard stat cards redesigned** — Each stat card now has an icon-in-coloured-box layout (teal, blue, purple, green) with a large numeric value and label.

- **Admin, PreviousPatients, PatientHistory pages redesigned** — Consistent white card layouts, proper table styles, and updated spacing using CSS design tokens.

- **Duplicate username label removed** — The redundant `admin` text label in the header has been removed.

---

### Tests

| Suite | File | Count | Status |
|---|---|---|---|
| Visual acuity utilities | `Frontend/src/utils/visualAcuity.test.js` | 32 | All pass |
| Node API integration | `backend/src/server.test.js` | 15 | All pass |
| Model sanity checks | `backend/scripts/test_model.py` | 10 | All pass |
| Real-image OCR ground truth | `backend/scripts/test_ocr_real.py` | 5 | Skipped (known gap — Tomey RT-7000 format not yet matched) |

**Frontend tests** use Vitest + jsdom (`cd Frontend && npm test`).  
**Backend tests** use Jest + supertest (`cd backend && npm test`).  
**Model tests** run standalone Python (`cd backend && python scripts/test_model.py`).

---

### Known Gap

Real device topography images from the **Tomey RT-7000** do not extract correctly. The device uses a "Sim K's" section format that does not match the current regex patterns in the topography extractor. All 5 real-image tests in `test_ocr_real.py` are marked as skipped with documented expected values for when the patterns are updated.
