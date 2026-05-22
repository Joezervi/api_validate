import pdfplumber
import re
from app.parsers.base import BaseParser

# Values in column 0 that indicate a header row
_HEADER_KEYWORDS = {"sku", "code", "item", "product", "barcode", "description"}

# Column indices for Toyota PO format (may vary — adjust based on actual PDFs)
_COL_SKU = 0
_COL_PRODUCT = 1
_COL_BARCODE = 2
_COL_QTY = 3
_COL_PRICE = 4


class ToyotaParser(BaseParser):
    """Parser for Toyota PO PDFs.

    Expected table column layout (may vary by PO format):
      col 0: SKU           col 1: Product Name
      col 2: Barcode       col 3: Qty
      col 4: Unit Price    col 5+: additional columns
    """

    def parse(self, pdf_source):
        products = []

        with pdfplumber.open(pdf_source) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row:
                            continue
                        if len(row) < 4:
                            continue

                        sku = (row[_COL_SKU] or "").strip()

                        if not sku or sku.lower() in _HEADER_KEYWORDS:
                            continue

                        product_name = (row[_COL_PRODUCT] or "").strip()
                        if not product_name:
                            continue

                        item = {
                            "sku": sku,
                            "product_name": product_name,
                        }

                        # Barcode
                        if len(row) > _COL_BARCODE and row[_COL_BARCODE]:
                            barcode = str(row[_COL_BARCODE]).strip()
                            if barcode and barcode.lower() != "none":
                                item["barcode"] = barcode

                        # Qty
                        if len(row) > _COL_QTY and row[_COL_QTY]:
                            qty_raw = str(row[_COL_QTY]).strip()
                            try:
                                item["qty"] = int(float(qty_raw))
                            except (ValueError, TypeError):
                                pass

                        # Unit Price
                        if len(row) > _COL_PRICE and row[_COL_PRICE]:
                            price_raw = str(row[_COL_PRICE]).strip().replace(",", ".")
                            try:
                                item["unit_price"] = float(
                                    re.sub(r"[^\d.]", "", price_raw)
                                )
                            except (ValueError, TypeError):
                                pass

                        products.append(item)

        return products
