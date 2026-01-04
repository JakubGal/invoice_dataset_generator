import base64
import json
import mimetypes
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def decode_uploaded_text(contents: str) -> str:
    """Dash Upload provides a base64 payload; decode it into UTF-8 text."""
    if not contents:
        return ""
    if "," not in contents:
        return contents
    _header, encoded = contents.split(",", 1)
    return base64.b64decode(encoded).decode("utf-8")


def parse_payload(text: str) -> Dict[str, Any]:
    """Load JSON string and ensure template + data keys exist."""
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("The JSON root must be an object.")

    if "template" not in payload or "data" not in payload:
        raise ValueError("JSON must contain both 'template' and 'data' sections.")
    return payload


def _tokenize_path(path: str) -> list[str]:
    """Split dotted paths and bracket indices into tokens (e.g., items[0].name -> ["items", "0", "name"])."""
    tokens: list[str] = []
    for segment in str(path).split("."):
        buf = segment
        while "[" in buf:
            before, _, rest = buf.partition("[")
            if before:
                tokens.append(before)
            idx_txt, _, remainder = rest.partition("]")
            if idx_txt:
                tokens.append(idx_txt)
            buf = remainder
        if buf:
            tokens.append(buf)
    return tokens


def dotted_get(data: Any, path: str, default: Any = "") -> Any:
    """Navigate dotted paths (supports bracket indices like items[0].name)."""
    if not path:
        return default

    node = data
    tokens = _tokenize_path(path)
    for tok in tokens:
        if isinstance(node, dict) and tok in node:
            node = node[tok]
            continue
        if isinstance(node, list) and tok.isdigit():
            try:
                node = node[int(tok)]
                continue
            except (IndexError, ValueError):
                return default
        return default
    return node


def ensure_media_uri(src: Optional[str], base_path: Optional[Path] = None) -> str:
    """Resolve local images to data URIs so they render inside the Dash preview/export."""
    if not src:
        return ""
    src = str(src)
    if src.startswith(("data:", "http://", "https://")):
        return src

    path = Path(src)
    if base_path and not path.is_absolute():
        path = base_path / path

    if path.exists():
        mime, _ = mimetypes.guess_type(path.as_posix())
        mime = mime or "application/octet-stream"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    # Fall back to original path so the browser can attempt to load it if accessible.
    return src


def format_currency(value: Any, currency_symbol: str = "$") -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value) if value is not None else ""
    return f"{currency_symbol}{number:,.2f}"


def coerce_text(value: Any, placeholder: str = "") -> str:
    if value is None or value == "":
        return placeholder
    return str(value)


def set_dotted(data: Dict[str, Any], path: str, value: Any) -> Dict[str, Any]:
    """Mutate a dict/list using dotted path syntax with optional list indices (e.g., items[0].name)."""
    if not path:
        return data

    tokens = _tokenize_path(path)
    if not tokens:
        return data

    node: Any = data
    for i, tok in enumerate(tokens):
        last = i == len(tokens) - 1
        is_index = tok.isdigit()
        if last:
            if is_index:
                idx = int(tok)
                if not isinstance(node, list):
                    return data
                while len(node) <= idx:
                    node.append({})
                node[idx] = value
            else:
                if isinstance(node, dict):
                    node[tok] = value
            return data

        next_tok = tokens[i + 1]
        if is_index:
            idx = int(tok)
            if not isinstance(node, list):
                return data
            while len(node) <= idx:
                node.append({} if not next_tok.isdigit() else [])
            if not isinstance(node[idx], (dict, list)):
                node[idx] = {} if not next_tok.isdigit() else []
            node = node[idx]
        else:
            if not isinstance(node, dict):
                return data
            if tok not in node or not isinstance(node[tok], (dict, list)):
                node[tok] = [] if next_tok.isdigit() else {}
            node = node[tok]
    return data


def parse_field_lines(text: str) -> list[Dict[str, Any]]:
    """Parse lines formatted as 'Label | value_path' into field dicts."""
    fields: list[Dict[str, Any]] = []
    if not text:
        return fields
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        parts = [p.strip() for p in cleaned.split("|")]
        if len(parts) >= 2:
            fields.append({"label": parts[0], "value_path": parts[1]})
    return fields


def parse_table_columns(text: str) -> list[Dict[str, Any]]:
    """Parse lines formatted as 'Label | key_or_value_path | align'."""
    cols: list[Dict[str, Any]] = []
    if not text:
        return cols
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        parts = [p.strip() for p in cleaned.split("|")]
        if len(parts) >= 2:
            col = {"label": parts[0]}
            col["value_path"] = parts[1]
            if len(parts) >= 3 and parts[2]:
                col["align"] = parts[2]
            cols.append(col)
    return cols


def parse_table_totals(text: str) -> list[Dict[str, Any]]:
    """Parse lines formatted as 'Label | value_path | format'."""
    totals: list[Dict[str, Any]] = []
    if not text:
        return totals
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        parts = [p.strip() for p in cleaned.split("|")]
        if len(parts) >= 2:
            total = {"label": parts[0], "value_path": parts[1]}
            if len(parts) >= 3 and parts[2]:
                total["format"] = parts[2]
            totals.append(total)
    return totals


def build_ocr_ground_truth(pdf_bytes: bytes) -> str:
    """Extract text boxes from a PDF and return JSON with positions."""
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("PyMuPDF is required for OCR JSON. Install pymupdf.") from exc

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    items: list[Dict[str, Any]] = []
    for page_index, page in enumerate(doc):
        for word in page.get_text("words"):
            # word tuple: (x0, y0, x1, y1, "text", block_no, line_no, word_no, ...)
            x0, y0, x1, y1, text, *_rest = word
            items.append(
                {
                    "page": page_index + 1,
                    "x0": float(x0),
                    "y0": float(y0),
                    "x1": float(x1),
                    "y1": float(y1),
                    "text": text,
                }
            )
    doc.close()
    return json.dumps({"items": items}, ensure_ascii=False, indent=2)


def _find_wkhtmltopdf() -> Optional[str]:
    """Locate wkhtmltopdf binary across common locations."""
    env_candidates = [
        os.environ.get("PDFKIT_WKHTMLTOPDF"),
        os.environ.get("WKHTMLTOPDF_BINARY"),
    ]
    for candidate in env_candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))

    local_candidate = Path(__file__).resolve().parent / "bin" / "wkhtmltopdf.exe"
    if local_candidate.exists():
        return str(local_candidate)

    default_paths = [
        Path("C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe"),
        Path("C:/Program Files (x86)/wkhtmltopdf/bin/wkhtmltopdf.exe"),
    ]
    for path in default_paths:
        if path.exists():
            return str(path)

    which_path = shutil.which("wkhtmltopdf")
    if which_path:
        return which_path
    return None


def html_to_pdf_bytes(html_str: str, orientation: str = "portrait") -> bytes:
    """Convert HTML string to PDF bytes using wkhtmltopdf (via pdfkit).

    Raises RuntimeError with a human-friendly message if conversion fails.
    """
    try:
        import pdfkit  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("pdfkit is not installed. Add it via requirements and pip install.") from exc

    wkhtmltopdf_path = _find_wkhtmltopdf()
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path) if wkhtmltopdf_path else None

    options = {}
    if orientation and orientation.lower() in ("landscape", "portrait"):
        options["orientation"] = orientation.title()

    try:
        # Let pdfkit resolve wkhtmltopdf from PATH or the configured location.
        return pdfkit.from_string(html_str, False, configuration=config, options=options or None)
    except OSError as exc:
        raise RuntimeError(
            "wkhtmltopdf binary is required for PDF export. Install it (e.g., Program Files/wkhtmltopdf) "
            "or set PDFKIT_WKHTMLTOPDF to its path."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Unable to generate PDF: {exc}") from exc
