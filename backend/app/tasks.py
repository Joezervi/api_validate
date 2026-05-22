import os
import uuid

from app.checker import process_products
from app.config import OUTPUT_DIR
from app.parsers.factory import get_parser
from openpyxl import Workbook


async def process_po(pdf_path, customer_name, po_number=None):

    parser = get_parser(customer_name)

    products = parser.parse(pdf_path)

    result = await process_products(products, customer_name, po_number)

    workbook = Workbook()

    # ── Existing SKU sheet ──
    ws_existing = workbook.active
    ws_existing.title = "Existing SKU"
    ws_existing.append(["SKU", "Barcode", "Product Name", "Category", "Price"])
    for row in result["existing"]:
        ws_existing.append(
            [
                row.get("sku"),
                row.get("barcode", ""),
                row.get("product_name") or row.get("product"),
                row.get("category", ""),
                row.get("price", ""),
            ]
        )

    # ── Missing SKU sheet — 5‑column format ──
    ws_missing = workbook.create_sheet("Missing SKU")
    ws_missing.append(
        ["SKU Missing", "Barcode", "Product Name", "Category Name", "Noted"]
    )
    for row in result["missing"]:
        ws_missing.append(
            [
                row.get("sku_missing"),
                row.get("barcode"),
                row.get("product_name"),
                row.get("category_name"),
                row.get("noted"),
            ]
        )

    excel_filename = f"{uuid.uuid4()}.xlsx"

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    excel_path = os.path.join(OUTPUT_DIR, excel_filename)

    workbook.save(excel_path)

    return {
        "excel_file": excel_filename,
        "existing": result["existing"],
        "missing": result["missing"],
        "markdown_report": result.get("markdown_report", ""),
        "existing_count": len(result["existing"]),
        "missing_count": len(result["missing"]),
    }
