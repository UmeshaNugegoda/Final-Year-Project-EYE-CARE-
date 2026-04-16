"""
Retrain the XGBoost model with:
  1. monthsAfterDALK added as a 9th feature (item 1b)
  2. Probability calibration via CalibratedClassifierCV (item 1c)

Since the original training dataset is not in the repository, this script
generates a synthetic clinical dataset by:
  - Sampling realistic post-DALK parameter distributions
  - Getting predictions from the CURRENT model (knowledge distillation)
  - Training a new calibrated model on (synthetic features + current labels)
    with monthsAfterDALK included

The new artifacts replace the .pkl files in backend/.

Run from backend/:
    python scripts/retrain_model.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import pandas as pd
import joblib
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, accuracy_score
import xgboost as xgb

SEED = 42
np.random.seed(SEED)

print("\n── Loading existing model ─────────────────────────────────────")
MODEL    = joblib.load("eye_correction_model.pkl")
LE_OLD   = joblib.load("label_encoder.pkl")
SCALER   = joblib.load("scaler.pkl")
IMPUTER  = joblib.load("imputer.pkl")
FEATURES = joblib.load("feature_names.pkl")

# Compat shim
if not hasattr(IMPUTER, "_fill_dtype"):
    try:   IMPUTER._fill_dtype = np.asarray(IMPUTER.statistics_).dtype
    except: IMPUTER._fill_dtype = object

print(f"  Old features ({len(FEATURES)}): {FEATURES}")
print(f"  Classes: {list(LE_OLD.classes_)}")


# ── Generate synthetic dataset ────────────────────────────────────
print("\n── Generating synthetic dataset ───────────────────────────────")
N = 3000

# Post-DALK corneal topography distributions (diopters)
k1 = np.random.normal(44.5, 3.5, N).clip(36, 56)
astig = np.abs(np.random.normal(2.5, 2.0, N)).clip(0, 10)
k2 = k1 + astig

# Refraction
sphere   = np.random.normal(-2.5, 3.0, N).clip(-15, 5)
cylinder = -np.abs(np.random.normal(1.5, 1.5, N)).clip(0, 8)  # negative convention
axis     = np.random.uniform(0, 180, N)

# Pachymetry
cct = np.random.normal(510, 60, N).clip(200, 900)

# BCVA decimal (used by original model as visual_acuity_decimal)
bcva = np.random.beta(5, 2, N).clip(0.1, 1.4)

# monthsAfterDALK — clinically meaningful range
months = np.random.exponential(18, N).clip(1, 72).astype(int)

# Occasionally drop features to simulate missing data (as in real OCR)
for arr in [k1, k2, astig, cct]:
    mask = np.random.random(N) < 0.15
    arr[mask] = np.nan

df_old = pd.DataFrame({
    'K1_Flat'              : k1,
    'astigmatism_diopters' : astig,
    'K2_Steep'             : k2,
    'corneal_thickness_um' : cct,
    'sphere_diopters'      : sphere,
    'cylinder_diopters'    : cylinder,
    'axis_degrees'         : axis,
    'visual_acuity_decimal': bcva,
})

# Get labels from current model (knowledge distillation)
df_imp = pd.DataFrame(IMPUTER.transform(df_old), columns=FEATURES)
df_sc  = pd.DataFrame(SCALER.transform(df_imp),  columns=FEATURES)
y_idx  = MODEL.predict(df_sc)
y      = LE_OLD.inverse_transform(y_idx)

print(f"  Generated {N} synthetic samples")
print(f"  Label distribution: { {k: int((y==k).sum()) for k in LE_OLD.classes_} }")


# ── Build new feature matrix with monthsAfterDALK ────────────────
NEW_FEATURES = FEATURES + ['monthsAfterDALK']

df_new = df_old.copy()
df_new['monthsAfterDALK'] = months.astype(float)

print(f"\n── New feature set ({len(NEW_FEATURES)}): {NEW_FEATURES}")


# ── Preprocessing ─────────────────────────────────────────────────
print("\n── Fitting new preprocessors ──────────────────────────────────")
new_imputer = SimpleImputer(strategy='median')
new_scaler  = StandardScaler()
new_le      = LabelEncoder()

X = df_new[NEW_FEATURES].values
y_enc = new_le.fit_transform(y)

X_imp = new_imputer.fit_transform(X)
X_sc  = new_scaler.fit_transform(X_imp)

print(f"  Imputer medians: { {f: round(v,2) for f,v in zip(NEW_FEATURES, new_imputer.statistics_)} }")


# ── Train / test split ────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X_sc, y_enc, test_size=0.2, stratify=y_enc, random_state=SEED
)


# ── Train XGBoost + calibrate ─────────────────────────────────────
print("\n── Training XGBoost + probability calibration ─────────────────")
base_xgb = xgb.XGBClassifier(
    n_estimators     = 200,
    learning_rate    = 0.05,
    max_depth        = 7,
    subsample        = 0.8,
    colsample_bytree = 0.8,
    gamma            = 0.1,
    min_child_weight = 1,
    use_label_encoder= False,
    eval_metric      = 'mlogloss',
    random_state     = SEED,
    n_jobs           = -1,
)

# CalibratedClassifierCV wraps XGBoost and calibrates probabilities
# using isotonic regression (recommended for > 1000 samples)
calibrated_model = CalibratedClassifierCV(
    estimator = base_xgb,
    method    = 'isotonic',
    cv        = 5,
)

calibrated_model.fit(X_train, y_train)
print("  Training complete")

y_pred   = calibrated_model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"\n── Test set accuracy: {accuracy:.3f} ──────────────────────────")
print(classification_report(y_test, y_pred, target_names=new_le.classes_))


# ── Save artifacts ────────────────────────────────────────────────
print("\n── Saving new artifacts ───────────────────────────────────────")
joblib.dump(calibrated_model, "eye_correction_model.pkl")
joblib.dump(new_le,           "label_encoder.pkl")
joblib.dump(new_scaler,       "scaler.pkl")
joblib.dump(new_imputer,      "imputer.pkl")
joblib.dump(NEW_FEATURES,     "feature_names.pkl")

print("  eye_correction_model.pkl  ← calibrated XGBoost (9 features)")
print("  label_encoder.pkl")
print("  scaler.pkl")
print("  imputer.pkl")
print("  feature_names.pkl         ← includes monthsAfterDALK")


# ── Verify with test_model.py ─────────────────────────────────────
print("\n── Quick smoke test ───────────────────────────────────────────")
import subprocess, sys as _sys
result = subprocess.run(
    [_sys.executable, "scripts/test_model.py"],
    capture_output=True, text=True
)
lines = [l for l in result.stdout.splitlines() if l.strip()]
for l in lines[-8:]:
    print(" ", l)

if result.returncode == 0:
    print("\n  All sanity checks pass — new model is ready.")
else:
    print("\n  WARNING: some sanity checks failed — review before deploying.")
    sys.exit(1)
