import os

from dash import Dash

from invoice_app.callbacks import register_callbacks
from invoice_app.layout import build_layout


def create_app() -> Dash:
    app = Dash(
        __name__,
        suppress_callback_exceptions=True,
        title="Invoice Builder",
    )
    app.layout = build_layout(app)
    register_callbacks(app)
    return app


app = create_app()
server = app.server


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8050"))
    app.run_server(debug=True, host="0.0.0.0", port=port)
