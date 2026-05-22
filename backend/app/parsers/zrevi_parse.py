import re

import pdfplumber
from app.parsers.base import BaseParser

# Values in column 0 that indicate a header row
_HEADER_KEYWORDS = {"sku", "code", "item", "product", "barcode", "description"}

# Column indices for Zervi PO format (8 columns)
_COL_SKU = 0
_COL_BARCODE = 1
_COL_SUPPLIER = 2
_COL_PRODUCT = 3
_COL_JOBNO = 4
_COL_QTY = 5
_COL_PRICE = 6
_COL_SUBTOTAL = 7


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
        """Extract products from all pages — hybrid table + word approach.

        Each page is processed independently: table extraction is tried
        first; if it produces zero data rows, the page falls back to
        word-position extraction.  Column ranges from the first page's
        word detection are cached and reused for continuation pages that
        lack a header row.
        """
        all_products = []
        cached_col_ranges = None

        with pdfplumber.open(pdf_source) as pdf:
            pages = list(pdf.pages)
            for page_num, page in enumerate(pages, start=1):
                # Try table extraction for this page
                page_products = self._parse_page_via_tables(page, page_num)

                if not page_products:
                    # Fall back to word-based for this page
                    page_products = self._parse_page_via_words(
                        page, page_num, cached_col_ranges
                    )

                all_products.extend(page_products)
                # Cache column ranges from the first word-extracted page
                if page_products and cached_col_ranges is None and hasattr(self, '_last_word_col_ranges'):
                    cached_col_ranges = self._last_word_col_ranges

        print(
            f"[ZerviParser] Total: {len(all_products)} products "
            f"across {len(pages)} pages"
        )
        return all_products

    # ── Per-page table extraction ──────────────────────────────────────

    def _parse_page_via_tables(self, page, page_num):
        """Extract products from a SINGLE page using table extraction."""
        products = []
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

            if not has_data and len(table) > 1:
                print(
                    f"[ZerviParser] Page {page_num}: table had {len(table)} rows "
                    f"but zero data rows (all cells empty)"
                )

        if products:
            print(f"[ZerviParser] Page {page_num}: table → {len(products)} products")
        return products

    # ── Per-page word-position extraction ──────────────────────────────

    def _parse_page_via_words(self, page, page_num, cached_col_ranges=None):
        """Extract products from a SINGLE page using word-position extraction.

        If the page has no header (continuation of a multi-page table),
        ``cached_col_ranges`` from a previous page are reused.
        """
        products = []
        words = page.extract_words(
            keep_blank_chars=True,
            use_text_flow=True,
        )
        if not words:
            return products

        lines = self._group_words_into_lines(words, y_tolerance=5)
        if len(lines) < 2:
            return products

        header_line, data_lines = self._split_header_data(lines)

        # Reuse cached column ranges for continuation pages (no header)
        if data_lines and header_line is None and cached_col_ranges:
            col_ranges = cached_col_ranges
        elif header_line is not None:
            col_ranges = self._build_column_ranges_from_header(header_line)
        else:
            return products

        if len(col_ranges) < 4:
            return products

        # Cache for continuation pages
        self._last_word_col_ranges = col_ranges

        # If this page has a header, skip it; otherwise all lines are data
        if header_line is None and cached_col_ranges:
            data_lines = lines  # all lines are data — no header on this page

        print(
            f"[ZerviParser] Page {page_num}: detected {len(col_ranges)} columns, "
            f"{len(data_lines)} data lines"
        )

        for line_words in data_lines:
            row = self._words_to_columns(line_words, col_ranges)
            if not row:
                continue

            sku = row.get("sku", "")
            product_name = row.get("product_name", "")
            if not sku or not product_name:
                continue

            item = {"sku": sku, "product_name": product_name}
            for key in (
                "barcode", "supplier_code", "job_no",
                "qty", "unit_price", "subtotal",
            ):
                if row.get(key) not in (None, ""):
                    item[key] = row[key]

            products.append(item)

        if products:
            print(f"[ZerviParser] Page {page_num}: words → {len(products)} products")
        return products

    # ── Helpers ────────────────────────────────────────────────────────

    def _build_item(self, row, sku, product_name):
        """Build a product dict from a table row with all 8 columns."""
        item = {"sku": sku, "product_name": product_name}

        print(
            f"[ZerviParser] Processing row: {row} → SKU: {sku}, Product: {product_name}"
        )
        # Barcode (col 1)
        if len(row) > _COL_BARCODE and row[_COL_BARCODE]:
            val = str(row[_COL_BARCODE]).strip()
            if val and val.lower() != "none":
                item["barcode"] = val

        # Supplier Code (col 2)
        if len(row) > _COL_SUPPLIER and row[_COL_SUPPLIER]:
            val = str(row[_COL_SUPPLIER]).strip()
            if val and val.lower() != "none":
                item["supplier_code"] = val

        # Job No. (col 4)
        if len(row) > _COL_JOBNO and row[_COL_JOBNO]:
            val = str(row[_COL_JOBNO]).strip()
            if val and val.lower() != "none":
                item["job_no"] = val

        # Qty (col 5)
        if len(row) > _COL_QTY and row[_COL_QTY]:
            try:
                item["qty"] = int(float(str(row[_COL_QTY]).strip()))
            except (ValueError, TypeError):
                pass

        # Unit Price (col 6)
        if len(row) > _COL_PRICE and row[_COL_PRICE]:
            price_raw = str(row[_COL_PRICE]).strip().replace(",", ".")
            try:
                item["unit_price"] = float(re.sub(r"[^\d.]", "", price_raw))
            except (ValueError, TypeError):
                pass

        # Subtotal (col 7)
        if len(row) > _COL_SUBTOTAL and row[_COL_SUBTOTAL]:
            subtotal_raw = str(row[_COL_SUBTOTAL]).strip().replace(",", ".")
            try:
                item["subtotal"] = float(re.sub(r"[^\d.]", "", subtotal_raw))
            except (ValueError, TypeError):
                pass

        return item

    @staticmethod
    def _group_words_into_lines(words, y_tolerance=5):
        """Group word dicts into lines by proximity of Y (top) coordinate."""
        if not words:
            return []

        sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
        lines = []
        current_line = [sorted_words[0]]
        current_y = sorted_words[0]["top"]

        for w in sorted_words[1:]:
            if abs(w["top"] - current_y) <= y_tolerance:
                current_line.append(w)
            else:
                current_line.sort(key=lambda w: w["x0"])
                lines.append(current_line)
                current_line = [w]
                current_y = w["top"]

        current_line.sort(key=lambda w: w["x0"])
        lines.append(current_line)
        return lines

    @staticmethod
    def _split_header_data(lines):
        """Identify the header line and split from data."""
        header_terms = {
            "sku",
            "product",
            "barcode",
            "item",
            "description",
            "qty",
            "price",
            "supplier",
            "job",
            "subtotal",
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

        return lines[header_idx], lines[header_idx + 1 :]

    # Known column names in order — the FIRST word of each column header
    _COLUMN_NAMES = [
        "sku",          # col 0
        "barcode",      # col 1
        "supplier",     # col 2  (full: "Supplier Code")
        "product",      # col 3  (full: "Product Name")
        "job",          # col 4  (full: "Job No.")
        "qty",          # col 5
        "unit",         # col 6  (full: "Unit Price")
        "subtotal",     # col 7
    ]

    @staticmethod
    def _build_column_ranges_from_header(header_line):
        """Build exact 8-column boundaries by matching header words to known names.

        Each header word is matched against _COLUMN_NAMES.  The X0 of the
        matched word becomes the LEFT boundary.  The RIGHT boundary is the
        X0 of the next column (or +200 for the last).  Missing columns are
        interpolated/extrapolated from neighbors.
        """
        if not header_line:
            return []

        header_words = [
            (float(w["x0"]), w["text"].strip().lower())
            for w in header_line
        ]

        col_x0 = [None] * len(ZerviParser._COLUMN_NAMES)
        word_idx = 0
        for col_idx, col_name in enumerate(ZerviParser._COLUMN_NAMES):
            while word_idx < len(header_words):
                _, text = header_words[word_idx]
                if text == col_name or text.startswith(col_name):
                    col_x0[col_idx] = header_words[word_idx][0]
                    word_idx += 1
                    break
                word_idx += 1

        # Fill gaps by interpolation
        last_x0, last_col = None, 0
        for i in range(len(col_x0)):
            if col_x0[i] is not None:
                last_x0 = col_x0[i]
                last_col = i
            elif last_x0 is not None:
                next_x0, next_col = None, len(col_x0)
                for j in range(i + 1, len(col_x0)):
                    if col_x0[j] is not None:
                        next_x0 = col_x0[j]
                        next_col = j
                        break
                if next_x0 is not None:
                    span = next_x0 - last_x0
                    steps = next_col - last_col
                    col_x0[i] = last_x0 + span * (i - last_col) / steps
                else:
                    col_x0[i] = last_x0 + 80 * (i - last_col)

        ranges = []
        for i in range(len(col_x0)):
            x0 = col_x0[i] if col_x0[i] is not None else (50 + i * 80)
            x1 = (
                col_x0[i + 1] if i + 1 < len(col_x0) and col_x0[i + 1] is not None
                else x0 + 200
            )
            ranges.append({"x0": x0, "x1": x1})

        print(
            f"[ZerviParser] Header-anchored column ranges ({len(ranges)} cols): "
            + ", ".join(f"{r['x0']:.0f}-{r['x1']:.0f}" for r in ranges)
        )
        return ranges

    @staticmethod
    def _words_to_columns(line_words, col_ranges):
        """Assign words from a data line to columns by X-coordinate.

        Returns a dict with all 8 column keys, or None if no SKU.
        """
        if not line_words:
            return None

        col_texts = ["" for _ in col_ranges]
        unassigned = []
        for w in line_words:
            x_center = (float(w["x0"]) + float(w["x1"])) / 2.0
            assigned = False
            for idx, cr in enumerate(col_ranges):
                if cr["x0"] <= x_center < cr["x1"]:
                    col_texts[idx] = (
                        col_texts[idx] + " " + w["text"]
                        if col_texts[idx]
                        else w["text"]
                    )
                    assigned = True
                    break
            if not assigned:
                unassigned.append(w["text"])

        if unassigned:
            print(f"[ZerviParser] Unassigned words: {unassigned}")

        result = {}

        def _get(idx):
            return col_texts[idx].strip() if idx < len(col_texts) else ""

        # SKU
        if _get(_COL_SKU):
            result["sku"] = _get(_COL_SKU)

        # Barcode
        b = _get(_COL_BARCODE)
        if b and re.match(r"^[\dA-Za-z\-\s]{5,}$", b):
            result["barcode"] = b

        # Supplier Code
        if _get(_COL_SUPPLIER):
            result["supplier_code"] = _get(_COL_SUPPLIER)

        # Product Name
        if _get(_COL_PRODUCT):
            result["product_name"] = _get(_COL_PRODUCT)

        # Job No.
        if _get(_COL_JOBNO):
            result["job_no"] = _get(_COL_JOBNO)

        # Qty
        qty_raw = _get(_COL_QTY)
        if qty_raw:
            try:
                result["qty"] = int(float(qty_raw))
            except (ValueError, TypeError):
                pass

        # Unit Price
        price_raw = _get(_COL_PRICE)
        if price_raw:
            try:
                result["unit_price"] = float(
                    re.sub(r"[^\d.]", "", price_raw.replace(",", "."))
                )
            except (ValueError, TypeError):
                pass

        # Subtotal
        subtotal_raw = _get(_COL_SUBTOTAL)
        if subtotal_raw:
            try:
                result["subtotal"] = float(
                    re.sub(r"[^\d.]", "", subtotal_raw.replace(",", "."))
                )
            except (ValueError, TypeError):
                pass

        return result if result.get("sku") else None
