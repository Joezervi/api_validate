import re

import pdfplumber
from app.parsers.base import BaseParser

# Values in column 0 that indicate a header row
_HEADER_KEYWORDS = {"sku", "code", "item", "product", "barcode", "description"}

# Column indices for Zervi PO format
_COL_SKU = 0
_COL_BARCODE = 1
_COL_PRODUCT = 3
_COL_QTY = 5
_COL_PRICE = 6


class ZerviParser(BaseParser):
    """Parser for Zervi PO PDFs.

    Column layout (from PO-43881):
      col 0: SKU         col 1: Barcode
      col 2: Supplier    col 3: Product Name
      col 4: Job No.     col 5: Qty
      col 6: Unit Price  col 7: Subtotal

    Falls back to word-position extraction when pdfplumber's table
    extraction returns empty cells (common with certain PDF fonts).
    """

    def parse(self, pdf_source):
        # ── Primary: table-based extraction ──
        products = self._parse_via_tables(pdf_source)

        if products:
            print(f"[ZerviParser] Table extraction produced {len(products)} products")
            return products

        # ── Fallback: word-position-based extraction ──
        print(
            "[ZerviParser] Table extraction empty, falling back to word-position extraction"
        )
        products = self._parse_via_words(pdf_source)
        print(f"[ZerviParser] Word-based extraction produced {len(products)} products")
        return products

    # ── Table-based extraction ─────────────────────────────────────────

    def _parse_via_tables(self, pdf_source):
        products = []

        with pdfplumber.open(pdf_source) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    has_data = False
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

                        has_data = True
                        item = self._build_item(row, sku, product_name)
                        products.append(item)

                    if not has_data:
                        # Table structure found but no text — discard
                        print(
                            f"[ZerviParser] Table had {len(table)} rows but zero data rows (all cells empty)"
                        )

        return products

    # ── Word-position-based extraction (fallback) ──────────────────────

    def _parse_via_words(self, pdf_source):
        """Use pdfplumber's extract_words() with positional data.

        Groups words into lines by Y-coordinate, identifies column
        boundaries from the header row, then assigns words to columns
        by X-coordinate for each data line.
        """
        products = []

        with pdfplumber.open(pdf_source) as pdf:
            for page in pdf.pages:
                words = page.extract_words(
                    keep_blank_chars=True,
                    use_text_flow=True,
                )
                if not words:
                    continue

                # Group words into lines by Y tolerance
                lines = self._group_words_into_lines(words, y_tolerance=5)
                if len(lines) < 2:
                    continue

                # Find header line and data lines
                header_line, data_lines = self._split_header_data(lines)
                if header_line is None or not data_lines:
                    continue

                # Build column X-ranges from header word positions
                col_ranges = self._build_column_ranges(header_line)
                if len(col_ranges) < 4:
                    continue

                print(
                    f"[ZerviParser] Detected {len(col_ranges)} columns, {len(data_lines)} data lines"
                )

                # Parse each data line
                for line_words in data_lines:
                    print(f"[ZerviParser] Parsing line with {line_words} words")
                    row = self._words_to_columns(line_words, col_ranges)
                    print(f"[ZerviParser] Parsed row: {row}")
                    if not row:
                        continue

                    sku = row.get("sku", "")
                    product_name = row.get("product_name", "")
                    if not sku or not product_name:
                        continue

                    item = {
                        "sku": sku,
                        "product_name": product_name,
                    }
                    if row.get("barcode"):
                        item["barcode"] = row["barcode"]
                    if row.get("qty") is not None:
                        item["qty"] = row["qty"]
                    if row.get("unit_price") is not None:
                        item["unit_price"] = row["unit_price"]

                    products.append(item)

        return products

    # ── Helpers ────────────────────────────────────────────────────────

    def _build_item(self, row, sku, product_name):
        """Build a product dict from a table row."""
        item = {"sku": sku, "product_name": product_name}

        if len(row) > _COL_BARCODE and row[_COL_BARCODE]:
            barcode = str(row[_COL_BARCODE]).strip()
            if barcode and barcode.lower() != "none":
                item["barcode"] = barcode

        if len(row) > _COL_QTY and row[_COL_QTY]:
            try:
                item["qty"] = int(float(str(row[_COL_QTY]).strip()))
            except (ValueError, TypeError):
                pass

        if len(row) > _COL_PRICE and row[_COL_PRICE]:
            price_raw = str(row[_COL_PRICE]).strip().replace(",", ".")
            try:
                item["unit_price"] = float(re.sub(r"[^\d.]", "", price_raw))
            except (ValueError, TypeError):
                pass

        return item

    @staticmethod
    def _group_words_into_lines(words, y_tolerance=5):
        """Group word dicts into lines by proximity of their Y (top) coordinate."""
        if not words:
            return []

        # Sort by Y then X
        sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
        lines = []
        current_line = [sorted_words[0]]
        current_y = sorted_words[0]["top"]

        for w in sorted_words[1:]:
            if abs(w["top"] - current_y) <= y_tolerance:
                current_line.append(w)
            else:
                # Sort current line by X before appending
                current_line.sort(key=lambda w: w["x0"])
                lines.append(current_line)
                current_line = [w]
                current_y = w["top"]

        current_line.sort(key=lambda w: w["x0"])
        lines.append(current_line)
        return lines

    @staticmethod
    def _split_header_data(lines):
        """Identify the header line (contains known column names) and split from data."""
        header_terms = {
            "sku",
            "product",
            "barcode",
            "item",
            "description",
            "qty",
            "price",
        }

        header_idx = None
        for i, line_words in enumerate(lines):
            line_text = " ".join(w["text"] for w in line_words).lower()
            matches = sum(1 for t in header_terms if t in line_text)
            if matches >= 2:
                header_idx = i
                break

        if header_idx is None:
            return None, []

        header_line = lines[header_idx]
        data_lines = lines[header_idx + 1 :]
        return header_line, data_lines

    @staticmethod
    def _build_column_ranges(header_line):
        """Build (x0_min, x1_max) boundaries per column from header word positions.

        Returns a list of dicts: {'x0': float, 'x1': float, 'text': str}
        representing the X range each column occupies.
        """
        # Merge adjacent header words that belong to the same column
        # (e.g., "Product" and "Name" should merge into one column)
        columns = []
        for w in header_line:
            text = w["text"].strip()
            if not text:
                continue
            columns.append(
                {
                    "x0": float(w["x0"]),
                    "x1": float(w["x1"]),
                    "text": text.lower(),
                }
            )

        # Merge multi-word column headers
        merged = []
        i = 0
        while i < len(columns):
            current = columns[i]
            # Look ahead for words that are close to this column's right edge
            j = i + 1
            while j < len(columns):
                gap = columns[j]["x0"] - current["x1"]
                if gap < 15:  # small gap — same column header
                    current["x1"] = columns[j]["x1"]
                    current["text"] += " " + columns[j]["text"]
                    j += 1
                else:
                    break
            merged.append(current)
            i = j

        # Now expand each column's range to include the gap up to the next column
        ranges = []
        for idx, col in enumerate(merged):
            r = {"x0": col["x0"], "text": col["text"]}
            if idx + 1 < len(merged):
                r["x1"] = merged[idx + 1]["x0"]
            else:
                r["x1"] = col["x1"] + 200  # generous right bound
            ranges.append(r)

        return ranges

    @staticmethod
    def _words_to_columns(line_words, col_ranges):
        """Assign words from a data line to columns based on X-coordinate ranges.

        Returns a dict with keys: sku, barcode, product_name, qty, unit_price
        or None if the line doesn't contain a valid SKU.
        """
        if not line_words:
            return None

        # Build column text by assigning each word to the column range it falls in
        col_texts = ["" for _ in col_ranges]
        for w in line_words:
            x_center = (float(w["x0"]) + float(w["x1"])) / 2.0
            for idx, cr in enumerate(col_ranges):
                if cr["x0"] <= x_center < cr["x1"]:
                    if col_texts[idx]:
                        col_texts[idx] += " " + w["text"]
                    else:
                        col_texts[idx] = w["text"]
                    break

        result = {}

        # Map known columns by index
        if _COL_SKU < len(col_texts) and col_texts[_COL_SKU]:
            result["sku"] = col_texts[_COL_SKU].strip()

        if _COL_BARCODE < len(col_texts) and col_texts[_COL_BARCODE]:
            b = col_texts[_COL_BARCODE].strip()
            # Barcodes: digits, dashes, spaces, letters (Code 128, EAN, UPC, etc.)
            if b and re.match(r"^[\dA-Za-z\-\s]{5,}$", b):
                result["barcode"] = b

        if _COL_PRODUCT < len(col_texts) and col_texts[_COL_PRODUCT]:
            result["product_name"] = col_texts[_COL_PRODUCT].strip()

        if _COL_QTY < len(col_texts) and col_texts[_COL_QTY]:
            try:
                result["qty"] = int(float(col_texts[_COL_QTY].strip()))
            except (ValueError, TypeError):
                pass

        if _COL_PRICE < len(col_texts) and col_texts[_COL_PRICE]:
            price_raw = col_texts[_COL_PRICE].strip().replace(",", ".")
            try:
                result["unit_price"] = float(re.sub(r"[^\d.]", "", price_raw))
            except (ValueError, TypeError):
                pass

        return result if result.get("sku") else None
