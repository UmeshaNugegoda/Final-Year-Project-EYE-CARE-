import joblib
import numpy as np
import pandas as pd
import tempfile
import os

from flask import Flask, request, jsonify
from flask_cors import CORS

from ocr.reader import run_ocr, get_reader
from ocr.utils import calculate_k2
from ocr.preprocessing import _analyze_image_quality

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ── ML model ──────────────────────────────────────────────────────────────────
MODEL    = joblib.load("eye_correction_model.pkl")
LE       = joblib.load("label_encoder.pkl")
SCALER   = joblib.load("scaler.pkl")
IMPUTER  = joblib.load("imputer.pkl")
FEATURES = joblib.load("feature_names.pkl")
print(f"Model loaded | Features: {FEATURES} | Classes: {list(LE.classes_)}")

# Compatibility shim for models pickled with older scikit-learn versions.
if not hasattr(IMPUTER, "_fill_dtype"):
    try:
        IMPUTER._fill_dtype = np.asarray(IMPUTER.statistics_).dtype
    except Exception:
        IMPUTER._fill_dtype = object


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/extract", methods=["POST"])
def extract():
    eye = request.form.get("eye", "OD").upper()
    extracted, temps = {}, []
    try:
        for img_key, img_type in [("topography", "topography"), ("pachymetry", "pachymetry")]:
            if img_key in request.files:
                f = request.files[img_key]
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
    result = {"warnings": {"topography": [], "pachymetry": []}}
    temps = []
    try:
        for img_key in ["topography", "pachymetry"]:
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
        idx     = MODEL.predict(row_sc)[0]
        probs   = MODEL.predict_proba(row_sc)[0]
        label   = LE.inverse_transform([idx])[0]
        return jsonify({
            "prediction"   : label,
            "confidence"   : round(float(max(probs)) * 100, 1),
            "probabilities": {c: round(float(p) * 100, 1) for c, p in zip(LE.classes_, probs)},
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "features": FEATURES, "classes": list(LE.classes_)})


@app.route("/api/debug", methods=["POST"])
def debug():
    """Temporary route — shows raw OCR text from uploaded images."""
    eye    = request.form.get("eye", "OD").upper()
    reader = get_reader()
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
                chunks = reader.readtext(tmp_path, detail=0)
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
