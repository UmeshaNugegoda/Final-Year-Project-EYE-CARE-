import express  from "express"
import multer   from "multer"
import fetch    from "node-fetch"
import FormData from "form-data"
 
const router = express.Router()
const FLASK  = process.env.FLASK_URL || "http://localhost:5000"
 
const upload = multer({ storage: multer.memoryStorage() })
 
const logmarToDecimal = (v) =>
    v != null ? Math.round(Math.pow(10, -Number(v)) * 100) / 100 : null
 
const calcK2 = (k1, astig) =>
    k1 != null && astig != null
        ? Math.round((Number(k1) + Math.abs(Number(astig))) * 100) / 100 : null
 
const EXPLANATIONS = {
    "Spectacles"    : "Based on corneal topography, pachymetry and refraction values, spectacles are recommended at this stage of post-DALK recovery.",
    "Contact Lenses": "Corneal measurements and refractive error profile suggest contact lenses would provide optimal visual correction.",
    "No Correction" : "Current measurements indicate optical correction may not be necessary. Regular monitoring is recommended.",
}
 
router.post("/",
    upload.fields([
        { name: "topography", maxCount: 1 },
        { name: "pachymetry", maxCount: 1 },
    ]),
    async (req, res) => {
        try {
            const { patientId, eye, monthsAfterDALK,
                    ucva_logmar, bcva_logmar,
                    sphere_diopters, cylinder_diopters, axis_degrees } = req.body
            const files = req.files
 
            // Step 1: Convert logMAR → decimal
            const ucva_decimal = logmarToDecimal(ucva_logmar)
            const bcva_decimal = logmarToDecimal(bcva_logmar)
 
            // Step 2: OCR both images
            let extractedValues = {}
            if (files?.topography?.[0] || files?.pachymetry?.[0]) {
                try {
                    const ocrForm = new FormData()
                    ocrForm.append("eye", eye || "OD")
                    if (files?.topography?.[0])
                        ocrForm.append("topography", files.topography[0].buffer,
                            { filename: files.topography[0].originalname, contentType: files.topography[0].mimetype })
                    if (files?.pachymetry?.[0])
                        ocrForm.append("pachymetry", files.pachymetry[0].buffer,
                            { filename: files.pachymetry[0].originalname, contentType: files.pachymetry[0].mimetype })
                    const ocrRes = await fetch(`${FLASK}/api/extract`,
                        { method:"POST", body:ocrForm, headers:ocrForm.getHeaders() })
                    if (ocrRes.ok) {
                        const d = await ocrRes.json()
                        extractedValues = d.extracted || {}
                    }
                } catch(e) { console.warn("OCR non-fatal:", e.message) }
            }
 
            // Step 3: K2
            const k1Raw    = extractedValues.K1_diopters
            const astigRaw = extractedValues.astigmatism_diopters
            const k2Raw    = extractedValues.K2_diopters
            const cctRaw   = extractedValues.corneal_thickness_um

            const k1 = k1Raw != null ? Number(k1Raw) : null

            // Model uses astigmatism magnitude in diopters (0..10).
            const astigFromOcr = astigRaw != null ? Number(astigRaw) : null
            const astig = astigFromOcr != null && Number.isFinite(astigFromOcr) && astigFromOcr >= 0 && astigFromOcr <= 10
                ? astigFromOcr
                : null

            const k2FromOcr = k2Raw != null ? Number(k2Raw) : null
            const k2 = k2FromOcr != null && Number.isFinite(k2FromOcr)
                ? k2FromOcr
                : calcK2(k1, astig)

            const cctFromOcrNum = cctRaw != null ? Number(cctRaw) : null
            const cct = cctFromOcrNum != null && Number.isFinite(cctFromOcrNum) && cctFromOcrNum >= 150 && cctFromOcrNum <= 1000
                ? cctFromOcrNum
                : null
 
            // Step 4: ML model
            const mlRes = await fetch(`${FLASK}/api/predict`, {
                method:"POST",
                headers:{"Content-Type":"application/json"},
                body: JSON.stringify({
                    K1_diopters: k1, K2_diopters: k2,
                    astigmatism_diopters: astig, corneal_thickness_um: cct,
                    sphere_diopters: Number(sphere_diopters),
                    cylinder_diopters: Number(cylinder_diopters),
                    axis_degrees: Number(axis_degrees),
                    visual_acuity_decimal: bcva_decimal,
                })
            })
            if (!mlRes.ok) throw new Error("ML prediction failed")
            const ml = await mlRes.json()
 
            res.json({
                recommended  : ml.prediction,
                confidence   : ml.confidence,
                probabilities: ml.probabilities,
                explanation  : EXPLANATIONS[ml.prediction] || "",
                extractedValues: {
                    K1_diopters          : k1 != null ? `${k1} D`    : "Not extracted",
                    K2_diopters          : k2 != null ? `${k2} D`    : "Not calculated",
                    astigmatism_diopters : astig != null ? `Corneal Astigmatism (Cyl): ${astig} D` : "Corneal Astigmatism (Cyl): Not extracted",
                    corneal_thickness_um : cct != null ? `${cct} µm`  : "Not extracted",
                    ucva: `${ucva_logmar} logMAR → ${ucva_decimal}`,
                    bcva: `${bcva_logmar} logMAR → ${bcva_decimal}`,
                },
                patientId, eye,
                monthsAfterDALK: Number(monthsAfterDALK),
                timestamp: new Date().toISOString(),
            })
        } catch(err) {
            console.error(err)
            res.status(500).json({ message: err.message, error: true })
        }
    }
)
 
export default router