import os
import uuid
import aiofiles

from fastapi import FastAPI
from fastapi import UploadFile
from fastapi import File
from fastapi import Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import UPLOAD_DIR, OUTPUT_DIR
from app.tasks import process_po

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


@app.post("/upload-po")
async def upload_po(
    customer_name: str = Form("zervi"),
    po_number: str = Form(None),
    file: UploadFile = File(...),
):
    filename = f"{uuid.uuid4()}.pdf"
    pdf_path = os.path.join(UPLOAD_DIR, filename)

    async with aiofiles.open(pdf_path, "wb") as out_file:
        content = await file.read()
        print(
            f"Received file {file.filename} ({len(content)} bytes) "
            f"→ {pdf_path}"
        )
        await out_file.write(content)

    result = await process_po(pdf_path, customer_name, po_number)
    print(
        f"Processed PO for {customer_name}: "
        f"{result['existing_count']} existing, "
        f"{result['missing_count']} missing"
    )
    return result


@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    return FileResponse(path=file_path, filename=filename)


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
