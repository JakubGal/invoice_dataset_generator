from dataclasses import dataclass, field
from typing import Any, Dict


def _to_px(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, (int, float)):
        return f"{value}px"
    return str(value)


@dataclass
class TemplateTheme:
    title: str = "Invoice"
    width: str = "900px"
    height: str = "auto"
    orientation: str = "portrait"
    padding: str = "32px"
    background_color: str = "#f8fafc"
    background_image: str = ""
    border_radius: str = "16px"
    font_family: str = "Segoe UI, system-ui, sans-serif"
    font_color: str = "#0f172a"
    font_size: str = "14px"
    accent_color: str = "#2563eb"
    currency: str = "$"
    logo: Dict[str, Any] = field(default_factory=dict)
    hide_border: bool = False

    @classmethod
    def from_template(cls, template: Dict[str, Any]) -> "TemplateTheme":
        page = template.get("page", {}) if isinstance(template.get("page", {}), dict) else {}
        font = template.get("font", {}) if isinstance(template.get("font", {}), dict) else {}
        orientation = page.get("orientation", "portrait")
        default_width = "1200px" if orientation == "landscape" else "900px"

        return cls(
            title=str(template.get("title", "Invoice")),
            width=str(page.get("width", default_width)),
            height=str(page.get("height", "auto")),
            orientation=orientation,
            padding=_to_px(page.get("padding", "32px"), "32px"),
            background_color=page.get("background_color", "#f8fafc"),
            background_image=page.get("background_image", ""),
            border_radius=_to_px(page.get("border_radius", "16px"), "16px"),
            font_family=font.get("family", "Segoe UI, system-ui, sans-serif"),
            font_color=font.get("color", "#0f172a"),
            font_size=_to_px(font.get("size", "14px"), "14px"),
            accent_color=template.get("accent_color", "#2563eb"),
            currency=template.get("currency", "$"),
            logo=template.get("logo", {}) if isinstance(template.get("logo", {}), dict) else {},
            hide_border=bool(page.get("hide_border", False)),
        )
