import express    from 'express'
import cors       from 'cors'
import bcrypt     from 'bcryptjs'
import jwt        from 'jsonwebtoken'
import dotenv     from 'dotenv'
import multer     from 'multer'
import fetch      from 'node-fetch'
import FormData   from 'form-data'
import { connectDb, getDb } from './db.js'

dotenv.config()

const app = express()

app.use(cors())
app.use(express.json())

const PORT       = process.env.PORT       || 4000
const JWT_SECRET = process.env.JWT_SECRET || 'dev-post-dalk-secret-change-me'
const FLASK_URL  = process.env.FLASK_URL  || 'http://localhost:5001'

let usersCollection
let predictionsCollection
let dbReady = false
let dbConnectInProgress = false
let httpServer

// ── Multer — store uploaded images in memory ──────────────────────
const upload = multer({
  storage: multer.memoryStorage(),
  limits : { fileSize: 10 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    ['image/jpeg', 'image/png', 'image/jpg'].includes(file.mimetype)
      ? cb(null, true)
      : cb(new Error('JPG and PNG only'))
  },
})

// ── Auth helpers ──────────────────────────────────────────────────
function generateToken(user) {
  return jwt.sign(
    {
      id      : user._id?.toString?.() || user.id,
      username: user.username,
      role    : user.role,
    },
    JWT_SECRET,
    { expiresIn: '8h' },
  )
}

function authMiddleware(req, res, next) {
  try {
    const header = req.headers.authorization || ''
    if (!header.startsWith('Bearer ')) {
      return res.status(401).json({ message: 'Unauthorized' })
    }
    const token   = header.slice('Bearer '.length)
    const payload = jwt.verify(token, JWT_SECRET)
    req.user = payload
    next()
  } catch {
    return res.status(401).json({ message: 'Invalid or expired token' })
  }
}

function adminOnly(req, res, next) {
  if (!req.user || req.user.role !== 'admin') {
    return res.status(403).json({ message: 'Admin access required' })
  }
  next()
}

function ensureDbReady(res) {
  if (!dbReady || !usersCollection || !predictionsCollection) {
    res.status(503).json({
      message: 'Service temporarily unavailable. Database connection is not ready yet.',
    })
    return false
  }
  return true
}

async function initAdminUser() {
  const count = await usersCollection.countDocuments({ role: 'admin' })
  if (count === 0) {
    const passwordHash = bcrypt.hashSync('admin123', 10)
    await usersCollection.insertOne({
      username : 'admin',
      passwordHash,
      role     : 'admin',
      createdAt: new Date().toISOString(),
    })
    console.log('Seeded default admin: username="admin" password="admin123"')
  }
}

// ── Conversion helpers ────────────────────────────────────────────
// logMAR → decimal  (formula: 10 ^ -logMAR)
const logmarToDecimal = (v) =>
  v != null ? Math.round(Math.pow(10, -Number(v)) * 100) / 100 : null

// K2 = K1 + |astigmatism|
const calcK2 = (k1, astig) =>
  k1 != null && astig != null
    ? Math.round((Number(k1) + Math.abs(Number(astig))) * 100) / 100
    : null

const EXPLANATIONS = {
  'Spectacles'    : 'Based on corneal topography, pachymetry and refraction values, spectacles are recommended at this stage of post-DALK recovery.',
  'Contact Lenses': 'Corneal measurements and refractive error profile suggest contact lenses would provide optimal visual correction.',
  'No Correction' : 'Current measurements indicate optical correction may not be necessary. Regular monitoring is recommended.',
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// AUTH ROUTES
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

app.post('/api/auth/login', async (req, res) => {
  if (!ensureDbReady(res)) return
  const { username, password } = req.body || {}
  if (!username || !password) {
    return res.status(400).json({ message: 'Username and password are required.' })
  }
  const user = await usersCollection.findOne({ username })
  if (!user) return res.status(401).json({ message: 'Invalid credentials.' })
  const isValid = bcrypt.compareSync(password, user.passwordHash)
  if (!isValid) return res.status(401).json({ message: 'Invalid credentials.' })
  const token = generateToken(user)
  return res.json({
    token,
    user: { id: user._id.toString(), username: user.username, role: user.role },
  })
})

app.get('/api/auth/me', authMiddleware, (req, res) => {
  return res.json({ user: req.user })
})

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// USER MANAGEMENT
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

app.post('/api/users', authMiddleware, adminOnly, async (req, res) => {
  if (!ensureDbReady(res)) return
  const { username, password, role } = req.body || {}
  if (!username || !password || !role) {
    return res.status(400).json({ message: 'Username, password and role are required.' })
  }
  if (!['admin', 'user'].includes(role)) {
    return res.status(400).json({ message: 'Role must be "admin" or "user".' })
  }
  const passwordHash = bcrypt.hashSync(password, 10)
  try {
    await usersCollection.insertOne({
      username, passwordHash, role, createdAt: new Date().toISOString(),
    })
    return res.status(201).json({ message: 'User created successfully.' })
  } catch (error) {
    if (String(error.message || '').includes('duplicate key')) {
      return res.status(409).json({ message: 'Username already exists.' })
    }
    console.error('Error creating user', error)
    return res.status(500).json({ message: 'Internal server error.' })
  }
})

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// PREDICTIONS ROUTE  ← updated to use real ML model via Flask
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

app.post(
  '/api/analyze-quality',
  upload.fields([
    { name: 'topography', maxCount: 1 },
    { name: 'pachymetry', maxCount: 1 },
  ]),
  async (req, res) => {
    try {
      const files = req.files
      const qualityForm = new FormData()
      for (const key of ['topography', 'pachymetry']) {
        if (files?.[key]?.[0]) {
          qualityForm.append(key, files[key][0].buffer, {
            filename   : files[key][0].originalname,
            contentType: files[key][0].mimetype,
          })
        }
      }
      const r = await fetch(`${FLASK_URL}/api/analyze-quality`, {
        method : 'POST',
        body   : qualityForm,
        headers: qualityForm.getHeaders(),
      })
      if (r.ok) return res.json(await r.json())
      return res.json({ warnings: { topography: [], pachymetry: [], eye_measurements: [] } })
    } catch (err) {
      console.warn('Quality check (non-fatal):', err.message)
      return res.json({ warnings: { topography: [], pachymetry: [], eye_measurements: [] } })
    }
  }
)

app.post(
  '/api/predictions',
  upload.fields([
    { name: 'topography',       maxCount: 1 },
    { name: 'pachymetry',       maxCount: 1 },
    { name: 'eye_measurements', maxCount: 1 },
  ]),
  async (req, res) => {
    try {
      if (!ensureDbReady(res)) return
      const {
        patientId, eye, monthsAfterDALK,
        ucva_logmar, bcva_logmar,
        sphere_diopters, cylinder_diopters, axis_degrees, corneal_thickness_override,
        k1_override, k2_override, cyl_override,
        mode,
      } = req.body

      const isManualMode = mode === 'manual'
      const k1Override  = k1_override  != null && k1_override  !== '' ? Number(k1_override)  : null
      const k2Override  = k2_override  != null && k2_override  !== '' ? Number(k2_override)  : null
      const cylOverride = cyl_override != null && cyl_override !== '' ? Number(cyl_override) : null

      const files = req.files
      const normalizedPatientId = String(patientId || '').trim()
      const normalizedEye = String(eye || '').trim().toUpperCase()

      // Validate required fields
      if (!normalizedPatientId || !normalizedEye || monthsAfterDALK === undefined ||
          ucva_logmar === undefined || bcva_logmar === undefined ||
          sphere_diopters === undefined || cylinder_diopters === undefined ||
          axis_degrees === undefined) {
        return res.status(400).json({ message: 'Missing required fields.' })
      }

      // ── Step 1: Convert logMAR → decimal ───────────────────────
      const ucva_decimal = logmarToDecimal(ucva_logmar)
      const bcva_decimal = logmarToDecimal(bcva_logmar)
      console.log(`VA: UCVA ${ucva_logmar} → ${ucva_decimal} | BCVA ${bcva_logmar} → ${bcva_decimal}`)

      // ── Step 2: OCR both images via Flask ───────────────────────
      let extractedValues     = {}
      let ocrExtractionStatus = {}

      if (!isManualMode && (files?.topography?.[0] || files?.pachymetry?.[0])) {
        try {
          const ocrForm = new FormData()
          ocrForm.append('eye', normalizedEye || 'OD')

          if (files?.topography?.[0]) {
            ocrForm.append('topography', files.topography[0].buffer, {
              filename   : files.topography[0].originalname,
              contentType: files.topography[0].mimetype,
            })
          }
          if (files?.pachymetry?.[0]) {
            ocrForm.append('pachymetry', files.pachymetry[0].buffer, {
              filename   : files.pachymetry[0].originalname,
              contentType: files.pachymetry[0].mimetype,
            })
          }
          if (files?.eye_measurements?.[0]) {
            ocrForm.append('eye_measurements', files.eye_measurements[0].buffer, {
              filename   : files.eye_measurements[0].originalname,
              contentType: files.eye_measurements[0].mimetype,
            })
          }

          const ocrAbort = new AbortController()
          const ocrTimer = setTimeout(() => ocrAbort.abort(), 180_000) // 3 min — EasyOCR is slow on first load
          const ocrRes = await fetch(`${FLASK_URL}/api/extract`, {
            method : 'POST',
            body   : ocrForm,
            headers: ocrForm.getHeaders(),
            signal : ocrAbort.signal,
          }).finally(() => clearTimeout(ocrTimer))

          if (ocrRes.ok) {
            const ocrData        = await ocrRes.json()
            extractedValues      = ocrData.extracted || {}
            ocrExtractionStatus  = ocrData.extraction_status || {}
            console.log('OCR extracted:', extractedValues)
          } else {
            console.warn('OCR request failed — proceeding without extracted values')
          }
        } catch (ocrErr) {
          // OCR failure is non-fatal — imputer handles missing values
          console.warn('OCR error (non-fatal):', ocrErr.message)
        }
      }

      // ── Step 3: Get extracted values (overrides take precedence) ─
      const k1Raw    = extractedValues.K1_diopters
      const astigRaw = extractedValues.astigmatism_diopters
      const k2Raw    = extractedValues.K2_diopters

      const k1FromOcr = k1Raw != null ? Number(k1Raw) : null
      const k1 = (k1Override != null && Number.isFinite(k1Override)) ? k1Override : k1FromOcr

      // Model uses astigmatism magnitude in diopters (0..10).
      const astigFromOcr = astigRaw != null ? Number(astigRaw) : null
      const astigOcrValid = astigFromOcr != null && Number.isFinite(astigFromOcr) && astigFromOcr >= 0 && astigFromOcr <= 10
        ? astigFromOcr : null
      const astig = (cylOverride != null && Number.isFinite(cylOverride) && cylOverride >= 0 && cylOverride <= 10)
        ? cylOverride
        : astigOcrValid

      const k2FromOcr = k2Raw != null ? Number(k2Raw) : null
      const k2 = (k2Override != null && Number.isFinite(k2Override))
        ? k2Override
        : (k2FromOcr != null && Number.isFinite(k2FromOcr) ? k2FromOcr : calcK2(k1, astig))

      const overrideCct = corneal_thickness_override != null && corneal_thickness_override !== ''
        ? Number(corneal_thickness_override)
        : null
      const cctFromOcrRaw = extractedValues.corneal_thickness_um ?? null
      const cctFromOcrNum = cctFromOcrRaw != null ? Number(cctFromOcrRaw) : null
      const cctFromOcrValid = cctFromOcrNum != null && Number.isFinite(cctFromOcrNum) && cctFromOcrNum >= 150 && cctFromOcrNum <= 1000
        ? cctFromOcrNum
        : null

      const cct = cctFromOcrValid ?? (
          Number.isFinite(overrideCct) && overrideCct >= 150 && overrideCct <= 1000
          ? overrideCct
          : null
      )

      // Build per-field extraction status (after overrides applied)
      const extractionStatus = {
        K1_diopters         : k1Override  != null ? 'manual_override' : (ocrExtractionStatus.K1_diopters          || 'not_found'),
        K2_diopters         : k2Override  != null ? 'manual_override' : (k2FromOcr != null ? 'extracted'          : 'not_found'),
        astigmatism_diopters: cylOverride != null ? 'manual_override' : (ocrExtractionStatus.astigmatism_diopters || 'not_found'),
        corneal_thickness_um: (overrideCct != null && cctFromOcrValid == null) ? 'manual_override' : (ocrExtractionStatus.corneal_thickness_um || 'not_found'),
      }

      console.log(`K1=${k1} Corneal Astigmatism (Cyl)=${astig} K2=${k2} CCT=${cct}`)

      // ── Step 4: Call Flask ML model ─────────────────────────────
      const mlAbort = new AbortController()
      const mlTimer = setTimeout(() => mlAbort.abort(), 30_000) // 30 s
      const mlRes = await fetch(`${FLASK_URL}/api/predict`, {
        method : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body   : JSON.stringify({
          K1_diopters          : k1,
          K2_diopters          : k2,
          astigmatism_diopters : astig,
          corneal_thickness_um : cct,
          sphere_diopters      : Number(sphere_diopters),
          cylinder_diopters    : Number(cylinder_diopters),
          axis_degrees         : Number(axis_degrees),
          visual_acuity_decimal: bcva_decimal,
        }),
        signal : mlAbort.signal,
      }).finally(() => clearTimeout(mlTimer))

      if (!mlRes.ok) {
        const err = await mlRes.json().catch(() => ({}))
        throw new Error(err.error || 'ML prediction failed')
      }

      const ml = await mlRes.json()

      // ── Step 5: Save to MongoDB ─────────────────────────────────
      const insertResult = await predictionsCollection.insertOne({
        patientId            : normalizedPatientId,
        eye                  : normalizedEye,
        monthsAfterDALK      : Number(monthsAfterDALK),
        ucva                 : Number(ucva_logmar),
        bcva                 : Number(bcva_logmar),
        sphere               : Number(sphere_diopters),
        cylinder             : Number(cylinder_diopters),
        axis                 : Number(axis_degrees),
        K1_diopters          : k1,
        K2_diopters          : k2,
        astigmatism_diopters : astig,
        corneal_thickness_um : cct,
        recommendedCorrection: ml.prediction,
        confidence           : ml.confidence,
        probabilities        : ml.probabilities,
        explanation          : EXPLANATIONS[ml.prediction] || '',
        createdAt            : new Date().toISOString(),
      })

      // ── Step 6: Return result to React ──────────────────────────
      // For fields not extracted by OCR, show the imputed value the model
      // actually used (from ml.used_features) so the clinician sees a number
      // rather than 'Not extracted'.
      const uf = ml.used_features || {}
      const k1Display    = k1    != null ? `${k1} D`    : (uf.K1_diopters           != null ? `${uf.K1_diopters} D`           : null)
      const k2Display    = k2    != null ? `${k2} D`    : (uf.K2_diopters           != null ? `${uf.K2_diopters} D`           : null)
      const astigDisplay = astig != null ? `Corneal Astigmatism (Cyl): ${astig} D`  : (uf.astigmatism_diopters != null ? `Corneal Astigmatism (Cyl): ${uf.astigmatism_diopters} D` : null)
      const cctDisplay   = cct   != null
        ? `${cct} µm${cctFromOcrValid == null && overrideCct != null ? ' (manual fallback)' : ''}`
        : (uf.corneal_thickness_um != null ? `${uf.corneal_thickness_um} µm` : null)

      // Eye measurements OCR fields (from third scanner)
      const ocrUcva     = extractedValues.ucva_snellen      || null
      const ocrBcva     = extractedValues.bcva_snellen      || null
      const ocrSphere   = extractedValues.sphere_diopters   != null ? Number(extractedValues.sphere_diopters)   : null
      const ocrCylinder = extractedValues.cylinder_diopters != null ? Number(extractedValues.cylinder_diopters) : null
      const ocrAxis     = extractedValues.axis_degrees      != null ? Number(extractedValues.axis_degrees)      : null

      // Add eye-measurement extraction statuses
      for (const f of ['ucva_snellen', 'bcva_snellen', 'sphere_diopters', 'cylinder_diopters', 'axis_degrees']) {
        if (!(f in extractionStatus)) extractionStatus[f] = 'not_found'
      }

      // True when OCR mode was used but at least one corneal field fell back to imputer defaults
      const hasEstimatedValues = !isManualMode &&
        ['K1_diopters','K2_diopters','astigmatism_diopters','corneal_thickness_um']
          .some(f => extractionStatus[f] === 'not_found')

      // Build display values including eye-measurement OCR fields
      const ucvaDisplay = ocrUcva
        ? `${ocrUcva} (OCR) → logMAR ${ucva_logmar} → decimal ${ucva_decimal}`
        : `${ucva_logmar} logMAR → ${ucva_decimal} decimal`
      const bcvaDisplay = ocrBcva
        ? `${ocrBcva} (OCR) → logMAR ${bcva_logmar} → decimal ${bcva_decimal}`
        : `${bcva_logmar} logMAR → ${bcva_decimal} decimal`

      return res.json({
        recommended  : ml.prediction,
        confidence   : ml.confidence,
        probabilities: ml.probabilities,
        explanation  : EXPLANATIONS[ml.prediction] || '',
        extractedValues: {
          K1_diopters          : k1Display,
          K2_diopters          : k2Display,
          astigmatism_diopters : astigDisplay,
          corneal_thickness_um : cctDisplay,
          ucva                 : ucvaDisplay,
          bcva                 : bcvaDisplay,
          ...(ocrSphere   != null ? { sphere_diopters:   `${ocrSphere} D (OCR)` }   : {}),
          ...(ocrCylinder != null ? { cylinder_diopters: `${ocrCylinder} D (OCR)` } : {}),
          ...(ocrAxis     != null ? { axis_degrees:      `${ocrAxis}°  (OCR)` }     : {}),
        },
        patientId: normalizedPatientId,
        eye: normalizedEye,
        monthsAfterDALK: Number(monthsAfterDALK),
        historySaved: true,
        recordId: String(insertResult?.insertedId ?? ''),
        timestamp      : new Date().toISOString(),
        extractionStatus,
        hasEstimatedValues,
        submissionMode: isManualMode ? 'manual' : 'ocr',
      })

    } catch (error) {
      console.error('Prediction error:', error)
      return res.status(500).json({ message: error.message || 'Internal server error.' })
    }
  }
)

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// DASHBOARD ROUTES
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

app.get('/api/dashboard/stats', authMiddleware, async (req, res) => {
  try {
    if (!ensureDbReady(res)) return
    const totalAssessments = await predictionsCollection.countDocuments()
    const glasses          = await predictionsCollection.countDocuments({ recommendedCorrection: 'Spectacles' })
    const contactLenses    = await predictionsCollection.countDocuments({ recommendedCorrection: 'Contact Lenses' })
    const noCorrection     = await predictionsCollection.countDocuments({ recommendedCorrection: 'No Correction' })
    return res.json({ totalAssessments, glasses, contactLenses, noCorrection })
  } catch (error) {
    console.error('Error fetching dashboard stats', error)
    return res.status(500).json({ message: 'Internal server error.' })
  }
})

app.get('/api/dashboard/activity', authMiddleware, async (req, res) => {
  try {
    if (!ensureDbReady(res)) return
    const list = await predictionsCollection
      .find({})
      .sort({ createdAt: -1 })
      .limit(10)
      .project({ patientId:1, eye:1, recommendedCorrection:1, createdAt:1 })
      .toArray()
    const activity = list.map((p) => ({
      patientId     : p.patientId,
      eye           : p.eye,
      recommendation: p.recommendedCorrection,
      createdAt     : p.createdAt,
    }))
    return res.json({ activity })
  } catch (error) {
    console.error('Error fetching dashboard activity', error)
    return res.status(500).json({ message: 'Internal server error.' })
  }
})

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// PATIENT ROUTES
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

app.get('/api/patients', authMiddleware, async (req, res) => {
  try {
    if (!ensureDbReady(res)) return
    const aggregated = await predictionsCollection
      .aggregate([
        { $sort: { createdAt: -1 } },
        {
          $group: {
            _id             : { patientId: '$patientId', eye: '$eye' },
            lastAssessment  : { $first: '$createdAt' },
            recommendation  : { $first: '$recommendedCorrection' },
            monthsAfterDALK : { $first: '$monthsAfterDALK' },
          },
        },
        {
          $project: {
            patientId      : '$_id.patientId',
            eye            : '$_id.eye',
            lastAssessment : 1,
            recommendation : 1,
            monthsAfterDALK: 1,
            _id            : 0,
          },
        },
        { $sort: { lastAssessment: -1 } },
      ])
      .toArray()
    return res.json({ patients: aggregated })
  } catch (error) {
    console.error('Error fetching patients', error)
    return res.status(500).json({ message: 'Internal server error.' })
  }
})

app.get('/api/patients/:patientId/history', authMiddleware, async (req, res) => {
  try {
    if (!ensureDbReady(res)) return
    const { patientId } = req.params
    const { eye }       = req.query
    const filter        = { patientId: String(patientId) }
    if (eye) filter.eye = String(eye)
    const list = await predictionsCollection
      .find(filter).sort({ createdAt: -1 }).toArray()
    const history = list.map((p) => ({
      patientId            : p.patientId,
      eye                  : p.eye,
      monthsAfterDALK      : p.monthsAfterDALK,
      recommendedCorrection: p.recommendedCorrection,
      confidence           : p.confidence,
      explanation          : p.explanation,
      // Stored measurement/extraction values so users can review
      // previous reports for the same patient.
      K1_diopters          : p.K1_diopters,
      K2_diopters          : p.K2_diopters,
      astigmatism_diopters : p.astigmatism_diopters,
      corneal_thickness_um : p.corneal_thickness_um,
      sphere               : p.sphere,
      cylinder             : p.cylinder,
      axis                 : p.axis,
      probabilities        : p.probabilities,
      createdAt            : p.createdAt,
    }))
    return res.json({ history })
  } catch (error) {
    console.error('Error fetching patient history', error)
    return res.status(500).json({ message: 'Internal server error.' })
  }
})

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// START SERVER
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

app.get('/api/health', async (req, res) => {
  return res.json({
    status: 'ok',
    database: dbReady ? 'connected' : 'connecting',
    flaskUrl: FLASK_URL,
  })
})

async function connectDbWithRetry() {
  if (dbConnectInProgress || dbReady) return
  dbConnectInProgress = true
  try {
    await connectDb()
    const db             = getDb()
    usersCollection      = db.collection('users')
    predictionsCollection = db.collection('predictions')
    await initAdminUser()
    dbReady = true
    console.log('Database connection established.')
  } catch (error) {
    dbReady = false
    console.error('Database connection failed. Retrying in 10 seconds...', error)
    setTimeout(() => {
      dbConnectInProgress = false
      connectDbWithRetry()
    }, 10000)
    return
  }
  dbConnectInProgress = false
}

async function start() {
  // Ensure DB (or in-memory fallback) is ready before accepting requests.
  await connectDbWithRetry()

  httpServer = app.listen(PORT, () => {
    console.log(`Backend server running on http://localhost:${PORT}`)
  })
  httpServer.on('close', () => {
    console.error('HTTP server closed unexpectedly. Restarting in 2 seconds...')
    setTimeout(start, 2000)
  })
  httpServer.on('error', (error) => {
    console.error('HTTP server error:', error)
  })
}

start()