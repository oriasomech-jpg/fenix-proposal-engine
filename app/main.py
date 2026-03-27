
from __future__ import annotations

import io
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.services.operational_report_parser import parse_operational_report
from app.services.fenix_pdf_filler import fill_fenix_pdf

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Fenix Proposal Engine")

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/parse")
async def parse_only(file: UploadFile = File(...)):
    pdf_bytes = await file.read()
    parsed = parse_operational_report(pdf_bytes)
    return JSONResponse(parsed.to_dict())


@app.post("/generate")
async def generate(file: UploadFile = File(...)):
    pdf_bytes = await file.read()
    parsed = parse_operational_report(pdf_bytes)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        output_path = tmp.name

    fill_fenix_pdf(
        parsed=parsed,
        template_pdf_path=str(BASE_DIR / "templates" / "GetPDF.pdf"),
        output_pdf_path=output_path,
    )
    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename="fenix_filled.pdf",
    )
