# Invoice Dataset Generator and Evaluation App

This repo contains a Dash web app for:
- Building invoice templates and previewing/exporting PDFs.
- Generating synthetic invoice datasets (PDF + OCR JSON + ground-truth JSON).
- Evaluating OCR baselines and multimodal LLMs on a fixed dataset.
- Inspecting OCR overlays.

The app is designed for benchmarking structured information extraction from invoice-like PDFs.

## Features

- Invoice template builder (JSON-based) with visual preview.
- PDF export and OCR ground-truth generation.
- Dataset generator with language, page count, and layout variability controls.
- OCR checker overlay for OCR JSON inspection.
- Evaluation pipeline with multiple methods and metrics.
- Optional LLM evaluation (text and vision).
- Optional Tesseract / EasyOCR baselines (if installed).

## Requirements

- Python 3.11 (recommended).
- wkhtmltopdf (for PDF export).
- Tesseract OCR (for image-based OCR in dataset generation and evaluation).

Optional:
- EasyOCR (if you want EasyOCR baselines).
- GPU for faster OCR/LLM usage.

## Quick Start (Local)

1) Create a virtual environment:

```bash
python -m venv .venv
```

2) Activate it:

Windows (PowerShell):
```bash
.venv\\Scripts\\Activate.ps1
```

3) Install dependencies:

```bash
pip install -r requirements.txt
```

4) Install wkhtmltopdf:
- Windows: https://wkhtmltopdf.org/downloads.html
- Ensure the binary is on PATH, or set:

```bash
setx PDFKIT_WKHTMLTOPDF "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"
```

5) Install Tesseract OCR:
- Windows builds: https://github.com/UB-Mannheim/tesseract/wiki
- Add to PATH or set:

```bash
setx TESSERACT_CMD "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
```

6) Run the app:

```bash
python -m invoice_app.app
```

Open: http://localhost:8050

## Environment Variables

These are optional, but recommended:

- `OPENAI_API_KEY` - default API key for OpenAI-compatible models.
- `OPENAI_BASE_URL` - custom base URL for OpenAI-compatible providers.
- `OPENAI_API_KEY_ALT` - secondary key for non-OpenAI providers.
- `OPENAI_BASE_URL_ALT` - secondary base URL (e.g., DashScope).
- `OPENAI_MODEL_MATCH_ALT` - comma-separated tokens; if a model name contains a token, the secondary key/base is used.
- `GEMINI_API_KEY` - for Gemini models.
- `ANTHROPIC_API_KEY` - for Claude models.
- `PDFKIT_WKHTMLTOPDF` - full path to wkhtmltopdf binary.
- `TESSERACT_CMD` / `TESSERACT_PATH` - full path to tesseract binary.
- `TESSERACT_LANGS` - languages for Tesseract (e.g., `eng+deu+ces+slk`).

## Usage Overview

### 1) Invoice builder
- Paste or upload a JSON template (`template` + `data`).
- Preview and download HTML or PDF.
- Generate OCR JSON for the exported PDF.

### 2) OCR checker
- Upload a PDF and an OCR JSON file.
- See OCR boxes overlayed on the page images.

### 3) Dataset maker
- Configure languages, page range, variability, fonts, colors, and augmentations.
- Generate a dataset with:
  - `sample_xxx_*.json` (ground truth)
  - `sample_xxx_*.pdf` (rendered PDF)
  - `sample_xxx_*.ocr.json` (OCR boxes)
- Use "Download dataset (ZIP)" to fetch the output folder as a ZIP.

Notes:
- If the PDF has no selectable text, OCR JSON is produced via Tesseract.
- If Tesseract is missing, OCR JSON will be empty and the sample will fail.

### 4) Model evaluation
- Point to a dataset folder (PDF + OCR JSON + JSON ground truth).
- Choose OCR sources and extraction methods.
- Add LLM models and run evaluation.
- Download results and plots (HTML).

Ground truth for evaluation is the `data` field inside each `sample_*.json`.
OCR JSON is only an input source, not ground truth.

## Dataset Structure

Each sample should have:

```
sample_001_abc123.json      # Ground truth (template + data)
sample_001_abc123.pdf       # Rendered PDF
sample_001_abc123.ocr.json  # OCR boxes (items array)
```

## Troubleshooting

### OCR JSON is empty
The PDF likely has no selectable text, and Tesseract is missing or misconfigured.
Install Tesseract and set `TESSERACT_CMD`, then regenerate the dataset.

### wkhtmltopdf error
Install wkhtmltopdf and set `PDFKIT_WKHTMLTOPDF`.

### Dataset not found (deployed)
Server paths are not your local PC. Use `/data/datasets` (mounted disk) or
download results via the ZIP button.

## Deployment Notes

The Dockerfile installs Tesseract and common language packs and sets:
`TESSERACT_LANGS=eng+deu+ces+slk+fra+spa+ita+pol+nld+por+ara+hin+jpn+chi_sim`.

If you deploy with Docker, rebuild after changing the Dockerfile.


