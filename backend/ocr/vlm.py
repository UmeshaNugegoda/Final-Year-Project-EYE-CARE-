"""
VLM (Claude Sonnet vision) extractors for topography and pachymetry images.
Complements eye_measurements_extractor.py which handles handwritten forms.
"""
import base64
import json
import re

_TOPO_PROMPT = """\
This is a corneal topography report (e.g. Tomey RT-7000 or similar device printout).
Extract keratometry values for the {eye_label} eye.

Return ONLY a JSON object (no markdown, no extra text) with exactly these keys:
{{
  "K1_diopters": numeric flat K (lower value, typical range 30–65 D) or null,
  "K2_diopters": numeric steep K (higher value, typical range 30–65 D) or null,
  "astigmatism_diopters": numeric corneal cylinder (positive, 0–15 D) or null
}}

Rules:
- K1 is the flatter (smaller) meridian, K2 is the steeper (larger) meridian.
- K1 must be ≤ K2.
- astigmatism_diopters = K2 − K1 (always positive).
- Look for "Sim K", "K flat / K steep", "Kf / Ks", or similar labels.
- Return null for any field you cannot read clearly.
"""

_PACHY_PROMPT = """\
This is a Zeiss CIRRUS HD-OCT "Pachymetry Analysis" report (or similar corneal pachymetry printout).

Extract the central corneal thickness (CCT) for the {eye_label} ONLY. Do NOT average or mix values \
from both eyes.

Return ONLY a JSON object (no markdown, no extra text) with exactly this key:
{{
  "corneal_thickness_um": numeric central corneal thickness in micrometres or null
}}

HOW TO READ THIS REPORT:

Layout: The page is split into two halves.
  - LEFT half  = OD (right eye): colour pachymetry map on the left, numeric zone table to its right.
  - RIGHT half = OS (left eye):  colour pachymetry map on the left, numeric zone table to its right.
  Look only at the half that matches {eye_label}.

The numeric zone table (to the right of the colour map) shows concentric ring averages:
  - The CENTRE cell / "Center" row / "0.0" or "0-1 mm" zone is the CCT.
  - Surrounding cells are inner and outer zone averages — ignore those.
  - The CCT is typically the LOWEST number in the table (cornea is thinnest centrally).
  - Typical post-DALK CCT: 400–650 µm. Valid range accepted: 150–1000 µm.

Below the pachymetry section there may be an "Epithelial Thickness" section — ignore those values \
entirely; we only need the full corneal thickness, not the epithelial layer.

If you cannot locate the zone table, look for any label "CCT", "Central", "Min Thickness", or \
"Minimum" near the correct eye's section.

Return null only if you genuinely cannot find a corneal thickness value for {eye_label}.
"""


def _call_vlm(image_bytes, prompt):
    import anthropic

    media_type = 'image/jpeg'
    if image_bytes[:4] == b'\x89PNG':
        media_type = 'image/png'

    b64 = base64.standard_b64encode(image_bytes).decode()
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=300,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {'type': 'base64', 'media_type': media_type, 'data': b64}},
                {'type': 'text', 'text': prompt},
            ]
        }]
    )
    raw = msg.content[0].text.strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```[a-z]*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw)
    raw = raw.strip()
    # Extract JSON object even if Claude added explanatory text before/after it
    start, end = raw.find('{'), raw.rfind('}')
    if start != -1 and end != -1 and end > start:
        raw = raw[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"[VLM] non-JSON response: {raw[:120]!r}")
        return {}


def extract_topography_vlm(image_bytes, eye='OD'):
    eye_label = 'right eye (OD)' if eye == 'OD' else 'left eye (OS)'
    data = _call_vlm(image_bytes, _TOPO_PROMPT.format(eye_label=eye_label))

    result = {}
    k1 = data.get('K1_diopters')
    k2 = data.get('K2_diopters')
    astig = data.get('astigmatism_diopters')

    if k1 is not None:
        k1 = float(k1)
        if 30.0 <= k1 <= 65.0:
            result['K1_diopters'] = round(k1, 2)
    if k2 is not None:
        k2 = float(k2)
        if 30.0 <= k2 <= 65.0:
            result['K2_diopters'] = round(k2, 2)

    # Enforce K1 ≤ K2
    if 'K1_diopters' in result and 'K2_diopters' in result:
        if result['K1_diopters'] > result['K2_diopters']:
            result['K1_diopters'], result['K2_diopters'] = result['K2_diopters'], result['K1_diopters']

    if astig is not None:
        astig = abs(float(astig))
        if 0.0 <= astig <= 15.0:
            result['astigmatism_diopters'] = round(astig, 2)

    # Derive astigmatism from K values if not extracted directly
    if 'astigmatism_diopters' not in result and 'K1_diopters' in result and 'K2_diopters' in result:
        result['astigmatism_diopters'] = round(result['K2_diopters'] - result['K1_diopters'], 2)

    return result


def extract_pachymetry_vlm(image_bytes, eye='OD'):
    eye_label = 'right eye (OD)' if eye == 'OD' else 'left eye (OS)'
    data = _call_vlm(image_bytes, _PACHY_PROMPT.format(eye_label=eye_label))
    print(f"[VLM/pachy raw] eye={eye} data={data}")

    result = {}
    cct = data.get('corneal_thickness_um')
    if cct is not None:
        cct = float(cct)
        if 150.0 <= cct <= 1000.0:
            result['corneal_thickness_um'] = round(cct, 0)
        else:
            print(f"[VLM/pachy] CCT {cct} out of valid range 150–1000 µm — discarded")
    return result


def extract_image_vlm(image_bytes, image_type, eye='OD'):
    """Dispatch to the correct VLM extractor based on image_type."""
    if image_type == 'topography':
        return extract_topography_vlm(image_bytes, eye)
    if image_type == 'pachymetry':
        return extract_pachymetry_vlm(image_bytes, eye)
    return {}
