import argparse
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

try:
    import fitz  # PyMuPDF
except Exception:  # noqa: BLE001
    fitz = None


EXCLUDE_SUFFIXES = (".ocr.json", "_failed.json")
EXCLUDE_PREFIXES = ("llm_response_raw_",)


FIELD_PATHS = [
    "invoice.number",
    "invoice.date",
    "invoice.due_date",
    "invoice.reference",
    "seller.name",
    "seller.contact",
    "seller.email",
    "seller.address",
    "client.name",
    "client.contact",
    "client.email",
    "client.address",
    "totals.subtotal",
    "totals.tax",
    "totals.due",
    "payment.bank",
    "payment.iban",
    "payment.reference",
    "notes",
]


LANG_PATTERNS = {
    "Czech": re.compile(r"[\u010D\u010F\u011B\u0148\u0159\u0161\u0165\u017E\u016F\u00FD\u00E1\u00ED\u00E9\u00FA]"),
    "German": re.compile(r"[\u00E4\u00F6\u00FC\u00DF\u00C4\u00D6\u00DC]"),
    "French": re.compile(r"[\u00E9\u00E8\u00EA\u00EB\u00E0\u00E2\u00EE\u00EF\u00F4\u00F9\u00FB\u00FC\u00E7]"),
    "Spanish": re.compile(r"[\u00F1\u00E1\u00E9\u00ED\u00F3\u00FA\u00FC\u00A1\u00BF]"),
    "Polish": re.compile(r"[\u0105\u0107\u0119\u0142\u0144\u00F3\u015B\u017A\u017C]"),
    "Portuguese": re.compile(r"[\u00E3\u00F5\u00E7\u00E1\u00E9\u00ED\u00F3\u00FA]"),
    "Italian": re.compile(r"[\u00E0\u00E8\u00EC\u00F2\u00F9]"),
    "Dutch": re.compile(r"[\u00EF\u00EB]"),
    "Slovak": re.compile(r"[\u00E1\u00E4\u010D\u010F\u00E9\u00ED\u013A\u013E\u0148\u00F3\u00F4\u0155\u0161\u0165\u00FA\u00FD\u017E]"),
}


def dotted_get(data: Dict[str, Any], path: str) -> Any:
    if not isinstance(data, dict):
        return None
    cur: Any = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def iter_strings(obj: Any) -> Iterable[str]:
    if isinstance(obj, dict):
        for val in obj.values():
            yield from iter_strings(val)
    elif isinstance(obj, list):
        for val in obj:
            yield from iter_strings(val)
    elif isinstance(obj, str):
        if obj.strip():
            yield obj


def guess_language(text: str) -> str:
    if not text:
        return "Unknown"
    counts = {
        "arabic": 0,
        "cjk": 0,
        "hiragana": 0,
        "katakana": 0,
        "cyrillic": 0,
        "latin": 0,
    }
    for ch in text:
        code = ord(ch)
        if 0x0600 <= code <= 0x06FF or 0x0750 <= code <= 0x077F:
            counts["arabic"] += 1
        elif 0x3040 <= code <= 0x309F:
            counts["hiragana"] += 1
            counts["cjk"] += 1
        elif 0x30A0 <= code <= 0x30FF:
            counts["katakana"] += 1
            counts["cjk"] += 1
        elif 0x4E00 <= code <= 0x9FFF:
            counts["cjk"] += 1
        elif 0x0400 <= code <= 0x04FF:
            counts["cyrillic"] += 1
        elif (0x0041 <= code <= 0x007A) or (0x00C0 <= code <= 0x024F):
            counts["latin"] += 1

    if counts["arabic"] > 0:
        return "Arabic"
    if counts["hiragana"] > 0 or counts["katakana"] > 0:
        return "Japanese"
    if counts["cjk"] > 0:
        return "Chinese"
    if counts["cyrillic"] > 0:
        return "Cyrillic"

    if counts["latin"] > 0:
        scores = {name: len(pattern.findall(text)) for name, pattern in LANG_PATTERNS.items()}
        best = max(scores.items(), key=lambda kv: kv[1])
        if best[1] > 0:
            return best[0]
        return "English/Other Latin"
    return "Unknown"


def entropy(counter: Counter) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    probs = [count / total for count in counter.values() if count > 0]
    ent = -sum(p * math.log2(p) for p in probs)
    return ent / math.log2(len(probs)) if len(probs) > 1 else 0.0


def load_payload(json_path: Path) -> Optional[Dict[str, Any]]:
    try:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(raw, dict) and "template" in raw and "data" in raw:
        return raw
    return None


def list_samples(dataset_dir: Path) -> List[Dict[str, Any]]:
    samples = []
    for json_path in dataset_dir.glob("*.json"):
        name = json_path.name
        if name.endswith(EXCLUDE_SUFFIXES) or name.startswith(EXCLUDE_PREFIXES):
            continue
        payload = load_payload(json_path)
        if not payload:
            continue
        base = json_path.stem
        pdf_path = json_path.with_suffix(".pdf")
        ocr_path = json_path.with_name(f"{base}.ocr.json")
        samples.append(
            {
                "id": base,
                "json_path": json_path,
                "pdf_path": pdf_path if pdf_path.exists() else None,
                "ocr_path": ocr_path if ocr_path.exists() else None,
                "payload": payload,
            }
        )
    return samples


def pdf_pages(pdf_path: Optional[Path]) -> Optional[int]:
    if not pdf_path or not pdf_path.exists() or fitz is None:
        return None
    try:
        doc = fitz.open(pdf_path)
        count = doc.page_count
        doc.close()
        return int(count)
    except Exception:
        return None


def pdf_word_count(pdf_path: Optional[Path]) -> Optional[int]:
    if not pdf_path or not pdf_path.exists() or fitz is None:
        return None
    try:
        doc = fitz.open(pdf_path)
        total = 0
        for page in doc:
            total += len(page.get_text("words"))
        doc.close()
        return int(total)
    except Exception:
        return None


def ocr_box_count(ocr_path: Optional[Path]) -> Optional[int]:
    if not ocr_path or not ocr_path.exists():
        return None
    try:
        data = json.loads(ocr_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return None
    return len(items)


def collect_stats(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    missing_counts = Counter()
    lengths_by_field: Dict[str, List[int]] = defaultdict(list)
    lang_counts = Counter()
    page_counts = []
    item_counts = []
    ocr_counts = []
    word_counts = []

    for sample in samples:
        payload = sample["payload"]
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        all_text = " ".join(iter_strings(data))
        lang = guess_language(all_text)
        lang_counts[lang] += 1
        pages = pdf_pages(sample["pdf_path"])
        words = pdf_word_count(sample["pdf_path"])
        ocr_count = ocr_box_count(sample["ocr_path"])
        if pages is not None:
            page_counts.append(pages)
        if words is not None:
            word_counts.append(words)
        if ocr_count is not None:
            ocr_counts.append(ocr_count)

        items = data.get("items", [])
        item_counts.append(len(items) if isinstance(items, list) else 0)

        for path in FIELD_PATHS:
            value = dotted_get(data, path)
            if value in (None, "", [], {}):
                missing_counts[path] += 1
            if isinstance(value, str):
                lengths_by_field[path].append(len(value))

        rows.append(
            {
                "id": sample["id"],
                "language": lang,
                "pages": pages or 0,
                "items": item_counts[-1],
                "ocr_boxes": ocr_count or 0,
                "pdf_words": words or 0,
            }
        )

    return {
        "rows": rows,
        "missing_counts": missing_counts,
        "lengths_by_field": lengths_by_field,
        "lang_counts": lang_counts,
        "page_counts": page_counts,
        "item_counts": item_counts,
        "ocr_counts": ocr_counts,
        "word_counts": word_counts,
    }


def build_figures(stats: Dict[str, Any]) -> List[Tuple[str, go.Figure]]:
    rows = stats["rows"]
    lang_counts = stats["lang_counts"]

    fig_lang = go.Figure(
        data=[go.Bar(x=list(lang_counts.keys()), y=list(lang_counts.values()))],
        layout=go.Layout(title="Samples per language (heuristic)", xaxis_title="Language", yaxis_title="Samples"),
    )

    fig_pages = go.Figure(
        data=[go.Histogram(x=stats["page_counts"])],
        layout=go.Layout(title="Pages per sample", xaxis_title="Pages", yaxis_title="Count"),
    )

    fig_items = go.Figure(
        data=[go.Histogram(x=stats["item_counts"])],
        layout=go.Layout(title="Line items per sample", xaxis_title="Items", yaxis_title="Count"),
    )

    fig_ocr = go.Figure(
        data=[go.Histogram(x=stats["ocr_counts"])],
        layout=go.Layout(title="OCR boxes per sample", xaxis_title="OCR boxes", yaxis_title="Count"),
    )

    fig_words = go.Figure(
        data=[go.Histogram(x=stats["word_counts"])],
        layout=go.Layout(title="Selectable PDF words per sample", xaxis_title="Word count", yaxis_title="Count"),
    )

    fig_scatter = go.Figure(
        data=[
            go.Scatter(
                x=[r["pages"] for r in rows],
                y=[r["items"] for r in rows],
                mode="markers",
                marker={"size": 6, "opacity": 0.7},
            )
        ],
        layout=go.Layout(title="Pages vs items", xaxis_title="Pages", yaxis_title="Items"),
    )

    missing_counts = stats["missing_counts"]
    total = len(rows) or 1
    fields = list(missing_counts.keys()) if missing_counts else FIELD_PATHS
    miss_rates = [(missing_counts.get(f, 0) / total) * 100 for f in fields]
    fig_missing = go.Figure(
        data=[go.Bar(x=fields, y=miss_rates)],
        layout=go.Layout(title="Missing field rate (%)", xaxis_title="Field", yaxis_title="Missing %"),
    )

    lengths_by_field = stats["lengths_by_field"]
    fig_lengths = go.Figure()
    for field, lengths in lengths_by_field.items():
        if lengths:
            fig_lengths.add_trace(go.Box(y=lengths, name=field))
    fig_lengths.update_layout(title="Text length by field (chars)", yaxis_title="Characters")

    return [
        ("language_counts", fig_lang),
        ("pages_hist", fig_pages),
        ("items_hist", fig_items),
        ("ocr_boxes_hist", fig_ocr),
        ("pdf_words_hist", fig_words),
        ("pages_vs_items", fig_scatter),
        ("missing_fields", fig_missing),
        ("field_lengths", fig_lengths),
    ]


def build_summary(stats: Dict[str, Any]) -> Dict[str, Any]:
    lang_counts = stats["lang_counts"]
    rows = stats["rows"]
    page_counts = stats["page_counts"]
    item_counts = stats["item_counts"]
    ocr_counts = stats["ocr_counts"]
    word_counts = stats["word_counts"]

    def _basic(values: List[int]) -> Dict[str, float]:
        if not values:
            return {"mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0}
        return {
            "mean": float(statistics.mean(values)),
            "median": float(statistics.median(values)),
            "min": float(min(values)),
            "max": float(max(values)),
        }

    return {
        "samples": len(rows),
        "language_counts": dict(lang_counts),
        "language_balance_entropy": entropy(lang_counts),
        "pages": _basic(page_counts),
        "items": _basic(item_counts),
        "ocr_boxes": _basic(ocr_counts),
        "pdf_words": _basic(word_counts),
    }


def write_html(figures: List[Tuple[str, go.Figure]], out_path: Path) -> None:
    parts = []
    for idx, (name, fig) in enumerate(figures):
        parts.append(f"<h2>{name.replace('_', ' ').title()}</h2>")
        parts.append(pio.to_html(fig, full_html=False, include_plotlyjs="cdn" if idx == 0 else False))
    html = "<html><head><meta charset='utf-8'></head><body>" + "\n".join(parts) + "</body></html>"
    out_path.write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dataset analysis and Plotly report.")
    parser.add_argument("--dataset", required=True, help="Path to dataset folder")
    parser.add_argument("--out", default="dataset_report.html", help="Output HTML report path")
    parser.add_argument("--summary", default="dataset_summary.json", help="Output JSON summary path")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset)
    if not dataset_dir.exists():
        print(f"Dataset not found: {dataset_dir}")
        return 1

    samples = list_samples(dataset_dir)
    if not samples:
        print("No samples found.")
        return 1

    stats = collect_stats(samples)
    figures = build_figures(stats)
    write_html(figures, Path(args.out))

    summary = build_summary(stats)
    Path(args.summary).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {args.out} and {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
