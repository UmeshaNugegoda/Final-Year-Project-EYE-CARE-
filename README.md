# Post-DALK Eye Correction Prediction System

An AI-powered clinical decision support system that recommends optical corrections for patients following Deep Anterior Lamellar Keratoplasty (DALK) surgery. Clinical staff enter patient measurements and optionally upload corneal report images; the system recommends **Spectacles**, **Contact Lenses**, or **No Correction**.

---

## Architecture

Three services run together:

```
Frontend (React/Vite)  →  Node/Express Backend  →  Flask ML Service
      :5173                      :4000                   :5001
```

| Layer | Stack | Purpose |
|-------|-------|---------|
| Frontend | React 18, React Router v6, Vite | UI, forms, result display |
| Node Backend | Express, MongoDB, JWT, Multer | Auth, file uploads, orchestration |
| Flask ML Service | Flask, EasyOCR, XGBoost | OCR extraction, ML prediction |

### Data Flow

1. Clinician submits a form (patient info + optional report images) via the React UI
2. Node backend forwards images to Flask `/api/extract` → OCR reads K1, K2, astigmatism, CCT
3. Node backend sends combined features to Flask `/api/predict` → XGBoost model returns prediction + confidence
4. Result is saved to MongoDB and returned to the UI

---

## Prerequisites

- **Node.js** v18+
- **Python** 3.9+ (with pip)
- **MongoDB** (local or Atlas) — the app falls back to an in-memory store if `MONGODB_URI` is not set
- **Anthropic API key** (optional but recommended) — enables Claude Sonnet vision for OCR; without it the system falls back to EasyOCR

---

## Getting Started

### 1. Clone the repository

```bash
git clone <repository-url>
cd Final-Year-Project-EYE-CARE
```

### 2. Configure environment variables

Create `backend/.env`:

```env
MONGODB_URI=mongodb://localhost:27017/postdalk
JWT_SECRET=your_secret_key_here
PORT=4000
FLASK_URL=http://localhost:5001

# Optional — enables Claude Sonnet vision (recommended for best OCR accuracy)
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Install dependencies

**Frontend:**
```bash
cd Frontend
npm install
```

**Node backend:**
```bash
cd backend
npm install
```

**Flask ML service — create and activate a Python virtual environment first:**

macOS / Linux:
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):
```powershell
cd backend
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4. Start all three services

Open three terminal windows. Make sure the virtual environment is activated in the Flask terminal.

**Terminal 1 — Flask ML service (port 5001):**

macOS / Linux:
```bash
cd backend
source venv/bin/activate
python app.py
```

Windows (PowerShell):
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python app.py
```

**Terminal 2 — Node backend (port 4000):**
```bash
cd backend
npm run dev
```

**Terminal 3 — Frontend (port 5173):**
```bash
cd Frontend
npm run dev
```

Then open [http://localhost:5173](http://localhost:5173) in your browser.

**Default admin credentials:** `username: admin` / `password: admin123`

---

## Project Structure

```
Final-Year-Project-EYE-CARE/
├── Frontend/
│   └── src/
│       ├── pages/
│       │   ├── Login/              # Login page
│       │   ├── Dashboard/          # Stats and recent activity
│       │   ├── Prediction/         # Main prediction form + results
│       │   ├── PreviousPatients/   # Patient list
│       │   ├── PatientHistory/     # Per-patient history
│       │   └── Admin/              # User management (admin only)
│       ├── components/             # Shared UI components
│       └── utils/
│           └── visualAcuity.js     # logMAR ↔ decimal conversion
├── backend/
│   ├── src/
│   │   ├── server.js               # Express app, routes
│   │   ├── db.js                   # MongoDB + in-memory fallback
│   │   └── predictions.js          # Prediction data access
│   ├── scripts/
│   │   ├── generate_test_images.py # Synthetic report image generator
│   │   └── test_ocr.py             # OCR pipeline test runner
│   ├── app.py                      # Flask ML + OCR service
│   ├── requirements.txt            # Python dependencies
│   ├── eye_correction_model.pkl    # Trained XGBoost model
│   ├── scaler.pkl                  # Feature scaler
│   ├── label_encoder.pkl           # Label encoder
│   ├── imputer.pkl                 # Missing value imputer
│   └── feature_names.pkl           # Model feature names
└── project_from_xgboost.py         # Model training script
```

---

## API Reference

### Node Backend (port 4000)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/auth/login` | Login, returns JWT | No |
| `GET` | `/api/auth/me` | Current user info | Yes |
| `POST` | `/api/predictions` | Submit prediction (multipart) | Yes |
| `GET` | `/api/dashboard/stats` | Summary statistics | Yes |
| `GET` | `/api/dashboard/activity` | Recent predictions | Yes |
| `GET` | `/api/patients` | All patients + latest assessment | Yes |
| `GET` | `/api/patients/:id/history` | Full history for one patient | Yes |
| `POST` | `/api/users` | Create user | Admin |
| `GET` | `/api/health` | Health check | No |

### Flask ML Service (port 5001)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/extract` | OCR extraction from image files |
| `POST` | `/api/predict` | XGBoost prediction |
| `GET` | `/api/health` | Health check |

---

## OCR Image Support

The system extracts values from two types of report images:

| Report Type | Device | Values Extracted |
|-------------|--------|-----------------|
| Pachymetry | Zeiss CIRRUS | Central Corneal Thickness (CCT) |
| Topography | Tomey RT-7000 | K1, K2, Astigmatism (CYL) |

When `ANTHROPIC_API_KEY` is set, Claude Sonnet vision is used as the primary extractor (more robust, handles angled/blurry images). EasyOCR is used as a fallback when no API key is present.

---

## Testing the OCR Pipeline

```bash
cd backend

# Generate synthetic test images
python3 scripts/generate_test_images.py

# Run the OCR test suite (no Flask server needed)
python3 scripts/test_ocr.py
```

Expected output: `8/12` or better checks passing. The 4 clean-image tests (Zeiss OD, Zeiss OS, Tomey OS, Tomey OD) should all pass.

---

## Domain Notes

- **Recommendation labels** are always exactly: `"Spectacles"`, `"Contact Lenses"`, or `"No Correction"`
- **Visual acuity** is entered in logMAR and converted to decimal (`10^(-logMAR)`) before model input
- **K2** is derived as `K1 + |astigmatism|` when not extracted from OCR
- **CCT valid range**: 150–1000 µm; values outside this range are discarded
- **Eye field**: always `"OD"` (right eye) or `"OS"` (left eye)

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | React 18, React Router v6, Vite |
| Node backend | Express, JWT, Multer, MongoDB driver |
| ML service | Flask, Claude Sonnet (VLM), EasyOCR fallback, OpenCV, XGBoost, scikit-learn |
| Database | MongoDB (`postdalk` db) with in-memory fallback |
| Model format | XGBoost (`.pkl` via joblib) |
