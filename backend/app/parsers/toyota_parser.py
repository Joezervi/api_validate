import pdfplumber
import re
from app.parsers.base import BaseParser

# Values in column 0 that indicate a header row
_HEADER_KEYWORDS = {"sku", "code", "item", "product", "barcode", "description"}


class ToyotaParser(BaseParser):
    """Parser for Toyota PO PDFs.

    Expected table column layout (may vary by PO format):
      col 0: SKU
      col 1: Product Name
      col 2: Barcode (optional)
      col 3: Qty (optional)
      col 4: Unit Price (optional)
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

                        sku = (row[0] or "").strip()

                        # ── Skip header rows ──
                        if not sku or sku.lower() in _HEADER_KEYWORDS:
                            continue

                        product_name = (row[1] or "").strip()

                        if not product_name:
                            continue

                        item = {
                            "sku": sku,
                            "product_name": product_name,
                        }

                        # Barcode — col 2
                        if len(row) > 2 and row[2]:
                            barcode = str(row[2]).strip()
                            if barcode and barcode.lower() != "none":
                                item["barcode"] = barcode

                        # Qty — col 3
                        if len(row) > 3 and row[3]:
                            qty_raw = str(row[3]).strip()
                            try:
                                item["qty"] = int(float(qty_raw))
                            except (ValueError, TypeError):
                                pass

                        # Unit Price — col 4
                        if len(row) > 4 and row[4]:
                            price_raw = str(row[4]).strip().replace(",", ".")
                            try:
                                item["unit_price"] = float(
                                    re.sub(r"[^\d.]", "", price_raw)
                                )
                            except (ValueError, TypeError):
                                pass

                        products.append(item)

        return products
