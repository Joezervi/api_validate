import os
import uuid
import aiofiles

from fastapi import FastAPI
from fastapi import UploadFile
from fastapi import File
from fastapi import Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from celery.result import AsyncResult

from app.tasks import process_po_task
from app.celery_app import celery

app = FastAPI()

UPLOAD_DIR = "uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/upload-po")
async def upload_po(
    customer_name: str = Form(...),
    po_number: str = Form(None),
    file: UploadFile = File(...),
):
    filename = f"{uuid.uuid4()}.pdf"
    pdf_path = f"{UPLOAD_DIR}/{filename}"

    async with aiofiles.open(pdf_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    task = process_po_task.delay(pdf_path, customer_name, po_number)

    return {"task_id": task.id}


@app.get("/task/{task_id}")
async def get_task(task_id: str):
    task = AsyncResult(task_id, app=celery)

    return {
        "status": task.status,
        "result": task.result,
    }


@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = f"outputs/{filename}"
    return FileResponse(path=file_path, filename=filename)
