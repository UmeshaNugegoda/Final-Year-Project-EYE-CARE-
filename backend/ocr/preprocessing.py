"""
Image preprocessing pipeline for OCR.

Functions here operate on raw image files (BGR arrays / file paths) using
OpenCV and do not touch EasyOCR. They are imported by reader.py.
"""

MAX_OCR_WIDTH = 1200  # pixels — larger images are scaled down before upscaling


def _cap_and_scale(gray_or_bgr, target_scale=2.5):
    """
    Scale image to an OCR-friendly size.
    - If the image is wide, scale DOWN to MAX_OCR_WIDTH first so EasyOCR
      doesn't run on a 5000px image when a 1500px one would do fine.
    - Then apply target_scale upscale (for small/low-res originals).
    Returns the scaled image.
    """
    import cv2
    h, w = gray_or_bgr.shape[:2]
    # Step 1: cap large images
    if w > MAX_OCR_WIDTH:
        scale = MAX_OCR_WIDTH / w
        gray_or_bgr = cv2.resize(gray_or_bgr, None, fx=scale, fy=scale,
                                  interpolation=cv2.INTER_AREA)
        h, w = gray_or_bgr.shape[:2]
    # Step 2: upscale small images
    if w < 800:
        gray_or_bgr = cv2.resize(gray_or_bgr, None, fx=target_scale, fy=target_scale,
                                  interpolation=cv2.INTER_CUBIC)
    return gray_or_bgr


def _pad_image(img, pad=40):
    """Add white border so edge text isn't clipped during OCR."""
    import cv2
    return cv2.copyMakeBorder(img, pad, pad, pad, pad,
                               cv2.BORDER_CONSTANT, value=(255, 255, 255))


def _sharpen(gray):
    """Unsharp-mask pass — helps blurry photographed images."""
    import cv2
    blurred = cv2.GaussianBlur(gray, (0, 0), 3)
    return cv2.addWeighted(gray, 1.5, blurred, -0.5, 0)


def _deskew(gray):
    """Detect and correct small rotations (≤15°) in photographed images."""
    import cv2
    import numpy as np
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


def _get_skew_angle(gray):
    """Return the skew angle of the image in degrees (reuses _deskew logic)."""
    import cv2
    import numpy as np
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(th > 0))
    if len(coords) < 50:
        return 0.0
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    return float(angle)


def _detect_hole_punches(bgr):
    """
    Return True if ≥ 2 genuine hole-punch marks are detected.

    Three criteria must ALL pass for a circle to count:
      1. Well-defined circle (param2=60, up from 30) — eliminates OCR character shapes.
      2. Near the left or right edge (within 18% of image width) — real punch holes
         are always near a margin; letter 'O' / digit '0' appear mid-page.
      3. Very dark interior (mean pixel < 70) — a punch hole is a physical hole
         (near-black); a printed character has a white interior.
    """
    import cv2
    import numpy as np
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)
    circles = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=50,
        param1=50, param2=60,       # was 30 — much stricter
        minRadius=30, maxRadius=120, # was 20 — punches are large
    )
    if circles is None:
        return False

    confirmed = []
    for x, y, r in np.round(circles[0]).astype(int):
        # Must sit within 18% of the left or right edge
        near_edge = (x < w * 0.18) or (x > w * 0.82)
        if not near_edge:
            continue
        # Interior must be very dark (physical hole ≈ black)
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.circle(mask, (x, y), max(r - 4, 5), 255, -1)
        mean_val = cv2.mean(gray, mask=mask)[0]
        if mean_val < 70:
            confirmed.append((x, y, r))

    return len(confirmed) >= 2


def _mask_hole_punches(bgr):
    """Paint detected hole-punch circles white to prevent OCR interference."""
    import cv2
    import numpy as np
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)
    circles = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=50,
        param1=50, param2=30, minRadius=20, maxRadius=120,
    )
    if circles is None or len(circles[0]) < 2:
        return bgr
    result = bgr.copy()
    for x, y, r in np.round(circles[0]).astype(int):
        cv2.circle(result, (x, y), r + 5, (255, 255, 255), -1)
    return result


def _analyze_image_quality(image_path):
    """
    Run computer-vision quality checks on an image (no OCR).
    Returns a list of {"code": str, "message": str} dicts for each problem found.
    """
    import cv2
    warnings = []
    bgr = cv2.imread(image_path)
    if bgr is None:
        return warnings
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    if cv2.Laplacian(gray, cv2.CV_64F).var() < 80:
        warnings.append({
            "code": "blurry",
            "message": "Image appears blurry — extracted values may be inaccurate",
        })

    if w < 800 or h < 800:
        warnings.append({
            "code": "low_resolution",
            "message": "Image resolution is low — higher quality gives better OCR results",
        })

    if _detect_hole_punches(bgr):
        warnings.append({
            "code": "hole_punch",
            "message": "Punch-hole marks detected and masked — check extracted values near the left margin",
        })

    angle = abs(_get_skew_angle(gray))
    if angle > 10:
        warnings.append({
            "code": "angled",
            "message": "Image appears angled — photograph straight overhead for best results",
        })

    pad = 30
    border_pixels = (
        (gray[:pad, :] < 128).sum()
        + (gray[-pad:, :] < 128).sum()
        + (gray[:, :pad] < 128).sum()
        + (gray[:, -pad:] < 128).sum()
    )
    if border_pixels > 50:
        warnings.append({
            "code": "edge_clipping",
            "message": "Content may be cut off at the image edge — ensure the full page is visible",
        })

    return warnings


def _preprocess_pachymetry_for_ocr(image_path):
    """
    Pachymetry tables are dense and OCR often misses micron values.
    Pipeline: pad → hole-mask → upscale → deskew → sharpen → CLAHE → threshold.
    Uses softer thresholding for blurry/photographed images.
    """
    import cv2

    bgr = cv2.imread(image_path)
    if bgr is None:
        return image_path

    bgr  = _pad_image(bgr, pad=30)
    bgr  = _mask_hole_punches(bgr)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = _cap_and_scale(gray, target_scale=2.5)
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
    Topography reports (Tomey/axvam) — grayscale preprocessing pipeline.
    Pad → hole-mask → cap/scale → deskew → sharpen → CLAHE → threshold.

    The colour-layer extraction (_extract_colored_text_layer) is NOT stacked here
    to avoid doubling the numpy array size sent to EasyOCR (which was causing
    macOS to OOM-kill Python on consecutive predictions). reader.py calls
    get_color_layer_for_topography() separately if K values are not found.
    """
    import cv2

    bgr = cv2.imread(image_path)
    if bgr is None:
        return image_path

    bgr = _pad_image(bgr, pad=30)
    bgr = _mask_hole_punches(bgr)

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = _cap_and_scale(gray, target_scale=2.5)
    gray = _deskew(gray)

    blurry = _is_blurry(gray)

    if blurry:
        gray = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
        gray = _sharpen(gray)
        clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
        gray  = clahe.apply(gray)
        th = cv2.adaptiveThreshold(
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
        th = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            35, 3,
        )

    return cv2.cvtColor(th, cv2.COLOR_GRAY2RGB)


def get_color_layer_for_topography(image_path):
    """
    Returns the red/green colour-channel extraction for a topography image.
    Called by reader.py only as a fallback when K values aren't found in
    the grayscale pass, to avoid holding both large arrays in memory at once.
    """
    import cv2

    bgr = cv2.imread(image_path)
    if bgr is None:
        return None

    bgr = _pad_image(bgr, pad=30)
    bgr = _mask_hole_punches(bgr)
    colored = _extract_colored_text_layer(bgr, scale=2.5)
    return cv2.cvtColor(colored, cv2.COLOR_GRAY2RGB)

