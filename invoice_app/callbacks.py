import base64
import copy
import json
import random
import re
import threading
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from dash import ALL, Input, Output, State, callback_context, dcc, html, no_update
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
import plotly.io as pio

from invoice_app.render import build_html_export, render_invoice
import invoice_app.evaluation as evaluation
from invoice_app.utils import (
    decode_uploaded_text,
    dotted_get,
    html_to_pdf_bytes,
    build_ocr_ground_truth,
    parse_field_lines,
    parse_table_columns,
    parse_table_totals,
    parse_payload,
    set_dotted,
    build_ocr_ground_truth,
)
import os
import uuid
import pathlib

SAMPLE_PATH = Path(__file__).parent / "templates" / "sample_invoice.json"


def _status(message: str, tone: str = "info") -> html.Div:
    return html.Div(message, className=f"pill {tone}")


def _load_sample_text() -> str:
    if SAMPLE_PATH.exists():
        return SAMPLE_PATH.read_text(encoding="utf-8")
    return ""


def _dump(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _update_field_label(template: Dict[str, Any], path: str, new_label: str) -> None:
    target = path.replace(".label", "")
    for section in template.get("sections", []) or []:
        stype = section.get("type", "grid")
        if stype == "grid":
            for field in section.get("fields", []) or []:
                if field.get("value_path") == target or (not field.get("value_path") and field.get("label") == target):
                    field["label"] = new_label
        if stype == "panels":
            for panel in section.get("panels", []) or []:
                for field in panel.get("fields", []) or []:
                    if field.get("value_path") == target or (not field.get("value_path") and field.get("label") == target):
                        field["label"] = new_label
        if stype == "table":
            for col in section.get("columns", []) or []:
                if col.get("label") == target or col.get("key") == target:
                    col["label"] = new_label
            for total in section.get("totals", []) or []:
                if total.get("label") == target:
                    total["label"] = new_label


def _update_style(template: Dict[str, Any], path: str, style_updates: Dict[str, Any]) -> None:
    if "styles" not in template or not isinstance(template.get("styles"), dict):
        template["styles"] = {}
    clean = {k: v for k, v in style_updates.items() if v not in (None, "", [])}
    template["styles"][path] = {**template["styles"].get(path, {}), **clean}


def _decode_upload_bytes(contents: str) -> bytes:
    if not contents or "," not in contents:
        return b""
    _header, encoded = contents.split(",", 1)
    return base64.b64decode(encoded)


def _decode_upload_text(contents: str) -> str:
    return _decode_upload_bytes(contents).decode("utf-8", errors="replace")


def _pdf_to_images(pdf_bytes: bytes, zoom: float = 1.5) -> List[Dict[str, Any]]:
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
    data = json.loads(text)
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        items_raw = data["items"]
    elif isinstance(data, list):
        items_raw = data
    else:
        raise ValueError("OCR JSON should be an array or an object with an 'items' array.")

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
        items.append(
            {
                "page": page,
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "text": item.get("text", ""),
            }
        )
    if not items:
        raise ValueError("No usable items found in OCR JSON.")
    return items


def _render_ocr_page(page: Dict[str, Any], page_items: List[Dict[str, Any]], max_width: int = 1000) -> html.Div:
    pdf_w = page.get("pdf_width") or 1
    pdf_h = page.get("pdf_height") or 1
    zoom = page.get("zoom") or 1.0
    img_w = pdf_w * zoom
    scale = min(1.0, max_width / img_w) if img_w else 1.0
    display_w = img_w * scale
    display_h = pdf_h * zoom * scale

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
                key=f"ocr-box-{page.get('page')}-{idx}",
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

def register_callbacks(app):
    @app.callback(
        Output("template-json-input", "value"),
        Output("upload-status", "children"),
        Input("load-sample-btn", "n_clicks"),
        Input("upload-json", "contents"),
        State("upload-json", "filename"),
        prevent_initial_call=True,
    )
    def handle_sources(sample_clicks: int, uploaded: str, filename: str):
        triggered = callback_context.triggered_id
        if triggered == "load-sample-btn":
            text = _load_sample_text()
            return text, _status("Sample template loaded.", "success")

        if triggered == "upload-json" and uploaded:
            text = decode_uploaded_text(uploaded)
            name = filename or "file"
            return text, _status(f"Loaded {name}.", "success")

        raise PreventUpdate

    @app.callback(
        Output("payload-store", "data"),
        Output("feedback", "children"),
        Input("preview-btn", "n_clicks"),
        State("template-json-input", "value"),
        prevent_initial_call=True,
    )
    def handle_preview(_n_clicks: int, text: str):
        if not text:
            return no_update, _status("Paste JSON first.", "warning")
        try:
            payload = parse_payload(text)
        except Exception as exc:  # noqa: BLE001 (surface the JSON issue)
            return no_update, _status(f"JSON error: {exc}", "danger")
        return payload, _status("Template parsed. Preview refreshed.", "success")

    @app.callback(
        Output("selection-store", "data"),
        Input(
            {
                "type": "editable-text",
                "path": ALL,
                "role": ALL,
                "section": ALL,
                "row": ALL,
                "col_idx": ALL,
                "total_idx": ALL,
            },
            "n_clicks",
        ),
        prevent_initial_call=True,
    )
    def select_field(clicks):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        trig_id = ctx.triggered_id
        if not trig_id:
            raise PreventUpdate
        # trig_id is a dict with "type" and "path"
        if isinstance(trig_id, dict):
            return trig_id
        raise PreventUpdate

    @app.callback(
        Output("selected-path", "children"),
        Output("selected-text-input", "value"),
        Output("selected-text-color", "value"),
        Output("selected-text-size", "value"),
        Output("selected-text-weight", "value"),
        Input("selection-store", "data"),
        State("payload-store", "data"),
    )
    def populate_selected(selection: Dict[str, Any], payload: Dict[str, Any]):
        if not selection or not selection.get("path"):
            return "Click a field in the preview to edit", "", "", None, None
        path = selection.get("path")
        if not payload:
            return f"Selected: {path}", "", "", None, None
        template = payload.get("template", {}) or {}
        data = payload.get("data", {}) or {}
        styles = template.get("styles", {}) or {}
        text_value = ""
        role = selection.get("role")
        section_idx = selection.get("section")
        if role in ("label", "header", "total-label"):
            # Figure out label text
            if role == "header" and section_idx is not None:
                try:
                    col_idx = int(selection.get("col_idx", 0))
                    text_value = template.get("sections", [])[int(section_idx)]["columns"][col_idx].get(
                        "label", ""
                    )
                except Exception:
                    text_value = ""
            elif role == "total-label" and section_idx is not None:
                try:
                    t_idx = int(selection.get("total_idx", 0))
                    text_value = template.get("sections", [])[int(section_idx)]["totals"][t_idx].get("label", "")
                except Exception:
                    text_value = ""
            else:
                target = path.replace(".label", "")
                for section in template.get("sections", []) or []:
                    stype = section.get("type", "grid")
                    if stype == "grid":
                        for f in section.get("fields", []) or []:
                            if f.get("value_path") == target or f.get("label") == target:
                                text_value = f.get("label", "")
                    if stype == "panels":
                        for panel in section.get("panels", []) or []:
                            for f in panel.get("fields", []) or []:
                                if f.get("value_path") == target or f.get("label") == target:
                                    text_value = f.get("label", "")
        else:
            text_value = dotted_get(data, path, "")

        style = styles.get(path, {}) if isinstance(styles, dict) else {}
        size = style.get("fontSize") or style.get("font_size")
        try:
            size_val = int(str(size).replace("px", "")) if size else None
        except ValueError:
            size_val = None
        weight = style.get("fontWeight") or style.get("font_weight")
        text_str = "" if text_value is None else str(text_value)
        return f"Selected: {path}", text_str, style.get("color", ""), size_val, weight

    @app.callback(
        Output("invoice-preview", "children"),
        Input("payload-store", "data"),
    )
    def update_preview(payload: Dict[str, Any]):
        if not payload:
            return html.Div("Load a template to see the invoice preview.", className="placeholder")
        try:
            return render_invoice(payload)
        except Exception as exc:  # noqa: BLE001
            return html.Div(f"Unable to render invoice: {exc}", className="error")

    @app.callback(
        Output("download-invoice", "data"),
        Input("download-btn", "n_clicks"),
        State("payload-store", "data"),
        prevent_initial_call=True,
    )
    def download_invoice(_n_clicks: int, payload: Dict[str, Any]):
        if not payload:
            raise PreventUpdate
        html_str = build_html_export(payload)
        base_name = dotted_get(payload.get("data", {}), "invoice.number", "invoice") if isinstance(payload, dict) else "invoice"
        base_name = str(base_name).replace(" ", "_")
        return dcc.send_string(html_str, filename=f"{base_name}.html")

    @app.callback(
        Output("download-pdf", "data"),
        Output("download-ocr", "data"),
        Output("download-feedback", "children"),
        Input("download-pdf-btn", "n_clicks"),
        State("payload-store", "data"),
        prevent_initial_call=True,
    )
    def download_pdf(_n_clicks: int, payload: Dict[str, Any]):
        if not payload:
            return no_update, no_update, _status("Generate a preview first, then download.", "warning")
        html_str = build_html_export(payload)
        orientation = (
            payload.get("template", {}).get("page", {}).get("orientation", "portrait")
            if isinstance(payload, dict)
            else "portrait"
        )
        base_name = dotted_get(payload.get("data", {}), "invoice.number", "invoice") if isinstance(payload, dict) else "invoice"
        base_name = str(base_name).replace(" ", "_")
        try:
            pdf_bytes = html_to_pdf_bytes(html_str, orientation=orientation)
        except Exception as exc:  # noqa: BLE001
            return no_update, no_update, _status(str(exc), "danger")

        ocr_json = None
        try:
            ocr_json = build_ocr_ground_truth(pdf_bytes)
        except Exception as exc:  # noqa: BLE001
            # Keep PDF download, but inform about OCR failure
            return (
                dcc.send_bytes(pdf_bytes, f"{base_name}.pdf"),
                no_update,
                _status(f"PDF saved, but OCR JSON failed: {exc}", "warning"),
            )

        return (
            dcc.send_bytes(pdf_bytes, f"{base_name}.pdf"),
            dcc.send_string(ocr_json, f"{base_name}.json"),
            _status("PDF and OCR JSON generated.", "success"),
        )

    @app.callback(
        Output("payload-store", "data", allow_duplicate=True),
        Output("template-json-input", "value", allow_duplicate=True),
        Output("feedback", "children", allow_duplicate=True),
        Input("apply-theme-btn", "n_clicks"),
        State("payload-store", "data"),
        State("theme-font-family", "value"),
        State("theme-font-size", "value"),
        State("theme-font-color", "value"),
        State("theme-accent-color", "value"),
        State("theme-bg-color", "value"),
        State("theme-bg-image", "value"),
        State("theme-orientation", "value"),
        State("theme-security-options", "value"),
        State("theme-security-watermark", "value"),
        prevent_initial_call=True,
    )
    def apply_theme(_n, payload, family, size, font_color, accent, bg, bg_image, orientation, sec_opts, sec_watermark):
        if not payload:
            return no_update, no_update, _status("Load or preview JSON first.", "warning")
        new_payload = copy.deepcopy(payload)
        template = new_payload.setdefault("template", {})
        font_cfg = template.setdefault("font", {})
        if family:
            font_cfg["family"] = family
        if size:
            font_cfg["size"] = size
        if font_color:
            font_cfg["color"] = font_color
        if accent:
            template["accent_color"] = accent
        page_cfg = template.setdefault("page", {})
        if bg:
            page_cfg["background_color"] = bg
        if bg_image:
            page_cfg["background_image"] = bg_image
        if orientation:
            page_cfg["orientation"] = orientation
            # Provide sensible widths based on orientation
            page_cfg["width"] = "1200px" if orientation == "landscape" else "900px"
        security_cfg = template.setdefault("security", {})
        if isinstance(sec_opts, list):
            security_cfg["options"] = sec_opts
        if sec_watermark is not None:
            security_cfg["watermark"] = sec_watermark
        return new_payload, _dump(new_payload), _status("Theme updated.", "success")

    @app.callback(
        Output("payload-store", "data", allow_duplicate=True),
        Output("template-json-input", "value", allow_duplicate=True),
        Output("feedback", "children", allow_duplicate=True),
        Input("update-text-btn", "n_clicks"),
        State("selection-store", "data"),
        State("selected-text-input", "value"),
        State("payload-store", "data"),
        prevent_initial_call=True,
    )
    def update_text(_n, selection, text_value, payload):
        if not payload or not selection or not selection.get("path"):
            return no_update, no_update, _status("Click a field to edit its text.", "warning")
        new_payload = copy.deepcopy(payload)
        path = selection.get("path")
        role = selection.get("role")
        template = new_payload.setdefault("template", {})
        if role in ("label", "header", "total-label"):
            if role == "header":
                try:
                    section_idx = int(selection.get("section", 0))
                    col_idx = int(selection.get("col_idx", 0))
                    template["sections"][section_idx]["columns"][col_idx]["label"] = text_value or ""
                except Exception:
                    pass
            elif role == "total-label":
                try:
                    section_idx = int(selection.get("section", 0))
                    t_idx = int(selection.get("total_idx", 0))
                    template["sections"][section_idx]["totals"][t_idx]["label"] = text_value or ""
                except Exception:
                    pass
            else:
                _update_field_label(template, path, text_value or "")
        else:
            set_dotted(new_payload.setdefault("data", {}), path, text_value or "")
        return new_payload, _dump(new_payload), _status("Text updated.", "success")

    @app.callback(
        Output("payload-store", "data", allow_duplicate=True),
        Output("template-json-input", "value", allow_duplicate=True),
        Output("feedback", "children", allow_duplicate=True),
        Input("update-style-btn", "n_clicks"),
        State("selection-store", "data"),
        State("selected-text-color", "value"),
        State("selected-text-size", "value"),
        State("selected-text-weight", "value"),
        State("payload-store", "data"),
        prevent_initial_call=True,
    )
    def update_style(_n, selection, color, size, weight, payload):
        if not payload or not selection or not selection.get("path"):
            return no_update, no_update, _status("Click a field to edit its style.", "warning")
        new_payload = copy.deepcopy(payload)
        style_updates = {
            "color": color,
            "fontSize": f"{size}px" if size else None,
            "fontWeight": weight,
        }
        _update_style(new_payload.setdefault("template", {}), selection["path"], style_updates)
        return new_payload, _dump(new_payload), _status("Style updated.", "success")

    @app.callback(
        Output("payload-store", "data", allow_duplicate=True),
        Output("template-json-input", "value", allow_duplicate=True),
        Output("feedback", "children", allow_duplicate=True),
        Input("builder-add-section-btn", "n_clicks"),
        State("builder-section-type", "value"),
        State("builder-section-title", "value"),
        State("builder-grid-columns", "value"),
        State("builder-fields", "value"),
        State("builder-table-data-path", "value"),
        State("builder-table-columns", "value"),
        State("builder-table-totals", "value"),
        State("payload-store", "data"),
        prevent_initial_call=True,
    )
    def add_section(_n, s_type, title, grid_cols, fields_text, table_path, table_cols, table_totals, payload):
        if not _n:
            raise PreventUpdate
        new_payload = copy.deepcopy(payload) if payload else {"template": {"sections": [], "title": "Invoice"}, "data": {}}
        template = new_payload.setdefault("template", {})
        sections = template.setdefault("sections", [])

        title_val = title or "Section"
        if s_type == "table":
            cols = parse_table_columns(table_cols or "")
            totals = parse_table_totals(table_totals or "")
            section = {
                "type": "table",
                "title": title_val,
                "data_path": table_path or "items",
                "columns": cols or [{"label": "Description", "value_path": "description"}],
                "totals": totals,
            }
            sections.append(section)
        elif s_type == "notes":
            fields = parse_field_lines(fields_text or "")
            value_path = fields[0]["value_path"] if fields else "notes"
            section = {"type": "notes", "title": title_val, "value_path": value_path}
            sections.append(section)
        else:
            fields = parse_field_lines(fields_text or "")
            if not fields:
                fields = [{"label": "Field", "value_path": "data.value"}]
            section = {
                "type": "grid",
                "title": title_val,
                "columns": grid_cols or 2,
                "fields": fields,
            }
            sections.append(section)

        return new_payload, _dump(new_payload), _status(f"Added {s_type} section.", "success")

    @app.callback(
        Output("section-order-dropdown", "options"),
        Output("section-order-dropdown", "value"),
        Input("payload-store", "data"),
    )
    def sync_section_dropdown(payload):
        if not payload:
            return [], None
        sections = payload.get("template", {}).get("sections", []) or []
        options = [{"label": sec.get("title", f"Section {idx+1}"), "value": idx} for idx, sec in enumerate(sections)]
        return options, options[0]["value"] if options else None

    @app.callback(
        Output("payload-store", "data", allow_duplicate=True),
        Output("template-json-input", "value", allow_duplicate=True),
        Output("feedback", "children", allow_duplicate=True),
        Input("section-move-up", "n_clicks"),
        Input("section-move-down", "n_clicks"),
        State("section-order-dropdown", "value"),
        State("payload-store", "data"),
        prevent_initial_call=True,
    )
    def move_section(up_clicks, down_clicks, selected_idx, payload):
        if payload is None or selected_idx is None:
            raise PreventUpdate
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        direction = ctx.triggered_id
        sections = copy.deepcopy(payload.get("template", {}).get("sections", []) or [])
        if not sections or selected_idx >= len(sections):
            raise PreventUpdate
        target_idx = selected_idx
        if direction == "section-move-up" and target_idx > 0:
            sections[target_idx - 1], sections[target_idx] = sections[target_idx], sections[target_idx - 1]
            new_selected = target_idx - 1
        elif direction == "section-move-down" and target_idx < len(sections) - 1:
            sections[target_idx + 1], sections[target_idx] = sections[target_idx], sections[target_idx + 1]
            new_selected = target_idx + 1
        else:
            raise PreventUpdate

        new_payload = copy.deepcopy(payload)
        new_payload.setdefault("template", {})["sections"] = sections
        # Also keep dropdown selection in sync via allow_duplicate outputs
        return new_payload, _dump(new_payload), _status("Reordered sections.", "success")

    @app.callback(
        Output("ocr-pdf-pages", "data"),
        Output("ocr-pdf-status", "children"),
        Input("ocr-pdf-upload", "contents"),
        State("ocr-pdf-upload", "filename"),
        prevent_initial_call=True,
    )
    def load_ocr_pdf(contents, filename):
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
        Output("ocr-json-status", "children"),
        Input("ocr-json-upload", "contents"),
        State("ocr-json-upload", "filename"),
        prevent_initial_call=True,
    )
    def load_ocr_json(contents, filename):
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
        Output("ocr-viewer", "children"),
        Output("ocr-viewer-placeholder", "children"),
        Input("ocr-pdf-pages", "data"),
        Input("ocr-items", "data"),
    )
    def render_ocr_viewer(pages, items):
        if not pages and not items:
            return [], "Upload a PDF and OCR JSON to see overlays."
        if not pages:
            return [], "Waiting for PDF..."
        if not items:
            return [], "Waiting for OCR JSON..."

        grouped: Dict[int, List[Dict[str, Any]]] = {}
        for item in items or []:
            page_no = int(item.get("page", 1))
            grouped.setdefault(page_no, []).append(item)

        rendered = []
        for page in pages or []:
            page_no = page.get("page")
            page_items = grouped.get(int(page_no), []) if page_no is not None else []
            rendered.append(_render_ocr_page(page, page_items))
        return rendered, ""

    # ---------- Dataset maker ----------

    def _normalize_page_range(pages_min, pages_max):
        try:
            min_pages = int(pages_min) if pages_min is not None else 1
        except Exception:
            min_pages = 1
        try:
            max_pages = int(pages_max) if pages_max is not None else min_pages
        except Exception:
            max_pages = min_pages
        if min_pages < 1:
            min_pages = 1
        if max_pages < min_pages:
            max_pages = min_pages
        return min_pages, max_pages

    def _build_page_targets(sample_count, pages_min, pages_max):
        count = max(1, int(sample_count or 1))
        min_pages, max_pages = _normalize_page_range(pages_min, pages_max)
        span = max_pages - min_pages + 1
        base = count // span
        remainder = count % span
        targets = []
        for offset in range(span):
            reps = base + (1 if offset < remainder else 0)
            targets.extend([min_pages + offset] * reps)
        return targets

    def _build_prompt_text(
        fonts,
        colors,
        augmentations,
        difficulty,
        variability,
        size_min,
        size_max,
        sample_count,
        languages,
        pages_min,
        pages_max,
    ):
        fonts = fonts or []
        colors = colors or []
        augmentations = augmentations or []
        size_min = size_min or 12
        size_max = size_max or 18
        difficulty = difficulty or 5
        variability = variability or 5
        pages_min, pages_max = _normalize_page_range(pages_min, pages_max)
        aug_text = ", ".join(augmentations) if augmentations else "none"
        font_text = ", ".join(fonts) if fonts else "any"
        color_text = ", ".join(colors) if colors else "any"
        lang_text = ", ".join(languages) if languages else "any language"
        return (
            "Generate a JSON OBJECT only (no prose) when one invoice sample is requested. "
            "Return exactly one sample per request; the caller handles total sample counts. "
            "The top-level keys 'template' and 'data' must be JSON objects, not strings. "
            "Each element must be an object: {\n"
            '  "template": {\n'
            '    "title": string,\n'
            '    "label": string,\n'
            '    "currency": string,\n'
            '    "accent_color": hex,\n'
            '    "security": { "options": [strings], "watermark": string },\n'
            '    "page": { "width": "900px", "height": "auto", "padding": "32px", "background_color": hex, "background_image": "", "border_radius": "18px", "orientation": "portrait|landscape" },\n'
            '    "font": { "family": string, "color": hex, "size": number },\n'
            '    "sections": [\n'
            '      { "type": "grid", "title": string, "columns": 2, "fields": [ { "label": string, "value_path": dotted_path, "format": "currency"|null, "placeholder": string|null } ] },\n'
            '      { "type": "table", "title": string, "data_path": "items", "columns": [ { "label": string, "key": string, "align": "left|center|right", "format": "currency"|null } ], "totals": [ { "label": string, "value_path": dotted_path, "format": "currency"|null } ] },\n'
            '      { "type": "panels", "title": string, "panels": [ { "heading": string, "fields": [ { "label": string, "value_path": dotted_path } ] } ] },\n'
            '      { "type": "notes", "title": string, "value_path": string }\n'
            "    ]\n"
            "  },\n"
            '  "data": {\n'
            '    "invoice": { "number": string, "date": iso-date, "due_date": iso-date, "reference": string },\n'
            '    "seller": { "name": string, "contact": string, "email": string, "address": string },\n'
            '    "client": { "name": string, "contact": string, "email": string, "address": string },\n'
            '    "items": [ { "description": string, "qty": number, "unit_price": number, "line_total": number } ],\n'
            '    "totals": { "subtotal": number, "tax": number, "due": number },\n'
            '    "payment": { "bank": string, "iban": string, "reference": string },\n'
            '    "notes": string\n'
            "  }\n"
            "}. "
            "Totals must match items. Provide varied but realistic content. "
            f"Max variability target {variability}/10: mix {pages_min}-{pages_max} pages by varying item counts (5-50), long/short notes, optional extra rows; shuffle section order; sometimes omit sections (e.g., notes/panels); vary spacing. "
            "Randomize logos/backgrounds with real URLs (e.g., https://picsum.photos/240/80 logos, https://picsum.photos/1200/800 backgrounds), and vary logo placement/size (top-left/right/center, large/small). "
            "Vary page orientation (portrait/landscape), widths/padding, and section titles. "
            "Allow missing/blank fields occasionally. "
            f"Use languages from: {lang_text}. When a prompt specifies 'Target language: <lang>', use only that language in labels and values. "
            f"Target page count range: {pages_min}-{pages_max}. When a prompt specifies 'Target pages: X', adjust content to reach about X pages. "
            "Use fonts that support these scripts (e.g., Noto Sans/Serif SC/JP/KR for CJK, Inter/Manrope/etc. for Latin). "
            f"Allowed font families: {font_text}. "
            f"Text colors palette: {color_text}. "
            f"Text size range: {size_min}-{size_max}px. "
            f"Augmentations to apply later: {aug_text}. "
            f"Difficulty target {difficulty}/10; mix easy/hard evenly (balanced set). "
            "Reply ONLY with the JSON array, no code fences or explanations."
        )

    @app.callback(
        Output("ds-prompt", "value"),
        Input("ds-refresh-prompt", "n_clicks"),
        State("ds-fonts", "value"),
        State("ds-colors", "value"),
        State("ds-augmentations", "value"),
        State("ds-difficulty", "value"),
        State("ds-variability", "value"),
        State("ds-pages-min", "value"),
        State("ds-pages-max", "value"),
        State("ds-size-min", "value"),
        State("ds-size-max", "value"),
        State("ds-sample-count", "value"),
        State("ds-languages", "value"),
        prevent_initial_call=True,
    )
    def refresh_prompt(
        _n,
        fonts,
        colors,
        augmentations,
        difficulty,
        variability,
        pages_min,
        pages_max,
        s_min,
        s_max,
        sample_count,
        languages,
    ):
        return _build_prompt_text(
            fonts,
            colors,
            augmentations,
            difficulty,
            variability,
            s_min,
            s_max,
            sample_count,
            languages,
            pages_min,
            pages_max,
        )

    def _call_openai(api_key: str, model: str, prompt: str, max_tokens: int = 1500):
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("openai package not installed. Add it to requirements and pip install.") from exc

        client = OpenAI(api_key=api_key)
        messages = [
            {
                "role": "system",
                "content": (
                    "You generate invoice datasets. Reply ONLY with a valid JSON object with keys "
                    "'template' and 'data'. Do not include any prose or code fences."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "response_format" in msg or "json_object" in msg:
                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=max_tokens,
                    )
                except Exception as exc2:  # noqa: BLE001
                    raise RuntimeError(f"OpenAI request failed: {exc2}") from exc2
            else:
                raise RuntimeError(f"OpenAI request failed: {exc}") from exc

        content = resp.choices[0].message.content if resp and resp.choices else ""
        if not content:
            raise RuntimeError("OpenAI returned empty content.")
        usage = getattr(resp, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
        print(f"[Dataset] OpenAI response received. Prompt tokens: {prompt_tokens}, Completion tokens: {completion_tokens}")
        return content, prompt_tokens, completion_tokens

    def _parse_llm_json(content: str):
        """Robustly parse LLM output that should be a JSON array."""
        def _strip_code_fence(txt: str) -> str:
            txt = txt.strip()
            if txt.startswith("```"):
                # remove leading ```json or ``` and trailing ```
                txt = re.sub(r"^```[a-zA-Z0-9]*", "", txt).strip()
                if txt.endswith("```"):
                    txt = txt[: -3].strip()
            return txt

        content = _strip_code_fence(content)

        try:
            return json.loads(content)
        except Exception:
            pass

        # Try first array block
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            snippet = _strip_code_fence(match.group(0))
            try:
                return json.loads(snippet)
            except Exception:
                pass

        # Try slice from first '[' to last ']'
        first = content.find("[")
        last = content.rfind("]")
        if first != -1 and last != -1 and last > first:
            snippet = _strip_code_fence(content[first : last + 1])
            try:
                return json.loads(snippet)
            except Exception:
                pass

        # Try first object block
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            snippet = _strip_code_fence(match.group(0))
            try:
                return json.loads(snippet)
            except Exception:
                pass

        # Try slice from first '{' to last '}'
        first = content.find("{")
        last = content.rfind("}")
        if first != -1 and last != -1 and last > first:
            snippet = _strip_code_fence(content[first : last + 1])
            try:
                return json.loads(snippet)
            except Exception:
                pass

        # Last resort: bracket-matching scan to extract top-level array
        in_str = False
        esc = False
        depth = 0
        start_idx = None
        for i, ch in enumerate(content):
            if ch == "\\" and not esc:
                esc = True
                continue
            if ch in ("'", '"') and not esc:
                in_str = not in_str
            if not in_str:
                if ch == "[":
                    if depth == 0:
                        start_idx = i
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0 and start_idx is not None:
                        snippet = content[start_idx : i + 1]
                        try:
                            return json.loads(_strip_code_fence(snippet))
                        except Exception:
                            pass
            esc = False

        # Last resort: bracket-matching scan to extract top-level object
        in_str = False
        esc = False
        depth = 0
        start_idx = None
        for i, ch in enumerate(content):
            if ch == "\\" and not esc:
                esc = True
                continue
            if ch in ("'", '"') and not esc:
                in_str = not in_str
            if not in_str:
                if ch == "{":
                    if depth == 0:
                        start_idx = i
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0 and start_idx is not None:
                        snippet = content[start_idx : i + 1]
                        try:
                            return json.loads(_strip_code_fence(snippet))
                        except Exception:
                            pass
            esc = False

        raise RuntimeError("LLM JSON could not be parsed. Ensure the response is valid JSON.")

    def _ensure_dir(path_str: str) -> pathlib.Path:
        path = pathlib.Path(path_str).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _truncate_message(msg: str, limit: int = 180) -> str:
        if not msg:
            return ""
        clean = " ".join(str(msg).split())
        return clean if len(clean) <= limit else f"{clean[: limit - 3]}..."

    def _find_template_payload(obj):
        if isinstance(obj, dict):
            if "template" in obj and "data" in obj:
                return obj
            for value in obj.values():
                found = _find_template_payload(value)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for value in obj:
                found = _find_template_payload(value)
                if found is not None:
                    return found
        return None

    def _extract_sample(parsed):
        if isinstance(parsed, list):
            if not parsed:
                return None, "parsed JSON list is empty"
            candidate = parsed[0]
        elif isinstance(parsed, dict):
            candidate = parsed
        else:
            return None, f"parsed JSON is {type(parsed).__name__}, not object or list"

        if isinstance(candidate, dict):
            for key in ("sample", "payload", "result"):
                if isinstance(candidate.get(key), dict):
                    candidate = candidate[key]
                    break

        found = _find_template_payload(candidate)
        if found is None:
            return None, "missing top-level 'template' and 'data' keys"
        return found, ""

    def _parse_jsonish(value, label):
        if not isinstance(value, str):
            return value, ""
        try:
            parsed = json.loads(value)
        except Exception:
            try:
                parsed = _parse_llm_json(value)
            except Exception as exc:
                return None, f"{label} is a string and could not be parsed: {exc}"
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            parsed = parsed[0]
        return parsed, ""

    def _coerce_payload(sample):
        if not isinstance(sample, dict):
            return None, "sample is not a JSON object"
        template = sample.get("template")
        data = sample.get("data")
        template, err = _parse_jsonish(template, "template")
        if err:
            return None, err
        found = _find_template_payload(template) if isinstance(template, (dict, list)) else None
        if found is not None:
            return _coerce_payload(found)
        data, err = _parse_jsonish(data, "data")
        if err:
            return None, err
        found = _find_template_payload(data) if isinstance(data, (dict, list)) else None
        if found is not None:
            return _coerce_payload(found)
        if not isinstance(template, dict):
            return None, f"template is {type(template).__name__}, expected object"
        if not isinstance(data, dict):
            return None, f"data is {type(data).__name__}, expected object"
        return {"template": template, "data": data}, ""

    _JOBS: Dict[str, Dict[str, Any]] = {}
    _JOBS_LOCK = threading.Lock()

    def _run_dataset_job(
        job_id: str,
        api_key: str,
        model: str,
        prompt_text: str,
        output_dir: str,
        sample_count: int,
        languages,
        pages_min,
        pages_max,
    ):
        target_dir = _ensure_dir(output_dir)
        lang_list = [lang for lang in (languages or []) if lang] or ["any"]
        per_language = max(1, int(sample_count or 1))
        pages_min, pages_max = _normalize_page_range(pages_min, pages_max)
        page_targets = _build_page_targets(per_language, pages_min, pages_max)
        total_samples = per_language * len(lang_list)
        total_prompt_tokens = 0
        total_completion_tokens = 0
        log_preview: List[str] = []
        written = 0
        errors = 0
        last_error = ""

        sample_idx = 0
        for lang in lang_list:
            for lang_idx in range(per_language):
                sample_idx += 1
                target_pages = page_targets[lang_idx]
                single_prompt = (
                    prompt_text
                    + "\\nReturn exactly one sample as a JSON object."
                    + "\\nThe JSON object must have top-level keys 'template' and 'data'."
                    + f"\\nTarget language: {lang}. Use only this language for labels and values."
                    + f"\\nTarget pages: {target_pages}. Adjust item counts/notes/sections to reach about this many pages."
                )
                def _request_sample(prompt: str, suffix: str):
                    max_tokens = min(3500, 1200 + target_pages * 350)
                    llm_response, prompt_tokens, completion_tokens = _call_openai(
                        api_key, model, prompt, max_tokens=max_tokens
                    )
                    total_tokens = (prompt_tokens or 0, completion_tokens or 0)
                    raw_name = f"llm_response_raw_{sample_idx:03d}{suffix}.txt"
                    (target_dir / raw_name).write_text(llm_response, encoding="utf-8")
                    parsed = _parse_llm_json(llm_response)
                    sample, reason = _extract_sample(parsed)
                    return sample, reason, raw_name, total_tokens

                def _attempt_payload(prompt: str, suffix: str):
                    sample, reason, raw_name, tokens = _request_sample(prompt, suffix)
                    if sample is None:
                        return None, reason, raw_name, tokens
                    payload, reason = _coerce_payload(sample)
                    if payload is None:
                        return None, reason, raw_name, tokens
                    return payload, "", raw_name, tokens

                try:
                    payload, reason, raw_name, tokens = _attempt_payload(single_prompt, "")
                    total_prompt_tokens += tokens[0]
                    total_completion_tokens += tokens[1]
                except Exception as exc:
                    errors += 1
                    last_error = f"sample {sample_idx} request/parse: {exc}"
                    print(f"[Dataset] Sample {sample_idx} failed to parse or request: {exc}")
                    (target_dir / f"sample_{sample_idx:03d}_error.txt").write_text(
                        f"{last_error}\n\n{traceback.format_exc()}",
                        encoding="utf-8",
                    )
                    with _JOBS_LOCK:
                        _JOBS[job_id].update(
                            {
                                "written": written,
                                "errors": errors,
                                "total": total_samples,
                                "log_preview": log_preview.copy(),
                                "prompt_tokens": total_prompt_tokens,
                                "completion_tokens": total_completion_tokens,
                                "last_error": last_error,
                            }
                        )
                    continue

                if payload is None:
                    retry_prompt = (
                        "Your previous response was invalid. Return ONLY one JSON object with top-level keys "
                        "'template' and 'data'. Do not wrap it in any other keys or arrays. "
                        "Both 'template' and 'data' must be JSON objects, not strings. No prose."
                        f" Target language: {lang}. Target pages: {target_pages}."
                    )
                    try:
                        payload, reason, retry_raw, tokens = _attempt_payload(retry_prompt, "_retry")
                        total_prompt_tokens += tokens[0]
                        total_completion_tokens += tokens[1]
                        raw_name = retry_raw
                    except Exception as exc:
                        errors += 1
                        last_error = f"sample {sample_idx} retry failed: {exc}"
                        print(f"[Dataset] Sample {sample_idx} retry failed: {exc}")
                        (target_dir / f"sample_{sample_idx:03d}_error.txt").write_text(
                            f"{last_error}\n\n{traceback.format_exc()}",
                            encoding="utf-8",
                        )
                        with _JOBS_LOCK:
                            _JOBS[job_id].update(
                                {
                                    "written": written,
                                    "errors": errors,
                                    "total": total_samples,
                                    "log_preview": log_preview.copy(),
                                    "prompt_tokens": total_prompt_tokens,
                                    "completion_tokens": total_completion_tokens,
                                    "last_error": last_error,
                                }
                            )
                        continue

                if payload is None:
                    errors += 1
                    last_error = f"sample {sample_idx} invalid: {reason}"
                    print(f"[Dataset] Sample {sample_idx} invalid: {reason}")
                    (target_dir / f"sample_{sample_idx:03d}_error.txt").write_text(
                        f"{last_error}\nRaw response file: {raw_name}",
                        encoding="utf-8",
                    )
                    with _JOBS_LOCK:
                        _JOBS[job_id].update(
                            {
                                "written": written,
                                "errors": errors,
                                "total": total_samples,
                                "log_preview": log_preview.copy(),
                                "prompt_tokens": total_prompt_tokens,
                                "completion_tokens": total_completion_tokens,
                                "last_error": last_error,
                            }
                        )
                    continue
                try:
                    html_str = build_html_export(payload)
                    pdf_bytes = html_to_pdf_bytes(
                        html_str, orientation=payload.get("template", {}).get("page", {}).get("orientation", "portrait")
                    )
                    ocr_json = build_ocr_ground_truth(pdf_bytes)
                    base_name = f"sample_{sample_idx:03d}_{uuid.uuid4().hex[:6]}"
                    (target_dir / f"{base_name}.json").write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    (target_dir / f"{base_name}.pdf").write_bytes(pdf_bytes)
                    (target_dir / f"{base_name}.ocr.json").write_text(ocr_json, encoding="utf-8")
                    written += 1
                    if len(log_preview) < 2:
                        log_preview.append(json.dumps(payload, ensure_ascii=False, indent=2))
                except Exception as exc:
                    errors += 1
                    last_error = f"sample {sample_idx} render/save: {exc}"
                    print(f"[Dataset] Sample {sample_idx} failed during render/save: {exc}")
                    (target_dir / f"sample_{sample_idx:03d}_failed.json").write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    (target_dir / f"sample_{sample_idx:03d}_error.txt").write_text(
                        f"{last_error}\n\n{traceback.format_exc()}",
                        encoding="utf-8",
                    )
                    continue

                with _JOBS_LOCK:
                    _JOBS[job_id].update(
                        {
                            "written": written,
                            "errors": errors,
                            "total": total_samples,
                            "log_preview": log_preview.copy(),
                            "prompt_tokens": total_prompt_tokens,
                            "completion_tokens": total_completion_tokens,
                            "last_error": last_error,
                        }
                    )

        with _JOBS_LOCK:
            _JOBS[job_id].update(
                {
                    "written": written,
                    "errors": errors,
                    "total": total_samples,
                    "done": True,
                    "log_preview": log_preview.copy(),
                    "prompt_tokens": total_prompt_tokens,
                    "completion_tokens": total_completion_tokens,
                    "last_error": last_error,
                }
            )

    @app.callback(
        Output("ds-status", "children", allow_duplicate=True),
        Output("ds-progress", "value", allow_duplicate=True),
        Output("ds-log", "children", allow_duplicate=True),
        Output("ds-job-id", "data", allow_duplicate=True),
        Input("ds-generate", "n_clicks"),
        State("ds-api-key", "value"),
        State("ds-model", "value"),
        State("ds-prompt", "value"),
        State("ds-output-path", "value"),
        State("ds-sample-count", "value"),
        State("ds-languages", "value"),
        State("ds-variability", "value"),
        State("ds-pages-min", "value"),
        State("ds-pages-max", "value"),
        prevent_initial_call=True,
    )
    def start_dataset_job(
        _n,
        api_key,
        model,
        prompt_text,
        output_dir,
        sample_count,
        languages,
        variability,
        pages_min,
        pages_max,
    ):
        try:
            if not api_key or not model:
                return _status("Provide API key and model to generate.", "warning"), "0", "", None
            if not output_dir:
                return _status("Set an output directory first.", "warning"), "0", "", None
            if not prompt_text:
                return _status("Create or paste a prompt first.", "warning"), "0", "", None

            lang_list = [lang for lang in (languages or []) if lang] or ["any"]
            per_language = max(1, int(sample_count or 1))
            total_samples = per_language * len(lang_list)
            job_id = uuid.uuid4().hex
            print(f"[Dataset] Starting job {job_id} for {per_language} per language ({total_samples} total)")
            with _JOBS_LOCK:
                _JOBS[job_id] = {
                    "written": 0,
                    "errors": 0,
                    "total": total_samples,
                    "done": False,
                    "log_preview": [],
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "last_error": "",
                }

            thread = threading.Thread(
                target=_run_dataset_job,
                args=(
                    job_id,
                    api_key,
                    model,
                    prompt_text,
                    output_dir,
                    per_language,
                    lang_list,
                    pages_min,
                    pages_max,
                ),
                daemon=True,
            )
            thread.start()
            return _status("Generation started...", "info"), "0", "", job_id
        except Exception as exc:  # noqa: BLE001
            print(f"[Dataset] Failed to start job: {exc}")
            return _status(f"Failed to start: {exc}", "danger"), "0", "", None

    @app.callback(
        Output("ds-status", "children", allow_duplicate=True),
        Output("ds-progress", "value", allow_duplicate=True),
        Output("ds-log", "children", allow_duplicate=True),
        Input("ds-progress-interval", "n_intervals"),
        State("ds-job-id", "data"),
        prevent_initial_call=True,
    )
    def poll_dataset_job(_n, job_id):
        if not job_id:
            print("[Dataset] Poll: no job id")
            return _status("Idle.", "info"), "0", ""
        with _JOBS_LOCK:
            info = _JOBS.get(job_id)
        if not info:
            print(f"[Dataset] Poll: job {job_id} not found")
            return _status("Idle.", "info"), "0", ""
        total = info.get("total", 1) or 1
        written = info.get("written", 0)
        errors = info.get("errors", 0)
        prompt_tokens = info.get("prompt_tokens", 0)
        completion_tokens = info.get("completion_tokens", 0)
        progress = int((written + errors) / total * 100)
        log_preview = info.get("log_preview", [])
        log_text = "\\n\\n".join(log_preview)
        last_error = info.get("last_error", "")
        error_note = f" Last error: { _truncate_message(last_error) }" if last_error else ""
        status = _status(
            f"Progress: {written}/{total} (errors: {errors}). Tokens: prompt_total={prompt_tokens}, completion_total={completion_tokens}.{error_note}",
            "info" if not info.get("done") else ("success" if errors == 0 else "warning"),
        )
        if info.get("done"):
            print(f"[Dataset] Job {job_id} done. Written {written}, errors {errors}")
            with _JOBS_LOCK:
                _JOBS.pop(job_id, None)
        return status, str(progress), log_text

    # ---------- Model evaluation ----------

    _EVAL_JOBS: Dict[str, Dict[str, Any]] = {}
    _EVAL_LOCK = threading.Lock()

    def _build_eval_methods(ocr_sources, methods, models):
        method_list = []
        if "regex" in methods:
            for src in ocr_sources:
                method_list.append({"name": f"{src}-regex", "kind": "regex", "ocr_source": src})
        if "key_value" in methods:
            for src in ocr_sources:
                method_list.append({"name": f"{src}-kv", "kind": "key_value", "ocr_source": src})
        if "pattern" in methods:
            for src in ocr_sources:
                method_list.append({"name": f"{src}-pattern", "kind": "pattern", "ocr_source": src})
        if "ensemble" in methods:
            for src in ocr_sources:
                method_list.append({"name": f"{src}-ensemble", "kind": "ensemble", "ocr_source": src})
        if "llm_text" in methods:
            for src in ocr_sources:
                for model in models:
                    method_list.append(
                        {"name": f"{src}-llm-{model}", "kind": "llm_text", "ocr_source": src, "model": model}
                    )
        if "llm_text_hybrid" in methods:
            for src in ocr_sources:
                for model in models:
                    method_list.append(
                        {
                            "name": f"{src}-llm-hybrid-{model}",
                            "kind": "llm_text_hybrid",
                            "ocr_source": src,
                            "model": model,
                        }
                    )
        if "llm_vision" in methods:
            for model in models:
                method_list.append({"name": f"vision-llm-{model}", "kind": "llm_vision", "model": model})
        return method_list

    def _format_eval_summary(results: Dict[str, Any]) -> str:
        lines = []
        for method, data in results.items():
            overall = data.get("overall", {})
            fields = data.get("fields", {})
            worst = sorted(
                fields.items(),
                key=lambda kv: kv[1].get("normalized_rate", 1.0)
                if kv[1].get("normalized_rate") is not None
                else 1.0,
            )[:5]
            worst_text = ", ".join(
                [
                    f"{info.get('label', path)} ({info.get('normalized_rate', 0.0) or 0.0:.2f})"
                    for path, info in worst
                ]
            )
            item_acc = overall.get("item_field_accuracy", {})
            item_text = (
                ", ".join([f"{k}: {(v or 0.0):.2f}" for k, v in item_acc.items()]) if item_acc else "n/a"
            )
            lines.extend(
                [
                    f"### {method}",
                    f"- Samples: {overall.get('sample_count', 0)}",
                    f"- Exact match (macro): {(overall.get('exact_macro') or 0.0):.2f}",
                    f"- Normalized match (macro): {(overall.get('normalized_macro') or 0.0):.2f}",
                    f"- Token F1 (macro): {(overall.get('token_f1_macro') or 0.0):.2f}",
                    f"- Char similarity (macro): {(overall.get('char_similarity_macro') or 0.0):.2f}",
                    f"- Item precision/recall/F1: {(overall.get('item_precision') or 0.0):.2f} / {(overall.get('item_recall') or 0.0):.2f} / {(overall.get('item_f1') or 0.0):.2f}",
                    f"- Item field accuracy: {item_text}",
                    f"- Worst fields (normalized): {worst_text if worst_text else 'n/a'}",
                    "",
                ]
            )
        return "\n".join(lines).strip()

    def _format_eval_errors(results: Dict[str, Any]) -> str:
        lines = []
        for method, data in results.items():
            lines.append(method)
            fields = data.get("fields", {})
            worst = sorted(
                fields.items(),
                key=lambda kv: kv[1].get("normalized_rate", 1.0)
                if kv[1].get("normalized_rate") is not None
                else 1.0,
            )[:4]
            errors = data.get("errors", {})
            for path, info in worst:
                examples = errors.get(path, [])[:2]
                if not examples:
                    continue
                lines.append(f"  {info.get('label', path)} ({path})")
                for ex in examples:
                    gt = str(ex.get("gt", ""))
                    pred = str(ex.get("pred", ""))
                    lines.append(f"    {ex.get('sample', '')}: gt='{gt}' | pred='{pred}'")
            lines.append("")
        return "\n".join(lines).strip()

    def _format_runtime_errors(errors: List[str]) -> str:
        if not errors:
            return ""
        return "\n".join(errors[-50:])

    def _parse_eval_results(results_data: Any) -> Dict[str, Any]:
        if not results_data:
            return {}
        payload = results_data
        if isinstance(results_data, str):
            try:
                payload = json.loads(results_data)
            except Exception:
                return {}
        if isinstance(payload, dict) and isinstance(payload.get("results"), dict):
            return payload.get("results", {})
        return payload if isinstance(payload, dict) else {}

    def _build_eval_figures(results: Dict[str, Any]) -> Dict[str, Any]:
        if not results:
            return {
                "overall": go.Figure(),
                "items": go.Figure(),
                "fields": go.Figure(),
                "item_fields": go.Figure(),
            }
        methods = list(results.keys())
        overall_metrics = [
            ("exact_macro", "Exact macro"),
            ("normalized_macro", "Normalized macro"),
            ("token_f1_macro", "Token F1 macro"),
            ("char_similarity_macro", "Char similarity macro"),
        ]
        fig_overall = go.Figure()
        for key, label in overall_metrics:
            fig_overall.add_trace(
                go.Bar(
                    name=label,
                    x=methods,
                    y=[results[m].get("overall", {}).get(key, 0.0) or 0.0 for m in methods],
                    text=[f"{(results[m].get('overall', {}).get(key) or 0.0):.2f}" for m in methods],
                    textposition="auto",
                )
            )
        fig_overall.update_layout(
            title="Overall metrics (macro)",
            barmode="group",
            yaxis=dict(range=[0, 1], tickformat=".2f"),
            legend_title_text="Metric",
        )

        item_metrics = [("item_precision", "Item precision"), ("item_recall", "Item recall"), ("item_f1", "Item F1")]
        fig_items = go.Figure()
        for key, label in item_metrics:
            fig_items.add_trace(
                go.Bar(
                    name=label,
                    x=methods,
                    y=[results[m].get("overall", {}).get(key, 0.0) or 0.0 for m in methods],
                    text=[f"{(results[m].get('overall', {}).get(key) or 0.0):.2f}" for m in methods],
                    textposition="auto",
                )
            )
        fig_items.update_layout(
            title="Item metrics",
            barmode="group",
            yaxis=dict(range=[0, 1], tickformat=".2f"),
            legend_title_text="Metric",
        )

        sample_method = methods[0]
        fields_data = results[sample_method].get("fields", {})
        field_paths = list(fields_data.keys())
        field_labels = [fields_data[path].get("label", path) for path in field_paths]
        z_vals = []
        custom = []
        for path in field_paths:
            row = []
            custom_row = []
            for method in methods:
                info = results[method].get("fields", {}).get(path, {})
                if info.get("normalized_rate") is None:
                    row.append(None)
                else:
                    row.append(info.get("normalized_rate", 0.0))
                custom_row.append(
                    [
                        info.get("exact_rate", 0.0) or 0.0,
                        info.get("token_f1", 0.0) or 0.0,
                        info.get("char_similarity", 0.0) or 0.0,
                        info.get("present_rate", 0.0) or 0.0,
                    ]
                )
            z_vals.append(row)
            custom.append(custom_row)
        fig_fields = go.Figure(
            data=go.Heatmap(
                z=z_vals,
                x=methods,
                y=field_labels,
                customdata=custom,
                colorscale="Blues",
                zmin=0,
                zmax=1,
                hovertemplate=(
                    "Method: %{x}<br>Field: %{y}<br>"
                    "Normalized: %{z:.2f}<br>"
                    "Exact: %{customdata[0]:.2f}<br>"
                    "Token F1: %{customdata[1]:.2f}<br>"
                    "Char sim: %{customdata[2]:.2f}<br>"
                    "Present: %{customdata[3]:.2f}<extra></extra>"
                ),
            )
        )
        fig_fields.update_layout(
            title="Field normalized match (hover shows more metrics)",
            yaxis_autorange="reversed",
            height=max(420, 22 * len(field_labels)),
        )

        item_field_keys = list(results[sample_method].get("overall", {}).get("item_field_accuracy", {}).keys())
        if item_field_keys:
            item_z = [
                [
                    results[m].get("overall", {}).get("item_field_accuracy", {}).get(key, 0.0) or 0.0
                    for m in methods
                ]
                for key in item_field_keys
            ]
            fig_item_fields = go.Figure(
                data=go.Heatmap(
                    z=item_z,
                    x=methods,
                    y=item_field_keys,
                    colorscale="Viridis",
                    zmin=0,
                    zmax=1,
                    hovertemplate="Method: %{x}<br>Field: %{y}<br>Accuracy: %{z:.2f}<extra></extra>",
                )
            )
            fig_item_fields.update_layout(
                title="Item field accuracy",
                yaxis_autorange="reversed",
                height=max(320, 40 * len(item_field_keys)),
            )
        else:
            fig_item_fields = go.Figure()

        return {
            "overall": fig_overall,
            "items": fig_items,
            "fields": fig_fields,
            "item_fields": fig_item_fields,
        }

    def _figures_to_html(figures: Dict[str, Any]) -> str:
        sections = []
        order = [
            ("Overall metrics (macro)", figures.get("overall")),
            ("Item metrics", figures.get("items")),
            ("Field normalized match", figures.get("fields")),
            ("Item field accuracy", figures.get("item_fields")),
        ]
        first = True
        for title, fig in order:
            if fig is None:
                continue
            include_js = "cdn" if first else False
            first = False
            fig_html = pio.to_html(fig, include_plotlyjs=include_js, full_html=False)
            sections.append(f"<h2>{title}</h2>{fig_html}")
        body = "\n".join(sections)
        return (
            "<html><head><meta charset=\"utf-8\"/>"
            "<title>Evaluation plots</title>"
            "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:20px}h2{margin-top:28px}</style>"
            "</head><body>"
            "<h1>Evaluation plots</h1>"
            f"{body}"
            "</body></html>"
        )

    def _run_eval_job(job_id: str, config: Dict[str, Any]):
        dataset_path = Path(config["dataset_path"])
        samples = evaluation.list_dataset_samples(dataset_path)
        if config.get("shuffle"):
            rng = random.Random(config.get("seed", 0))
            rng.shuffle(samples)
        limit = config.get("sample_limit")
        if limit:
            samples = samples[: int(limit)]
        methods = config["methods"]
        total_steps = max(1, len(methods) * len(samples))
        results: Dict[str, Any] = {}
        aggregates = {method["name"]: evaluation.init_aggregate() for method in methods}

        done_steps = 0
        for sample in samples:
            text_cache: Dict[str, str] = {}
            images_cache = None
            for method in methods:
                try:
                    model_override = {}
                    if method.get("model"):
                        model_override = config.get("model_overrides", {}).get(method["model"], {})
                    method_api_key = model_override.get("api_key") or config.get("api_key")
                    method_api_base = model_override.get("api_base_url") or config.get("api_base_url")
                    if method["kind"] in ("regex", "key_value", "pattern", "ensemble", "llm_text", "llm_text_hybrid"):
                        src = method.get("ocr_source")
                        if src not in text_cache:
                            if src == "pymupdf":
                                text_cache[src] = evaluation.extract_text_pymupdf(sample["pdf_path"])
                            elif src == "tesseract":
                                text_cache[src] = evaluation.extract_text_tesseract(sample["pdf_path"])
                            elif src == "easyocr":
                                text_cache[src] = evaluation.extract_text_easyocr(sample["pdf_path"])
                            elif src == "ocr_json":
                                text_cache[src] = evaluation.extract_text_from_ocr_json(sample["ocr_path"])
                            else:
                                text_cache[src] = ""
                        if method["kind"] == "regex":
                            pred = evaluation.regex_extract(text_cache[src])
                        elif method["kind"] == "key_value":
                            pred = evaluation.kv_extract(text_cache[src])
                        elif method["kind"] == "pattern":
                            pred = evaluation.pattern_extract(text_cache[src])
                        elif method["kind"] == "ensemble":
                            pred = evaluation.ensemble_extract(text_cache[src])
                        elif method["kind"] == "llm_text_hybrid":
                            pred = evaluation.llm_extract_text(
                                method_api_key,
                                method["model"],
                                text_cache[src],
                                api_base_url=method_api_base,
                                gemini_api_key=config.get("gemini_api_key"),
                                anthropic_api_key=config.get("anthropic_api_key"),
                            )
                            fallback = evaluation.pattern_extract(text_cache[src])
                            pred = evaluation.merge_missing_fields(pred, fallback)
                        else:
                            pred = evaluation.llm_extract_text(
                                method_api_key,
                                method["model"],
                                text_cache[src],
                                api_base_url=method_api_base,
                                gemini_api_key=config.get("gemini_api_key"),
                                anthropic_api_key=config.get("anthropic_api_key"),
                            )
                    else:
                        if images_cache is None:
                            images_cache = evaluation.images_for_llm(sample["pdf_path"], config.get("max_pages", 2))
                        pred = evaluation.llm_extract_vision(
                            method_api_key,
                            method["model"],
                            images_cache,
                            api_base_url=method_api_base,
                            gemini_api_key=config.get("gemini_api_key"),
                            anthropic_api_key=config.get("anthropic_api_key"),
                        )
                except Exception as exc:  # noqa: BLE001
                    pred = {}
                    with _EVAL_LOCK:
                        _EVAL_JOBS[job_id]["errors"].append(f"{method['name']} {sample['id']}: {exc}")

                visible_paths = sample.get("visible_paths") if config.get("visible_only") else None
                items_visible = sample.get("items_visible") if config.get("visible_only") else None
                sample_result = evaluation.evaluate_prediction(
                    sample["data"],
                    pred,
                    sample["id"],
                    visible_paths=visible_paths,
                    items_visible=items_visible,
                )
                evaluation.update_aggregate(aggregates[method["name"]], sample_result)
                done_steps += 1
                with _EVAL_LOCK:
                    _EVAL_JOBS[job_id].update(
                        {
                            "done_steps": done_steps,
                            "total_steps": total_steps,
                            "current_method": method["name"],
                            "current_sample": sample["id"],
                        }
                    )

        for method in methods:
            results[method["name"]] = evaluation.finalize_aggregate(aggregates[method["name"]])

        summary = _format_eval_summary(results)
        errors_text = _format_eval_errors(results)
        plots_path = None
        if config.get("save_plots"):
            try:
                figures = _build_eval_figures(results)
                html_content = _figures_to_html(figures)
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                plots_path = dataset_path / f"evaluation_plots_{stamp}.html"
                plots_path.write_text(html_content, encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                with _EVAL_LOCK:
                    _EVAL_JOBS[job_id]["errors"].append(f"plots: {exc}")
        if plots_path:
            plots_line = f"Saved plots: `{plots_path}`"
            summary = f"{summary}\n\n{plots_line}" if summary else plots_line
        with _EVAL_LOCK:
            _EVAL_JOBS[job_id].update(
                {
                    "done": True,
                    "results": results,
                    "summary": summary,
                    "errors_text": errors_text,
                    "plots_path": str(plots_path) if plots_path else None,
                }
            )

    @app.callback(
        Output("eval-status", "children", allow_duplicate=True),
        Output("eval-progress", "value", allow_duplicate=True),
        Output("eval-summary", "children", allow_duplicate=True),
        Output("eval-errors", "children", allow_duplicate=True),
        Output("eval-runtime-errors", "children", allow_duplicate=True),
        Output("eval-graph-overall", "figure", allow_duplicate=True),
        Output("eval-graph-items", "figure", allow_duplicate=True),
        Output("eval-graph-fields", "figure", allow_duplicate=True),
        Output("eval-graph-item-fields", "figure", allow_duplicate=True),
        Output("eval-job-id", "data", allow_duplicate=True),
        Output("eval-results-store", "data", allow_duplicate=True),
        Input("eval-run", "n_clicks"),
        State("eval-dataset-path", "value"),
        State("eval-sample-limit", "value"),
        State("eval-shuffle", "value"),
        State("eval-seed", "value"),
        State("eval-visible-only", "value"),
        State("eval-save-plots", "value"),
        State("eval-ocr-sources", "value"),
        State("eval-methods", "value"),
        State("eval-api-key", "value"),
        State("eval-api-base-url", "value"),
        State("eval-api-key-alt", "value"),
        State("eval-api-base-url-alt", "value"),
        State("eval-api-key-alt-match", "value"),
        State("eval-gemini-api-key", "value"),
        State("eval-anthropic-api-key", "value"),
        State("eval-llm-models", "value"),
        State("eval-custom-models", "value"),
        State("eval-max-pages", "value"),
        prevent_initial_call=True,
    )
    def start_eval_job(
        _n,
        dataset_path,
        sample_limit,
        shuffle,
        seed,
        visible_only,
        save_plots,
        ocr_sources,
        methods,
        api_key,
        api_base_url,
        api_key_alt,
        api_base_url_alt,
        api_key_alt_match,
        gemini_api_key,
        anthropic_api_key,
        models,
        custom_models,
        max_pages,
    ):
        empty_figs = _build_eval_figures({})
        if not dataset_path:
            return (
                _status("Pick a dataset first.", "warning"),
                "0",
                "",
                "",
                "",
                empty_figs["overall"],
                empty_figs["items"],
                empty_figs["fields"],
                empty_figs["item_fields"],
                None,
                None,
            )
        samples = evaluation.list_dataset_samples(Path(dataset_path))
        if not samples:
            return (
                _status("No dataset samples found.", "warning"),
                "0",
                "",
                "",
                "",
                empty_figs["overall"],
                empty_figs["items"],
                empty_figs["fields"],
                empty_figs["item_fields"],
                None,
                None,
            )
        methods = methods or []
        ocr_sources = ocr_sources or []
        models = [model for model in (models or []) if model]
        custom_models = [m.strip() for m in re.split(r"[,\n;]+", custom_models or "") if m.strip()]
        if custom_models:
            models.extend(custom_models)
        seen_models = set()
        models = [m for m in models if not (m in seen_models or seen_models.add(m))]
        alt_tokens = [t.strip().lower() for t in re.split(r"[,\n;]+", api_key_alt_match or "") if t.strip()]

        def _uses_alt(model: str) -> bool:
            if not alt_tokens:
                return False
            norm = (model or "").lower()
            return any(token in norm for token in alt_tokens)

        requires_openai_key = any(
            not evaluation.is_gemini_model(model)
            and not evaluation.is_claude_model(model)
            and not _uses_alt(model)
            for model in models
        )
        if ("llm_text" in methods or "llm_vision" in methods or "llm_text_hybrid" in methods) and requires_openai_key and not api_key:
            return (
                _status("Provide an API key for LLM methods.", "warning"),
                "0",
                "",
                "",
                "",
                empty_figs["overall"],
                empty_figs["items"],
                empty_figs["fields"],
                empty_figs["item_fields"],
                None,
                None,
            )
        if ("llm_text" in methods or "llm_vision" in methods or "llm_text_hybrid" in methods) and not models:
            return (
                _status("Select at least one LLM model.", "warning"),
                "0",
                "",
                "",
                "",
                empty_figs["overall"],
                empty_figs["items"],
                empty_figs["fields"],
                empty_figs["item_fields"],
                None,
                None,
            )
        if any(_uses_alt(model) for model in models) and not api_key_alt:
            return (
                _status("Provide a secondary API key for the matching models.", "warning"),
                "0",
                "",
                "",
                "",
                empty_figs["overall"],
                empty_figs["items"],
                empty_figs["fields"],
                empty_figs["item_fields"],
                None,
                None,
            )
        if any(evaluation.is_gemini_model(model) for model in models) and not gemini_api_key:
            return (
                _status("Provide a Gemini API key for Gemini models.", "warning"),
                "0",
                "",
                "",
                "",
                empty_figs["overall"],
                empty_figs["items"],
                empty_figs["fields"],
                empty_figs["item_fields"],
                None,
                None,
            )
        if any(evaluation.is_claude_model(model) for model in models) and not anthropic_api_key:
            return (
                _status("Provide an Anthropic API key for Claude models.", "warning"),
                "0",
                "",
                "",
                "",
                empty_figs["overall"],
                empty_figs["items"],
                empty_figs["fields"],
                empty_figs["item_fields"],
                None,
                None,
            )

        availability = evaluation.get_engine_availability()
        filtered_ocr = []
        skipped = []
        for src in ocr_sources:
            if src == "tesseract" and not availability.get("tesseract"):
                skipped.append("tesseract")
                continue
            if src == "easyocr" and not availability.get("easyocr"):
                skipped.append("easyocr")
                continue
            filtered_ocr.append(src)

        if (
            "regex" in methods
            or "key_value" in methods
            or "pattern" in methods
            or "ensemble" in methods
            or "llm_text" in methods
            or "llm_text_hybrid" in methods
        ) and not filtered_ocr:
            return (
                _status("Select at least one OCR source.", "warning"),
                "0",
                "",
                "",
                "",
                empty_figs["overall"],
                empty_figs["items"],
                empty_figs["fields"],
                empty_figs["item_fields"],
                None,
                None,
            )

        eval_methods = _build_eval_methods(filtered_ocr, methods, models)
        if not eval_methods:
            return (
                _status("No evaluation methods selected.", "warning"),
                "0",
                "",
                "",
                "",
                empty_figs["overall"],
                empty_figs["items"],
                empty_figs["fields"],
                empty_figs["item_fields"],
                None,
                None,
            )

        sample_count = min(sample_limit or len(samples), len(samples))
        job_id = uuid.uuid4().hex
        with _EVAL_LOCK:
            _EVAL_JOBS[job_id] = {
                "done": False,
                "errors": [],
                "done_steps": 0,
                "total_steps": max(1, len(eval_methods) * sample_count),
            }
        api_base_url = (api_base_url or "").strip()
        api_base_url_alt = (api_base_url_alt or "").strip()
        model_overrides = {}
        if api_key_alt and alt_tokens:
            for model in models:
                if _uses_alt(model):
                    model_overrides[model] = {
                        "api_key": api_key_alt,
                        "api_base_url": api_base_url_alt or api_base_url,
                    }
        config = {
            "dataset_path": dataset_path,
            "sample_limit": sample_count,
            "shuffle": "shuffle" in (shuffle or []),
            "seed": seed or 0,
            "visible_only": "visible" in (visible_only or []),
            "save_plots": "save" in (save_plots or []),
            "methods": eval_methods,
            "api_key": api_key or "",
            "api_base_url": api_base_url,
            "gemini_api_key": gemini_api_key or "",
            "anthropic_api_key": anthropic_api_key or "",
            "model_overrides": model_overrides,
            "max_pages": max_pages or 2,
        }
        thread = threading.Thread(target=_run_eval_job, args=(job_id, config), daemon=True)
        thread.start()
        skipped_note = f" Skipped: {', '.join(skipped)}." if skipped else ""
        return (
            _status(f"Evaluation started.{skipped_note}", "info"),
            "0",
            "",
            "",
            "",
            empty_figs["overall"],
            empty_figs["items"],
            empty_figs["fields"],
            empty_figs["item_fields"],
            job_id,
            None,
        )

    @app.callback(
        Output("eval-status", "children", allow_duplicate=True),
        Output("eval-progress", "value", allow_duplicate=True),
        Output("eval-summary", "children", allow_duplicate=True),
        Output("eval-errors", "children", allow_duplicate=True),
        Output("eval-runtime-errors", "children", allow_duplicate=True),
        Output("eval-graph-overall", "figure", allow_duplicate=True),
        Output("eval-graph-items", "figure", allow_duplicate=True),
        Output("eval-graph-fields", "figure", allow_duplicate=True),
        Output("eval-graph-item-fields", "figure", allow_duplicate=True),
        Output("eval-results-store", "data", allow_duplicate=True),
        Output("eval-job-id", "data", allow_duplicate=True),
        Input("eval-progress-interval", "n_intervals"),
        State("eval-job-id", "data"),
        prevent_initial_call=True,
    )
    def poll_eval_job(_n, job_id):
        if not job_id:
            return (
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
            )
        with _EVAL_LOCK:
            info = _EVAL_JOBS.get(job_id)
        if not info:
            return (
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                None,
            )
        done_steps = info.get("done_steps", 0)
        total_steps = info.get("total_steps", 1) or 1
        progress = int(done_steps / total_steps * 100)
        runtime_errors = _format_runtime_errors(info.get("errors", []))
        status = _status(
            f"Progress: {done_steps}/{total_steps} ({info.get('current_method', '')} {info.get('current_sample', '')})",
            "info" if not info.get("done") else "success",
        )
        if info.get("done"):
            results_payload = {
                "results": info.get("results", {}),
                "runtime_errors": info.get("errors", []),
                "plots_path": info.get("plots_path"),
            }
            results_json = json.dumps(results_payload, ensure_ascii=False, indent=2)
            summary = info.get("summary", "")
            errors_text = info.get("errors_text", "")
            figures = _build_eval_figures(results_payload.get("results", {}))
            with _EVAL_LOCK:
                _EVAL_JOBS.pop(job_id, None)
            return (
                status,
                str(progress),
                summary,
                errors_text,
                runtime_errors,
                figures["overall"],
                figures["items"],
                figures["fields"],
                figures["item_fields"],
                results_json,
                None,
            )
        return (
            status,
            str(progress),
            no_update,
            no_update,
            runtime_errors,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
        )

    @app.callback(
        Output("download-eval-results", "data"),
        Input("eval-download-btn", "n_clicks"),
        State("eval-results-store", "data"),
        prevent_initial_call=True,
    )
    def download_eval_results(_n, results_json):
        if not results_json:
            raise PreventUpdate
        payload = results_json if isinstance(results_json, str) else json.dumps(results_json, ensure_ascii=False, indent=2)
        return dcc.send_string(payload, filename="evaluation_results.json")

    @app.callback(
        Output("download-eval-plots", "data"),
        Input("eval-download-plots-btn", "n_clicks"),
        State("eval-results-store", "data"),
        prevent_initial_call=True,
    )
    def download_eval_plots(_n, results_json):
        results = _parse_eval_results(results_json)
        if not results:
            raise PreventUpdate
        figures = _build_eval_figures(results)
        html_content = _figures_to_html(figures)
        return dcc.send_string(html_content, filename="evaluation_plots.html")
