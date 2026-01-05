import os

from dash import dcc, html


def build_layout(app):
    api_key_default = os.environ.get("OPENAI_API_KEY", "")
    gemini_api_key_default = os.environ.get("GEMINI_API_KEY", "")
    anthropic_api_key_default = os.environ.get("ANTHROPIC_API_KEY", "")
    api_base_url_default = os.environ.get("OPENAI_BASE_URL", "")
    if os.name == "nt":
        ds_output_default = "C:/Users/bukaj/Documents/Bakalarka/gen"
        eval_dataset_path = "C:/Users/bukaj/Documents/Bakalarka/gen_EN_50"
    else:
        ds_output_default = "/data/datasets"
        eval_dataset_path = "/data/datasets"
    api_key_alt_default = os.environ.get("OPENAI_API_KEY_ALT", "")
    api_base_url_alt_default = os.environ.get(
        "OPENAI_BASE_URL_ALT",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    api_key_alt_match_default = os.environ.get("OPENAI_MODEL_MATCH_ALT", "qwen")
    api_key_hint = (
        "Loaded from OPENAI_API_KEY environment variable."
        if api_key_default
        else "Set OPENAI_API_KEY before starting the app to prefill this field."
    )
    gemini_api_key_hint = (
        "Loaded from GEMINI_API_KEY environment variable."
        if gemini_api_key_default
        else "Set GEMINI_API_KEY before starting the app to prefill this field."
    )
    anthropic_api_key_hint = (
        "Loaded from ANTHROPIC_API_KEY environment variable."
        if anthropic_api_key_default
        else "Set ANTHROPIC_API_KEY before starting the app to prefill this field."
    )
    api_key_alt_hint = (
        "Loaded from OPENAI_API_KEY_ALT environment variable."
        if api_key_alt_default
        else "Optional secondary key for OpenAI-compatible providers."
    )
    api_base_url_alt_hint = (
        "Loaded from OPENAI_BASE_URL_ALT environment variable."
        if os.environ.get("OPENAI_BASE_URL_ALT")
        else (
            "Default: Alibaba Model Studio intl endpoint "
            "(use https://dashscope.aliyuncs.com/compatible-mode/v1 for China region)."
        )
    )
    api_key_alt_match_hint = (
        "Loaded from OPENAI_MODEL_MATCH_ALT environment variable."
        if os.environ.get("OPENAI_MODEL_MATCH_ALT")
        else "Default: qwen. Comma-separated tokens; if a model name contains a token, the secondary key/base is used."
    )

    invoice_tab = html.Div(
        children=[
            html.Div(
                className="page-header",
                children=[
                    html.Div(
                        [
                            html.H1("Invoice builder"),
                            html.P(
                                "Load or author a JSON template with both structure and data, "
                                "preview the invoice, then export the result."
                            ),
                        ]
                    ),
                    html.Div(
                        className="header-actions",
                        children=[
                            html.Button("Load sample", id="load-sample-btn", n_clicks=0, className="secondary"),
                            html.Button("Preview invoice", id="preview-btn", n_clicks=0, className="primary"),
                            html.Button("Download HTML", id="download-btn", n_clicks=0, className="ghost"),
                            html.Button("Download PDF", id="download-pdf-btn", n_clicks=0, className="ghost"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="main-grid",
                children=[
                    html.Div(
                        className="card",
                        children=[
                            html.H3("Template and data JSON"),
                            html.P(
                                "Drag a JSON file here or paste the JSON content below. "
                                "The file should contain 'template' and 'data' keys."
                            ),
                            dcc.Upload(
                                id="upload-json",
                                children=html.Div(["Drop JSON here or ", html.B("click to select a file")]),
                                multiple=False,
                                className="upload-area",
                            ),
                            html.Div(id="upload-status", className="muted"),
                            dcc.Textarea(
                                id="template-json-input",
                                placeholder="Paste template + data JSON here...",
                                spellCheck=False,
                                className="json-editor",
                            ),
                        ],
                    ),
                    html.Div(
                        className="card",
                        children=[
                            html.H3("Layout builder"),
                            html.P(
                                className="muted",
                                children=(
                                    "Quickly add sections without hand-editing JSON. You can still fine-tune "
                                    "text and styles via the designer."
                                ),
                            ),
                            html.Div(
                                className="form-grid",
                                children=[
                                    html.Label("Section type"),
                                    dcc.Dropdown(
                                        id="builder-section-type",
                                        options=[
                                            {"label": "Grid of fields", "value": "grid"},
                                            {"label": "Table", "value": "table"},
                                            {"label": "Notes", "value": "notes"},
                                        ],
                                        value="grid",
                                        clearable=False,
                                    ),
                                    html.Label("Section title"),
                                    dcc.Input(
                                        id="builder-section-title",
                                        type="text",
                                        placeholder="e.g. Invoice details",
                                        className="text-input",
                                    ),
                                    html.Label("Grid columns (for grid)"),
                                    dcc.Input(
                                        id="builder-grid-columns",
                                        type="number",
                                        min=1,
                                        max=4,
                                        step=1,
                                        value=2,
                                        className="text-input",
                                    ),
                                    html.Label("Table data path (for table)"),
                                    dcc.Input(
                                        id="builder-table-data-path",
                                        type="text",
                                        placeholder="items",
                                        className="text-input",
                                    ),
                                ],
                            ),
                            html.Label("Fields (one per line: Label | value_path)"),
                            dcc.Textarea(
                                id="builder-fields",
                                className="text-input",
                                placeholder="Invoice # | invoice.number\nDate | invoice.date",
                                style={"minHeight": "120px"},
                            ),
                            html.Label("Table columns (for table: Label | key/value_path | align)"),
                            dcc.Textarea(
                                id="builder-table-columns",
                                className="text-input",
                                placeholder=(
                                    "Description | description | left\n"
                                    "Qty | qty | center\n"
                                    "Unit price | unit_price | right\n"
                                    "Total | line_total | right"
                                ),
                                style={"minHeight": "120px"},
                            ),
                            html.Label("Table totals (optional: Label | value_path | format)"),
                            dcc.Textarea(
                                id="builder-table-totals",
                                className="text-input",
                                placeholder="Subtotal | totals.subtotal | currency\nAmount due | totals.due | currency",
                                style={"minHeight": "90px"},
                            ),
                            html.Button(
                                "Add section",
                                id="builder-add-section-btn",
                                n_clicks=0,
                                className="primary",
                                style={"marginTop": "10px"},
                            ),
                            html.Hr(),
                            html.H4("Reorder sections"),
                            html.P(className="muted", children="Pick a section, then move it up or down."),
                            dcc.Dropdown(id="section-order-dropdown", options=[], placeholder="Select section"),
                            html.Div(
                                className="form-actions",
                                children=[
                                    html.Button("Move up", id="section-move-up", n_clicks=0, className="secondary"),
                                    html.Button("Move down", id="section-move-down", n_clicks=0, className="secondary"),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="card designer-card",
                        children=[
                            html.H3("Visual designer"),
                            html.P(
                                className="muted",
                                children="Click any field in the preview to edit its text and styling directly.",
                            ),
                            html.Div(
                                className="designer-section",
                                children=[
                                    html.H4("Theme"),
                                    html.Div(
                                        className="form-grid",
                                        children=[
                                            html.Label("Font family"),
                                            dcc.Dropdown(
                                                id="theme-font-family",
                                                options=[
                                                    {"label": "Inter", "value": "Inter"},
                                                    {"label": "Manrope", "value": "Manrope"},
                                                    {"label": "Roboto", "value": "Roboto"},
                                                    {"label": "Segoe UI", "value": "Segoe UI"},
                                                    {"label": "Open Sans", "value": "Open Sans"},
                                                    {"label": "Montserrat", "value": "Montserrat"},
                                                    {"label": "Lato", "value": "Lato"},
                                                    {"label": "Source Sans Pro", "value": "Source Sans Pro"},
                                                    {"label": "Georgia", "value": "Georgia"},
                                                    {"label": "Times New Roman", "value": "Times New Roman"},
                                                    {"label": "Playfair Display", "value": "Playfair Display"},
                                                    {"label": "Cormorant Garamond", "value": "Cormorant Garamond"},
                                                    {"label": "Merriweather", "value": "Merriweather"},
                                                    {"label": "EB Garamond", "value": "EB Garamond"},
                                                    {"label": "DM Serif Display", "value": "DM Serif Display"},
                                                    {"label": "Spectral", "value": "Spectral"},
                                                    {"label": "PT Serif", "value": "PT Serif"},
                                                    {"label": "Courier New", "value": "Courier New"},
                                                    {"label": "Space Mono", "value": "Space Mono"},
                                                    {"label": "IBM Plex Mono", "value": "IBM Plex Mono"},
                                                    {"label": "Comic Sans MS", "value": "Comic Sans MS"},
                                                    {"label": "Handlee (handwritten)", "value": "Handlee"},
                                                    {"label": "Caveat (handwritten)", "value": "Caveat"},
                                                    {"label": "Shadows Into Light", "value": "Shadows Into Light"},
                                                    {"label": "Amatic SC", "value": "Amatic SC"},
                                                    {"label": "Pacifico", "value": "Pacifico"},
                                                    {"label": "Rock Salt", "value": "Rock Salt"},
                                                    {"label": "Permanent Marker", "value": "Permanent Marker"},
                                                    {"label": "Noto Sans SC", "value": "Noto Sans SC"},
                                                    {"label": "Noto Serif SC", "value": "Noto Serif SC"},
                                                    {"label": "Noto Sans JP", "value": "Noto Sans JP"},
                                                    {"label": "Noto Serif JP", "value": "Noto Serif JP"},
                                                    {"label": "Noto Sans KR", "value": "Noto Sans KR"},
                                                ],
                                                placeholder="Pick a font family",
                                                clearable=True,
                                                searchable=True,
                                            ),
                                            html.Label("Font size (px)"),
                                            dcc.Input(
                                                id="theme-font-size",
                                                type="number",
                                                min=8,
                                                max=36,
                                                step=1,
                                                className="text-input",
                                            ),
                                            html.Label("Font color"),
                                            dcc.Dropdown(
                                                id="theme-font-color",
                                                options=[
                                                    {"label": "Black", "value": "#000000"},
                                                    {"label": "Dark gray", "value": "#333333"},
                                                    {"label": "Gray", "value": "#666666"},
                                                    {"label": "White", "value": "#FFFFFF"},
                                                    {"label": "Navy", "value": "#1F3A93"},
                                                    {"label": "Blue", "value": "#1E88E5"},
                                                    {"label": "Teal", "value": "#00897B"},
                                                    {"label": "Green", "value": "#2E7D32"},
                                                    {"label": "Orange", "value": "#FB8C00"},
                                                    {"label": "Red", "value": "#C62828"},
                                                ],
                                                placeholder="Pick a text color",
                                                clearable=True,
                                                searchable=True,
                                    ),
                                    html.Label("Accent color"),
                                    dcc.Dropdown(
                                        id="theme-accent-color",
                                        options=[
                                            {"label": "Blue", "value": "#2563eb"},
                                            {"label": "Indigo", "value": "#4338ca"},
                                            {"label": "Teal", "value": "#0d9488"},
                                            {"label": "Green", "value": "#2e7d32"},
                                            {"label": "Orange", "value": "#fb8c00"},
                                            {"label": "Red", "value": "#c62828"},
                                            {"label": "Pink", "value": "#d81b60"},
                                            {"label": "Purple", "value": "#7c3aed"},
                                            {"label": "Gray", "value": "#4b5563"},
                                            {"label": "Black", "value": "#111827"},
                                        ],
                                        placeholder="Pick an accent color",
                                        clearable=True,
                                        searchable=True,
                                    ),
                                    html.Label("Background color"),
                                    dcc.Dropdown(
                                        id="theme-bg-color",
                                        options=[
                                            {"label": "White", "value": "#ffffff"},
                                            {"label": "Off white", "value": "#f8fafc"},
                                            {"label": "Light gray", "value": "#f1f5f9"},
                                            {"label": "Warm gray", "value": "#f5f0eb"},
                                            {"label": "Cool gray", "value": "#e5e7eb"},
                                            {"label": "Soft blue", "value": "#e0f2fe"},
                                            {"label": "Soft green", "value": "#e8f5e9"},
                                            {"label": "Soft yellow", "value": "#fff7e6"},
                                            {"label": "Soft pink", "value": "#fef2f2"},
                                            {"label": "Soft purple", "value": "#f3e8ff"},
                                        ],
                                        placeholder="Pick a background color",
                                        clearable=True,
                                        searchable=True,
                                    ),
                                            html.Label("Orientation"),
                                            dcc.Dropdown(
                                                id="theme-orientation",
                                                options=[
                                                    {"label": "Portrait (vertical)", "value": "portrait"},
                                                    {"label": "Landscape (horizontal)", "value": "landscape"},
                                                ],
                                                value="portrait",
                                                clearable=False,
                                            ),
                                            html.Label("Background image URL/path"),
                                            dcc.Input(
                                                id="theme-bg-image",
                                                type="text",
                                                placeholder="https://... or local path",
                                                className="text-input",
                                            ),
                                    html.Label("Augmentation"),
                                    dcc.Checklist(
                                        id="theme-security-options",
                                        options=[
                                            {"label": "Diagonal hatch", "value": "diagonal_lines"},
                                            {"label": "Noise texture", "value": "noise"},
                                            {"label": "Watermark text", "value": "watermark"},
                                            {"label": "Thin black lines", "value": "thin_lines"},
                                            {"label": "Slight blur", "value": "blur_text"},
                                        ],
                                        value=[],
                                        className="checklist",
                                    ),
                                            html.Label("Watermark text (if enabled)"),
                                            dcc.Input(
                                                id="theme-security-watermark",
                                                type="text",
                                                placeholder="Confidential / Draft / Sample",
                                                className="text-input",
                                            ),
                                        ],
                                    ),
                                    html.Button("Apply theme", id="apply-theme-btn", n_clicks=0, className="secondary"),
                                ],
                            ),
                            html.Hr(),
                            html.Div(
                                className="designer-section",
                                children=[
                                    html.H4("Selected element"),
                                    html.Div(id="selected-path", className="muted"),
                                    html.Label("Text content"),
                                    dcc.Textarea(
                                        id="selected-text-input",
                                        className="text-input",
                                        placeholder="Click a field in preview to edit its text",
                                    ),
                                    html.Div(
                                        className="form-grid",
                                        children=[
                                            html.Label("Text color"),
                                            dcc.Dropdown(
                                                id="selected-text-color",
                                                options=[
                                                    {"label": "Black", "value": "#000000"},
                                                    {"label": "Dark gray", "value": "#333333"},
                                                    {"label": "Gray", "value": "#666666"},
                                                    {"label": "White", "value": "#FFFFFF"},
                                                    {"label": "Navy", "value": "#1F3A93"},
                                                    {"label": "Blue", "value": "#1E88E5"},
                                                    {"label": "Teal", "value": "#00897B"},
                                                    {"label": "Green", "value": "#2E7D32"},
                                                    {"label": "Orange", "value": "#FB8C00"},
                                                    {"label": "Red", "value": "#C62828"},
                                                ],
                                                placeholder="Pick a text color",
                                                clearable=True,
                                                searchable=True,
                                            ),
                                            html.Label("Font size (px)"),
                                            dcc.Input(
                                                id="selected-text-size",
                                                type="number",
                                                min=8,
                                                max=48,
                                                step=1,
                                                className="text-input",
                                            ),
                                            html.Label("Font weight"),
                                            dcc.Dropdown(
                                                id="selected-text-weight",
                                                options=[
                                                    {"label": "Normal", "value": "400"},
                                                    {"label": "Medium", "value": "500"},
                                                    {"label": "Semibold", "value": "600"},
                                                    {"label": "Bold", "value": "700"},
                                                ],
                                                clearable=True,
                                                placeholder="Choose weight",
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="form-actions",
                                        children=[
                                            html.Button("Update text", id="update-text-btn", n_clicks=0, className="primary"),
                                            html.Button("Update style", id="update-style-btn", n_clicks=0, className="secondary"),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="card",
                        children=[
                            html.H3("Preview"),
                            html.P(
                                className="muted",
                                children="Rendered invoice uses your template styling, background, fonts, and logo.",
                            ),
                            dcc.Loading(
                                id="preview-loader",
                                type="circle",
                                children=html.Div(id="invoice-preview", className="invoice-preview"),
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    html.H3("JSON cheat sheet"),
                    html.Ul(
                        [
                            html.Li("Top-level keys: template (layout/styling) and data (values)."),
                            html.Li("Template controls page size, background image/color, logo, fonts, and sections."),
                            html.Li("Sections support grid fields, two-column panels, item tables, and notes areas."),
                            html.Li(
                                "Use dotted value_path entries (e.g. invoice.number or totals.subtotal) to bind data."
                            ),
                            html.Li("Use format:'currency' to format numbers with the template's currency symbol."),
                        ]
                    ),
                    html.Div(id="feedback", className="feedback"),
                    html.Div(id="download-feedback", className="feedback"),
                ],
            ),
        ],
    )

    ocr_tab = html.Div(
        className="card",
        children=[
            html.H3("OCR checker"),
            html.P(
                className="muted",
                children=(
                    "Upload a rendered PDF and the OCR JSON (from build_ocr_ground_truth) to see overlayed boxes and "
                    "verify positions quickly."
                ),
            ),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "12px", "marginBottom": "8px"},
                children=[
                    html.Div(
                        children=[
                            html.Label("PDF"),
                            dcc.Upload(
                                id="ocr-pdf-upload",
                                children=html.Div(["Drop PDF here or ", html.B("click to choose")]),
                                multiple=False,
                                className="upload-area",
                            ),
                            html.Div(id="ocr-pdf-status", className="muted"),
                        ]
                    ),
                    html.Div(
                        children=[
                            html.Label("OCR JSON"),
                            dcc.Upload(
                                id="ocr-json-upload",
                                children=html.Div(["Drop OCR JSON here or ", html.B("click to choose")]),
                                multiple=False,
                                className="upload-area",
                            ),
                            html.Div(id="ocr-json-status", className="muted"),
                        ]
                    ),
                ],
            ),
            html.Div(id="ocr-viewer-placeholder", className="muted", style={"marginTop": "4px"}),
            html.Div(id="ocr-viewer", style={"marginTop": "12px"}),
        ],
    )

    dataset_tab = html.Div(
        className="card",
        children=[
            html.H3("Dataset maker"),
            html.P(
                className="muted",
                children=(
                    "Generate batches of PDFs with OCR JSON using an LLM prompt. Configure fonts, colors, augmentations, "
                    "and difficulty, then edit the prompt before generating."
                ),
            ),
            html.Div(
                className="form-grid",
                children=[
                    html.Label("OpenAI API key"),
                    dcc.Input(
                        id="ds-api-key",
                        type="password",
                        placeholder="sk-...",
                        value=api_key_default,
                        className="text-input",
                    ),
                    html.Div(api_key_hint, className="muted"),
                    html.Label("Model"),
                    dcc.Dropdown(
                        id="ds-model",
                        options=[
                            {"label": "gpt-4.1-mini", "value": "gpt-4.1-mini"},
                            {"label": "gpt-4.1", "value": "gpt-4.1"},
                            {"label": "gpt-4o-mini", "value": "gpt-4o-mini"},
                            {"label": "gpt-4o", "value": "gpt-4o"},
                            {"label": "o4-mini", "value": "o4-mini"},
                        ],
                        value="gpt-4.1-mini",
                        clearable=False,
                        searchable=True,
                        placeholder="Choose a model",
                    ),
                    html.Label("Samples per language"),
                    dcc.Input(
                        id="ds-sample-count",
                        type="number",
                        min=1,
                        max=9999999,
                        step=1,
                        value=5,
                        className="text-input",
                    ),
                    html.Label("Difficulty"),
                    dcc.Slider(
                        id="ds-difficulty",
                        min=1,
                        max=10,
                        step=1,
                        value=5,
                        marks={1: "Easy", 5: "Moderate", 10: "Hard"},
                    ),
                    html.Label("Variability (layout/content)"),
                    dcc.Slider(
                        id="ds-variability",
                        min=1,
                        max=10,
                        step=1,
                        value=7,
                        marks={1: "Low", 5: "Med", 10: "High"},
                    ),
                    html.Label("Min pages"),
                    dcc.Input(
                        id="ds-pages-min",
                        type="number",
                        min=1,
                        max=20,
                        step=1,
                        value=1,
                        className="text-input",
                    ),
                    html.Label("Max pages"),
                    dcc.Input(
                        id="ds-pages-max",
                        type="number",
                        min=1,
                        max=20,
                        step=1,
                        value=5,
                        className="text-input",
                    ),
                    html.Label("Allowed fonts"),
                    dcc.Dropdown(
                        id="ds-fonts",
                        options=[
                            {"label": name, "value": name}
                            for name in [
                                "Inter",
                                "Manrope",
                                "Roboto",
                                "Segoe UI",
                                "Open Sans",
                                "Montserrat",
                                "Lato",
                                "Source Sans Pro",
                                "Georgia",
                                "Times New Roman",
                                "Playfair Display",
                                "Cormorant Garamond",
                                "Merriweather",
                                "EB Garamond",
                                "DM Serif Display",
                                "Spectral",
                                "PT Serif",
                                "Space Mono",
                                "IBM Plex Mono",
                                "Handlee",
                                "Caveat",
                                "Shadows Into Light",
                                "Amatic SC",
                                "Pacifico",
                                "Rock Salt",
                                "Permanent Marker",
                                "Noto Sans SC",
                                "Noto Serif SC",
                                "Noto Sans JP",
                                "Noto Serif JP",
                                "Noto Sans KR",
                            ]
                        ],
                        multi=True,
                        value=["Inter", "Manrope", "Roboto"],
                        placeholder="Select fonts to use",
                    ),
                    html.Label("Languages (for content)"),
                    dcc.Dropdown(
                        id="ds-languages",
                        options=[
                            {"label": "English", "value": "English"},
                            {"label": "Czech", "value": "Czech"},
                            {"label": "Slovak", "value": "Slovak"},
                            {"label": "German", "value": "German"},
                            {"label": "French", "value": "French"},
                            {"label": "Spanish", "value": "Spanish"},
                            {"label": "Polish", "value": "Polish"},
                            {"label": "Italian", "value": "Italian"},
                            {"label": "Dutch", "value": "Dutch"},
                            {"label": "Portuguese", "value": "Portuguese"},
                            {"label": "Arabic", "value": "Arabic"},
                            {"label": "Hindi", "value": "Hindi"},
                            {"label": "Chinese", "value": "Chinese"},
                            {"label": "Japanese", "value": "Japanese"},
                        ],
                        multi=True,
                        value=["English", "Czech", "German"],
                        placeholder="Select languages to allow",
                    ),
                    html.Label("Text sizes (px)"),
                    dcc.Input(
                        id="ds-size-min",
                        type="number",
                        min=8,
                        max=32,
                        step=1,
                        value=12,
                        className="text-input",
                        placeholder="Min size",
                    ),
                    dcc.Input(
                        id="ds-size-max",
                        type="number",
                        min=8,
                        max=48,
                        step=1,
                        value=18,
                        className="text-input",
                        placeholder="Max size",
                    ),
                    html.Label("Allowed text colors"),
                    dcc.Dropdown(
                        id="ds-colors",
                        options=[
                            {"label": "Black", "value": "#000000"},
                            {"label": "Dark gray", "value": "#333333"},
                            {"label": "Gray", "value": "#666666"},
                            {"label": "Navy", "value": "#1F3A93"},
                            {"label": "Blue", "value": "#1E88E5"},
                            {"label": "Teal", "value": "#00897B"},
                            {"label": "Green", "value": "#2E7D32"},
                            {"label": "Orange", "value": "#FB8C00"},
                            {"label": "Red", "value": "#C62828"},
                        ],
                        multi=True,
                        value=["#000000", "#333333", "#1F3A93", "#1E88E5"],
                        placeholder="Select text colors",
                    ),
                    html.Label("Augmentations"),
                    dcc.Checklist(
                        id="ds-augmentations",
                        options=[
                            {"label": "Diagonal hatch", "value": "diagonal_lines"},
                            {"label": "Noise texture", "value": "noise"},
                            {"label": "Watermark", "value": "watermark"},
                            {"label": "Thin lines", "value": "thin_lines"},
                            {"label": "Blur text", "value": "blur_text"},
                        ],
                        value=["diagonal_lines", "noise"],
                        className="checklist",
                    ),
                    html.Label("Output directory"),
                    dcc.Input(
                        id="ds-output-path",
                        type="text",
                        placeholder="C:/path/to/output",
                        value=ds_output_default,
                        className="text-input",
                    ),
                ],
            ),
            html.Label("Prompt (editable)"),
            dcc.Textarea(
                id="ds-prompt",
                className="json-editor",
                style={"minHeight": "160px"},
            ),
            html.Div(
                className="form-actions",
                children=[
                    html.Button("Refresh prompt from settings", id="ds-refresh-prompt", n_clicks=0, className="secondary"),
                    html.Button("Generate dataset", id="ds-generate", n_clicks=0, className="primary"),
                    html.Button("Download dataset (ZIP)", id="ds-download-zip", n_clicks=0, className="ghost"),
                ],
                style={"marginTop": "8px"},
            ),
            html.Div(
                style={"display": "flex", "alignItems": "center", "gap": "12px", "marginTop": "10px"},
                children=[
                    html.Progress(id="ds-progress", value="0", max=100, style={"width": "200px"}),
                    html.Div(html.Div("Idle.", className="pill info"), id="ds-status", className="feedback"),
                ],
            ),
            html.Div(id="ds-download-status", className="feedback"),
            html.Label("Raw LLM output (first 1–2 samples)"),
            html.Pre(id="ds-log", className="json-editor", style={"minHeight": "140px"}),
            dcc.Store(id="ds-job-id"),
            dcc.Interval(id="ds-progress-interval", interval=800, n_intervals=0, disabled=False),
        ],
    )

    evaluation_tab = html.Div(
        className="main-grid",
        children=[
            html.Div(
                className="card",
                children=[
                    html.H3("Model evaluation"),
                    html.P(
                        className="muted",
                        children=(
                            "Benchmark OCR baselines and multimodal LLMs on a fixed invoice dataset. "
                            "Run multiple methods, compare metrics, and review error patterns."
                        ),
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    html.H4("Dataset"),
                    html.Div(
                        className="form-grid",
                        children=[
                            html.Label("Dataset location"),
                            dcc.Input(
                                id="eval-dataset-path",
                                type="text",
                                value=eval_dataset_path,
                                placeholder="C:/path/to/dataset",
                                className="text-input",
                            ),
                            html.Label("Dataset ZIP upload (optional)"),
                            dcc.Upload(
                                id="eval-dataset-upload",
                                children=html.Div(["Drop dataset ZIP here or ", html.B("click to select")]),
                                multiple=False,
                                className="upload-area",
                            ),
                            html.Div(id="eval-upload-status", className="muted"),
                            html.Label("Samples to evaluate"),
                            dcc.Input(
                                id="eval-sample-limit",
                                type="number",
                                min=1,
                                max=500,
                                step=1,
                                value=50,
                                className="text-input",
                            ),
                            html.Label("Shuffle dataset"),
                            dcc.Checklist(
                                id="eval-shuffle",
                                options=[{"label": "Shuffle before sampling", "value": "shuffle"}],
                                value=["shuffle"],
                                className="checklist",
                            ),
                            html.Label("Random seed"),
                            dcc.Input(
                                id="eval-seed",
                                type="number",
                                min=0,
                                max=9999,
                                step=1,
                                value=42,
                                className="text-input",
                            ),
                            html.Label("Scoring scope"),
                            dcc.Checklist(
                                id="eval-visible-only",
                                options=[{"label": "Score only fields rendered by the template", "value": "visible"}],
                                value=["visible"],
                                className="checklist",
                            ),
                            html.Label("Plots"),
                            dcc.Checklist(
                                id="eval-save-plots",
                                options=[{"label": "Save plots to dataset folder (HTML)", "value": "save"}],
                                value=["save"],
                                className="checklist",
                            ),
                        ],
                    ),
                    html.P(
                        className="muted",
                        children="Use an absolute path to a dataset folder that contains PDF and OCR JSON pairs.",
                        style={"marginTop": "8px"},
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    html.H4("OCR sources"),
                    dcc.Checklist(
                        id="eval-ocr-sources",
                        options=[
                            {"label": "PDF text (PyMuPDF)", "value": "pymupdf"},
                            {"label": "Tesseract OCR (if installed)", "value": "tesseract"},
                            {"label": "EasyOCR (if installed)", "value": "easyocr"},
                            {"label": "OCR JSON (ground truth)", "value": "ocr_json"},
                        ],
                        value=["pymupdf", "tesseract", "easyocr", "ocr_json"],
                        className="checklist",
                    ),
                    html.H4("Extraction methods"),
                    dcc.Checklist(
                        id="eval-methods",
                        options=[
                            {"label": "Regex baseline", "value": "regex"},
                            {"label": "Key-value baseline", "value": "key_value"},
                            {"label": "Pattern baseline", "value": "pattern"},
                            {"label": "Ensemble baseline", "value": "ensemble"},
                            {"label": "LLM from text", "value": "llm_text"},
                            {"label": "LLM text + patterns", "value": "llm_text_hybrid"},
                            {"label": "LLM from images (vision)", "value": "llm_vision"},
                        ],
                        value=["regex", "key_value", "pattern", "ensemble", "llm_text", "llm_text_hybrid", "llm_vision"],
                        className="checklist",
                    ),
                    html.P(
                        className="muted",
                        children="Tesseract/EasyOCR methods are skipped if the libraries are not installed.",
                        style={"marginTop": "8px"},
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    html.H4("LLM settings"),
                    html.Div(
                        className="form-grid",
                        children=[
                            html.Label("API key"),
                            dcc.Input(
                                id="eval-api-key",
                                type="password",
                                placeholder="sk-...",
                                value=api_key_default,
                                className="text-input",
                            ),
                            html.Div(api_key_hint, className="muted"),
                            html.Label("API base URL (optional)"),
                            dcc.Input(
                                id="eval-api-base-url",
                                type="text",
                                placeholder="https://api.openai.com/v1",
                                value=api_base_url_default,
                                className="text-input",
                            ),
                            html.Div(
                                "Use this for OpenAI-compatible providers (OpenRouter, local servers).",
                                className="muted",
                            ),
                            html.Label("Secondary API key (optional)"),
                            dcc.Input(
                                id="eval-api-key-alt",
                                type="password",
                                placeholder="sk-...",
                                value=api_key_alt_default,
                                className="text-input",
                            ),
                            html.Div(api_key_alt_hint, className="muted"),
                            html.Label("Secondary API base URL (optional)"),
                            dcc.Input(
                                id="eval-api-base-url-alt",
                                type="text",
                                placeholder="https://api.provider.com/v1",
                                value=api_base_url_alt_default,
                                className="text-input",
                            ),
                            html.Div(api_base_url_alt_hint, className="muted"),
                            html.Label("Secondary key model match (comma-separated)"),
                            dcc.Input(
                                id="eval-api-key-alt-match",
                                type="text",
                                placeholder="qwen, openrouter/, provider/model",
                                value=api_key_alt_match_default,
                                className="text-input",
                            ),
                            html.Div(api_key_alt_match_hint, className="muted"),
                            html.Label("Gemini API key (optional)"),
                            dcc.Input(
                                id="eval-gemini-api-key",
                                type="password",
                                placeholder="AIza...",
                                value=gemini_api_key_default,
                                className="text-input",
                            ),
                            html.Div(gemini_api_key_hint, className="muted"),
                            html.Label("Anthropic API key (optional)"),
                            dcc.Input(
                                id="eval-anthropic-api-key",
                                type="password",
                                placeholder="sk-ant-...",
                                value=anthropic_api_key_default,
                                className="text-input",
                            ),
                            html.Div(anthropic_api_key_hint, className="muted"),
                            html.Label("Models"),
                            dcc.Dropdown(
                                id="eval-llm-models",
                                options=[
                                    {"label": "gpt-4.1-mini", "value": "gpt-4.1-mini"},
                                    {"label": "gpt-4.1", "value": "gpt-4.1"},
                                    {"label": "gpt-4o-mini", "value": "gpt-4o-mini"},
                                    {"label": "gpt-4o", "value": "gpt-4o"},
                                    {"label": "o4-mini", "value": "o4-mini"},
                                    {"label": "Claude Sonnet 4.5 (2025-09-29)", "value": "claude-sonnet-4-5-20250929"},
                                    {"label": "Claude Opus 4.5 (2025-11-01)", "value": "claude-opus-4-5-20251101"},
                                    {"label": "Claude Haiku 4.5 (2025-10-01)", "value": "claude-haiku-4-5-20251001"},
                                    {"label": "Claude Opus 4.1 (2025-08-05)", "value": "claude-opus-4-1-20250805"},
                                    {"label": "Claude Opus 4 (2025-05-14)", "value": "claude-opus-4-20250514"},
                                    {"label": "Claude Sonnet 4 (2025-05-14)", "value": "claude-sonnet-4-20250514"},
                                    {"label": "Claude 3.5 Haiku (2024-10-22)", "value": "claude-3-5-haiku-20241022"},
                                    {"label": "Claude 3 Haiku (2024-03-07)", "value": "claude-3-haiku-20240307"},
                                    {"label": "Seed1.6-vision", "value": "Seed1.6-vision"},
                                    {"label": "TeleMMM-2.0", "value": "TeleMMM-2.0"},
                                    {"label": "Qwen Plus", "value": "qwen-plus"},
                                    {"label": "Qwen Max", "value": "qwen-max"},
                                    {"label": "Qwen VL Plus", "value": "qwen-vl-plus"},
                                    {"label": "Qwen VL Max", "value": "qwen-vl-max"},
                                    {"label": "Qwen3 VL Plus (2025-12-19)", "value": "qwen3-vl-plus-2025-12-19"},
                                    {"label": "Qwen3-Omni-30B-A3B-Instruct", "value": "Qwen3-Omni-30B-A3B-Instruct"},
                                    {"label": "Qwen3 Omni Flash", "value": "qwen3-omni-flash"},
                                    {"label": "Qwen3 Omni Flash Realtime (2025-12-01)", "value": "qwen3-omni-flash-realtime-2025-12-01"},
                                    {"label": "Nemotron Nano V2 VL (12B)", "value": "Nemotron Nano V2 VL (12B)"},
                                    {"label": "Gemini 2.5 Pro", "value": "gemini-2.5-pro"},
                                ],
                                value=["gpt-4.1-mini"],
                                multi=True,
                                placeholder="Select models",
                            ),
                            html.Label("Custom models (comma-separated)"),
                            dcc.Input(
                                id="eval-custom-models",
                                type="text",
                                placeholder="provider/model-id, other-model",
                                value="",
                                className="text-input",
                            ),
                            html.Label("Max pages for vision"),
                            dcc.Input(
                                id="eval-max-pages",
                                type="number",
                                min=1,
                                max=5,
                                step=1,
                                value=2,
                                className="text-input",
                            ),
                        ],
                    ),
                    html.P(
                        className="muted",
                        children=(
                            "LLM methods require an API key. Vision models receive page images directly; "
                            "use a vision-capable model such as gpt-4o or gpt-4o-mini. "
                            "For non-OpenAI models, set an OpenAI-compatible base URL and ensure the model ID matches "
                            "your provider."
                        ),
                        style={"marginTop": "8px"},
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    html.Div(
                        className="form-actions",
                        children=[
                            html.Button("Run evaluation", id="eval-run", n_clicks=0, className="primary"),
                            html.Button("Download results", id="eval-download-btn", n_clicks=0, className="secondary"),
                            html.Button("Download plots (HTML)", id="eval-download-plots-btn", n_clicks=0, className="ghost"),
                        ],
                    ),
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "12px", "marginTop": "10px"},
                        children=[
                            html.Progress(id="eval-progress", value="0", max=100, style={"width": "200px"}),
                            html.Div(id="eval-status", className="feedback"),
                        ],
                    ),
                    dcc.Markdown(id="eval-summary", className="muted"),
                    html.H4("Plots"),
                    dcc.Graph(id="eval-graph-overall"),
                    dcc.Graph(id="eval-graph-items"),
                    dcc.Graph(id="eval-graph-fields"),
                    dcc.Graph(id="eval-graph-item-fields"),
                    html.H4("Error analysis"),
                    html.Pre(id="eval-errors", className="json-editor", style={"minHeight": "200px"}),
                    html.H4("Runtime errors"),
                    html.Pre(id="eval-runtime-errors", className="json-editor", style={"minHeight": "140px"}),
                ],
            ),
        ],
    )

    return html.Div(
        className="page-shell",
        children=[
            dcc.Store(id="payload-store"),
            dcc.Store(id="selection-store"),
            dcc.Store(id="ocr-pdf-pages"),
            dcc.Store(id="ocr-items"),
            dcc.Store(id="ds-prompt-store"),
            dcc.Store(id="eval-job-id"),
            dcc.Store(id="eval-results-store"),
            dcc.Store(id="eval-uploaded-dataset-path"),
            dcc.Download(id="download-invoice"),
            dcc.Download(id="download-pdf"),
            dcc.Download(id="download-ocr"),
            dcc.Download(id="ds-download"),
            dcc.Download(id="download-eval-results"),
            dcc.Download(id="download-eval-plots"),
            dcc.Tabs(
                id="main-tabs",
                value="tab-invoice",
                children=[
                    dcc.Tab(label="Invoice builder", value="tab-invoice", children=invoice_tab),
                    dcc.Tab(label="OCR checker", value="tab-ocr", children=ocr_tab),
                    dcc.Tab(label="Dataset maker", value="tab-dataset", children=dataset_tab),
                    dcc.Tab(label="Model evaluation", value="tab-eval", children=evaluation_tab),
                ],
            ),
            dcc.Interval(id="eval-progress-interval", interval=1000, n_intervals=0, disabled=False),
        ],
    )
