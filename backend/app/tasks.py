import asyncio
import os
import uuid

from app.celery_app import celery
from app.checker import process_products
from app.parsers.factory import get_parser
from openpyxl import Workbook

OUTPUT_DIR = "outputs"


@celery.task
def process_po_task(pdf_path, customer_name):

    parser = get_parser(customer_name)

    products = parser.parse(pdf_path)

    result = asyncio.run(process_products(products, customer_name))

    workbook = Workbook()

    ws_existing = workbook.active
    ws_existing.title = "Existing SKU"
    ws_existing.append(["SKU", "Product Name", "Category", "Price"])
    for row in result["existing"]:
        ws_existing.append(
            [
                row.get("sku"),
                row.get("product_name") or row.get("product"),
                row.get("category", ""),
                row.get("price", ""),
            ]
        )

    ws_missing = workbook.create_sheet("Missing SKU")
    ws_missing.append(["SKU", "Product Name", "Category", "Price"])
    for row in result["missing"]:
        ws_missing.append(
            [
                row.get("sku"),
                row.get("product_name"),
                row.get("category", ""),
                row.get("price", ""),
            ]
        )

    excel_filename = f"{uuid.uuid4()}.xlsx"

    excel_path = os.path.join(OUTPUT_DIR, excel_filename)

    workbook.save(excel_path)

    return {
        "excel_file": excel_filename,
        "existing": result["existing"],
        "missing": result["missing"],
        "existing_count": len(result["existing"]),
        "missing_count": len(result["missing"]),
    }
