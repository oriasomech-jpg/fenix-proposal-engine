
from __future__ import annotations

import io
import os
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.services.operational_report_parser import ParsedReport


FONT_NAME = "DejaVuSans"
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    str(Path(__file__).resolve().parent.parent.parent / "app" / "static" / "DejaVuSans.ttf"),
]


def _register_font() -> str:
    try:
        pdfmetrics.getFont(FONT_NAME)
        return FONT_NAME
    except Exception:
        pass
    for path in FONT_PATHS:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(FONT_NAME, path))
            return FONT_NAME
    return "Helvetica"


def _draw_text(c, text: str, x: float, y: float, size: int = 10):
    if not text:
        return
    font_name = _register_font()
    c.setFont(font_name, size)
    c.drawRightString(x, y, text)


def _draw_x(c, x: float, y: float, size: int = 11):
    font_name = _register_font()
    c.setFont(font_name, size)
    c.drawCentredString(x, y, "X")


def _overlay_page_1(c, parsed: ParsedReport):
    # rough initial mapping for page 1 of the Fenix proposal form
    # coordinates in reportlab points from bottom-left, A4 portrait
    p = parsed.primary_insured
    s = parsed.secondary_insured

    # primary candidate row
    _draw_text(c, p.full_name, 470, 676, 9)
    _draw_text(c, p.id_number, 470, 659, 9)
    _draw_text(c, p.birth_date, 470, 642, 9)
    _draw_text(c, p.health_fund, 470, 625, 9)
    _draw_text(c, p.supplementary_insurance, 470, 608, 9)
    _draw_text(c, p.occupation, 470, 591, 9)
    _draw_text(c, p.mobile, 470, 574, 9)
    _draw_text(c, p.email, 470, 557, 8)
    _draw_text(c, p.address.street, 470, 540, 8)
    _draw_text(c, p.address.house_number, 470, 523, 8)
    _draw_text(c, p.address.city, 470, 506, 9)
    _draw_text(c, p.address.zip_code, 470, 489, 9)

    # secondary candidate row
    _draw_text(c, s.full_name, 470, 457, 9)
    _draw_text(c, s.id_number, 470, 440, 9)
    _draw_text(c, s.birth_date, 470, 423, 9)
    _draw_text(c, s.health_fund, 470, 406, 9)
    _draw_text(c, s.supplementary_insurance, 470, 389, 9)
    _draw_text(c, s.occupation, 470, 372, 9)
    _draw_text(c, s.mobile, 470, 355, 9)
    _draw_text(c, s.email, 470, 338, 8)
    _draw_text(c, s.address.street, 470, 321, 8)
    _draw_text(c, s.address.house_number, 470, 304, 8)
    _draw_text(c, s.address.city, 470, 287, 9)
    _draw_text(c, s.address.zip_code, 470, 270, 9)

    # agent / request info
    _draw_text(c, parsed.agent_name or "איתי סומך", 160, 742, 9)
    _draw_text(c, parsed.requested_start_date, 160, 725, 9)

    # editable helper hints on page 1
    _draw_text(c, "להשלמה ידנית: מוטבים / חתימות / פרטי סוכן חסרים", 420, 102, 9)


def _overlay_health_page(c, answers: dict[str, str], start_q: int, end_q: int):
    # very rough X placement in 'לא' column for sample layout
    y = 654
    step = 25.5
    no_x = 487
    for idx, q in enumerate(range(start_q, end_q + 1)):
        ans = answers.get(f"q{q}", "")
        if ans == "לא":
            _draw_x(c, no_x, y - idx * step, 10)
        elif ans == "כן":
            _draw_x(c, no_x - 28, y - idx * step, 10)


def fill_fenix_pdf(parsed: ParsedReport, template_pdf_path: str, output_pdf_path: str):
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)

    # page 1 overlay
    _overlay_page_1(c, parsed)
    c.showPage()

    # blank pages 2-6
    for _ in range(2, 7):
        c.showPage()

    # page 7 - primary health (questions 1-8)
    _draw_text(c, parsed.primary_insured.full_name, 483, 748, 10)
    _draw_text(c, parsed.primary_insured.height_cm, 306, 651, 9)
    _draw_text(c, parsed.primary_insured.weight_kg, 306, 635, 9)
    _overlay_health_page(c, parsed.health_declarations_primary, 1, 8)
    c.showPage()

    # page 8 - primary health (questions 9-16)
    _draw_text(c, parsed.primary_insured.full_name, 483, 748, 10)
    _overlay_health_page(c, parsed.health_declarations_primary, 9, 16)
    c.showPage()

    # page 9 - secondary health (questions 1-8)
    _draw_text(c, parsed.secondary_insured.full_name, 483, 748, 10)
    _draw_text(c, parsed.secondary_insured.height_cm, 306, 651, 9)
    _draw_text(c, parsed.secondary_insured.weight_kg, 306, 635, 9)
    _overlay_health_page(c, parsed.health_declarations_secondary, 1, 8)
    c.showPage()

    # page 10 - secondary health (questions 9-16)
    _draw_text(c, parsed.secondary_insured.full_name, 483, 748, 10)
    _overlay_health_page(c, parsed.health_declarations_secondary, 9, 16)
    c.save()

    packet.seek(0)
    overlay_pdf = PdfReader(packet)
    template_pdf = PdfReader(template_pdf_path)
    writer = PdfWriter()

    max_pages = max(len(template_pdf.pages), len(overlay_pdf.pages))
    for idx in range(max_pages):
        if idx < len(template_pdf.pages):
            page = template_pdf.pages[idx]
        else:
            page = overlay_pdf.pages[idx]
            writer.add_page(page)
            continue
        if idx < len(overlay_pdf.pages):
            try:
                page.merge_page(overlay_pdf.pages[idx])
            except Exception:
                pass
        writer.add_page(page)

    with open(output_pdf_path, "wb") as f:
        writer.write(f)
