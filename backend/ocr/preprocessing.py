"""
Image preprocessing pipeline for OCR.

Functions here operate on raw image files (BGR arrays / file paths) using
OpenCV and do not touch EasyOCR. They are imported by reader.py.
"""


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
    """Return True if ≥ 2 circular hole-punch marks are detected in the image."""
    import cv2
    import numpy as np
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)
    circles = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=50,
        param1=50, param2=30, minRadius=20, maxRadius=120,
    )
    if circles is None:
        return False
    return len(circles[0]) >= 2


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
    bgr = _mask_hole_punches(bgr)

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
