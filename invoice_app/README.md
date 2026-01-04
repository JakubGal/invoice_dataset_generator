# Invoice builder (Dash)

Run a small Dash app that previews invoices defined fully through JSON (structure and data).

## Quick start
- Install deps: `pip install -r requirements.txt`
- Run the server: `python -m invoice_app.app`
- Load the provided sample via the "Load sample" button, edit the JSON, click "Preview invoice", then "Download HTML" or "Download PDF" to export.
- PDF export uses `pdfkit` and auto-detects `wkhtmltopdf` from PATH, `C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe`, `C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe`, a local `invoice_app/bin/wkhtmltopdf.exe`, or the `PDFKIT_WKHTMLTOPDF` env var. If missing, the app will show an error pill instead of downloading.
- Use the “Visual designer” panel to adjust theme (fonts, colors) and to click any field in the preview, edit its text, and set per-field font size/weight/color without hand-editing JSON.
- Theme also supports a background image (URL or local path) set via the designer.
- Orientation (portrait/landscape) set in the designer is respected in the PDF export.
- PDF download also ships an OCR ground-truth JSON (same base name) with bounding boxes for each text item (requires PyMuPDF).
- Use the “Layout builder” card to add sections quickly: choose type (grid/table/notes), provide a title, paste lines for fields (`Label | value_path`) or table columns (`Label | key/value_path | align`), and click “Add section”. The JSON and preview update automatically.

## Model evaluation tab
- Open the "Model evaluation" tab to benchmark OCR baselines and LLM extraction on a dataset.
- Set the dataset path (e.g., `C:/Users/bukaj/Documents/Bakalarka/gen_EN_50`) to evaluate another folder.
- Choose OCR sources (PDF text, Tesseract, EasyOCR, OCR JSON) and extraction methods (regex, key-value, pattern, ensemble, LLM text, LLM text + patterns, LLM vision).
- Enable "Score only fields rendered by the template" to avoid penalizing fields that are not present in the PDF.
- Enable "Save plots to dataset folder (HTML)" to persist interactive charts next to the dataset.
- LLM methods require an OpenAI API key and at least one model selection.
- Tesseract and EasyOCR are optional: if missing, their methods are skipped. Install Tesseract and ensure `tesseract` is on PATH; install EasyOCR via `pip install easyocr`.
- Results include field metrics (exact/normalized handle numeric/date tolerance), token F1, char similarity, numeric/date errors, item precision/recall/F1, runtime errors, and downloadable JSON summaries with error examples. Download plotly-based HTML charts from the evaluation tab.

## JSON shape
- Top-level keys: `template` (layout + styling + structure) and `data` (values).
- Template supports page styling (`page`), fonts (`font`), branding (`logo`, `background_image`, `accent_color`, `currency`), and `sections`.
- Section types:
  - `grid`: `columns`, `fields` (each with `label`, `value_path`, optional `format`, `placeholder`, `style`).
  - `panels`: `panels` array; each has `heading` and `fields`.
  - `table`: `data_path`, `columns` (with `key` or `value_path`, `label`, optional `format`, `align`, `width`), optional `totals`.
  - `notes`: single rich text block with `value_path`.
- `value_path` can be dotted (e.g., `invoice.number`); `format: "currency"` renders with the template currency symbol.

See `templates/sample_invoice.json` for a working example that includes logo, fonts, and color choices.
