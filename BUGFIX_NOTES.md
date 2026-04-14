# Bug Fix Notes

---

## Bug 1 — Wrong Label on the Dashboard Activity Feed

### What was broken

On the Dashboard page, there is a "Recent Activity" section that shows a coloured dot next to each patient entry. The dot colour is supposed to change depending on what correction was recommended — green for spectacles, purple for contact lenses, grey for everything else.

But the dot was always showing grey, no matter what the recommendation was.

### Why it happened

Think of it like a name tag mix-up.

The ML model and the database always save the recommendation as **"Spectacles"**. But the code that picks the dot colour was looking for the name **"Glasses"**. It never found it — because "Glasses" is never stored anywhere in the system — so it always fell back to grey.

```
Database says:  "Spectacles"
Code looks for: "Glasses"     ← these don't match, so it gives up and uses grey
```

### The fix

Changed the word the code was looking for from `"Glasses"` to `"Spectacles"` so it actually matches what the database stores.

**File changed:** `Frontend/src/pages/Dashboard/Dashboard.jsx` — line 98

```js
// Before (broken)
if (rec === 'Glasses') return 'assessment'

// After (fixed)
if (rec === 'Spectacles') return 'assessment'
```

---

## Bug 2 — Pages Inside Pages (Invalid HTML Structure)

### What was broken

Two pages — **Previous Patients** and **Patient History** — had a structural mistake in the HTML. They had a `<main>` tag sitting inside another `<main>` tag.

### Why it's a problem

Think of `<main>` like the "main room" of a house. A house can only have one main room. If you put a main room inside another main room, the blueprint doesn't make sense — builders get confused.

In web terms:
- Browsers and screen readers (used by people with visual impairments) expect only **one** `<main>` on a page
- Having two can cause layout and styling to behave unexpectedly
- It is officially invalid HTML

```html
<!-- What it looked like (broken) -->
<main class="layout-main">
  <main class="patients-container">   ← this second <main> should not be here
    ...
  </main>
</main>
```

### The fix

Replaced the inner `<main>` with a `<div>`. A `<div>` is a plain container — it wraps content without making any structural promises about being the "main" area of the page.

**Files changed:**
- `Frontend/src/pages/PreviousPatients/PreviousPatients.jsx`
- `Frontend/src/pages/PatientHistory/PatientHistory.jsx`

```html
<!-- After (fixed) -->
<main class="layout-main">
  <div class="patients-container">    ← just a plain wrapper now, no conflict
    ...
  </div>
</main>
```

The visual appearance stays exactly the same — the CSS class names were not changed, only the HTML tag type.

---

---

## Bug 3 — OCR Image Preprocessing Never Ran (Missing OpenCV Dependency)

### What was broken

The OCR system has two preprocessing functions that are supposed to improve image quality before scanning:

- `_preprocess_pachymetry_for_ocr` — upscales pachymetry images 2×, boosts local contrast, and applies adaptive thresholding so dense number tables are easier for EasyOCR to read
- `_preprocess_topography_for_ocr` — upscales topography images 2.5×, denoises, and enhances contrast so small coloured labels (K1, K2, CYL) are readable

Both functions use the `cv2` library (OpenCV). But `opencv-python` was never listed in `requirements.txt`, so it was never installed. Every time either function was called, Python threw a `ModuleNotFoundError`, which was silently caught, and the system fell back to scanning the raw, unprocessed image.

In other words: the preprocessing pipeline existed in code but had never run. EasyOCR was always reading the raw images, which are harder to parse (small text, low contrast, dense tables).

### The fix

Added `opencv-python` to `requirements.txt`.

**File changed:** `backend/requirements.txt`

```
# Before (missing)
flask
flask-cors
easyocr
...

# After (fixed)
flask
flask-cors
easyocr
opencv-python   ← added
...
```

After pulling the updated file, run:
```bash
pip install -r requirements.txt
```

---

## Bug 4 — OCR Lost Column Position, Causing Wrong OD/OS Value Assignment

### What was broken

The OCR was called with `detail=0`, which makes EasyOCR return only the text it reads, discarding the bounding box coordinates that say *where* on the image each word was found.

Medical eye reports are printed as two-column tables — the left column contains OD (right eye) values, the right column contains OS (left eye) values. Without knowing the x-position of each number, the code had no reliable way to tell which column a value belonged to.

The code tried to work around this by guessing from the order tokens appeared in the list (assuming OD values always came first). But EasyOCR does not guarantee left-to-right ordering within a row, so this assumption often broke on real reports.

The result was values from the wrong eye being extracted — K1, K2, CCT etc. could come from OD when the user selected OS, or vice versa.

### A related problem in the topography two-pass

For topography images the code ran OCR twice (once on the original, once on the preprocessed image) and concatenated all tokens from both passes into a single list without removing duplicates. This doubled every value in the list, so the index-based column selection (`eye_idx = 0` for OD, `1` for OS) was pointing at the wrong position.

### The fix

**1. Switched to `detail=1`** — EasyOCR now returns `(bounding_box, text, confidence)` for each detected token instead of just the text.

**2. Added `_spatially_sorted_chunks()`** — A new helper function that:
- Takes the bounding box output
- Groups tokens into rows based on their vertical centre coordinate (tokens within 15 pixels of each other vertically are treated as the same row)
- Sorts each row left-to-right by horizontal centre coordinate

This guarantees the chunk list always follows the physical column order on the image — OD (left column) values always appear before OS (right column) values, making `eye_idx = 0/1` reliable.

**3. Fixed the topography two-pass** — The preprocessed image is now used as the sole source for the `chunks` list (index-based column extraction). The original image pass still runs, but its output is only appended to the text string used for regex pattern searches. This preserves broad coverage without doubling the chunk list.

**File changed:** `backend/app.py`

```python
# Before (broken) — discards position, order not guaranteed
for tok in reader.readtext(src, detail=0):
    chunks.append(tok)

# After (fixed) — uses bounding boxes to sort by row then column
results = reader.readtext(primary_src, detail=1)
chunks = _spatially_sorted_chunks(results)   # sorted top→bottom, left→right
```

---

---

## Bug 5 — Flask Service Unreachable (Port 5000 Blocked by macOS AirPlay)

### What was broken

The Flask ML service would not start — port 5000 was already in use. The Node backend's requests to Flask all failed with a connection refused error, causing every prediction attempt to return "ML Prediction Failed".

### Why it happened

macOS Monterey (and later) enables AirPlay Receiver by default, which binds to port 5000. This silently occupies the port before Flask can.

### The fix

Changed the Flask service to run on port **5001** instead of 5000, and updated the Node backend's environment variable to match.

**Files changed:**
- `backend/app.py` — `app.run(port=5001)`
- `backend/.env` — `FLASK_URL=http://localhost:5001`

---

## Bug 6 — Zeiss Pachymetry Extracting the Wrong Eye's CCT

### What was broken

When the user selected OD (right eye), the system sometimes returned the OS (left eye) CCT value, and vice versa.

### Why it happened

A Zeiss CIRRUS pachymetry report prints both eyes side-by-side on one image — OD on the left half, OS on the right. After spatial sorting, the OCR token list interleaved values from both columns. The extraction logic was designed for a single-eye view and didn't account for this, so it could pick up numbers from the wrong side.

### The fix

Added `_split_ocr_by_column()` in `backend/app.py`. Before building the chunk list, it measures the image width, calculates the midpoint, and keeps only the tokens whose bounding box centre falls in the correct half:

- **OD** → keep tokens with x-centre **< midpoint** (left half)
- **OS** → keep tokens with x-centre **≥ midpoint** (right half)

```python
def _split_ocr_by_column(ocr_results, image_width, eye):
    mid = image_width / 2
    filtered = [item for item in ocr_results
                if (eye == "OD" and (item[0][0][0] + item[0][2][0]) / 2 < mid)
                or (eye == "OS" and (item[0][0][0] + item[0][2][0]) / 2 >= mid)]
    return filtered if filtered else ocr_results
```

**File changed:** `backend/app.py`

---

## Bug 7 — CCT Extraction Returning Minimum Thickness Instead of Central Corneal Thickness

### What was broken

After the column-split fix (Bug 6), the CCT extractor saw only one eye's text. The existing extraction functions expected both OD and OS values to be present and used index-based logic to locate the CCT. With only one eye's text available, the index arithmetic was off and the function returned the **Minimum Thickness** value (a nearby row) instead of the **Central Corneal Thickness**.

Example: OD minimum thickness = 414, OD CCT = 424 — the wrong value was returned.

### Why it happened

The dual-column extraction strategies assumed a two-column layout. Once the column split was applied, that assumption no longer held, and the code landed on the wrong row.

### The fix

Added a **single-column extraction path** in `run_ocr` that runs before the dual-column functions. It uses a two-anchor approach:

1. Find the position of the `"Corneal Thickness"` keyword in the OCR text
2. Find the position of the `"Central"` keyword
3. Determine the relative order of the two anchors:
   - If **Central comes first** → the CCT value appears *after* "Corneal Thickness" → take the first valid 3–4 digit number after that label
   - If **Corneal Thickness comes first** → the CCT value appears *between* the two anchors → scan that window and take the last valid number (avoids picking up intermediate table values)

```python
if pos_cen < pos_cth:
    # value is after "Corneal Thickness"
    for nm in re.finditer(r"\b(\d{3,4})\b", text[pos_cth:]):
        if 150 <= float(nm.group(1)) <= 1000:
            _found = float(nm.group(1)); break
else:
    # value is between the two anchors — take the last one
    for nm in re.finditer(r"\b(\d{3,4})\b", text[pos_cth:pos_cen]):
        if 150 <= float(nm.group(1)) <= 1000:
            _found = float(nm.group(1))
```

**File changed:** `backend/app.py`

---

## Bug 8 — Colored Text in Tomey Topography Not Readable by OCR

### What was broken

On Tomey RT-7000 topography reports, critical values (K1, K2, CYL) are printed in **red** and secondary values in **green**. EasyOCR struggled to read these against the light background after standard grayscale preprocessing — the red/green text blended with the grey background and was often missed entirely.

### Why it happened

Converting a color image to grayscale loses hue information. Red (RGB ~200,0,0) and green (RGB ~0,140,0) both map to mid-range grey values that are hard to threshold cleanly when surrounded by black text on white.

### The fix

Added `_extract_colored_text_layer()` in `backend/app.py`. It:

1. Converts the image to HSV color space
2. Creates masks for red (hue ranges 0–12° and 158–180°) and green (hue range 35–90°) pixels
3. Dilates the masks slightly to close gaps in characters
4. Renders the masked pixels as black text on a white canvas

The color layer is stacked **below** the standard grayscale-preprocessed image before being passed to EasyOCR, giving the OCR engine two chances to read each value — once from the standard view, once from the color-isolated view.

**File changed:** `backend/app.py`

---

## Summary

| # | File | What was wrong | What was changed |
|---|------|----------------|-----------------|
| 1 | `Dashboard.jsx` | Checked for `"Glasses"` but the app uses `"Spectacles"` | Changed the string to `"Spectacles"` |
| 2 | `PreviousPatients.jsx` | Had a `<main>` nested inside a `<main>` | Changed inner `<main>` to `<div>` |
| 2 | `PatientHistory.jsx` | Had a `<main>` nested inside a `<main>` | Changed inner `<main>` to `<div>` |
| 3 | `requirements.txt` | `opencv-python` missing — image preprocessing silently never ran | Added `opencv-python` to requirements |
| 4 | `app.py` | `detail=0` discarded bounding boxes; wrong OD/OS column values extracted | Switched to `detail=1` + spatial sort helper; fixed topography two-pass chunk doubling |
| 5 | `app.py`, `.env` | macOS AirPlay occupies port 5000 — Flask could not start | Moved Flask to port 5001 |
| 6 | `app.py` | Zeiss side-by-side layout caused wrong-eye CCT to be extracted | Added `_split_ocr_by_column()` to filter tokens to the correct image half before extraction |
| 7 | `app.py` | After column split, index-based CCT logic landed on Minimum Thickness row | Added two-anchor single-column extraction path using "Central" + "Corneal Thickness" keyword positions |
| 8 | `app.py` | Red/green text on Tomey reports lost in grayscale conversion — OCR missed K values | Added `_extract_colored_text_layer()` using HSV masking; color layer stacked with grayscale result |
