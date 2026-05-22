import os
import uuid
import aiofiles

from fastapi import FastAPI
from fastapi import UploadFile
from fastapi import File
from fastapi import Form
from fastapi import Body
from fastapi import BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from app.config import UPLOAD_DIR, OUTPUT_DIR
from app.parsers.factory import get_parser
from app.spreadsheet_parser import parse_spreadsheet
from app.tasks import process_po, run_verification

app = FastAPI()

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ─────────────────────────────────────────────────────────────


def _safe_remove(filepath: str):
    """Delete a file silently — no error if it doesn't exist."""
    try:
        os.remove(filepath)
        print(f"[Cleanup] Removed {filepath}")
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"[Cleanup] Failed to remove {filepath}: {e}")


def _cleanup_dir(directory: str):
    """Remove all files in a directory."""
    if not os.path.isdir(directory):
        return
    count = 0
    for fname in os.listdir(directory):
        _safe_remove(os.path.join(directory, fname))
        count += 1
    if count:
        print(f"[Cleanup] Removed {count} files from {directory}")


# ── Pydantic models ────────────────────────────────────────────────────


class ProductItem(BaseModel):
    sku: str
    product_name: str = ""
    barcode: Optional[str] = ""
    supplier_code: Optional[str] = ""
    job_no: Optional[str] = ""
    qty: Optional[int] = None
    unit_price: Optional[float] = None
    subtotal: Optional[float] = None


class VerifyRequest(BaseModel):
    customer_name: str = "zervi"
    po_number: Optional[str] = None
    products: list[ProductItem]


class CleanupRequest(BaseModel):
    filenames: Optional[list[str]] = None
    """Specific filenames to delete from OUTPUT_DIR."""
    all_outputs: bool = False
    """Delete all files in OUTPUT_DIR."""
    all_uploads: bool = False
    """Delete all files in UPLOAD_DIR."""


# ── Step 1: Extract PO data (no DB, no verification) ──────────────────


@app.post("/extract-po")
async def extract_po(
    customer_name: str = Form("zervi"),
    file: UploadFile = File(...),
):
    """Upload a PO PDF, extract all 8 columns, return raw data for editing."""
    filename = f"{uuid.uuid4()}.pdf"
    pdf_path = os.path.join(UPLOAD_DIR, filename)

    try:
        async with aiofiles.open(pdf_path, "wb") as out_file:
            content = await file.read()
            print(
                f"[Extract] Received {file.filename} ({len(content)} bytes) → {pdf_path}"
            )
            await out_file.write(content)

        parser = get_parser(customer_name)
        products = parser.parse(pdf_path)

        print(f"[Extract] Parsed {len(products)} products for {customer_name}")
        return {
            "products": products,
            "product_count": len(products),
        }
    finally:
        _safe_remove(pdf_path)


# ── Step 1b: Extract data from CSV / Excel ───────────────────────────


@app.post("/extract-file")
async def extract_file(
    file: UploadFile = File(...),
):
    """Upload a CSV or Excel file, extract all 8 columns, return raw data."""
    content = await file.read()
    print(
        f"[Extract-File] Received {file.filename} ({len(content)} bytes)"
    )

    products = parse_spreadsheet(content, file.filename or "")

    print(f"[Extract-File] Parsed {len(products)} products")
    return {
        "products": products,
        "product_count": len(products),
    }


# ── Step 2: Verify (potentially edited) products ───────────────────────


@app.post("/verify-po")
async def verify_po(body: VerifyRequest):
    """Receive a (potentially user-edited) product list and run 6-step verification."""
    products = [p.model_dump() for p in body.products]

    print(
        f"[Verify] Received {len(products)} products "
        f"for customer '{body.customer_name}'"
    )

    result = await run_verification(
        products,
        body.customer_name,
        body.po_number,
    )
    print(
        f"[Verify] Done: {result['existing_count']} existing, "
        f"{result['missing_count']} missing"
    )
    return result


# ── Combined endpoint (backward-compatible) ────────────────────────────


@app.post("/upload-po")
async def upload_po(
    customer_name: str = Form("zervi"),
    po_number: str = Form(None),
    file: UploadFile = File(...),
):
    """Upload a PO PDF, parse it, and run verification in one step."""
    filename = f"{uuid.uuid4()}.pdf"
    pdf_path = os.path.join(UPLOAD_DIR, filename)

    try:
        async with aiofiles.open(pdf_path, "wb") as out_file:
            content = await file.read()
            print(
                f"Received file {file.filename} ({len(content)} bytes) → {pdf_path}"
            )
            await out_file.write(content)

        result = await process_po(pdf_path, customer_name, po_number)
        print(
            f"Processed PO for {customer_name}: "
            f"{result['existing_count']} existing, "
            f"{result['missing_count']} missing"
        )
        return result
    finally:
        _safe_remove(pdf_path)


# ── Static files & cleanup ──────────────────────────────────────────────


@app.get("/download/{filename}")
async def download_file(filename: str, background_tasks: BackgroundTasks):
    """Serve an Excel file, then schedule it for deletion."""
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.isfile(file_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")

    # Schedule deletion after the response has been sent
    background_tasks.add_task(_safe_remove, file_path)
    return FileResponse(path=file_path, filename=filename)


@app.post("/cleanup")
async def cleanup(body: CleanupRequest = CleanupRequest()):
    """Delete temporary files.

    - `filenames`: delete specific files from outputs/
    - `all_outputs`: delete everything in outputs/
    - `all_uploads`: delete everything in uploads/
    """
    removed = []

    if body.filenames:
        for fname in body.filenames:
            # Sanitize: only allow alphanumeric, dash, underscore, dot
            safe = "".join(c for c in fname if c.isalnum() or c in "-_.")
            if safe == fname:
                path = os.path.join(OUTPUT_DIR, safe)
                if os.path.isfile(path):
                    _safe_remove(path)
                    removed.append(safe)

    if body.all_outputs:
        _cleanup_dir(OUTPUT_DIR)
        removed.append("all outputs")

    if body.all_uploads:
        _cleanup_dir(UPLOAD_DIR)
        removed.append("all uploads")

    return {"removed": removed}


@app.get("/health")
async def health_check():
    """Verify database connectivity."""
    try:
        from app.db import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
