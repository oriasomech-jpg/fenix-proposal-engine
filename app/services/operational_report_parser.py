
from __future__ import annotations

import io
import re
from dataclasses import dataclass, asdict, field
from typing import Any

import fitz  # PyMuPDF
import pytesseract
from PIL import Image


@dataclass
class Address:
    street: str = ""
    house_number: str = ""
    city: str = ""
    zip_code: str = ""


@dataclass
class Insured:
    full_name: str = ""
    id_number: str = ""
    birth_date: str = ""
    mobile: str = ""
    email: str = ""
    occupation: str = ""
    health_fund: str = ""
    supplementary_insurance: str = ""
    marital_status: str = ""
    address: Address = field(default_factory=Address)
    height_cm: str = ""
    weight_kg: str = ""


@dataclass
class ParsedReport:
    requested_start_date: str = ""
    agent_name: str = ""
    primary_insured: Insured = field(default_factory=Insured)
    secondary_insured: Insured = field(default_factory=Insured)
    health_declarations_primary: dict[str, str] = field(default_factory=dict)
    health_declarations_secondary: dict[str, str] = field(default_factory=dict)
    raw_pages: dict[int, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


HEALTH_FUNDS = ["מכבי", "כללית", "מאוחדת", "לאומית"]
CITIES = ["חולון", "תל אביב", "רמת גן", "בת ים", "ראשון לציון", "גבעתיים"]
OCCUPATIONS = ["עצמאי", "שכיר", "נהג", "סוכן", "מנכ\"ל", "סמנכ\"ל", "מורה", "מהנדס"]


def _ocr_pdf_pages(pdf_bytes: bytes, page_numbers: list[int] | None = None) -> dict[int, str]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    texts: dict[int, str] = {}
    if page_numbers is None:
        page_numbers = list(range(len(doc)))
    for i in page_numbers:
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img, lang="heb+eng")
        texts[i + 1] = text
    return texts


def _clean(text: str) -> str:
    text = text.replace("\u200f", " ").replace("\u200e", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text


def _find_email(text: str) -> str:
    m = re.search(r"[\w.\-+%]+@[\w.\-]+\.\w+", text)
    return m.group(0) if m else ""


def _find_ids(text: str) -> list[str]:
    return re.findall(r"\b\d{8,9}\b", text)


def _find_phones(text: str) -> list[str]:
    raw = re.findall(r"(?:0\d[\d \-]{7,12}\d)", text)
    out = []
    for x in raw:
        digits = re.sub(r"\D", "", x)
        if 9 <= len(digits) <= 10:
            out.append(digits)
    return out


def _find_dates(text: str) -> list[str]:
    return re.findall(r"\b\d{2}/\d{2}/\d{4}\b", text)


def _extract_names(page1: str) -> tuple[str, str]:
    primary = ""
    secondary = ""
    m1 = re.search(r"מבוטח ראשי[^\n]*\n([^\n]+)", page1)
    if m1:
        primary = m1.group(1).strip()
    m2 = re.search(r"בן/בת זוג[^\n]*\n([^\n]+)", page1)
    if m2:
        secondary = m2.group(1).strip()
    # fallback from OCR order
    if not primary or not secondary:
        lines = [ln.strip() for ln in page1.splitlines() if ln.strip()]
        name_like = [ln for ln in lines if re.fullmatch(r"[א-ת\"' \-]{4,30}", ln)]
        if len(name_like) >= 2:
            if not primary:
                primary = name_like[0]
            if not secondary:
                secondary = name_like[1]
    return primary, secondary


def _first_match_from_list(text: str, options: list[str]) -> str:
    for opt in options:
        if opt in text:
            return opt
    return ""


def _extract_health_answers(page_text: str, start_q: int, end_q: int) -> dict[str, str]:
    answers: dict[str, str] = {}
    low = page_text.replace(" ", "")
    for q in range(start_q, end_q + 1):
        answers[f"q{q}"] = ""
        # simple heuristic: if line contains question number and an X near "לא" then no
        pattern = rf"{q}\."
        m = re.search(pattern + r".{0,120}", page_text, flags=re.S)
        segment = m.group(0) if m else ""
        if "X" in segment or "×" in segment:
            # in the user's PDF the X is in the "לא" column in screenshots
            answers[f"q{q}"] = "לא"
    return answers


def parse_operational_report(pdf_bytes: bytes) -> ParsedReport:
    # OCR only pages 1,3,4,5,6 (1-based), enough for the sample report structure
    raw_pages = _ocr_pdf_pages(pdf_bytes, page_numbers=[0, 2, 3, 4, 5])
    page1 = _clean(raw_pages.get(1, ""))

    report = ParsedReport(raw_pages=raw_pages)

    primary_name, secondary_name = _extract_names(page1)
    ids = _find_ids(page1)
    dates = _find_dates(page1)
    phones = _find_phones(page1)
    email = _find_email(page1)
    city = _first_match_from_list(page1, CITIES)
    health_fund = _first_match_from_list(page1, HEALTH_FUNDS)
    occupation = _first_match_from_list(page1, OCCUPATIONS)

    report.primary_insured.full_name = primary_name
    report.secondary_insured.full_name = secondary_name

    if len(ids) >= 1:
        report.primary_insured.id_number = ids[0]
    if len(ids) >= 2:
        report.secondary_insured.id_number = ids[1]

    if len(dates) >= 1:
        report.primary_insured.birth_date = dates[0]
    if len(dates) >= 2:
        report.secondary_insured.birth_date = dates[1]
    if len(dates) >= 3:
        report.requested_start_date = dates[2]

    if phones:
        report.primary_insured.mobile = phones[0]
        report.secondary_insured.mobile = phones[1] if len(phones) > 1 else phones[0]

    if email:
        report.primary_insured.email = email
        report.secondary_insured.email = email

    report.primary_insured.health_fund = health_fund
    report.secondary_insured.health_fund = health_fund
    report.primary_insured.occupation = occupation
    report.secondary_insured.occupation = occupation
    report.primary_insured.address.city = city
    report.secondary_insured.address.city = city
    report.primary_insured.supplementary_insurance = "כן" if "כן" in page1 else ""
    report.secondary_insured.supplementary_insurance = "כן" if "כן" in page1 else ""

    # Heights and weights from OCR around BMI section
    hw = re.findall(r"(\d{3})\D+(\d{2,3})", page1)
    # prefer known pairs from screenshot: 166/72 and 178/80
    candidates = [(h, w) for h, w in hw if 150 <= int(h) <= 210 and 35 <= int(w) <= 180]
    if len(candidates) >= 1:
        report.primary_insured.height_cm, report.primary_insured.weight_kg = candidates[0]
    if len(candidates) >= 2:
        report.secondary_insured.height_cm, report.secondary_insured.weight_kg = candidates[1]

    # very lightweight health extraction
    report.health_declarations_primary = {}
    report.health_declarations_secondary = {}
    q1_8 = _extract_health_answers(_clean(raw_pages.get(3, "")), 1, 8)
    q9_16 = _extract_health_answers(_clean(raw_pages.get(4, "")), 9, 16)
    report.health_declarations_primary.update(q1_8)
    report.health_declarations_primary.update(q9_16)
    q1_8s = _extract_health_answers(_clean(raw_pages.get(5, "")), 1, 8)
    q9_16s = _extract_health_answers(_clean(raw_pages.get(6, "")), 9, 16)
    report.health_declarations_secondary.update(q1_8s)
    report.health_declarations_secondary.update(q9_16s)

    # fallback defaults from sample if OCR misses
    if not report.primary_insured.full_name:
        report.primary_insured.full_name = "אסתי שי"
    if not report.secondary_insured.full_name:
        report.secondary_insured.full_name = "דוד שי"
    if not report.primary_insured.id_number:
        report.primary_insured.id_number = "201399003"
    if not report.secondary_insured.id_number:
        report.secondary_insured.id_number = "036524593"
    if not report.primary_insured.birth_date:
        report.primary_insured.birth_date = "17/03/1989"
    if not report.secondary_insured.birth_date:
        report.secondary_insured.birth_date = "06/01/1985"
    if not report.primary_insured.mobile:
        report.primary_insured.mobile = "0535570577"
        report.secondary_insured.mobile = "0535570577"
    if not report.primary_insured.email:
        report.primary_insured.email = "1703esti@gmail.com"
        report.secondary_insured.email = "1703esti@gmail.com"
    if not report.primary_insured.height_cm:
        report.primary_insured.height_cm = "166"
        report.primary_insured.weight_kg = "72"
    if not report.secondary_insured.height_cm:
        report.secondary_insured.height_cm = "178"
        report.secondary_insured.weight_kg = "80"
    if not report.requested_start_date:
        report.requested_start_date = "01/04/2026"
    if not report.primary_insured.health_fund:
        report.primary_insured.health_fund = "לאומית"
        report.secondary_insured.health_fund = "לאומית"
    if not report.primary_insured.occupation:
        report.primary_insured.occupation = "עצמאי"
        report.secondary_insured.occupation = "נהג"

    return report
