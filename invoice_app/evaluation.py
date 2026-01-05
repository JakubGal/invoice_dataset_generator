from __future__ import annotations

import base64
import json
import os
import re
import shutil
import statistics
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from invoice_app.utils import dotted_get, set_dotted

DEFAULT_DATASET_PATH = Path("C:/Users/bukaj/Documents/Bakalarka/gen7")


@dataclass(frozen=True)
class FieldSpec:
    path: str
    label: str
    ftype: str


FIELD_SPECS: List[FieldSpec] = [
    FieldSpec("invoice.number", "Invoice number", "text"),
    FieldSpec("invoice.date", "Invoice date", "date"),
    FieldSpec("invoice.due_date", "Due date", "date"),
    FieldSpec("invoice.reference", "Reference", "text"),
    FieldSpec("seller.name", "Seller name", "text"),
    FieldSpec("seller.contact", "Seller contact", "text"),
    FieldSpec("seller.email", "Seller email", "text"),
    FieldSpec("seller.address", "Seller address", "text"),
    FieldSpec("client.name", "Client name", "text"),
    FieldSpec("client.contact", "Client contact", "text"),
    FieldSpec("client.email", "Client email", "text"),
    FieldSpec("client.address", "Client address", "text"),
    FieldSpec("totals.subtotal", "Subtotal", "amount"),
    FieldSpec("totals.tax", "Tax", "amount"),
    FieldSpec("totals.due", "Amount due", "amount"),
    FieldSpec("payment.bank", "Bank", "text"),
    FieldSpec("payment.iban", "IBAN", "text"),
    FieldSpec("payment.reference", "Payment reference", "text"),
    FieldSpec("notes", "Notes", "text"),
]

ITEM_FIELD_SPECS: List[FieldSpec] = [
    FieldSpec("description", "Item description", "text"),
    FieldSpec("qty", "Quantity", "number"),
    FieldSpec("unit_price", "Unit price", "amount"),
    FieldSpec("line_total", "Line total", "amount"),
]

LABEL_MAP: Dict[str, List[str]] = {
    "invoice.number": [
        "invoice number",
        "invoice no",
        "invoice #",
        "invoice id",
        "rechnungsnummer",
        "rechnungs nr",
        "rechnungsnr",
        "cislo faktury",
        "c\u00edslo faktury",
        "faktura c",
        "faktura \u010d",
        "\u53d1\u7968\u7f16\u53f7",
        "\u53d1\u7968\u53f7\u7801",
        "\u53d1\u7968\u53f7",
    ],
    "invoice.date": [
        "invoice date",
        "date",
        "rechnungsdatum",
        "ausstellungsdatum",
        "datum vystaveni",
        "datum vystaven\u00ed",
        "\u5f00\u7968\u65e5\u671f",
        "\u53d1\u7968\u65e5\u671f",
    ],
    "invoice.due_date": [
        "due date",
        "payment due",
        "pay by",
        "faelligkeitsdatum",
        "f\u00e4lligkeitsdatum",
        "zahlbar bis",
        "datum splatnosti",
        "splatnost",
        "\u5230\u671f\u65e5\u671f",
        "\u5230\u671f\u65e5",
        "\u4ed8\u6b3e\u671f\u9650",
    ],
    "invoice.reference": [
        "reference",
        "ref",
        "order ref",
        "po",
        "bestellnummer",
        "auftragsnummer",
        "referenz",
        "variabilni symbol",
        "variabiln\u00ed symbol",
        "objednavka",
        "objedn\u00e1vka",
        "\u53c2\u8003\u53f7",
        "\u53c2\u8003\u7f16\u53f7",
        "\u8ba2\u5355\u53f7",
        "\u8ba2\u5355\u7f16\u53f7",
        "\u91c7\u8d2d\u8ba2\u5355",
    ],
    "seller.name": [
        "seller",
        "from",
        "supplier",
        "lieferant",
        "verkaeufer",
        "verk\u00e4ufer",
        "dodavatel",
        "dodavatel",
        "vystavitel",
        "vystavitel",
        "\u5356\u65b9",
        "\u9500\u552e\u65b9",
        "\u4f9b\u5e94\u5546",
        "\u53d1\u7968\u65b9",
    ],
    "seller.contact": [
        "seller contact",
        "from contact",
        "supplier contact",
        "kontakt",
        "kontaktperson",
        "ansprechpartner",
        "kontaktni osoba",
        "kontaktn\u00ed osoba",
        "\u8054\u7cfb\u4eba",
        "\u8054\u7cfb\u65b9\u5f0f",
    ],
    "seller.email": [
        "seller email",
        "from email",
        "supplier email",
        "email",
        "e-mail",
        "emailova adresa",
        "emailov\u00e1 adresa",
        "\u7535\u5b50\u90ae\u4ef6",
        "\u90ae\u7bb1",
    ],
    "seller.address": [
        "seller address",
        "from address",
        "supplier address",
        "address",
        "anschrift",
        "adresse",
        "adresa",
        "sidlo",
        "s\u00eddlo",
        "\u5730\u5740",
    ],
    "client.name": [
        "client",
        "bill to",
        "customer",
        "kunde",
        "rechnungsempfaenger",
        "rechnungsempf\u00e4nger",
        "empfaenger",
        "empf\u00e4nger",
        "odberatel",
        "odb\u011bratel",
        "zakaznik",
        "z\u00e1kazn\u00edk",
        "\u4e70\u65b9",
        "\u5ba2\u6237",
        "\u8d2d\u65b9",
    ],
    "client.contact": [
        "client contact",
        "bill to contact",
        "customer contact",
        "kontakt",
        "ansprechpartner",
        "kontaktni osoba",
        "kontaktn\u00ed osoba",
        "\u8054\u7cfb\u4eba",
        "\u8054\u7cfb\u65b9\u5f0f",
    ],
    "client.email": [
        "client email",
        "customer email",
        "email",
        "e-mail",
        "\u7535\u5b50\u90ae\u4ef6",
        "\u90ae\u7bb1",
    ],
    "client.address": [
        "client address",
        "bill to address",
        "customer address",
        "anschrift",
        "adresse",
        "adresa",
        "\u5730\u5740",
    ],
    "totals.subtotal": ["subtotal", "zwischensumme", "netto", "mezisoucet", "mezisou\u010det", "\u5c0f\u8ba1"],
    "totals.tax": ["tax", "vat", "mwst", "umsatzsteuer", "ust", "dph", "da\u0148", "\u7a0e\u989d", "\u7a0e"],
    "totals.due": [
        "total",
        "amount due",
        "balance due",
        "total due",
        "gesamt",
        "gesamtbetrag",
        "summe",
        "celkem",
        "castka k uhrade",
        "\u010d\u00e1stka k \u00fahrad\u011b",
        "k uhrade",
        "\u5408\u8ba1",
        "\u603b\u8ba1",
        "\u5e94\u4ed8",
        "\u5e94\u4ed8\u91d1\u989d",
        "\u603b\u989d",
    ],
    "payment.bank": ["bank", "bankverbindung", "banka", "bankovni spojeni", "bankovn\u00ed spojen\u00ed", "\u5f00\u6237\u884c", "\u94f6\u884c"],
    "payment.iban": ["iban"],
    "payment.reference": [
        "payment reference",
        "payment ref",
        "reference",
        "verwendungszweck",
        "zahlungsreferenz",
        "variabilni symbol",
        "variabiln\u00ed symbol",
        "specificky symbol",
        "specifick\u00fd symbol",
        "\u4ed8\u6b3e\u53c2\u8003",
        "\u6c47\u6b3e\u9644\u8a00",
    ],
    "notes": ["notes", "note", "bemerkungen", "hinweis", "notiz", "poznamka", "pozn\u00e1mka", "\u5907\u6ce8", "\u8bf4\u660e"],
}

SUBLABEL_SKIP = {
    "name",
    "contact",
    "email",
    "e-mail",
    "address",
    "jmeno",
    "jm\u00e9no",
    "nazev",
    "n\u00e1zev",
    "kontakt",
    "kontaktni osoba",
    "kontaktn\u00ed osoba",
    "adresa",
    "anschrift",
    "adresse",
    "\u540d\u79f0",
    "\u8054\u7cfb\u4eba",
    "\u8054\u7cfb\u65b9\u5f0f",
    "\u7535\u5b50\u90ae\u4ef6",
    "\u90ae\u7bb1",
    "\u5730\u5740",
}

SYSTEM_PROMPT = (
    "You extract structured invoice data. Reply ONLY with a JSON object (no prose, no code fences). "
    "Use ISO dates (YYYY-MM-DD) when possible. Use numbers for amounts and quantities."
)

SCHEMA_HINT = {
    "invoice": {"number": "", "date": "", "due_date": "", "reference": ""},
    "seller": {"name": "", "contact": "", "email": "", "address": ""},
    "client": {"name": "", "contact": "", "email": "", "address": ""},
    "items": [{"description": "", "qty": "", "unit_price": "", "line_total": ""}],
    "totals": {"subtotal": "", "tax": "", "due": ""},
    "payment": {"bank": "", "iban": "", "reference": ""},
    "notes": "",
}


def list_dataset_samples(dataset_dir: Path) -> List[Dict[str, Any]]:
    samples: List[Dict[str, Any]] = []
    if not dataset_dir.exists():
        return samples

    def _strip_code_fence(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z0-9]*", "", text).strip()
            if text.endswith("```"):
                text = text[: -3].strip()
        return text

    def _parse_jsonish(value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return value
        if not isinstance(value, str):
            return value
        cleaned = _strip_code_fence(value)
        try:
            return json.loads(cleaned)
        except Exception:
            pass
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return value

    def _find_template_payload(obj: Any) -> Optional[Dict[str, Any]]:
        if isinstance(obj, dict):
            if "template" in obj and "data" in obj:
                return obj
            for val in obj.values():
                found = _find_template_payload(val)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for val in obj:
                found = _find_template_payload(val)
                if found is not None:
                    return found
        return None

    def _coerce_payload(raw: Any) -> Optional[Dict[str, Any]]:
        found = _find_template_payload(raw)
        if found is None:
            return None
        template = _parse_jsonish(found.get("template"))
        data = _parse_jsonish(found.get("data"))
        nested = _find_template_payload(template) if isinstance(template, (dict, list)) else None
        if nested is not None:
            return _coerce_payload(nested)
        nested = _find_template_payload(data) if isinstance(data, (dict, list)) else None
        if nested is not None:
            return _coerce_payload(nested)
        if not isinstance(template, dict) or not isinstance(data, dict):
            return None
        return {"template": template, "data": data}

    for json_path in dataset_dir.glob("*.json"):
        name = json_path.name
        if name.endswith(".ocr.json") or name.startswith("llm_response_raw_") or name.endswith("_failed.json"):
            continue
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        payload = _coerce_payload(raw)
        if payload is None:
            continue
        base = json_path.stem
        pdf_path = json_path.with_suffix(".pdf")
        ocr_path = json_path.with_name(f"{base}.ocr.json")
        if not pdf_path.exists() or not ocr_path.exists():
            continue
        template = payload.get("template", {}) if isinstance(payload.get("template", {}), dict) else {}
        visible_paths, items_visible = collect_visible_paths(template)
        samples.append(
            {
                "id": base,
                "data": payload.get("data", {}),
                "template": template,
                "visible_paths": visible_paths,
                "items_visible": items_visible,
                "pdf_path": pdf_path,
                "ocr_path": ocr_path,
            }
        )
    return sorted(samples, key=lambda s: s["id"])


def get_engine_availability() -> Dict[str, bool]:
    availability = {"tesseract": False, "easyocr": False}
    availability["tesseract"] = bool(shutil.which("tesseract"))
    try:
        import easyocr  # type: ignore  # noqa: F401

        availability["easyocr"] = True
    except Exception:
        availability["easyocr"] = False
    return availability


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _token_f1(gt: str, pred: str) -> float:
    gt_tokens = _tokenize(gt)
    pred_tokens = _tokenize(pred)
    if not gt_tokens and not pred_tokens:
        return 1.0
    if not gt_tokens or not pred_tokens:
        return 0.0
    gt_counts: Dict[str, int] = {}
    pred_counts: Dict[str, int] = {}
    for tok in gt_tokens:
        gt_counts[tok] = gt_counts.get(tok, 0) + 1
    for tok in pred_tokens:
        pred_counts[tok] = pred_counts.get(tok, 0) + 1
    overlap = 0
    for tok, cnt in gt_counts.items():
        overlap += min(cnt, pred_counts.get(tok, 0))
    precision = overlap / len(pred_tokens) if pred_tokens else 0.0
    recall = overlap / len(gt_tokens) if gt_tokens else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _jaccard(gt: str, pred: str) -> float:
    gt_set = set(_tokenize(gt))
    pred_set = set(_tokenize(pred))
    if not gt_set and not pred_set:
        return 1.0
    if not gt_set or not pred_set:
        return 0.0
    return len(gt_set & pred_set) / len(gt_set | pred_set)


def _char_similarity(gt: str, pred: str) -> float:
    if not gt and not pred:
        return 1.0
    if not gt or not pred:
        return 0.0
    try:
        from collections import Counter

        common = sum((Counter(gt) & Counter(pred)).values())
        if common:
            return common / max(len(gt), len(pred))
    except Exception:
        pass
    try:
        import difflib

        return difflib.SequenceMatcher(None, gt, pred).ratio()
    except Exception:
        return 0.0


def _parse_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    text = text.strip()
    if not text:
        return None
    text = re.sub(r"[^\d,.\-]", "", text)
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "")
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except Exception:
        return None


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            continue
    match = re.search(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", text)
    if match:
        part1 = int(match.group(1))
        part2 = int(match.group(2))
        year = int(match.group(3))
        if part1 > 12:
            day, month = part1, part2
        elif part2 > 12:
            month, day = part1, part2
        else:
            day, month = part1, part2
        try:
            return date(year, month, day)
        except Exception:
            return None
    return None


def _extract_lines(text: str) -> List[str]:
    lines = []
    for line in text.splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        if cleaned:
            lines.append(cleaned)
    return lines


def _normalize_label_line(line: str) -> str:
    cleaned = re.sub(r"\s+", " ", line).strip().lower()
    return cleaned


LABEL_NORMALIZED = {
    _normalize_label_line(label)
    for labels in LABEL_MAP.values()
    for label in labels
    if label and str(label).strip()
}


def _looks_like_label(line: str) -> bool:
    norm = _normalize_label_line(line)
    return norm in LABEL_NORMALIZED or norm in SUBLABEL_SKIP


def _token_jaccard(left: str, right: str) -> float:
    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    left_set = set(left_tokens)
    right_set = set(right_tokens)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


ITEM_DESC_HEADERS = [
    "description",
    "item",
    "items",
    "article",
    "beschreibung",
    "artikel",
    "popis",
    "polozka",
    "polo\u017eka",
    "\u5546\u54c1",
    "\u63cf\u8ff0",
    "\u54c1\u540d",
]
ITEM_QTY_HEADERS = ["qty", "quantity", "menge", "anzahl", "mnozstvi", "mno\u017estv\u00ed", "\u6570\u91cf"]
ITEM_UNIT_HEADERS = [
    "unit price",
    "unit",
    "einzelpreis",
    "preis",
    "jednotkova cena",
    "jednotkov\u00e1 cena",
    "\u5355\u4ef7",
]
ITEM_TOTAL_HEADERS = [
    "total",
    "amount",
    "betrag",
    "summe",
    "celkem",
    "\u91d1\u989d",
    "\u603b\u4ef7",
    "\u5408\u8ba1",
]
SECTION_STOP_HEADERS = [
    "invoice info",
    "invoice information",
    "payment information",
    "contact information",
    "seller",
    "client",
    "totals",
    "subtotal",
    "tax",
    "amount due",
    "\u53d1\u7968\u4fe1\u606f",
    "\u8054\u7cfb\u65b9\u5f0f",
    "\u4ed8\u6b3e\u4fe1\u606f",
    "\u5c0f\u8ba1",
    "\u7a0e",
    "\u5408\u8ba1",
    "\u603b\u8ba1",
    "rechnungsinformationen",
    "zahlungsinformationen",
    "kontaktdaten",
    "zwischensumme",
    "umsatzsteuer",
    "gesamt",
    "faktura",
    "soucet",
    "sou\u010det",
    "celkem",
]


def _find_item_table_start(lines: List[str]) -> Optional[int]:
    window = 6
    for idx in range(len(lines)):
        end = idx
        found_desc = found_qty = found_unit = found_total = False
        for offset, line in enumerate(lines[idx : idx + window]):
            norm = _normalize_label_line(line)
            if any(key in norm for key in ITEM_DESC_HEADERS):
                found_desc = True
                end = idx + offset
            if any(key in norm for key in ITEM_QTY_HEADERS):
                found_qty = True
                end = idx + offset
            if any(key in norm for key in ITEM_UNIT_HEADERS):
                found_unit = True
                end = idx + offset
            if any(key in norm for key in ITEM_TOTAL_HEADERS):
                found_total = True
                end = idx + offset
        if found_desc and found_qty and found_unit and found_total:
            return end + 1
    return None


def extract_items_from_lines(lines: List[str]) -> List[Dict[str, Any]]:
    if not lines:
        return []
    start = _find_item_table_start(lines)
    if start is None:
        return []
    items: List[Dict[str, Any]] = []
    idx = start
    while idx + 3 < len(lines):
        line = lines[idx].strip()
        norm = _normalize_label_line(line)
        if any(key in norm for key in SECTION_STOP_HEADERS):
            break
        if any(key in norm for key in ITEM_DESC_HEADERS):
            idx += 1
            continue
        if _parse_number(line) is not None:
            idx += 1
            continue
        qty = _parse_number(lines[idx + 1])
        unit = _parse_number(lines[idx + 2])
        total = _parse_number(lines[idx + 3])
        if qty is None or unit is None or total is None:
            idx += 1
            continue
        items.append(
            {
                "description": line,
                "qty": qty,
                "unit_price": unit,
                "line_total": total,
            }
        )
        idx += 4
    return items


def collect_visible_paths(template: Dict[str, Any]) -> Tuple[set[str], bool]:
    visible: set[str] = set()
    items_visible = False
    sections = template.get("sections", []) if isinstance(template, dict) else []
    for section in sections or []:
        if not isinstance(section, dict):
            continue
        stype = section.get("type", "grid")
        if stype == "grid":
            for field in section.get("fields", []) or []:
                if not isinstance(field, dict):
                    continue
                path = field.get("value_path")
                if path:
                    visible.add(str(path))
        elif stype == "panels":
            for panel in section.get("panels", []) or []:
                if not isinstance(panel, dict):
                    continue
                for field in panel.get("fields", []) or []:
                    if not isinstance(field, dict):
                        continue
                    path = field.get("value_path")
                    if path:
                        visible.add(str(path))
        elif stype == "table":
            data_path = section.get("data_path")
            if data_path:
                visible.add(str(data_path))
                if str(data_path) == "items":
                    items_visible = True
            for total in section.get("totals", []) or []:
                if not isinstance(total, dict):
                    continue
                path = total.get("value_path")
                if path:
                    visible.add(str(path))
        elif stype == "notes":
            path = section.get("value_path")
            if path:
                visible.add(str(path))
    return visible, items_visible


def _extract_label_value(lines: List[str], labels: Iterable[str]) -> str:
    if not lines or not labels:
        return ""
    label_list = sorted({label.strip() for label in labels if label and str(label).strip()}, key=len, reverse=True)
    if not label_list:
        return ""
    label_regex = re.compile("|".join(re.escape(label) for label in label_list), re.IGNORECASE)
    for idx, line in enumerate(lines):
        match = label_regex.search(line)
        if not match:
            continue
        matched = match.group(0)
        if ":" in line or "\uff1a" in line:
            parts = re.split(r"[:\uff1a]", line, maxsplit=1)
            after = parts[1].strip(" -#") if len(parts) > 1 else ""
            if after:
                return after
        line_norm = _normalize_label_line(line)
        matched_norm = _normalize_label_line(matched)
        if line_norm == matched_norm:
            if idx + 1 < len(lines):
                next_line = lines[idx + 1].strip()
                if next_line and not label_regex.search(next_line):
                    if _normalize_label_line(next_line) in SUBLABEL_SKIP and idx + 2 < len(lines):
                        return lines[idx + 2].strip()
                    return next_line
            continue
        start, end = match.span()
        before = line[start - 1] if start > 0 else ""
        after = line[end] if end < len(line) else ""
        if (before.isalnum() or after.isalnum()) and ":" not in line and "\uff1a" not in line:
            continue
        candidate = line[end:].strip(" -#")
        if candidate:
            return candidate
        if idx + 1 < len(lines):
            next_line = lines[idx + 1].strip()
            if next_line and not label_regex.search(next_line):
                if _normalize_label_line(next_line) in SUBLABEL_SKIP and idx + 2 < len(lines):
                    return lines[idx + 2].strip()
                return next_line
    return ""


def regex_extract(text: str) -> Dict[str, Any]:
    lines = _extract_lines(text or "")
    result: Dict[str, Any] = {
        "invoice": {},
        "seller": {},
        "client": {},
        "items": [],
        "totals": {},
        "payment": {},
        "notes": "",
    }
    for spec in FIELD_SPECS:
        labels = LABEL_MAP.get(spec.path, [])
        value = _extract_label_value(lines, labels)
        if spec.path == "notes" and not value:
            for line in lines:
                if "note" in line.lower():
                    value = line
                    break
        if value:
            set_dotted(result, spec.path, value)

    # Simple fallback for totals using amount regex
    amount_regex = re.compile(r"([0-9]+(?:[.,][0-9]{2})?)")
    for key in ("totals.subtotal", "totals.tax", "totals.due"):
        if dotted_get(result, key):
            continue
        labels = LABEL_MAP.get(key, [])
        value = _extract_label_value(lines, labels)
        if value:
            match = amount_regex.search(value)
            if match:
                set_dotted(result, key, match.group(1))
    if not result.get("items"):
        result["items"] = extract_items_from_lines(lines)
    return result


def kv_extract(text: str) -> Dict[str, Any]:
    lines = _extract_lines(text or "")
    result: Dict[str, Any] = {
        "invoice": {},
        "seller": {},
        "client": {},
        "items": [],
        "totals": {},
        "payment": {},
        "notes": "",
    }
    for idx, line in enumerate(lines):
        if ":" in line or "\uff1a" in line:
            left, right = re.split(r"[:\uff1a]", line, maxsplit=1)
        elif " - " in line or " \u2013 " in line or " \u2014 " in line:
            parts = re.split(r"\s[-\u2013\u2014]\s", line, maxsplit=1)
            if len(parts) != 2:
                continue
            left, right = parts
        else:
            left = line
            right = ""
        left_norm = _normalize_label_line(left)
        right = right.strip()
        best_path = None
        best_score = 0.0
        for path, labels in LABEL_MAP.items():
            for label in labels:
                label_norm = label.lower().strip()
                if label_norm and label_norm in left_norm:
                    score = 1.0
                else:
                    score = _token_jaccard(left_norm, label_norm)
                if score > best_score:
                    best_score = score
                    best_path = path
        if best_path and best_score >= 0.8 and not dotted_get(result, best_path):
            if right:
                set_dotted(result, best_path, right)
            elif idx + 1 < len(lines):
                next_line = lines[idx + 1].strip()
                if next_line and not _looks_like_label(next_line):
                    set_dotted(result, best_path, next_line)

    if not result.get("items"):
        result["items"] = extract_items_from_lines(lines)
    return result


def pattern_extract(text: str) -> Dict[str, Any]:
    result = regex_extract(text)
    lines = _extract_lines(text or "")
    text_blob = " ".join(lines)
    if not dotted_get(result, "payment.iban"):
        iban_match = re.search(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b", text_blob)
        if iban_match:
            set_dotted(result, "payment.iban", iban_match.group(0))
    emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text_blob, flags=re.IGNORECASE)
    if emails:
        if not dotted_get(result, "seller.email"):
            set_dotted(result, "seller.email", emails[0])
        if len(emails) > 1 and not dotted_get(result, "client.email"):
            set_dotted(result, "client.email", emails[1])
    phones = re.findall(r"\+?\d[\d\s().-]{6,}\d", text_blob)
    filtered_phones = []
    for phone in phones:
        digits = re.findall(r"\d", phone)
        if len(digits) < 7:
            continue
        if not re.search(r"[+\s().-]", phone):
            continue
        filtered_phones.append(phone)
    if filtered_phones:
        if not dotted_get(result, "seller.contact"):
            set_dotted(result, "seller.contact", filtered_phones[0].strip())
        if len(filtered_phones) > 1 and not dotted_get(result, "client.contact"):
            set_dotted(result, "client.contact", filtered_phones[1].strip())
    dates = re.findall(r"\d{4}[-/]\d{2}[-/]\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{4}", text_blob)
    if dates:
        parsed_dates = []
        for d in dates:
            parsed = _parse_date(d)
            if parsed:
                parsed_dates.append((parsed, d))
        parsed_dates.sort()
        if parsed_dates and not dotted_get(result, "invoice.date"):
            set_dotted(result, "invoice.date", parsed_dates[0][1])
        if len(parsed_dates) > 1 and not dotted_get(result, "invoice.due_date"):
            set_dotted(result, "invoice.due_date", parsed_dates[-1][1])
    if not dotted_get(result, "invoice.number"):
        inv_candidates = re.findall(r"\b[A-Z0-9][A-Z0-9-]{5,}\b", text_blob.upper())
        for token in inv_candidates:
            if token.startswith(("INV", "RE", "FAK", "DE-", "CZ-", "SK-")) or "INV" in token:
                set_dotted(result, "invoice.number", token)
                break
    if not result.get("items"):
        result["items"] = extract_items_from_lines(lines)
    return result


def merge_missing_fields(primary: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(primary, dict):
        primary = {}
    if not isinstance(fallback, dict):
        fallback = {}
    merged = json.loads(json.dumps(primary))
    for spec in FIELD_SPECS:
        if not dotted_get(merged, spec.path):
            value = dotted_get(fallback, spec.path)
            if value not in (None, "", []):
                set_dotted(merged, spec.path, value)
    if not merged.get("items"):
        items = fallback.get("items", [])
        if items:
            merged["items"] = items
    return merged


def ensemble_extract(text: str) -> Dict[str, Any]:
    regex = regex_extract(text)
    kv = kv_extract(text)
    pattern = pattern_extract(text)
    merged = merge_missing_fields(pattern, kv)
    merged = merge_missing_fields(merged, regex)
    candidates = [regex.get("items", []), kv.get("items", []), pattern.get("items", [])]
    best_items = max(candidates, key=lambda items: len(items) if isinstance(items, list) else 0)
    if best_items:
        merged["items"] = best_items
    return merged


def extract_text_pymupdf(pdf_path: Path) -> str:
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("PyMuPDF is required for PDF text extraction.") from exc
    if not pdf_path.exists():
        raise FileNotFoundError(str(pdf_path))
    doc = fitz.open(pdf_path)
    chunks: List[str] = []
    for page in doc:
        chunks.append(page.get_text("text"))
    doc.close()
    return "\n".join(chunks)


def extract_text_from_ocr_json(ocr_path: Path) -> str:
    if not ocr_path.exists():
        return ""
    try:
        data = json.loads(ocr_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return ""
    def _sort_key(item: Dict[str, Any]) -> Tuple[int, float, float]:
        return (int(item.get("page", 1)), float(item.get("y0", 0.0)), float(item.get("x0", 0.0)))
    sorted_items = sorted([i for i in items if isinstance(i, dict)], key=_sort_key)
    lines: List[str] = []
    current_line: List[str] = []
    last_y: Optional[float] = None
    for item in sorted_items:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        y0 = float(item.get("y0", 0.0))
        if last_y is None or abs(y0 - last_y) < 4.0:
            current_line.append(text)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [text]
        last_y = y0
    if current_line:
        lines.append(" ".join(current_line))
    return "\n".join(lines)


def _pdf_pages_to_images(pdf_path: Path, zoom: float = 1.7) -> List[bytes]:
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("PyMuPDF is required for PDF rendering.") from exc
    doc = fitz.open(pdf_path)
    images: List[bytes] = []
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        images.append(pix.tobytes("png"))
    doc.close()
    return images


def extract_text_tesseract(pdf_path: Path) -> str:
    tesseract_cmd = (
        os.environ.get("TESSERACT_CMD")
        or os.environ.get("TESSERACT_PATH")
        or shutil.which("tesseract")
    )
    if not tesseract_cmd:
        raise RuntimeError("tesseract binary not found in PATH.")
    tesseract_langs = os.environ.get("TESSERACT_LANGS", "").strip()
    pages = _pdf_pages_to_images(pdf_path)
    texts: List[str] = []
    for img_bytes in pages:
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "page.png"
            img_path.write_bytes(img_bytes)
            try:
                cmd = [tesseract_cmd, str(img_path), "stdout", "--oem", "1"]
                if tesseract_langs:
                    cmd.extend(["-l", tesseract_langs])
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(f"tesseract failed: {exc.stderr}") from exc
            texts.append(result.stdout or "")
    return "\n".join(texts)


def extract_text_easyocr(pdf_path: Path) -> str:
    try:
        import easyocr  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("easyocr is not installed.") from exc
    pages = _pdf_pages_to_images(pdf_path)
    reader = easyocr.Reader(["en"], gpu=False)
    chunks: List[str] = []
    for img_bytes in pages:
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "page.png"
            img_path.write_bytes(img_bytes)
            results = reader.readtext(str(img_path))
        page_text = " ".join([r[1] for r in results if len(r) > 1])
        chunks.append(page_text)
    return "\n".join(chunks)


def _build_llm_prompt() -> str:
    return (
        "Extract the invoice data into JSON using this schema:\n"
        f"{json.dumps(SCHEMA_HINT, separators=(',', ':'))}\n"
        "Return ONLY valid JSON with the same keys. Use empty strings when a field is missing. "
        "Keep numbers as numbers, not formatted strings. Minify the JSON (single line, no extra whitespace)."
    )


def is_gemini_model(model: str) -> bool:
    if not model:
        return False
    normalized = model.strip().lower()
    if "/" in normalized:
        return False
    return normalized.startswith("gemini")


def is_claude_model(model: str) -> bool:
    if not model:
        return False
    normalized = model.strip().lower()
    if "/" in normalized:
        return False
    return normalized.startswith("claude")


def _parse_llm_json(content: str) -> Any:
    def _strip_code_fence(txt: str) -> str:
        txt = txt.strip()
        if txt.startswith("```"):
            txt = re.sub(r"^```[a-zA-Z0-9]*", "", txt).strip()
            if txt.endswith("```"):
                txt = txt[:-3].strip()
        return txt

    def _snippet(text: str, limit: int = 400) -> str:
        clipped = text[:limit].replace("\n", " ").replace("\r", " ")
        try:
            return clipped.encode("unicode_escape").decode("ascii")
        except Exception:
            return clipped

    content = _strip_code_fence(content)
    try:
        return json.loads(content)
    except Exception:
        pass
    try:
        return json.JSONDecoder(strict=False).decode(content)
    except Exception:
        pass
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        snippet = _strip_code_fence(match.group(0))
        try:
            return json.loads(snippet)
        except Exception as exc:
            try:
                return json.JSONDecoder(strict=False).decode(snippet)
            except Exception:
                pass
            cleaned = re.sub(r",\s*([}\]])", r"\1", snippet)
            try:
                return json.loads(cleaned)
            except Exception:
                raise RuntimeError(f"LLM JSON could not be parsed. Snippet: {_snippet(snippet)}") from exc
    raise RuntimeError(f"LLM JSON could not be parsed. Snippet: {_snippet(content)}")


def _normalize_llm_output(parsed: Any) -> Dict[str, Any]:
    if isinstance(parsed, dict):
        if "data" in parsed and isinstance(parsed.get("data"), dict):
            return parsed["data"]
        return parsed
    raise RuntimeError("LLM output is not a JSON object.")


def _is_qwen_realtime_model(model: str) -> bool:
    return "qwen3-omni-flash-realtime" in (model or "").lower()


def _is_qwen_stream_model(model: str) -> bool:
    norm = (model or "").lower()
    return "qwen3-omni-flash" in norm and "realtime" not in norm


def _collect_streamed_text(stream) -> str:
    chunks: List[str] = []
    for event in stream:
        choice = event.choices[0] if event.choices else None
        if not choice:
            continue
        delta = getattr(choice, "delta", None)
        if delta and getattr(delta, "content", None):
            chunks.append(delta.content)
    return "".join(chunks)


def _gemini_generate_content(
    api_key: str,
    model: str,
    parts: List[Any],
    max_tokens: int,
) -> str:
    try:
        import google.generativeai as genai  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("google-generativeai package not installed.") from exc
    genai.configure(api_key=api_key)
    gemini = genai.GenerativeModel(model)
    generation_config = {
        "temperature": 0.0,
        "max_output_tokens": max_tokens,
        "response_mime_type": "application/json",
    }
    def _extract_text(resp: Any) -> str:
        try:
            text = getattr(resp, "text", None)
            if text:
                return text
        except Exception:
            pass
        candidates = getattr(resp, "candidates", None) or []
        texts: List[str] = []
        for cand in candidates:
            content = getattr(cand, "content", None) or (cand.get("content") if isinstance(cand, dict) else None)
            parts_list = getattr(content, "parts", None) if content is not None else None
            if parts_list is None and isinstance(content, dict):
                parts_list = content.get("parts")
            if not parts_list:
                continue
            for part in parts_list:
                text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
                if text:
                    texts.append(text)
        if texts:
            return "".join(texts)
        finish_reason = getattr(candidates[0], "finish_reason", None) if candidates else None
        safety = getattr(candidates[0], "safety_ratings", None) if candidates else None
        raise RuntimeError(f"Gemini returned no text parts (finish_reason={finish_reason}, safety={safety}).")
    try:
        resp = gemini.generate_content(parts, generation_config=generation_config)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "response_mime_type" in msg:
            resp = gemini.generate_content(parts, generation_config={"temperature": 0.0, "max_output_tokens": max_tokens})
        else:
            raise RuntimeError(f"Gemini request failed ({model}): {exc}") from exc
    return _extract_text(resp)


def _anthropic_generate_content(
    api_key: str,
    model: str,
    parts: List[Dict[str, Any]],
    max_tokens: int,
) -> str:
    try:
        from anthropic import Anthropic  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("anthropic package not installed.") from exc
    client = Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0.0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": parts}],
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Claude request failed ({model}): {exc}") from exc
    chunks: List[str] = []
    for block in getattr(resp, "content", []) or []:
        if isinstance(block, dict):
            text = block.get("text")
        else:
            text = getattr(block, "text", None)
        if text:
            chunks.append(text)
    content = "".join(chunks).strip()
    if not content:
        raise RuntimeError("Claude returned empty content.")
    return content


def llm_extract_text(
    api_key: str,
    model: str,
    text: str,
    max_tokens: int = 2000,
    api_base_url: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    if model and "qwen" in model.lower():
        max_tokens = max(max_tokens, 4096)
    if is_gemini_model(model):
        if not gemini_api_key:
            raise RuntimeError("Missing Gemini API key.")
        prompt = _build_llm_prompt()
        clipped = text if len(text) <= 12000 else text[:12000]
        gemini_max = max(max_tokens, 4096)
        def _call_gemini(text_payload: str, out_tokens: int) -> str:
            return _gemini_generate_content(
                gemini_api_key,
                model,
                [f"{prompt}\n\nTEXT:\n{text_payload}"],
                out_tokens,
            )

        try:
            content = _call_gemini(clipped, gemini_max)
            parsed = _parse_llm_json(content)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            retry_text = clipped
            retry_tokens = gemini_max
            if "no text parts" in msg and len(clipped) > 6000:
                retry_text = clipped[:6000]
                retry_tokens = max(retry_tokens, 8192)
            elif gemini_max < 8192:
                retry_tokens = 8192
            else:
                raise RuntimeError(f"Gemini response parse failed ({model}): {exc}") from exc
            try:
                content = _call_gemini(retry_text, retry_tokens)
                parsed = _parse_llm_json(content)
            except Exception as exc2:  # noqa: BLE001
                raise RuntimeError(f"Gemini response parse failed ({model}): {exc2}") from exc2
        return _normalize_llm_output(parsed)
    if is_claude_model(model):
        if not anthropic_api_key:
            raise RuntimeError("Missing Anthropic API key.")
        prompt = _build_llm_prompt()
        clipped = text if len(text) <= 12000 else text[:12000]
        parts = [{"type": "text", "text": f"{prompt}\n\nTEXT:\n{clipped}"}]
        content = _anthropic_generate_content(anthropic_api_key, model, parts, max_tokens)
        try:
            parsed = _parse_llm_json(content)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Claude response parse failed ({model}): {exc}") from exc
        return _normalize_llm_output(parsed)
    if not api_key:
        raise RuntimeError("Missing API key.")
    if _is_qwen_realtime_model(model):
        raise RuntimeError("Qwen realtime models are not supported via this endpoint. Use qwen3-omni-flash.")
    try:
        from openai import OpenAI  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("openai package not installed.") from exc
    client = OpenAI(api_key=api_key, base_url=api_base_url) if api_base_url else OpenAI(api_key=api_key)
    prompt = _build_llm_prompt()
    clipped = text if len(text) <= 12000 else text[:12000]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{prompt}\n\nTEXT:\n{clipped}"},
    ]
    try:
        if _is_qwen_stream_model(model):
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
                modalities=["text"],
            )
            content = _collect_streamed_text(stream)
        else:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content if resp and resp.choices else ""
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "response_format" in msg or "json_object" in msg:
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=max_tokens,
                )
                content = resp.choices[0].message.content if resp and resp.choices else ""
            except Exception as exc2:  # noqa: BLE001
                raise RuntimeError(f"LLM request failed ({model}): {exc2}") from exc2
        else:
            raise RuntimeError(f"LLM request failed ({model}): {exc}") from exc
    if not content:
        raise RuntimeError("LLM returned empty content.")
    try:
        parsed = _parse_llm_json(content)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"LLM response parse failed ({model}): {exc}") from exc
    return _normalize_llm_output(parsed)


def llm_extract_vision(
    api_key: str,
    model: str,
    images_b64: List[str],
    max_tokens: int = 2000,
    api_base_url: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    if is_gemini_model(model):
        if not gemini_api_key:
            raise RuntimeError("Missing Gemini API key.")
        prompt = _build_llm_prompt()
        parts: List[Any] = [prompt]
        for img in images_b64:
            try:
                img_bytes = base64.b64decode(img)
            except Exception:
                img_bytes = b""
            parts.append({"mime_type": "image/png", "data": img_bytes})
        gemini_max = max(max_tokens, 4096)
        content_str = _gemini_generate_content(gemini_api_key, model, parts, gemini_max)
        try:
            parsed = _parse_llm_json(content_str)
        except Exception as exc:  # noqa: BLE001
            if gemini_max < 8192:
                content_str = _gemini_generate_content(gemini_api_key, model, parts, 8192)
                try:
                    parsed = _parse_llm_json(content_str)
                except Exception as exc2:  # noqa: BLE001
                    raise RuntimeError(f"Gemini vision parse failed ({model}): {exc2}") from exc2
            else:
                raise RuntimeError(f"Gemini vision parse failed ({model}): {exc}") from exc
        return _normalize_llm_output(parsed)
    if is_claude_model(model):
        if not anthropic_api_key:
            raise RuntimeError("Missing Anthropic API key.")
        prompt = _build_llm_prompt()
        parts: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img in images_b64:
            parts.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": img},
                }
            )
        content_str = _anthropic_generate_content(anthropic_api_key, model, parts, max_tokens)
        try:
            parsed = _parse_llm_json(content_str)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Claude vision parse failed ({model}): {exc}") from exc
        return _normalize_llm_output(parsed)
    if not api_key:
        raise RuntimeError("Missing API key.")
    if _is_qwen_realtime_model(model):
        raise RuntimeError("Qwen realtime models are not supported for vision.")
    if _is_qwen_stream_model(model):
        raise RuntimeError("Qwen3 Omni Flash does not support vision via this endpoint. Use a vision model.")
    try:
        from openai import OpenAI  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("openai package not installed.") from exc
    client = OpenAI(api_key=api_key, base_url=api_base_url) if api_base_url else OpenAI(api_key=api_key)
    prompt = _build_llm_prompt()
    content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
    for img in images_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}})
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0,
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
                    temperature=0.0,
                    max_tokens=max_tokens,
                )
            except Exception as exc2:  # noqa: BLE001
                raise RuntimeError(f"LLM vision request failed ({model}): {exc2}") from exc2
        else:
            raise RuntimeError(f"LLM vision request failed ({model}): {exc}") from exc
    content_str = resp.choices[0].message.content if resp and resp.choices else ""
    if not content_str:
        raise RuntimeError("LLM returned empty content.")
    try:
        parsed = _parse_llm_json(content_str)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"LLM vision parse failed ({model}): {exc}") from exc
    return _normalize_llm_output(parsed)


def evaluate_prediction(
    gt_data: Dict[str, Any],
    pred_data: Dict[str, Any],
    sample_id: str,
    visible_paths: Optional[set[str]] = None,
    items_visible: Optional[bool] = None,
) -> Dict[str, Any]:
    field_metrics: Dict[str, Dict[str, Any]] = {}
    field_errors: Dict[str, List[Dict[str, Any]]] = {}
    for spec in FIELD_SPECS:
        if visible_paths is not None and spec.path not in visible_paths:
            continue
        gt_val = dotted_get(gt_data, spec.path, "")
        pred_val = dotted_get(pred_data, spec.path, "")
        gt_str = "" if gt_val is None else str(gt_val)
        pred_str = "" if pred_val is None else str(pred_val)
        exact = int(gt_str == pred_str)
        normalized = int(_normalize_text(gt_str) == _normalize_text(pred_str))
        token_f1 = _token_f1(gt_str, pred_str)
        jaccard = _jaccard(gt_str, pred_str)
        char_sim = _char_similarity(gt_str, pred_str)
        numeric = {}
        date_metric = {}
        if spec.ftype in ("amount", "number"):
            gt_num = _parse_number(gt_val)
            pred_num = _parse_number(pred_val)
            if gt_num is not None and pred_num is not None:
                abs_err = abs(gt_num - pred_num)
                rel_err = abs_err / max(abs(gt_num), 1e-6)
                tol = 0.01 if spec.ftype == "amount" else 0.5
                numeric_exact = abs_err <= tol
                exact = int(numeric_exact)
                normalized = int(numeric_exact)
                numeric = {
                    "abs_err": abs_err,
                    "rel_err": rel_err,
                    "within_tol": abs_err <= tol,
                }
        if spec.ftype == "date":
            gt_date = _parse_date(gt_val)
            pred_date = _parse_date(pred_val)
            if gt_date and pred_date:
                exact = int(gt_date == pred_date)
                normalized = int(gt_date == pred_date)
                date_metric = {"abs_days": abs((pred_date - gt_date).days)}
        field_metrics[spec.path] = {
            "label": spec.label,
            "type": spec.ftype,
            "exact": exact,
            "normalized": normalized,
            "token_f1": token_f1,
            "jaccard": jaccard,
            "char_sim": char_sim,
            "numeric": numeric,
            "date": date_metric,
            "present": bool(pred_str.strip()),
        }
        score = token_f1 if spec.ftype == "text" else (1.0 if exact else 0.0)
        if not pred_str.strip() or score < 0.5:
            field_errors.setdefault(spec.path, []).append(
                {"sample": sample_id, "gt": gt_str, "pred": pred_str, "score": score}
            )

    if items_visible is None:
        items_visible = True
    item_metrics = evaluate_items(gt_data.get("items", []), pred_data.get("items", []), sample_id, items_visible)
    return {"fields": field_metrics, "field_errors": field_errors, "items": item_metrics}


def _item_similarity(gt: Dict[str, Any], pred: Dict[str, Any]) -> float:
    desc_score = _token_f1(str(gt.get("description", "")), str(pred.get("description", "")))
    qty_score = 0.0
    unit_score = 0.0
    total_score = 0.0
    gt_qty = _parse_number(gt.get("qty"))
    pred_qty = _parse_number(pred.get("qty"))
    if gt_qty is not None and pred_qty is not None:
        qty_score = 1.0 - min(abs(gt_qty - pred_qty) / max(abs(gt_qty), 1.0), 1.0)
    gt_unit = _parse_number(gt.get("unit_price"))
    pred_unit = _parse_number(pred.get("unit_price"))
    if gt_unit is not None and pred_unit is not None:
        unit_score = 1.0 - min(abs(gt_unit - pred_unit) / max(abs(gt_unit), 1.0), 1.0)
    gt_total = _parse_number(gt.get("line_total"))
    pred_total = _parse_number(pred.get("line_total"))
    if gt_total is not None and pred_total is not None:
        total_score = 1.0 - min(abs(gt_total - pred_total) / max(abs(gt_total), 1.0), 1.0)
    return 0.4 * desc_score + 0.2 * qty_score + 0.2 * unit_score + 0.2 * total_score


def evaluate_items(gt_items: Any, pred_items: Any, sample_id: str, enabled: bool = True) -> Dict[str, Any]:
    if not enabled:
        return {"sample": sample_id, "skip": True}
    gt_list = gt_items if isinstance(gt_items, list) else []
    pred_list = pred_items if isinstance(pred_items, list) else []
    matches: List[Tuple[int, int, float]] = []
    used_pred = set()
    for gi, gt in enumerate(gt_list):
        best = (-1, 0.0)
        for pi, pred in enumerate(pred_list):
            if pi in used_pred:
                continue
            score = _item_similarity(gt, pred)
            if score > best[1]:
                best = (pi, score)
        if best[0] >= 0 and best[1] >= 0.5:
            used_pred.add(best[0])
            matches.append((gi, best[0], best[1]))
    matched_count = len(matches)
    gt_count = len(gt_list)
    pred_count = len(pred_list)
    precision = matched_count / pred_count if pred_count else 0.0
    recall = matched_count / gt_count if gt_count else 0.0
    f1 = 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)

    field_scores: Dict[str, Dict[str, int]] = {spec.path: {"correct": 0, "total": 0} for spec in ITEM_FIELD_SPECS}
    for gi, pi, _score in matches:
        gt = gt_list[gi]
        pred = pred_list[pi]
        for spec in ITEM_FIELD_SPECS:
            gt_val = gt.get(spec.path, "")
            pred_val = pred.get(spec.path, "")
            ok = False
            if spec.ftype == "text":
                ok = _normalize_text(gt_val) == _normalize_text(pred_val)
            else:
                gt_num = _parse_number(gt_val)
                pred_num = _parse_number(pred_val)
                if gt_num is not None and pred_num is not None:
                    tol = 0.01 if spec.ftype == "amount" else 0.5
                    ok = abs(gt_num - pred_num) <= tol
            field_scores[spec.path]["total"] += 1
            if ok:
                field_scores[spec.path]["correct"] += 1
    field_accuracy = {
        spec.path: (field_scores[spec.path]["correct"] / field_scores[spec.path]["total"] if field_scores[spec.path]["total"] else 0.0)
        for spec in ITEM_FIELD_SPECS
    }
    return {
        "sample": sample_id,
        "matched": matched_count,
        "gt_count": gt_count,
        "pred_count": pred_count,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "field_scores": field_scores,
        "field_accuracy": field_accuracy,
    }


def init_aggregate() -> Dict[str, Any]:
    return {
        "fields": {
            spec.path: {
                "label": spec.label,
                "type": spec.ftype,
                "count": 0,
                "present": 0,
                "exact": 0,
                "normalized": 0,
                "token_f1_sum": 0.0,
                "jaccard_sum": 0.0,
                "char_sim_sum": 0.0,
                "abs_err_sum": 0.0,
                "rel_err_sum": 0.0,
                "within_tol": 0,
                "date_err_sum": 0.0,
                "date_count": 0,
                "numeric_count": 0,
                "examples": [],
            }
            for spec in FIELD_SPECS
        },
        "item": {
            "gt_count": 0,
            "pred_count": 0,
            "matched": 0,
            "samples": 0,
            "field_scores": {spec.path: {"correct": 0, "total": 0} for spec in ITEM_FIELD_SPECS},
        },
        "field_errors": {spec.path: [] for spec in FIELD_SPECS},
        "sample_count": 0,
    }


def update_aggregate(agg: Dict[str, Any], sample_result: Dict[str, Any]) -> None:
    agg["sample_count"] += 1
    for path, metrics in sample_result["fields"].items():
        stats = agg["fields"][path]
        stats["count"] += 1
        if metrics.get("present"):
            stats["present"] += 1
        stats["exact"] += metrics.get("exact", 0)
        stats["normalized"] += metrics.get("normalized", 0)
        stats["token_f1_sum"] += metrics.get("token_f1", 0.0)
        stats["jaccard_sum"] += metrics.get("jaccard", 0.0)
        stats["char_sim_sum"] += metrics.get("char_sim", 0.0)
        numeric = metrics.get("numeric", {})
        if numeric:
            stats["numeric_count"] += 1
            stats["abs_err_sum"] += numeric.get("abs_err", 0.0)
            stats["rel_err_sum"] += numeric.get("rel_err", 0.0)
            if numeric.get("within_tol"):
                stats["within_tol"] += 1
        date_metric = metrics.get("date", {})
        if date_metric:
            stats["date_count"] += 1
            stats["date_err_sum"] += date_metric.get("abs_days", 0.0)
        # Track worst examples per field
        errors = sample_result["field_errors"].get(path, [])
        if errors:
            agg["field_errors"][path].extend(errors)

    item = sample_result["items"]
    if item.get("skip"):
        return
    agg["item"]["samples"] += 1
    agg["item"]["gt_count"] += item.get("gt_count", 0)
    agg["item"]["pred_count"] += item.get("pred_count", 0)
    agg["item"]["matched"] += item.get("matched", 0)
    field_scores = item.get("field_scores", {})
    for spec in ITEM_FIELD_SPECS:
        scores = field_scores.get(spec.path, {})
        agg["item"]["field_scores"][spec.path]["total"] += scores.get("total", 0)
        agg["item"]["field_scores"][spec.path]["correct"] += scores.get("correct", 0)


def finalize_aggregate(agg: Dict[str, Any]) -> Dict[str, Any]:
    field_metrics: Dict[str, Any] = {}
    exact_rates = []
    norm_rates = []
    token_f1s = []
    char_sims = []
    for path, stats in agg["fields"].items():
        if stats["count"] == 0:
            field_metrics[path] = {
                "label": stats["label"],
                "type": stats["type"],
                "count": 0,
                "present_rate": None,
                "exact_rate": None,
                "normalized_rate": None,
                "token_f1": None,
                "char_similarity": None,
                "jaccard": None,
                "numeric_mae": None,
                "numeric_mape": None,
                "numeric_within_tol": None,
                "date_mae_days": None,
            }
            continue
        count = stats["count"]
        exact_rate = stats["exact"] / count
        norm_rate = stats["normalized"] / count
        token_f1_avg = stats["token_f1_sum"] / count
        char_sim_avg = stats["char_sim_sum"] / count
        jaccard_avg = stats["jaccard_sum"] / count
        present_rate = stats["present"] / count
        numeric_mae = stats["abs_err_sum"] / stats["numeric_count"] if stats["numeric_count"] else None
        numeric_mape = stats["rel_err_sum"] / stats["numeric_count"] if stats["numeric_count"] else None
        numeric_within = stats["within_tol"] / stats["numeric_count"] if stats["numeric_count"] else None
        date_mae = stats["date_err_sum"] / stats["date_count"] if stats["date_count"] else None
        field_metrics[path] = {
            "label": stats["label"],
            "type": stats["type"],
            "count": stats["count"],
            "present_rate": present_rate,
            "exact_rate": exact_rate,
            "normalized_rate": norm_rate,
            "token_f1": token_f1_avg,
            "char_similarity": char_sim_avg,
            "jaccard": jaccard_avg,
            "numeric_mae": numeric_mae,
            "numeric_mape": numeric_mape,
            "numeric_within_tol": numeric_within,
            "date_mae_days": date_mae,
        }
        exact_rates.append(exact_rate)
        norm_rates.append(norm_rate)
        token_f1s.append(token_f1_avg)
        char_sims.append(char_sim_avg)

    item = agg["item"]
    if item.get("samples", 0) == 0:
        item_precision = None
        item_recall = None
        item_f1 = None
        item_field_acc = {spec.path: None for spec in ITEM_FIELD_SPECS}
    else:
        item_precision = item["matched"] / item["pred_count"] if item["pred_count"] else 0.0
        item_recall = item["matched"] / item["gt_count"] if item["gt_count"] else 0.0
        item_f1 = (
            0.0
            if (item_precision + item_recall) == 0
            else 2 * item_precision * item_recall / (item_precision + item_recall)
        )
        item_field_acc = {
            spec.path: (
                item["field_scores"][spec.path]["correct"] / item["field_scores"][spec.path]["total"]
                if item["field_scores"][spec.path]["total"]
                else 0.0
            )
            for spec in ITEM_FIELD_SPECS
        }

    error_examples: Dict[str, List[Dict[str, Any]]] = {}
    for spec in FIELD_SPECS:
        examples = agg["field_errors"].get(spec.path, [])
        sorted_examples = sorted(examples, key=lambda e: e.get("score", 0.0))[:5]
        error_examples[spec.path] = sorted_examples

    overall = {
        "sample_count": agg["sample_count"],
        "exact_macro": statistics.mean(exact_rates) if exact_rates else None,
        "normalized_macro": statistics.mean(norm_rates) if norm_rates else None,
        "token_f1_macro": statistics.mean(token_f1s) if token_f1s else None,
        "char_similarity_macro": statistics.mean(char_sims) if char_sims else None,
        "item_precision": item_precision,
        "item_recall": item_recall,
        "item_f1": item_f1,
        "item_field_accuracy": item_field_acc,
    }
    return {"overall": overall, "fields": field_metrics, "errors": error_examples}


def images_for_llm(pdf_path: Path, max_pages: int = 3) -> List[str]:
    images = _pdf_pages_to_images(pdf_path)
    b64_images = [base64.b64encode(img).decode("ascii") for img in images[:max_pages]]
    return b64_images
