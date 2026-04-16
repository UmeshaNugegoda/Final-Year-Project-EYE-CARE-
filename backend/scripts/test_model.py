"""
Model Sanity Check Tests
========================
Verifies that all .pkl artifacts are consistent and the model produces
valid outputs. Run from the backend/ directory:

    python scripts/test_model.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np

PASS = 0
FAIL = 0

def ok(name):
    global PASS
    PASS += 1
    print(f"  PASS  {name}")

def fail(name, detail=""):
    global FAIL
    FAIL += 1
    print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


print("\n── Loading artifacts ─────────────────────────────────────────")
try:
    import joblib
    MODEL    = joblib.load("eye_correction_model.pkl")
    LE       = joblib.load("label_encoder.pkl")
    SCALER   = joblib.load("scaler.pkl")
    IMPUTER  = joblib.load("imputer.pkl")
    FEATURES = joblib.load("feature_names.pkl")
    # Compatibility shim for models pickled with older scikit-learn
    if not hasattr(IMPUTER, "_fill_dtype"):
        try:
            IMPUTER._fill_dtype = np.asarray(IMPUTER.statistics_).dtype
        except Exception:
            IMPUTER._fill_dtype = object
    ok("All pkl files loaded")
except Exception as e:
    fail("Load pkl files", str(e))
    sys.exit(1)


print("\n── Artifact consistency ──────────────────────────────────────")

# 1. Label encoder has exactly 3 classes
expected_classes = {"Contact Lenses", "No Correction", "Spectacles"}
actual_classes   = set(LE.classes_)
if actual_classes == expected_classes:
    ok(f"LabelEncoder has 3 expected classes: {sorted(actual_classes)}")
else:
    fail("LabelEncoder classes", f"got {actual_classes}")

# 2. Feature list is non-empty and all strings
if FEATURES and all(isinstance(f, str) for f in FEATURES):
    ok(f"feature_names.pkl has {len(FEATURES)} features: {FEATURES}")
else:
    fail("feature_names.pkl", f"got {FEATURES}")

# 3. Imputer n_features_in_ matches feature count
n_feat = len(FEATURES)
imp_n  = getattr(IMPUTER, "n_features_in_", None)
if imp_n == n_feat:
    ok(f"Imputer n_features_in_ = {imp_n} matches feature count")
elif imp_n is None:
    ok(f"Imputer n_features_in_ not set (older sklearn) — skipping")
else:
    fail("Imputer feature count mismatch", f"imputer={imp_n} features={n_feat}")

# 4. Scaler n_features_in_ matches feature count
scl_n = getattr(SCALER, "n_features_in_", None)
if scl_n == n_feat:
    ok(f"Scaler n_features_in_ = {scl_n} matches feature count")
elif scl_n is None:
    ok("Scaler n_features_in_ not set (older sklearn) — skipping")
else:
    fail("Scaler feature count mismatch", f"scaler={scl_n} features={n_feat}")


print("\n── Prediction smoke tests ────────────────────────────────────")
import pandas as pd

def predict(feature_values: dict) -> tuple:
    """Returns (label, confidence_pct)."""
    row     = pd.DataFrame([{f: feature_values.get(f, np.nan) for f in FEATURES}])
    row_imp = IMPUTER.transform(row)
    row_sc  = SCALER.transform(row_imp)
    idx     = MODEL.predict(row_sc)[0]
    probs   = MODEL.predict_proba(row_sc)[0]
    label   = LE.inverse_transform([idx])[0]
    return label, round(float(max(probs)) * 100, 1)

# 5. Typical spectacle candidate
try:
    label, conf = predict({
        "K1_Flat": 46.5, "K2_Steep": 48.0, "astigmatism_diopters": 1.5,
        "corneal_thickness_um": 510, "sphere_diopters": -2.0,
        "cylinder_diopters": -1.5, "axis_degrees": 90, "visual_acuity_decimal": 0.5,
    })
    if label in expected_classes and 0 < conf <= 100:
        ok(f"Typical input → {label} ({conf}%)")
    else:
        fail("Typical input prediction invalid", f"label={label} conf={conf}")
except Exception as e:
    fail("Typical input prediction crashed", str(e))

# 6. All-NaN input (imputer must fill in)
try:
    label, conf = predict({})
    if label in expected_classes and 0 < conf <= 100:
        ok(f"All-NaN input (imputer fills) → {label} ({conf}%)")
    else:
        fail("All-NaN prediction invalid", f"label={label} conf={conf}")
except Exception as e:
    fail("All-NaN prediction crashed", str(e))

# 7. Extreme values don't crash
try:
    label, conf = predict({
        "K1_Flat": 70.0, "K2_Steep": 72.0, "astigmatism_diopters": 10.0,
        "corneal_thickness_um": 200, "sphere_diopters": -20.0,
        "cylinder_diopters": -10.0, "axis_degrees": 180, "visual_acuity_decimal": 0.02,
    })
    if label in expected_classes and 0 < conf <= 100:
        ok(f"Extreme values → {label} ({conf}%) — no crash")
    else:
        fail("Extreme values prediction invalid", f"label={label} conf={conf}")
except Exception as e:
    fail("Extreme values prediction crashed", str(e))

# 8. Output label is always one of the 3 known classes
try:
    import random
    random.seed(42)
    all_valid = True
    for _ in range(20):
        label, conf = predict({
            "K1_Flat": random.uniform(38, 65),
            "K2_Steep": random.uniform(39, 67),
            "astigmatism_diopters": random.uniform(0, 8),
            "corneal_thickness_um": random.uniform(200, 900),
            "sphere_diopters": random.uniform(-15, 5),
            "cylinder_diopters": random.uniform(-8, 0),
            "axis_degrees": random.uniform(0, 180),
            "visual_acuity_decimal": random.uniform(0.1, 1.2),
        })
        if label not in expected_classes or not (0 < conf <= 100):
            all_valid = False
            fail(f"Random input produced invalid output: label={label} conf={conf}")
            break
    if all_valid:
        ok("20 random inputs all produce valid label + confidence")
except Exception as e:
    fail("Random input batch crashed", str(e))

# 9. Confidence is between 0 and 100
try:
    _, conf = predict({"K1_Flat": 45.0, "visual_acuity_decimal": 0.8})
    if 0 < conf <= 100:
        ok(f"Confidence in valid range: {conf}%")
    else:
        fail("Confidence out of range", str(conf))
except Exception as e:
    fail("Confidence range check crashed", str(e))


print(f"\n── Results ───────────────────────────────────────────────────")
print(f"  {PASS} passed, {FAIL} failed\n")
sys.exit(0 if FAIL == 0 else 1)
