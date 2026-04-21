import joblib
import numpy as np
import pandas as pd
import tempfile
import os

# Load .env so ANTHROPIC_API_KEY is available without manual shell export
_env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _, _v = _line.partition('=')
                os.environ.setdefault(_k.strip(), _v.strip())

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from ocr.reader import run_ocr, _run_ocr_subprocess
from ocr.utils import calculate_k2
from ocr.preprocessing import _analyze_image_quality

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# Rate limiting — only applies to VLM (Anthropic API) path on /api/extract
limiter = Limiter(get_remote_address, app=app, default_limits=[])

# ── ML model ──────────────────────────────────────────────────────────────────
MODEL    = joblib.load("eye_correction_model.pkl")
LE       = joblib.load("label_encoder.pkl")
SCALER   = joblib.load("scaler.pkl")
IMPUTER  = joblib.load("imputer.pkl")
FEATURES = joblib.load("feature_names.pkl")
print(f"Model loaded | Features: {FEATURES} | Classes: {list(LE.classes_)}")
_api_key_present = bool(os.environ.get("ANTHROPIC_API_KEY"))
try:
    import anthropic as _anthropic_check  # noqa: F401
    _anthropic_pkg = True
except ImportError:
    _anthropic_pkg = False
print(f"VLM status: {'ENABLED (Claude Sonnet)' if _api_key_present and _anthropic_pkg else 'DISABLED — ' + ('anthropic package missing' if _api_key_present else 'no ANTHROPIC_API_KEY in env')}")

# Compatibility shim for models pickled with older scikit-learn versions.
if not hasattr(IMPUTER, "_fill_dtype"):
    try:
        IMPUTER._fill_dtype = np.asarray(IMPUTER.statistics_).dtype
    except Exception:
        IMPUTER._fill_dtype = object


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/extract", methods=["POST"])
@limiter.limit(
    "5 per minute; 50 per day",
    exempt_when=lambda: not bool(os.environ.get("ANTHROPIC_API_KEY")),
    error_message='{"error": "VLM rate limit exceeded. Max 5 requests/minute and 50/day."}',
)
def extract():
    eye = request.form.get("eye", "OD").upper()
    use_vlm = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if use_vlm:
        try:
            import anthropic as _anthropic_check  # noqa: F401
        except ImportError:
            use_vlm = False
            print("[WARNING] ANTHROPIC_API_KEY set but 'anthropic' package not installed — falling back to EasyOCR")
    print(f"[extract] eye={eye} use_vlm={use_vlm}")
    extracted, temps = {}, []
    try:
        for img_key, img_type in [("topography", "topography"), ("pachymetry", "pachymetry")]:
            if img_key not in request.files:
                continue
            f = request.files[img_key]
            if use_vlm:
                from ocr.vlm import extract_image_vlm
                part = extract_image_vlm(f.read(), img_type, eye)
                print(f"[VLM/{img_type}/{eye}] {part}")
            else:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(f.filename)[1] or ".jpg")
                tmp_path = tmp.name
                tmp.close()
                f.save(tmp_path)
                temps.append(tmp_path)
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

        extraction_status = {
            key: ("extracted" if extracted.get(key) is not None else "not_found")
            for key in ["K1_diopters", "K2_diopters", "astigmatism_diopters", "corneal_thickness_um"]
        }

        # ── Eye measurements report (handwritten refraction form) ─────
        eye_meas_file = request.files.get("eye_measurements")
        if eye_meas_file:
            eye_meas_bytes = eye_meas_file.read()
            if use_vlm:
                from ocr.eye_measurements_extractor import extract_eye_measurements_vlm
                em_result = extract_eye_measurements_vlm(eye_meas_bytes, eye=eye)
            else:
                from ocr.eye_measurements_extractor import extract_eye_measurements
                em_result = extract_eye_measurements(eye_meas_bytes, eye=eye)
            em_status = em_result.pop("eye_extraction_status", {})
            for field in ["ucva_snellen", "bcva_snellen", "sphere_diopters", "cylinder_diopters", "axis_degrees"]:
                if em_result.get(field) is not None:
                    extracted[field] = em_result[field]
            extraction_status.update(em_status)

        success = sum(1 for v in extraction_status.values() if v == 'extracted')
        total   = len(extraction_status)
        print(f"[OCR] {success}/{total} fields extracted | eye={eye} | {extraction_status}")

        return jsonify({"extracted": extracted, "eye": eye, "extraction_status": extraction_status})
    except Exception as e:
        return jsonify({"error": str(e), "extracted": {}}), 500
    finally:
        for p in temps:
            if os.path.exists(p):
                try:
                    os.unlink(p)
                except PermissionError:
                    pass


@app.route("/api/analyze-quality", methods=["POST"])
def analyze_quality():
    """Lightweight image quality check — no OCR, sub-second response."""
    result = {"warnings": {"topography": [], "pachymetry": [], "eye_measurements": []}}
    temps = []
    try:
        for img_key in ["topography", "pachymetry", "eye_measurements"]:
            if img_key in request.files:
                f = request.files[img_key]
                tmp = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=os.path.splitext(f.filename)[1] or ".jpg",
                )
                tmp_path = tmp.name
                tmp.close()
                f.save(tmp_path)
                temps.append(tmp_path)
                result["warnings"][img_key] = _analyze_image_quality(tmp_path)
    except Exception as e:
        result["error"] = str(e)
    finally:
        for p in temps:
            if os.path.exists(p):
                try:
                    os.unlink(p)
                except PermissionError:
                    pass
    return jsonify(result)


@app.route("/api/predict", methods=["POST"])
def predict():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    try:
        if data.get("K2_diopters") is None:
            data["K2_diopters"] = calculate_k2(data.get("K1_diopters"), data.get("astigmatism_diopters"))
        row     = pd.DataFrame([{f: data.get(f, np.nan) for f in FEATURES}])
        row_imp = IMPUTER.transform(row)
        row_sc  = SCALER.transform(row_imp)
        idx        = MODEL.predict(row_sc)[0]
        probs      = MODEL.predict_proba(row_sc)[0]
        label      = LE.inverse_transform([idx])[0]
        confidence = round(float(max(probs)) * 100, 1)

        CONFIDENCE_THRESHOLD = 65.0
        if confidence < CONFIDENCE_THRESHOLD:
            label = "Refer to Specialist"

        # Build a dict of the actual values used (post-imputation) so the
        # frontend can display estimated values alongside extracted ones.
        feature_map = {
            "K1_Flat"              : "K1_diopters",
            "K2_Steep"             : "K2_diopters",
            "astigmatism_diopters" : "astigmatism_diopters",
            "corneal_thickness_um" : "corneal_thickness_um",
        }
        used_features = {}
        for feat_name, out_key in feature_map.items():
            if feat_name in FEATURES:
                fi = FEATURES.index(feat_name)
                val = float(row_imp[0][fi])
                used_features[out_key] = round(val, 2)

        return jsonify({
            "prediction"   : label,
            "confidence"   : confidence,
            "probabilities": {c: round(float(p) * 100, 1) for c, p in zip(LE.classes_, probs)},
            "used_features": used_features,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "features": FEATURES,
        "classes": list(LE.classes_),
        "vlm_available": bool(os.environ.get("ANTHROPIC_API_KEY")),
    })


@app.route("/api/debug", methods=["POST"])
def debug():
    """Temporary route — shows raw OCR text from uploaded images."""
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
                raw = _run_ocr_subprocess(tmp_path)
                chunks = [item[1] for item in raw]
                result[img_key] = {
                    "full_text": " ".join(chunks),
                    "chunks"   : chunks,
                }
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5001)
