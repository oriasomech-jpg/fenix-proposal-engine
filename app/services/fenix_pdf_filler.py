
from __future__ import annotations

import io
import os
import re
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.services.operational_report_parser import ParsedReport

try:
    from bidi.algorithm import get_display as bidi_get_display
except Exception:  # pragma: no cover
    bidi_get_display = None


FONT_REGULAR = "DejaVuSans"
FONT_BOLD = "DejaVuSansBold"
FONT_PATHS = {
    FONT_REGULAR: [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        str(Path(__file__).resolve().parent.parent / "static" / "DejaVuSans.ttf"),
    ],
    FONT_BOLD: [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        str(Path(__file__).resolve().parent.parent / "static" / "DejaVuSans-Bold.ttf"),
    ],
}

PAGE_HEIGHT = A4[1]

# ---- page 1 precise option-1 mapping (candidate 1 + 2 only) ----
# Coordinates are in PDF points, measured against the original Fenix PDF page 1.
PAGE1 = {
    "candidate1": {
        "left": 351,
        "right": 401,
        "surname_y": 583,
        "name_y": 562,
        "id_y": 542,
        "birth_y": 479,
        "mobile_y": 396,
        "gender": {"male_x": 385, "female_x": 365, "y": 520},
    },
    "candidate2": {
        "left": 301,
        "right": 351,
        "surname_y": 583,
        "name_y": 562,
        "id_y": 542,
        "birth_y": 479,
        "mobile_y": 396,
        "gender": {"male_x": 335, "female_x": 315, "y": 520},
    },
}


def _register_font(font_name: str) -> str:
    try:
        pdfmetrics.getFont(font_name)
        return font_name
    except Exception:
        pass
    for path in FONT_PATHS.get(font_name, []):
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(font_name, path))
            return font_name
    return "Helvetica-Bold" if "Bold" in font_name else "Helvetica"


def _rtl_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if bidi_get_display is not None:
        return bidi_get_display(text)
    return text[::-1] if re.search(r"[א-ת]", text) else text


def _split_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in (full_name or "").split() if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _register_default_fonts() -> tuple[str, str]:
    return _register_font(FONT_REGULAR), _register_font(FONT_BOLD)


def _draw_text_right(
    c: canvas.Canvas,
    text: str,
    right_x: float,
    y: float,
    *,
    size: float = 10.8,
    bold: bool = True,
    max_width: float | None = None,
):
    text = (text or "").strip()
    if not text:
        return
    regular, boldf = _register_default_fonts()
    font_name = boldf if bold else regular
    rendered = _rtl_text(text)
    chosen = size
    if max_width:
        while chosen > 7 and pdfmetrics.stringWidth(rendered, font_name, chosen) > max_width:
            chosen -= 0.2
    c.setFont(font_name, chosen)
    c.drawRightString(right_x, y, rendered)


def _draw_ltr_spaced(
    c: canvas.Canvas,
    value: str,
    *,
    left_x: float,
    right_x: float,
    y: float,
    size: float = 10.6,
    bold: bool = True,
):
    chars = list(value or "")
    if not chars:
        return
    regular, boldf = _register_default_fonts()
    c.setFont(boldf if bold else regular, size)
    width = right_x - left_x
    step = width / max(len(chars), 1)
    for i, ch in enumerate(chars):
        cx = left_x + (i + 0.5) * step
        c.drawCentredString(cx, y, ch)


def _draw_x(c: canvas.Canvas, x: float, y: float, size: int = 11):
    _, boldf = _register_default_fonts()
    c.setFont(boldf, size)
    c.drawCentredString(x, y, "X")


def _mark_gender(c: canvas.Canvas, value: str, male_x: float, female_x: float, y: float):
    value = (value or "").strip()
    if value == "זכר":
        _draw_x(c, male_x, y)
    elif value == "נקבה":
        _draw_x(c, female_x, y)


def _draw_candidate_option1(c: canvas.Canvas, insured, cfg: dict):
    first_name, last_name = _split_name(insured.full_name)
    width = cfg["right"] - cfg["left"] - 4

    _draw_text_right(c, last_name, cfg["right"] - 2, cfg["surname_y"], size=10.9, max_width=width)
    _draw_text_right(c, first_name, cfg["right"] - 2, cfg["name_y"], size=10.9, max_width=width)

    digits_id = _only_digits(getattr(insured, "id_number", ""))[:9]
    _draw_ltr_spaced(c, digits_id, left_x=cfg["left"] + 2, right_x=cfg["right"] - 2, y=cfg["id_y"], size=10.2)

    _mark_gender(c, getattr(insured, "gender", ""), **cfg["gender"])

    birth_digits = _only_digits(getattr(insured, "birth_date", ""))[:8]
    _draw_ltr_spaced(c, birth_digits, left_x=cfg["left"] + 2, right_x=cfg["right"] - 2, y=cfg["birth_y"], size=9.7)

    mobile_digits = _only_digits(getattr(insured, "mobile", ""))[:10]
    _draw_ltr_spaced(c, mobile_digits, left_x=cfg["left"] + 1, right_x=cfg["right"] - 1, y=cfg["mobile_y"], size=9.3)


def _overlay_page_1(c: canvas.Canvas, parsed: ParsedReport):
    _draw_candidate_option1(c, parsed.primary_insured, PAGE1["candidate1"])
    _draw_candidate_option1(c, parsed.secondary_insured, PAGE1["candidate2"])


def fill_fenix_pdf(parsed: ParsedReport, template_pdf_path: str, output_pdf_path: str):
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)

    _overlay_page_1(c, parsed)
    # Keep remaining pages blank in overlay for now.
    template_pages = len(PdfReader(template_pdf_path).pages)
    for _ in range(1, template_pages):
        c.showPage()
    c.save()

    packet.seek(0)
    overlay_pdf = PdfReader(packet)
    template_pdf = PdfReader(template_pdf_path)
    writer = PdfWriter()

    for page_num, page in enumerate(template_pdf.pages):
        if page_num < len(overlay_pdf.pages):
            page.merge_page(overlay_pdf.pages[page_num])
        writer.add_page(page)

    with open(output_pdf_path, "wb") as f:
        writer.write(f)
