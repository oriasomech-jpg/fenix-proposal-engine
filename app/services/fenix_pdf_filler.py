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
    # Fallback: reverse only when Hebrew letters are present.
    return text[::-1] if re.search(r"[א-ת]", text) else text


def _split_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in (full_name or "").split() if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    first = parts[0]
    last = " ".join(parts[1:])
    return first, last


def _only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _normalize_date_digits(value: str) -> str:
    digits = _only_digits(value)
    if len(digits) == 8:
        return digits
    return digits[:8]


def _draw_text(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    *,
    size: float = 11,
    bold: bool = True,
    align: str = "right",
    max_width: float | None = None,
):
    text = (text or "").strip()
    if not text:
        return
    font_name = _register_font(FONT_BOLD if bold else FONT_REGULAR)
    rendered = _rtl_text(text)
    chosen_size = size
    if max_width:
        while chosen_size > 7 and pdfmetrics.stringWidth(rendered, font_name, chosen_size) > max_width:
            chosen_size -= 0.3
    c.setFont(font_name, chosen_size)
    if align == "center":
        c.drawCentredString(x, y, rendered)
    elif align == "left":
        c.drawString(x, y, rendered)
    else:
        c.drawRightString(x, y, rendered)


def _draw_chars_in_boxes(
    c: canvas.Canvas,
    value: str,
    *,
    left_x: float,
    right_x: float,
    y: float,
    count: int,
    size: float = 11,
    bold: bool = True,
):
    chars = list((value or "")[:count])
    if not chars or count <= 0:
        return
    font_name = _register_font(FONT_BOLD if bold else FONT_REGULAR)
    c.setFont(font_name, size)
    step = (right_x - left_x) / count
    for idx, ch in enumerate(chars):
        cx = left_x + (idx + 0.5) * step
        c.drawCentredString(cx, y, ch)


def _draw_x(c: canvas.Canvas, x: float, y: float, size: int = 13):
    font_name = _register_font(FONT_BOLD)
    c.setFont(font_name, size)
    c.drawCentredString(x, y, "X")


def _mark_yes_no(c: canvas.Canvas, value: str, yes_x: float, no_x: float, y: float):
    value = (value or "").strip()
    if value == "כן":
        _draw_x(c, yes_x, y)
    elif value == "לא":
        _draw_x(c, no_x, y)


def _mark_gender(c: canvas.Canvas, value: str, male_x: float, female_x: float, y: float):
    value = (value or "").strip()
    if value == "זכר":
        _draw_x(c, male_x, y)
    elif value == "נקבה":
        _draw_x(c, female_x, y)


def _mark_delivery_pref(c: canvas.Canvas, value: str, email_x: float, post_x: float, y_email: float, y_post: float):
    v = (value or "").lower()
    if "email" in v or "mail" in v or "מייל" in v:
        _draw_x(c, email_x, y_email)
    elif "דואר" in v:
        _draw_x(c, post_x, y_post)


def _overlay_candidate_column(c: canvas.Canvas, insured, *, right_x: float, left_x: float):
    first_name, last_name = _split_name(insured.full_name)
    text_right = right_x - 8
    width = right_x - left_x - 14

    _draw_text(c, last_name, text_right, 585, max_width=width)
    _draw_text(c, first_name, text_right, 564, max_width=width)
    _draw_text(c, _only_digits(insured.id_number), text_right, 543, size=10.2, max_width=width)
    _mark_gender(c, getattr(insured, "gender", ""), male_x=right_x - 48, female_x=right_x - 17, y=523)

    marital = (getattr(insured, "marital_status", "") or "").replace("נשואה", "נשוי")
    if marital:
        mapping = {
            "רווק": right_x - 20,
            "נשוי": right_x - 51,
            "גרוש": right_x - 82,
        }
        x = mapping.get(marital)
        if x:
            _draw_x(c, x, 502)

    birth_text = insured.birth_date.replace('/', '/')
    _draw_text(c, birth_text, text_right, 461, size=10.0, max_width=width)
    _draw_text(c, insured.health_fund, text_right, 440, max_width=width)
    _mark_yes_no(c, insured.supplementary_insurance, yes_x=right_x - 48, no_x=right_x - 20, y=419)
    _draw_text(c, insured.occupation, text_right, 398, max_width=width)
    _draw_text(c, _only_digits(insured.mobile), text_right, 356, size=10.0, max_width=width)
    email = (insured.email or '').strip()
    if email:
        _draw_text(c, email, text_right, 316, size=7.9, max_width=width)
    _mark_delivery_pref(c, getattr(insured, 'delivery_preference', ''), email_x=right_x - 18, post_x=right_x - 18, y_email=251, y_post=231)

def _overlay_page_1(c: canvas.Canvas, parsed: ParsedReport):
    p = parsed.primary_insured
    s = parsed.secondary_insured

    # top section - requested start date
    start_digits = _normalize_date_digits(parsed.requested_start_date)
    if start_digits:
        _draw_chars_in_boxes(c, start_digits, left_x=131, right_x=200, y=770, count=8, size=10.2)

    # agent area (simple, no perfect mapping yet)
    _draw_text(c, parsed.agent_name or "איתי סומך", 418, 726, size=10.5, max_width=78)

    # candidate columns (page 1)
    _overlay_candidate_column(c, p, right_x=418, left_x=362)
    _overlay_candidate_column(c, s, right_x=361, left_x=305)

    # signatures section helper placeholder kept small and official


PRIMARY_HEALTH_X = {"כן": 484, "לא": 512}
SECONDARY_HEALTH_X = {"כן": 456, "לא": 484}
HEALTH_Y_1_8 = {1: 654, 2: 628, 3: 600, 4: 573, 5: 546, 6: 519, 7: 492, 8: 465}
HEALTH_Y_9_16 = {9: 654, 10: 628, 11: 600, 12: 573, 13: 546, 14: 519, 15: 492, 16: 465}


def _overlay_health_page(c: canvas.Canvas, answers: dict[str, str], q_to_y: dict[int, float], yes_x: float, no_x: float):
    for q, y in q_to_y.items():
        ans = answers.get(f"q{q}", "")
        _mark_yes_no(c, ans, yes_x=yes_x, no_x=no_x, y=y)


def fill_fenix_pdf(parsed: ParsedReport, template_pdf_path: str, output_pdf_path: str):
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)

    # page 1 overlay
    _overlay_page_1(c, parsed)
    c.showPage()

    # keep pages 2-6 blank for now
    for _ in range(2, 7):
        c.showPage()

    # page 7 - primary health (questions 1-8)
    _draw_text(c, parsed.primary_insured.full_name, 483, 748, size=10.5, max_width=120)
    _draw_chars_in_boxes(c, _only_digits(parsed.primary_insured.height_cm), left_x=286, right_x=323, y=651, count=max(1, len(_only_digits(parsed.primary_insured.height_cm)) or 1), size=10)
    _draw_chars_in_boxes(c, _only_digits(parsed.primary_insured.weight_kg), left_x=286, right_x=323, y=635, count=max(1, len(_only_digits(parsed.primary_insured.weight_kg)) or 1), size=10)
    _overlay_health_page(c, parsed.health_declarations_primary, HEALTH_Y_1_8, yes_x=PRIMARY_HEALTH_X["כן"], no_x=PRIMARY_HEALTH_X["לא"])
    c.showPage()

    # page 8 - primary health (questions 9-16)
    _draw_text(c, parsed.primary_insured.full_name, 483, 748, size=10.5, max_width=120)
    _overlay_health_page(c, parsed.health_declarations_primary, HEALTH_Y_9_16, yes_x=PRIMARY_HEALTH_X["כן"], no_x=PRIMARY_HEALTH_X["לא"])
    c.showPage()

    # page 9 - secondary health (questions 1-8)
    _draw_text(c, parsed.secondary_insured.full_name, 483, 748, size=10.5, max_width=120)
    _draw_chars_in_boxes(c, _only_digits(parsed.secondary_insured.height_cm), left_x=286, right_x=323, y=651, count=max(1, len(_only_digits(parsed.secondary_insured.height_cm)) or 1), size=10)
    _draw_chars_in_boxes(c, _only_digits(parsed.secondary_insured.weight_kg), left_x=286, right_x=323, y=635, count=max(1, len(_only_digits(parsed.secondary_insured.weight_kg)) or 1), size=10)
    _overlay_health_page(c, parsed.health_declarations_secondary, HEALTH_Y_1_8, yes_x=SECONDARY_HEALTH_X["כן"], no_x=SECONDARY_HEALTH_X["לא"])
    c.showPage()

    # page 10 - secondary health (questions 9-16)
    _draw_text(c, parsed.secondary_insured.full_name, 483, 748, size=10.5, max_width=120)
    _overlay_health_page(c, parsed.health_declarations_secondary, HEALTH_Y_9_16, yes_x=SECONDARY_HEALTH_X["כן"], no_x=SECONDARY_HEALTH_X["לא"])
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
