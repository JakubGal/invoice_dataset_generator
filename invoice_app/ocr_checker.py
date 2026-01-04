import base64
import json
from typing import Any, Dict, List

import dash
from dash import Dash, Input, Output, State, dcc, html, no_update
from dash.exceptions import PreventUpdate


def _decode_upload_bytes(contents: str) -> bytes:
    """Dash upload payload -> raw bytes."""
    if not contents or "," not in contents:
        return b""
    _header, encoded = contents.split(",", 1)
    return base64.b64decode(encoded)


def _decode_upload_text(contents: str) -> str:
    raw = _decode_upload_bytes(contents)
    return raw.decode("utf-8", errors="replace")


def _pdf_to_images(pdf_bytes: bytes, zoom: float = 1.5) -> List[Dict[str, Any]]:
    """Render each PDF page to PNG along with geometry for overlays."""
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("PyMuPDF (pymupdf) is required for PDF rendering.") from exc

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: List[Dict[str, Any]] = []
    for idx, page in enumerate(doc):
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img_b64 = base64.b64encode(pix.tobytes("png")).decode("ascii")
        pages.append(
            {
                "page": idx + 1,
                "pdf_width": float(page.rect.width),
                "pdf_height": float(page.rect.height),
                "zoom": zoom,
                "img_width": pix.width,
                "img_height": pix.height,
                "image": f"data:image/png;base64,{img_b64}",
            }
        )
    doc.close()
    return pages


def _parse_ocr_items(text: str) -> List[Dict[str, Any]]:
    """Normalize OCR JSON into a list of items with page + box coords."""
    data = json.loads(text)
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        items_raw = data["items"]
    elif isinstance(data, list):
        items_raw = data
    else:
        raise ValueError("JSON should be an array or an object with an 'items' array.")

    items: List[Dict[str, Any]] = []
    for item in items_raw:
        if not isinstance(item, dict):
            continue
        try:
            page = int(item.get("page", 1))
            x0 = float(item["x0"])
            y0 = float(item["y0"])
            x1 = float(item["x1"])
            y1 = float(item["y1"])
        except Exception:
            continue
        text_val = item.get("text", "")
        items.append({"page": page, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "text": text_val})
    if not items:
        raise ValueError("No usable items found in OCR JSON.")
    return items


def _status(message: str, tone: str = "info") -> html.Div:
    color = {"info": "#444", "success": "#0a7a29", "warning": "#a66b00", "danger": "#b3261e"}.get(tone, "#444")
    return html.Div(message, style={"color": color, "fontWeight": "500"})


def _render_page(page: Dict[str, Any], page_items: List[Dict[str, Any]], max_width: int = 1000) -> html.Div:
    pdf_w = page.get("pdf_width") or 1
    pdf_h = page.get("pdf_height") or 1
    zoom = page.get("zoom") or 1.0
    img_w = pdf_w * zoom
    img_h = pdf_h * zoom
    scale = min(1.0, max_width / img_w) if img_w else 1.0
    display_w = img_w * scale
    display_h = img_h * scale

    overlays: List[html.Div] = []
    for idx, item in enumerate(page_items):
        left = item["x0"] * zoom * scale
        top = item["y0"] * zoom * scale
        width = (item["x1"] - item["x0"]) * zoom * scale
        height = (item["y1"] - item["y0"]) * zoom * scale
        overlays.append(
            html.Div(
                [
                    html.Div(
                        item.get("text", ""),
                        style={
                            "fontSize": "10px",
                            "background": "rgba(255, 255, 255, 0.8)",
                            "padding": "1px 3px",
                            "borderRadius": "3px",
                            "position": "absolute",
                            "top": "-14px",
                            "left": "0",
                            "whiteSpace": "nowrap",
                            "overflow": "hidden",
                            "textOverflow": "ellipsis",
                            "maxWidth": "150px",
                        },
                    )
                ],
                key=f"box-{page['page']}-{idx}",
                style={
                    "position": "absolute",
                    "left": f"{left}px",
                    "top": f"{top}px",
                    "width": f"{width}px",
                    "height": f"{height}px",
                    "border": "2px solid rgba(220, 38, 38, 0.8)",
                    "background": "rgba(239, 68, 68, 0.15)",
                    "boxSizing": "border-box",
                },
                title=item.get("text", ""),
            )
        )

    return html.Div(
        [
            html.Div(f"Page {page.get('page')}", style={"marginBottom": "6px", "fontWeight": "600"}),
            html.Div(
                [
                    html.Img(
                        src=page["image"],
                        style={
                            "width": f"{display_w}px",
                            "height": f"{display_h}px",
                            "display": "block",
                        },
                    ),
                    html.Div(overlays, style={"position": "absolute", "left": 0, "top": 0}),
                ],
                style={
                    "position": "relative",
                    "width": f"{display_w}px",
                    "height": f"{display_h}px",
                    "border": "1px solid #ccc",
                    "overflow": "hidden",
                    "background": "#fff",
                },
            ),
        ],
        style={"marginBottom": "24px"},
    )


def create_app() -> Dash:
    app = dash.Dash(__name__, title="PDF OCR checker")
    app.layout = html.Div(
        style={"fontFamily": "Segoe UI, sans-serif", "padding": "20px", "maxWidth": "1200px", "margin": "0 auto"},
        children=[
            html.H2("PDF ↔ OCR ground truth checker"),
            html.P(
                "Upload a rendered PDF and the OCR JSON (from build_ocr_ground_truth). "
                "The viewer overlays OCR rectangles over each page image so you can visually verify alignment."
            ),
            dcc.Store(id="pdf-pages"),
            dcc.Store(id="ocr-items"),
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "1fr 1fr",
                    "gap": "16px",
                    "marginBottom": "12px",
                },
                children=[
                    html.Div(
                        [
                            html.H4("PDF"),
                            dcc.Upload(
                                id="pdf-upload",
                                children=html.Div(["Drop PDF here or ", html.B("click to choose")]),
                                multiple=False,
                                style={
                                    "border": "1px dashed #888",
                                    "padding": "14px",
                                    "borderRadius": "6px",
                                    "textAlign": "center",
                                },
                            ),
                            html.Div(id="pdf-status", style={"marginTop": "6px"}),
                        ]
                    ),
                    html.Div(
                        [
                            html.H4("OCR JSON"),
                            dcc.Upload(
                                id="ocr-upload",
                                children=html.Div(["Drop OCR JSON here or ", html.B("click to choose")]),
                                multiple=False,
                                style={
                                    "border": "1px dashed #888",
                                    "padding": "14px",
                                    "borderRadius": "6px",
                                    "textAlign": "center",
                                },
                            ),
                            html.Div(id="ocr-status", style={"marginTop": "6px"}),
                        ]
                    ),
                ],
            ),
            html.Div(id="viewer-placeholder", style={"marginBottom": "12px", "fontStyle": "italic", "color": "#555"}),
            html.Div(id="viewer"),
        ],
    )

    @app.callback(
        Output("pdf-pages", "data"),
        Output("pdf-status", "children"),
        Input("pdf-upload", "contents"),
        State("pdf-upload", "filename"),
        prevent_initial_call=True,
    )
    def handle_pdf(contents, filename):
        if not contents:
            raise PreventUpdate
        try:
            pdf_bytes = _decode_upload_bytes(contents)
            pages = _pdf_to_images(pdf_bytes)
        except Exception as exc:  # noqa: BLE001
            return no_update, _status(f"PDF error: {exc}", "danger")
        name = filename or "PDF"
        return pages, _status(f"Loaded {name}.", "success")

    @app.callback(
        Output("ocr-items", "data"),
        Output("ocr-status", "children"),
        Input("ocr-upload", "contents"),
        State("ocr-upload", "filename"),
        prevent_initial_call=True,
    )
    def handle_ocr(contents, filename):
        if not contents:
            raise PreventUpdate
        try:
            text = _decode_upload_text(contents)
            items = _parse_ocr_items(text)
        except Exception as exc:  # noqa: BLE001
            return no_update, _status(f"OCR JSON error: {exc}", "danger")
        name = filename or "JSON"
        return items, _status(f"Loaded {name} with {len(items)} boxes.", "success")

    @app.callback(
        Output("viewer", "children"),
        Output("viewer-placeholder", "children"),
        Input("pdf-pages", "data"),
        Input("ocr-items", "data"),
    )
    def render_viewer(pages, items):
        if not pages and not items:
            return [], "Upload a PDF and OCR JSON to see overlays."
        if not pages:
            return [], "Waiting for PDF..."
        if not items:
            return [], "Waiting for OCR JSON..."

        grouped: Dict[int, List[Dict[str, Any]]] = {}
        for item in items:
            page_no = int(item.get("page", 1))
            grouped.setdefault(page_no, []).append(item)

        rendered = []
        for page in pages:
            page_no = page.get("page")
            page_items = grouped.get(page_no, [])
            rendered.append(_render_page(page, page_items))
        return rendered, ""

    return app


if __name__ == "__main__":
    create_app().run_server(debug=True)
