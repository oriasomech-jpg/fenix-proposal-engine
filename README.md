# Fenix Proposal Engine

Upload an operational-report PDF and download a filled Fenix proposal PDF.

## Local run
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:
- http://127.0.0.1:8000/

## Deploy on Render
This repo is already prepared for Render with `Dockerfile` and `render.yaml`.
