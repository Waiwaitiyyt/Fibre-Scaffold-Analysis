# FibreScope Web Service — Technical Design

## Overview

This document describes how the FibreScope analysis pipeline can be exposed as an HTTP service and consumed by a TypeScript/Node.js backend.

The C++ extension (`measure_tool`) is dropped entirely. Both `bresenham_line` and `local_pca_normal` have Python fallbacks already present in `fibre_measure.py`; the real compute bottleneck (skeletonize, Hessian matrix, scipy KDE) is already in Cython/C via scikit-image and scipy, so the performance impact is negligible at `rate ≤ 0.5`.

---

## Architecture

```
Browser / Client
      │  HTTP
      ▼
┌─────────────────────┐
│  TypeScript Backend │  (Express / Fastify / NestJS)
│  - Auth / sessions  │
│  - File handling    │
│  - Business logic   │
└────────┬────────────┘
         │  HTTP (internal)
         ▼
┌─────────────────────┐
│   Flask Python API  │  (runs on localhost or docker sidecar)
│  - Image analysis   │
│  - fibre_measure    │
│  - pore_measure     │
└─────────────────────┘
```

The TS backend owns the external surface (auth, routing, file storage, response shaping). The Flask service is an internal compute worker — never exposed directly to clients.

---

## Flask API

### `POST /analyse`

Accepts a multipart upload and returns the analysis result as JSON.

**Request** — `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `image` | file | yes | JPEG / PNG image of the scaffold |
| `mode` | string | yes | `"fibre"` or `"pore"` |
| `scale_factor` | float | no | default `1.25` |
| `jer` | float | no | default `40` |
| `rate` | float | no | default `0.5` |
| `msd` | int | no | default `50` |
| `sigma` | float | no | default `2.0` |
| `threshold` | float | no | default `0.15` |
| `oer` | float | no | default `10.0` |

**Response `200`** — `application/json`

```json
{
  "mode": "fibre",
  "stats": {
    "average": 20.67,
    "std": 4.81,
    "kde_peak": 19.28,
    "sem": 0.079,
    "median": 19.61,
    "q1": 11.01,
    "q3": 54.25,
    "iqr": 43.24,
    "ci_95": [19.61, 19.61]
  },
  "raw": [20.35, 20.08, 18.12, "..."]
}
```

`raw` contains the full per-measurement array (floats). Omit it from the response if the client only needs summary stats — just drop `"Raw"` before serialising `fibre_dict`.

**Response `400`** — validation error (bad mode, missing image, parameter out of range)

```json
{ "error": "invalid parameter: rate must be in [0.01, 1.0]" }
```

**Response `500`** — analysis failure (e.g. image too small, no ridges detected)

```json
{ "error": "analysis failed: no ridge pixels found after thresholding" }
```

---

### Minimal Flask implementation sketch

```python
# api.py
import tempfile, os
from pathlib import Path
from flask import Flask, request, jsonify
import sys
sys.path.insert(0, str(Path(__file__).parent / "src" / "python"))

from core import fibre_measure, pore_measure

app = Flask(__name__)

DEFAULTS = {
    "scale_factor": 1.25, "jer": 40.0, "rate": 0.5,
    "msd": 50, "sigma": 2.0, "threshold": 0.15, "oer": 10.0,
}

@app.post("/analyse")
def analyse():
    if "image" not in request.files:
        return jsonify(error="image file required"), 400
    mode = request.form.get("mode")
    if mode not in ("fibre", "pore"):
        return jsonify(error="mode must be 'fibre' or 'pore'"), 400

    p = {k: type(v)(request.form.get(k, v)) for k, v in DEFAULTS.items()}

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        request.files["image"].save(tmp.name)
        img_path = tmp.name

    try:
        if mode == "fibre":
            diameters, _, _, stats = fibre_measure.measure(
                img_path,
                sample_rate=p["rate"],
                max_search_distance=int(p["msd"]),
                jer=p["jer"],
                sigma=p["sigma"],
                scale_factor=p["scale_factor"],
                threshold=p["threshold"],
                overlap_exclusion_radius=p["oer"],
            )
        else:
            areas, _, _, stats, _ = pore_measure.measure(img_path, scale_factor=p["scale_factor"])
    except Exception as e:
        return jsonify(error=f"analysis failed: {e}"), 500
    finally:
        os.unlink(img_path)

    key_map = {
        "Average": "average", "Standard Deviation": "std",
        "KDE Peak": "kde_peak", "SEM": "sem", "median": "median",
        "Q1, Q3": ("q1", "q3"), "IQR": "iqr", "95% CI": "ci_95",
    }
    out = {"mode": mode, "stats": {}, "raw": stats["Raw"]}
    for src, dst in key_map.items():
        val = stats[src]
        if isinstance(dst, tuple):
            out["stats"][dst[0]], out["stats"][dst[1]] = val
        else:
            out["stats"][dst] = val

    return jsonify(out)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
```

---

## TypeScript Backend Integration

The TS backend forwards the uploaded file to the Flask service without writing it to disk a second time (stream the multipart directly).

```typescript
// analysisService.ts
import FormData from "form-data";
import fetch from "node-fetch";

const FLASK_URL = process.env.FLASK_URL ?? "http://127.0.0.1:5000";

export interface AnalysisParams {
  mode: "fibre" | "pore";
  scaleFactor?: number;
  jer?: number;
  rate?: number;
  msd?: number;
  sigma?: number;
  threshold?: number;
  oer?: number;
}

export async function runAnalysis(
  imageBuffer: Buffer,
  filename: string,
  params: AnalysisParams
) {
  const form = new FormData();
  form.append("image", imageBuffer, { filename });
  form.append("mode", params.mode);
  if (params.scaleFactor != null) form.append("scale_factor", String(params.scaleFactor));
  if (params.jer       != null) form.append("jer",          String(params.jer));
  if (params.rate      != null) form.append("rate",         String(params.rate));
  if (params.msd       != null) form.append("msd",          String(params.msd));
  if (params.sigma     != null) form.append("sigma",        String(params.sigma));
  if (params.threshold != null) form.append("threshold",    String(params.threshold));
  if (params.oer       != null) form.append("oer",          String(params.oer));

  const res = await fetch(`${FLASK_URL}/analyse`, { method: "POST", body: form });
  if (!res.ok) {
    const { error } = await res.json() as { error: string };
    throw new Error(`Analysis service error: ${error}`);
  }
  return res.json();
}
```

Expose this through whatever route layer the TS backend uses (Express/Fastify/NestJS). Validate and sanitise parameters on the TS side before calling Flask — Flask trusts what it receives.

---

## Key Considerations

**Long-running jobs**  
At `rate=1.0` on a large image, analysis can take 10–30 s in pure Python. For a browser-facing API, consider making `/analyse` asynchronous:
- `POST /analyse` → returns `{ jobId }` immediately
- `GET /jobs/:id` → returns `{ status: "pending" | "done" | "failed", result? }`

A simple in-memory dict works for single-process deployments; Redis + a task queue (Celery, RQ, or BullMQ on the TS side) is better for production.

**File size and memory**  
Images are loaded fully into memory as NumPy arrays. Set a `MAX_CONTENT_LENGTH` on Flask and validate MIME type on the TS side before forwarding.

**Concurrency**  
Flask's development server is single-threaded. Use `gunicorn --workers 2` (or more) for any real load. Each worker loads a separate Python interpreter so there is no GIL contention.

**Dropping the C++ extension**  
Remove the `try/except import measure_tool` block in `fibre_measure.py` and delete the CMake build step from CI. The pure-Python fallbacks (`bresenham_line`, `local_pca_normal`) will be called unconditionally.
