/**
 * Complete Visual Acuity Scoring System — Snellen (6m / 20ft) to logMAR / decimal.
 * Values follow the reference tables (including +/- steps and low-vision rows).
 * Qualitative: CF, HM (numeric); PL, NPL have no standard logMAR here → null.
 */

const LOGMAR_BY_KEY = {
  // High / normal (table 1)
  '6/3': -0.301,
  '6/4': -0.176,
  '6/5': -0.079,
  '6/6++': -0.041,
  '6/6+': -0.021,
  '6/6': 0.0,
  '6/6-': 0.022,
  '6/6--': 0.046,
  '6/7.5': 0.097,
  '6/9++': 0.143,
  '6/9+': 0.161,
  '6/9': 0.176,
  '6/9-': 0.194,
  // Table 2
  '6/12++': 0.26,
  '6/12+': 0.284,
  '6/12': 0.301,
  '6/12-': 0.319,
  '6/15': 0.398,
  '6/18++': 0.444,
  '6/18+': 0.469,
  '6/18': 0.477,
  '6/18-': 0.495,
  '6/24': 0.602,
  '6/36': 0.778,
  '6/60': 1.0,
  // Low vision (table 3) — metric & matching imperial alias
  '3/60': 1.301,
  '10/200': 1.301,
  '4/60': 1.176,
  '2/60': 1.477,
  '1/60': 1.778,
  CF: 1.854,
  HM: 2.699,
}

const DECIMAL_BY_KEY = {
  '6/3': 2.0,
  '6/4': 1.5,
  '6/5': 1.2,
  '6/6++': 1.1,
  '6/6+': 1.05,
  '6/6': 1.0,
  '6/6-': 0.95,
  '6/6--': 0.9,
  '6/7.5': 0.8,
  '6/9++': 0.72,
  '6/9+': 0.69,
  '6/9': 0.667,
  '6/9-': 0.64,
  '6/12++': 0.55,
  '6/12+': 0.52,
  '6/12': 0.5,
  '6/12-': 0.48,
  '6/15': 0.4,
  '6/18++': 0.36,
  '6/18+': 0.34,
  '6/18': 0.333,
  '6/18-': 0.32,
  '6/24': 0.25,
  '6/36': 0.167,
  '6/60': 0.1,
  '3/60': 0.05,
  '10/200': 0.05,
  '4/60': 0.067,
  '2/60': 0.033,
  '1/60': 0.017,
  CF: 0.014,
  HM: 0.002,
}

function roundLogmar(v) {
  return Math.round(v * 1000) / 1000
}

function roundDecimal(v) {
  return Math.round(v * 1000) / 1000
}

/**
 * Normalize user input to a lookup key (metric Snellen, 6/x, or qualitative).
 * Supports 6/x, 20/x (converted to 6/x), 10/200, 3/60 … 1/60, CF, HM, PL, NPL.
 */
export function normalizeVisualAcuityKey(raw) {
  const s = String(raw || '')
    .trim()
    .replace(/\s+/g, '')
  if (!s) return null

  const qual = s.match(/^(CF|HM|PL|NPL)$/i)
  if (qual) return qual[1].toUpperCase()

  const m = s.match(/^(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)([+-]{0,2})?$/)
  if (!m) return null

  let num = Number(m[1])
  let den = Number(m[2])
  const suffix = (m[3] || '')
    .replace(/−/g, '-')
    .replace(/＋/g, '+')

  if (!Number.isFinite(num) || !Number.isFinite(den) || num <= 0 || den <= 0) {
    return null
  }

  // 20-foot Snellen → 6-metre equivalent denominator
  if (num === 20) {
    den = (den * 6) / 20
    num = 6
  }

  if (num === 10 && den === 200) return `10/200${suffix}`

  if ([1, 2, 3, 4].includes(num)) {
    return `${num}/${den}${suffix}`
  }

  if (num === 6) {
    const denStr = Number.isInteger(den) ? String(den) : String(Math.round(den * 1000) / 1000)
    return `6/${denStr}${suffix}`
  }

  return null
}

/**
 * logMAR for API / model. Uses scoring table; falls back to -log10(decimal) for plain 6/x.
 */
export function snellenToLogmar(raw) {
  const key = normalizeVisualAcuityKey(raw)
  if (!key) return null
  if (key === 'PL' || key === 'NPL') return null

  if (Object.prototype.hasOwnProperty.call(LOGMAR_BY_KEY, key)) {
    return roundLogmar(LOGMAR_BY_KEY[key])
  }

  const m = key.match(/^6\/(\d+(?:\.\d+)?)$/)
  if (m) {
    const den = Number(m[1])
    const decimal = 6 / den
    if (decimal > 0) return roundLogmar(-Math.log10(decimal))
  }

  return null
}

/** Decimal acuity for display (same scoring system). */
export function snellenToDecimal(raw) {
  const key = normalizeVisualAcuityKey(raw)
  if (!key) return null
  if (key === 'PL' || key === 'NPL') return null

  if (Object.prototype.hasOwnProperty.call(DECIMAL_BY_KEY, key)) {
    return roundDecimal(DECIMAL_BY_KEY[key])
  }

  const m = key.match(/^6\/(\d+(?:\.\d+)?)$/)
  if (m) {
    const den = Number(m[1])
    return roundDecimal(6 / den)
  }

  return null
}

export function isQualitativeNoNumeric(key) {
  return key === 'PL' || key === 'NPL'
}
