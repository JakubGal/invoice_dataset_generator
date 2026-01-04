from pathlib import Path
from typing import Any, Dict, List, Optional

from dash import html

from invoice_app.models import TemplateTheme
from invoice_app.utils import coerce_text, dotted_get, ensure_media_uri, format_currency


GOOGLE_FONT_FAMILIES: Dict[str, str] = {
    "Inter": "Inter",
    "Manrope": "Manrope",
    "Roboto": "Roboto",
    "Open Sans": "Open+Sans",
    "Montserrat": "Montserrat",
    "Lato": "Lato",
    "Source Sans Pro": "Source+Sans+Pro",
    "Playfair Display": "Playfair+Display",
    "Cormorant Garamond": "Cormorant+Garamond",
    "Merriweather": "Merriweather",
    "EB Garamond": "EB+Garamond",
    "DM Serif Display": "DM+Serif+Display",
    "Spectral": "Spectral",
    "PT Serif": "PT+Serif",
    "Space Mono": "Space+Mono",
    "IBM Plex Mono": "IBM+Plex+Mono",
    "Handlee": "Handlee",
    "Caveat": "Caveat",
    "Shadows Into Light": "Shadows+Into+Light",
    "Amatic SC": "Amatic+SC",
    "Pacifico": "Pacifico",
    "Rock Salt": "Rock+Salt",
    "Permanent Marker": "Permanent+Marker",
    "Noto Sans SC": "Noto+Sans+SC",
    "Noto Serif SC": "Noto+Serif+SC",
    "Noto Sans JP": "Noto+Sans+JP",
    "Noto Serif JP": "Noto+Serif+JP",
    "Noto Sans KR": "Noto+Sans+KR",
}


def _font_import_url(family: str) -> Optional[str]:
    if not family:
        return None
    fam = family.strip()
    query = GOOGLE_FONT_FAMILIES.get(fam)
    if not query:
        return None
    # Use a modest weight set; many handwriting fonts only ship 400.
    return f"https://fonts.googleapis.com/css2?family={query}:wght@400;500;600;700&display=swap"


def _font_stack(family: str) -> str:
    """Return a CSS font stack with a sensible fallback based on family."""
    if not family:
        return "sans-serif"
    family_clean = family.strip()
    lower = family_clean.lower()
    fallback = "sans-serif"
    if "mono" in lower or "courier" in lower or "code" in lower:
        fallback = "monospace"
    elif any(key in lower for key in ["garamond", "serif", "times"]):
        fallback = "serif"
    elif any(key in lower for key in ["caveat", "amatic", "pacifico", "rock salt", "permanent marker", "shadows into light", "handlee", "comic sans", "marker"]):
        fallback = "cursive"
    return f"'{family_clean}', {fallback}"


def _security_overlays_div(security: Dict[str, Any], theme: TemplateTheme) -> html.Div:
    """Build overlay layers (hatch/noise/watermark) for the live preview."""
    options = security.get("options", []) if isinstance(security, dict) else []
    watermark = security.get("watermark") if isinstance(security, dict) else None
    overlays: List[html.Div] = []

    if "diagonal_lines" in options:
        overlays.append(
            html.Div(
                style={
                    "position": "absolute",
                    "top": 0,
                    "right": 0,
                    "bottom": 0,
                    "left": 0,
                    "background": "repeating-linear-gradient(45deg, rgba(0,0,0,0.04) 0px, rgba(0,0,0,0.04) 10px, transparent 10px, transparent 20px)",
                    "pointerEvents": "none",
                    "zIndex": 3,
                }
            )
        )

    if "noise" in options:
        overlays.append(
            html.Div(
                style={
                    "position": "absolute",
                    "top": 0,
                    "right": 0,
                    "bottom": 0,
                    "left": 0,
                    "background": "radial-gradient(rgba(0,0,0,0.04) 1px, transparent 1px)",
                    "backgroundSize": "8px 8px",
                    "pointerEvents": "none",
                    "zIndex": 2,
                }
            )
        )

    if "watermark" in options and watermark:
        overlays.append(
            html.Div(
                watermark,
                style={
                    "position": "absolute",
                    "top": 0,
                    "right": 0,
                    "bottom": 0,
                    "left": 0,
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "fontSize": "64px",
                    "fontWeight": "700",
                    "color": "rgba(0,0,0,0.07)",
                    "transform": "rotate(-25deg)",
                    "pointerEvents": "none",
                    "zIndex": 4,
                    "textTransform": "uppercase",
                    "letterSpacing": "0.2em",
                    "textAlign": "center",
                },
            )
        )

    if "thin_lines" in options:
        overlays.append(
            html.Div(
                style={
                    "position": "absolute",
                    "top": 0,
                    "right": 0,
                    "bottom": 0,
                    "left": 0,
                    "background": "repeating-linear-gradient(0deg, rgba(0,0,0,0.15) 0px, rgba(0,0,0,0.15) 1px, transparent 1px, transparent 4px)",
                    "pointerEvents": "none",
                    "zIndex": 1,
                }
            )
        )

    return html.Div(
        overlays,
        style={"position": "absolute", "top": 0, "right": 0, "bottom": 0, "left": 0, "pointerEvents": "none"},
    )


def _security_overlay_html(security: Dict[str, Any], theme: TemplateTheme) -> str:
    """Return HTML for overlay layers in exported HTML/PDF."""
    options = security.get("options", []) if isinstance(security, dict) else []
    watermark = security.get("watermark") if isinstance(security, dict) else None
    layers: List[str] = []

    if "diagonal_lines" in options:
        layers.append(
            "<div style=\"position:absolute;top:0;right:0;bottom:0;left:0;pointer-events:none;z-index:3;"
            "background:repeating-linear-gradient(45deg, rgba(0,0,0,0.04) 0px, rgba(0,0,0,0.04) 10px, transparent 10px, transparent 20px);\"></div>"
        )
    if "noise" in options:
        layers.append(
            "<div style=\"position:absolute;top:0;right:0;bottom:0;left:0;pointer-events:none;z-index:2;"
            "background:radial-gradient(rgba(0,0,0,0.04) 1px, transparent 1px);background-size:8px 8px;\"></div>"
        )
    if "watermark" in options and watermark:
        wm = str(watermark).upper()
        layers.append(
            f"<div style=\"position:absolute;top:0;right:0;bottom:0;left:0;display:flex;align-items:center;justify-content:center;pointer-events:none;z-index:4;"
            f"font-size:64px;font-weight:700;color:rgba(0,0,0,0.07);transform:rotate(-25deg);text-transform:uppercase;letter-spacing:0.2em;text-align:center;\">{wm}</div>"
        )
    if "thin_lines" in options:
        layers.append(
            "<div style=\"position:absolute;top:0;right:0;bottom:0;left:0;pointer-events:none;z-index:1;"
            "background:repeating-linear-gradient(0deg, rgba(0,0,0,0.15) 0px, rgba(0,0,0,0.15) 1px, transparent 1px, transparent 4px);\"></div>"
        )

    if not layers:
        return ""
    return (
        "<div class='security-overlays' style='position:absolute;top:0;right:0;bottom:0;left:0;pointer-events:none;'>"
        f"{''.join(layers)}</div>"
    )


def _apply_format(value: Any, fmt: Optional[str], currency: str) -> str:
    if fmt == "currency":
        return format_currency(value, currency)
    return coerce_text(value)


def _field_value(data: Dict[str, Any], path: str) -> Any:
    return dotted_get(data, path, "")


def _resolve_field_style(field: Dict[str, Any], path: str, styles_map: Dict[str, Any]) -> Dict[str, Any]:
    base_style = field.get("style", {}) if isinstance(field.get("style"), dict) else {}
    extra_style = styles_map.get(path, {}) if isinstance(styles_map, dict) else {}
    merged = {**base_style, **extra_style}
    # Normalize font size keys to valid CSS values where possible.
    if "font_size" in merged and "fontSize" not in merged:
        merged["fontSize"] = merged.pop("font_size")
    if isinstance(merged.get("fontSize"), (int, float)):
        merged["fontSize"] = f"{merged['fontSize']}px"
    return merged


def _render_field(field: Dict[str, Any], data: Dict[str, Any], theme: TemplateTheme, styles_map: Dict[str, Any]) -> html.Div:
    label = field.get("label", "")
    path = field.get("value_path", "")
    effective_path = path or label or f"field_{id(field)}"
    fmt = field.get("format")
    placeholder = field.get("placeholder", "")
    value = _apply_format(_field_value(data, path), fmt, theme.currency)
    if value == "":
        value = placeholder

    style = _resolve_field_style(field, effective_path, styles_map)
    return html.Div(
        className="field",
        children=[
            html.Div(
                label,
                className="field-label",
                id={
                    "type": "editable-text",
                    "path": f"{effective_path}.label",
                    "role": "label",
                    "section": -1,
                    "row": -1,
                    "col_idx": -1,
                    "total_idx": -1,
                },
                n_clicks=0,
            ),
            html.Div(
                value,
                className="field-value",
                id={
                    "type": "editable-text",
                    "path": effective_path,
                    "role": "value",
                    "section": -1,
                    "row": -1,
                    "col_idx": -1,
                    "total_idx": -1,
                },
                n_clicks=0,
                style={"cursor": "pointer"},
            ),
        ],
        style=style,
    )


def _render_grid_section(
    section: Dict[str, Any], data: Dict[str, Any], theme: TemplateTheme, styles_map: Dict[str, Any]
) -> html.Div:
    fields = section.get("fields", [])
    columns = section.get("columns", 2) or 2
    grid_style = {
        "display": "grid",
        "gridTemplateColumns": f"repeat({columns}, minmax(0, 1fr))",
        "gap": section.get("gap", "12px"),
    }

    return html.Div(
        className="section",
        children=[
            html.Div(section.get("title", ""), className="section-title", style={"color": theme.accent_color}),
            html.Div(
                [_render_field(f, data, theme, styles_map) for f in fields],
                className="field-grid",
                style=grid_style,
            ),
        ],
    )


def _render_panels_section(
    section: Dict[str, Any], data: Dict[str, Any], theme: TemplateTheme, styles_map: Dict[str, Any]
) -> html.Div:
    panels = section.get("panels", [])
    panel_components: List[html.Div] = []
    for panel in panels:
        fields = panel.get("fields", [])
        panel_components.append(
            html.Div(
                className="panel",
                style=panel.get("style", {}),
                children=[
                    html.Div(panel.get("heading", ""), className="panel-heading"),
                    html.Div([_render_field(f, data, theme, styles_map) for f in fields], className="panel-fields"),
                ],
            )
        )

    return html.Div(
        className="section",
        children=[
            html.Div(section.get("title", ""), className="section-title", style={"color": theme.accent_color}),
            html.Div(panel_components, className="panel-grid"),
        ],
    )


def _extract_row_value(row: Dict[str, Any], data: Dict[str, Any], col: Dict[str, Any]) -> Any:
    path = col.get("value_path") or col.get("key")
    if path is None:
        return ""
    # Prefer row values, then fall back to the global data.
    if isinstance(row, dict):
        if path in row:
            return row[path]
        nested = dotted_get(row, path, None)
        if nested is not None:
            return nested
    return dotted_get(data, path, "")


def _render_table_section(
    section: Dict[str, Any], data: Dict[str, Any], theme: TemplateTheme, styles_map: Dict[str, Any], section_idx: int
) -> html.Div:
    rows = dotted_get(data, section.get("data_path", "items"), []) or []
    columns = section.get("columns", [])
    computed_rows: List[List[str]] = []

    for row in rows:
        row_values: List[str] = []
        for col in columns:
            raw_value = _extract_row_value(row, data, col)
            fmt = col.get("format")
            if col.get("key") == "line_total" and raw_value in ("", None):
                qty = row.get("qty", 0)
                unit = row.get("unit_price", 0)
                raw_value = qty * unit
                fmt = fmt or "currency"
            row_values.append(_apply_format(raw_value, fmt, theme.currency))
        computed_rows.append(row_values)

    header_cells = []
    for c_idx, col in enumerate(columns):
        header_cells.append(
            html.Th(
                col.get("label", ""),
                style={"textAlign": col.get("align", "left"), "width": col.get("width")},
                id={
                    "type": "editable-text",
                    "path": f"table.{section_idx}.columns.{c_idx}.label",
                    "role": "header",
                    "section": section_idx,
                    "col_idx": c_idx,
                    "row": -1,
                    "total_idx": -1,
                },
                n_clicks=0,
            )
        )

    body_rows = []
    for row_idx, row in enumerate(computed_rows):
        body_rows.append(
            html.Tr(
                [
                    html.Td(
                        value,
                        id={
                            "type": "editable-text",
                            "path": f"{section.get('data_path', 'items')}[{row_idx}].{columns[idx].get('value_path') or columns[idx].get('key')}",
                            "role": "cell",
                        "section": section_idx,
                        "row": row_idx,
                        "col_idx": idx,
                        "total_idx": -1,
                    },
                    n_clicks=0,
                    style={
                        "textAlign": columns[idx].get("align", "left"),
                        **_resolve_field_style(
                                {"style": {}},
                                f"{section.get('data_path', 'items')}[{row_idx}].{columns[idx].get('value_path') or columns[idx].get('key')}",
                                styles_map,
                            ),
                            "cursor": "pointer",
                        },
                    )
                    for idx, value in enumerate(row)
                ]
            )
        )

    totals = section.get("totals", [])
    total_rows: List[html.Tr] = []
    for t_idx, total in enumerate(totals):
        label = total.get("label", "")
        path = total.get("value_path", "")
        fmt = total.get("format")
        raw_total = dotted_get(data, path, "")
        total_rows.append(
            html.Tr(
                [
                    html.Td(
                        label,
                        className="total-label",
                        colSpan=max(len(columns) - 1, 1),
                        id={
                            "type": "editable-text",
                            "path": f"table.{section_idx}.totals.{t_idx}.label",
                            "role": "total-label",
                            "section": section_idx,
                            "total_idx": t_idx,
                            "row": -1,
                            "col_idx": -1,
                        },
                        n_clicks=0,
                    ),
                    html.Td(
                        _apply_format(raw_total, fmt, theme.currency),
                        className="total-value",
                        id={
                            "type": "editable-text",
                            "path": path,
                            "role": "total-value",
                            "section": section_idx,
                            "total_idx": t_idx,
                            "row": -1,
                            "col_idx": -1,
                        },
                        n_clicks=0,
                        style={
                            "color": theme.accent_color,
                            **_resolve_field_style({"style": {}}, path, styles_map),
                            "cursor": "pointer",
                        },
                    ),
                ]
            )
        )

    table_children = [html.Thead(html.Tr(header_cells)), html.Tbody(body_rows + total_rows)]

    return html.Div(
        className="section",
        children=[
            html.Div(section.get("title", ""), className="section-title", style={"color": theme.accent_color}),
            html.Div(
                className="table-wrapper",
                children=html.Table(table_children, className="items-table"),
            ),
        ],
    )


def _render_notes_section(
    section: Dict[str, Any], data: Dict[str, Any], theme: TemplateTheme, styles_map: Dict[str, Any]
) -> html.Div:
    text = _field_value(data, section.get("value_path", "notes"))
    return html.Div(
        className="section",
        children=[
            html.Div(
                section.get("title", "Notes"),
                className="section-title",
                style={"color": theme.accent_color},
            ),
            html.Div(
                coerce_text(text),
                className="note-block",
                id={
                    "type": "editable-text",
                    "path": section.get("value_path", "notes"),
                    "role": "note",
                    "section": -1,
                    "row": -1,
                    "col_idx": -1,
                    "total_idx": -1,
                },
                n_clicks=0,
                style=_resolve_field_style(
                    {"style": section.get("style", {})},
                    section.get("value_path", "notes"),
                    styles_map,
                )
                | {"cursor": "pointer"},
            ),
        ],
    )


def _render_section(
    section: Dict[str, Any], data: Dict[str, Any], theme: TemplateTheme, styles_map: Dict[str, Any], section_idx: int
) -> Optional[html.Div]:
    if not isinstance(section, dict):
        return None
    section_type = section.get("type", "grid")
    if section_type == "table":
        return _render_table_section(section, data, theme, styles_map, section_idx)
    if section_type == "panels":
        return _render_panels_section(section, data, theme, styles_map)
    if section_type == "notes":
        return _render_notes_section(section, data, theme, styles_map)
    return _render_grid_section(section, data, theme, styles_map)


def render_invoice(payload: Dict[str, Any]) -> html.Div:
    template = payload.get("template", {})
    data = payload.get("data", {})
    theme = TemplateTheme.from_template(template)
    font_stack = _font_stack(theme.font_family)
    font_import = _font_import_url(theme.font_family)
    security_opts = template.get("security", {}).get("options", []) if isinstance(template.get("security"), dict) else []
    blur_style = {"filter": "blur(0.6px)"} if "blur_text" in security_opts else {}
    base_path = Path.cwd()
    styles_map: Dict[str, Any] = template.get("styles", {}) if isinstance(template.get("styles", {}), dict) else {}
    page_style: Dict[str, Any] = {
        "width": theme.width,
        "height": theme.height,
        "padding": theme.padding,
        "backgroundColor": theme.background_color,
        "borderRadius": theme.border_radius,
        "color": theme.font_color,
        "fontFamily": font_stack,
        "fontSize": theme.font_size,
        "position": "relative",
        "overflow": "hidden",
        "backgroundImage": f"url('{ensure_media_uri(theme.background_image, base_path)}')"
        if theme.background_image
        else None,
    }
    # Remove None to keep styles clean.
    page_style = {k: v for k, v in page_style.items() if v is not None}

    logo_src = ensure_media_uri(theme.logo.get("src"), base_path) if theme.logo else ""
    sections = template.get("sections", []) if isinstance(template.get("sections", []), list) else []
    rendered_sections = [_render_section(section, data, theme, styles_map, idx) for idx, section in enumerate(sections)]
    rendered_sections = [s for s in rendered_sections if s is not None]

    header_children: List[Any] = []
    if logo_src:
        header_children.append(
            html.Img(
                src=logo_src,
                alt=theme.logo.get("alt", "Logo"),
                style={
                    "height": theme.logo.get("height", "64px"),
                    "maxWidth": "240px",
                    "objectFit": "contain",
                },
            )
        )
    header_children.append(
        html.Div(
            [
                html.Div(
                    template.get("label", "INVOICE"),
                    className="invoice-chip",
                    style={"background": theme.accent_color},
                ),
                html.H2(theme.title, className="invoice-title"),
            ]
        )
    )

    overlays_div = _security_overlays_div(template.get("security", {}), theme)
    content = html.Div(
        className="invoice-page",
        style=page_style,
        children=[
            overlays_div,
            html.Div(
                [
                    html.Div(header_children, className="invoice-header"),
                    html.Div(rendered_sections, className="invoice-body"),
                ],
                className="invoice-content",
                style=blur_style,
            ),
        ],
    )

    # Include a font import link so custom families render in preview.
    if font_import:
        return html.Div([html.Link(rel="stylesheet", href=font_import), content])
    return content


def _html_field(label: str, value: str) -> str:
    return f"<div class='field'><div class='field-label'>{label}</div><div class='field-value'>{value}</div></div>"


def build_html_export(payload: Dict[str, Any]) -> str:
    """Produce a minimal self-contained HTML export for download."""
    template = payload.get("template", {})
    data = payload.get("data", {})
    theme = TemplateTheme.from_template(template)
    font_stack = _font_stack(theme.font_family)
    font_import = _font_import_url(theme.font_family)
    overlays_html = _security_overlay_html(template.get("security", {}), theme)
    base_path = Path.cwd()
    logo_src = ensure_media_uri(theme.logo.get("src"), base_path) if theme.logo else ""
    bg = (
        f"background-image:url('{ensure_media_uri(theme.background_image, base_path)}');"
        if theme.background_image
        else ""
    )

    sections_html: List[str] = []
    for section in template.get("sections", []):
        stype = section.get("type", "grid")
        title_html = f"<div class='section-title'>{section.get('title','')}</div>"
        if stype == "table":
            cols = section.get("columns", [])
            headers = "".join(
                f"<th style='text-align:{c.get('align','left')};width:{c.get('width','auto')}'>{c.get('label','')}</th>"
                for c in cols
            )
            rows_html = ""
            rows = dotted_get(data, section.get("data_path", "items"), []) or []
            for row in rows:
                cells = []
                for col in cols:
                    raw = _extract_row_value(row, data, col)
                    fmt = col.get("format")
                    if col.get("key") == "line_total" and raw in ("", None):
                        raw = row.get("qty", 0) * row.get("unit_price", 0)
                        fmt = fmt or "currency"
                    cells.append(
                        f"<td style='text-align:{col.get('align','left')}'>{_apply_format(raw, fmt, theme.currency)}</td>"
                    )
                rows_html += f"<tr>{''.join(cells)}</tr>"

            totals_html = ""
            for total in section.get("totals", []):
                raw = dotted_get(data, total.get("value_path", ""), "")
                totals_html += (
                    "<tr>"
                    f"<td colspan='{max(len(cols)-1,1)}' class='total-label'>{total.get('label','')}</td>"
                    f"<td class='total-value'>{_apply_format(raw, total.get('format'), theme.currency)}</td>"
                    "</tr>"
                )

            table_html = (
                f"<div class='table-wrapper'><table class='items-table'><thead><tr>{headers}</tr></thead>"
                f"<tbody>{rows_html}{totals_html}</tbody></table></div>"
            )
            sections_html.append(f"<div class='section'>{title_html}{table_html}</div>")
            continue

        if stype == "panels":
            panels_html = ""
            for panel in section.get("panels", []):
                fields_html = "".join(
                    _html_field(f.get("label", ""), _apply_format(_field_value(data, f.get("value_path", "")), f.get("format"), theme.currency))
                    for f in panel.get("fields", [])
                )
                panels_html += (
                    "<div class='panel'>"
                    f"<div class='panel-heading'>{panel.get('heading','')}</div>"
                    f"<div class='panel-fields'>{fields_html}</div>"
                    "</div>"
                )
            sections_html.append(f"<div class='section'>{title_html}<div class='panel-grid'>{panels_html}</div></div>")
            continue

        if stype == "notes":
            note_val = coerce_text(_field_value(data, section.get("value_path", "notes")))
            sections_html.append(
                f"<div class='section'>{title_html}<div class='note-block'>{note_val}</div></div>"
            )
            continue

        fields_html = "".join(
            _html_field(
                f.get("label", ""),
                _apply_format(_field_value(data, f.get("value_path", "")), f.get("format"), theme.currency)
                or f.get("placeholder", ""),
            )
            for f in section.get("fields", [])
        )
        sections_html.append(
            f"<div class='section'>{title_html}"
            f"<div class='field-grid' style='grid-template-columns:repeat({section.get('columns',2)},minmax(0,1fr));'>"
            f"{fields_html}</div></div>"
        )

    blur_style = "filter:blur(0.6px);" if "blur_text" in (template.get("security", {}) or {}).get("options", []) else ""

    style_block = f"""
    <style>
      body {{
        font-family:{font_stack};
        color:{theme.font_color};
        background:#e5e7eb;
        padding:24px;
      }}
      .invoice-page {{
        width:{theme.width};
        padding:{theme.padding};
        background:{theme.background_color};
        border-radius:{theme.border_radius};
        {bg}
        background-size:cover;
        background-repeat:no-repeat;
        box-shadow:0 15px 50px rgba(15,23,42,0.15);
        margin:0 auto;
        position:relative;
        overflow:hidden;
      }}
      .invoice-header {{ display:flex; align-items:center; justify-content:space-between; gap:16px; }}
      .invoice-title {{ margin:4px 0 0 0; font-size:28px; }}
      .invoice-chip {{
        display:inline-flex;
        padding:6px 10px;
        background:{theme.accent_color};
        color:#fff;
        border-radius:999px;
        font-weight:600;
        letter-spacing:0.04em;
      }}
      .invoice-body {{ display:flex; flex-direction:column; gap:18px; margin-top:12px; }}
      .section {{ background:rgba(255,255,255,0.7); padding:14px 16px; border-radius:12px; border:1px solid #e2e8f0; }}
      .section-title {{ font-weight:700; color:{theme.accent_color}; margin-bottom:10px; }}
      .field-grid {{ display:grid; gap:10px; }}
      .field-label {{ font-size:12px; text-transform:uppercase; color:{theme.font_color}; letter-spacing:0.04em; }}
      .field-value {{ font-size:14px; font-weight:600; color:{theme.font_color}; }}
      .items-table {{ width:100%; border-collapse:collapse; }}
      .items-table th {{ text-align:left; font-size:12px; text-transform:uppercase; letter-spacing:0.05em; color:{theme.font_color}; border-bottom:1px solid #e2e8f0; padding:8px 6px; }}
      .items-table td {{ padding:10px 6px; border-bottom:1px solid #edf2f7; }}
      .table-wrapper {{ overflow:hidden; border:1px solid #e2e8f0; border-radius:12px; background:#fff; }}
      .total-label {{ text-align:right; font-weight:700; color:{theme.font_color}; }}
      .total-value {{ font-weight:800; font-size:16px; color:{theme.accent_color}; }}
      .panel-grid {{ display:grid; gap:10px; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); }}
      .panel {{ background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:12px; }}
      .panel-heading {{ font-weight:700; margin-bottom:8px; color:{theme.font_color}; }}
      .panel-fields {{ display:grid; gap:10px; }}
      .note-block {{ background:#fff; border:1px dashed #cbd5e1; padding:12px; border-radius:12px; color:{theme.font_color}; }}
      .invoice-content {{ {blur_style} }}
    </style>
    """

    logo_html = f"<img src='{logo_src}' style='height:{theme.logo.get('height','64px')};max-width:240px;object-fit:contain;' alt='Logo'/>" if logo_src else ""
    font_link = f"<link rel='stylesheet' href='{font_import}'/>" if font_import else ""
    html_body = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{theme.title}</title>{font_link}{style_block}</head>"
        "<body>"
        f"<div class='invoice-page' style='position:relative;overflow:hidden;{bg}'>"
        f"{overlays_html}"
        f"<div class='invoice-content' style='{blur_style}'>"
        "<div class='invoice-header'>"
        f"{logo_html}"
        "<div>"
        f"<div class='invoice-chip'>{template.get('label','INVOICE')}</div>"
        f"<h2 class='invoice-title'>{theme.title}</h2>"
        "</div></div>"
        f"<div class='invoice-body'>{''.join(sections_html)}</div>"
        "</div>"
        "</div></body></html>"
    )
    return html_body
