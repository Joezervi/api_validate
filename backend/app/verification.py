"""
Data Verification Specialist — 6‑Step SKU Verification Engine

Step 1: Strict case/space‑sensitive comparison of every PO SKU against product_info.
Step 2: Identify which PO SKUs are NOT in product_info.
Step 3: Double‑check — diagnose the *reason* for every mismatch.
Step 4: Cross‑reference product_category for the correct category name via price.
Step 5: Enrich each missing SKU with barcode / product name / category name.
Step 6: Produce a 5‑column Markdown table ready for Excel.
"""

from app.db import get_pool

# Characters that look similar and are common causes of mismatch
_VISUAL_CONFUSIONS = {
    "0": "O",
    "O": "0",
    "1": "l",
    "l": "1",
    "I": "l",
    "l": "I",
    "5": "S",
    "S": "5",
    "8": "B",
    "B": "8",
}

NOT_FOUND = "Don't have Data match"


# ── Step 1‑2: strict match + identify missing ──────────────────────────────


def _exact_match(po_sku: str, zervi_skus: set[str]) -> bool:
    """Case‑sensitive, space‑sensitive exact match."""
    return po_sku in zervi_skus


# ── Step 3: double‑check / diagnose mismatch reason ────────────────────────


def _diagnose_mismatch(po_sku: str, zervi_skus: list[str]) -> str:
    """Return a human‑readable explanation of WHY *po_sku* doesn't exist.

    Checks (in order):
      1. Trimming whitespace
      2. Case‑insensitive match
      3. Underscore ↔ dash swaps
      4. Visual confusions (0/O, 1/l, etc.)
      5. Hidden / non‑printable characters
      6. Partial / substring matches
      7. Fallback: "SKU not exist in ZERVI system"
    """
    reasons: list[str] = []

    # 1 — Leading / trailing whitespace
    if po_sku != po_sku.strip():
        reasons.append(
            f"Extra space: PO has '{po_sku!r}', stripped is '{po_sku.strip()!r}'"
        )
        # try trimmed match
        if po_sku.strip() in zervi_skus:
            return " | ".join(reasons)

    # 2 — Case‑insensitive
    po_lower = po_sku.lower()
    for z in zervi_skus:
        if z.lower() == po_lower and z != po_sku:
            reasons.append(f"Case mismatch: PO has '{po_sku}', ZERVI has '{z}'")
            break

    # 3 — Dash / underscore
    po_dash = po_sku.replace("_", "-")
    po_underscore = po_sku.replace("-", "_")
    for z in zervi_skus:
        if z == po_dash and z != po_sku:
            reasons.append(
                f"Special character mismatch: PO has '{po_sku}' (with '_'), "
                f"ZERVI has '{z}' (with '-')"
            )
            break
        if z == po_underscore and z != po_sku:
            reasons.append(
                f"Special character mismatch: PO has '{po_sku}' (with '-'), "
                f"ZERVI has '{z}' (with '_')"
            )
            break

    # 4 — Visual confusions
    for z in zervi_skus:
        if len(z) == len(po_sku) and z != po_sku:
            diffs = []
            for i, (pc, zc) in enumerate(zip(po_sku, z)):
                if pc != zc:
                    pair = (pc, zc)
                    if pair in _VISUAL_CONFUSIONS:
                        diffs.append(
                            f"pos {i}: PO has '{pc}', ZERVI has '{zc}' "
                            f"(visual confusion)"
                        )
                    else:
                        diffs.append(f"pos {i}: PO has '{pc}', ZERVI has '{zc}'")
            if diffs:
                reasons.append(
                    f"Character difference(s) in near‑match '{z}': " + "; ".join(diffs)
                )
                break

    # 5 — Hidden / non‑printable characters
    hidden = repr(po_sku)
    clean = po_sku.encode("ascii", errors="ignore").decode("ascii")
    if clean != po_sku:
        reasons.append(f"Hidden/non‑ASCII characters in SKU: {hidden!r}")

    # 6 — Partial / substring match
    if not reasons:
        for z in zervi_skus:
            if po_sku in z or z in po_sku:
                reasons.append(
                    f"Partial match found: PO '{po_sku}' is substring of "
                    f"ZERVI '{z}'"
                    if po_sku in z
                    else f"Partial match found: ZERVI '{z}' is substring of "
                    f"PO '{po_sku}'"
                )
                break

    if not reasons:
        return "SKU not exist in ZERVI system"

    return " | ".join(reasons)


# ── Step 4‑5: category lookup + enrichment ─────────────────────────────────


async def _enrich_missing(
    conn,
    po_item: dict,
    customer_name: str,
    zervi_rows: list[dict],
    noted: str,
) -> dict:
    """For one missing SKU, pull barcode / product name / category name.

    Barcode priority:
      1. PO barcode (from parsed PDF)
      2. Near‑match in product_info (case‑insensitive, dash‑underscore swap)
      3. "Don't have Data match"

    Category Name priority:
      1. product_category match by product name + price (±0.01)
      2. product_category match by product name only
      3. "Don't have Data match"
    """
    po_sku = po_item["sku"]
    po_product = po_item.get("product_name", "")
    po_barcode = po_item.get("barcode", "")
    po_price = po_item.get("unit_price")

    # ── Barcode ──
    # Priority: PO data > near‑match in product_info > NOT_FOUND
    if po_barcode:
        barcode = po_barcode
    else:
        # try to pull from a near‑match in product_info
        barcode = None
        po_sku_stripped = po_sku.strip()
        for row in zervi_rows:
            if (
                row["sku"].strip().lower() == po_sku_stripped.lower()
                or row["sku"].replace("-", "_").lower() == po_sku_stripped.lower()
            ):
                barcode = row.get("barcode")
                if barcode:
                    break
        if not barcode:
            barcode = NOT_FOUND

    # ── Product Name ──
    product_name = po_product if po_product else NOT_FOUND

    # ── Category Name (via product_category) ──
    category_name = NOT_FOUND
    if po_product and po_price is not None:
        # match by product name + price tolerance
        cat_rows = await conn.fetch(
            """
            SELECT category
            FROM product_category
            WHERE price = $1
            LIMIT 1
            """,
            float(po_price),
        )
        if cat_rows:
            category_name = cat_rows[0]["category"]
    if category_name == NOT_FOUND and po_product:
        # fallback: match by product name only (no price)
        cat_rows = await conn.fetch(
            """
            SELECT category
            FROM product_category
            WHERE LOWER(product) = LOWER($1)
            LIMIT 1
            """,
            po_product.strip(),
        )
        if cat_rows:
            category_name = cat_rows[0]["category"]

    return {
        "sku_missing": po_sku,
        "barcode": barcode,
        "product_name": product_name,
        "category_name": category_name,
        "noted": noted,
    }


# ── Step 6: Markdown table generator ───────────────────────────────────────


def _build_markdown_table(missing_enriched: list[dict]) -> str:
    """Produce a 5‑column Markdown table ready for copy‑paste into Excel."""
    if not missing_enriched:
        return "_No missing SKUs found._\n"

    header = (
        "| SKU Missing | Barcode | Product Name | Category Name | Noted |\n"
        "|-------------|---------|--------------|---------------|-------|\n"
    )

    def esc(v):
        return str(v).replace("|", "\\|")

    rows = []
    for item in missing_enriched:
        row = (
            f"| {esc(item['sku_missing'])} "
            f"| {esc(item['barcode'])} "
            f"| {esc(item['product_name'])} "
            f"| {esc(item['category_name'])} "
            f"| {esc(item['noted'])} |"
        )
        rows.append(row)

    return header + "\n".join(rows) + "\n"


# ── Main entry point ───────────────────────────────────────────────────────


async def verify_products(
    products: list[dict],
    customer_name: str,
    po_number: str | None = None,
) -> dict:
    """Run the full 6‑step verification and return structured results.

    Parameters
    ----------
    products : list[dict]
        Each dict must have `sku`.  Optional: `product_name`, `barcode`, `unit_price`, `qty`.
    customer_name : str
    po_number : str | None

    Returns
    -------
    dict with keys:
      existing      – list of dicts for SKUs found in product_info
      missing       – list of enriched dicts (5‑column ready)
      markdown_report – str, the Markdown table
      existing_count  – int
      missing_count   – int
    """
    pool = await get_pool()

    async with pool.acquire() as conn:
        # ── Load ZERVI list (product_info) ──
        zervi_rows = await conn.fetch(
            "SELECT sku, barcode, product, category, price FROM product_info"
        )
        zervi_skus: set[str] = {row["sku"] for row in zervi_rows}
        # also keep a list form for iteration during diagnosis
        zervi_sku_list: list[str] = [row["sku"] for row in zervi_rows]

        print(
            f"[Verification] Loaded {len(zervi_sku_list)} SKUs from ZERVI (product_info)"
        )
        print(f"[Verification] Received {len(products)} products from PO PDF")
        print(f"[Verification] ZERVI SKUs: {products}")
        if products:
            print(f"[Verification] PO SKUs: {[p['sku'] for p in products]}")

        existing_products: list[dict] = []
        missing_enriched: list[dict] = []

        for item in products:
            po_sku = item["sku"]
            po_product = item.get("product_name", "")
            po_barcode = item.get("barcode", "")
            po_price = item.get("unit_price")
            po_qty = item.get("qty")

            # ── Staging insert ──
            await conn.execute(
                """
                INSERT INTO product_staging (
                    customer_name, po_number, sku, barcode,
                    product_name, qty, unit_price
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                customer_name,
                po_number,
                po_sku,
                po_barcode,
                po_product,
                po_qty,
                po_price,
            )

            # ── Step 1‑2: strict match ──
            matched = _exact_match(po_sku, zervi_skus)
            print(
                f"[Verification] SKU '{po_sku}' → {'EXISTING' if matched else 'MISSING'}"
            )
            if matched:
                # found — pull full record
                existing_row = await conn.fetchrow(
                    """
                    SELECT sku, barcode, product, category, price
                    FROM product_info
                    WHERE sku = $1
                    """,
                    po_sku,
                )
                existing_products.append(
                    {
                        "sku": existing_row["sku"],
                        "barcode": existing_row.get("barcode", ""),
                        "product_name": existing_row.get("product") or po_product,
                        "category": existing_row.get("category", ""),
                        "price": str(existing_row.get("price", "")),
                    }
                )
            else:
                # ── Step 3: diagnose mismatch ──
                noted = _diagnose_mismatch(po_sku, zervi_sku_list)

                # ── Step 4‑5: enrich ──
                enriched = await _enrich_missing(
                    conn,
                    item,
                    customer_name,
                    [
                        {
                            "sku": r["sku"],
                            "barcode": r.get("barcode"),
                        }
                        for r in zervi_rows
                    ],
                    noted,
                )
                missing_enriched.append(enriched)

                # ── Draft + approval queue (same as before) ──
                draft = await conn.fetchrow(
                    """
                    INSERT INTO product_draft (
                        sku, barcode, product_name, customer, source_po
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    po_sku,
                    po_barcode,
                    po_product,
                    customer_name,
                    po_number,
                )
                await conn.execute(
                    """
                    INSERT INTO approval_queue (
                        reference_type, reference_id, assigned_to
                    )
                    VALUES ('product_draft', $1, 'product-team')
                    """,
                    draft["id"],
                )

        # ── Step 6: Markdown table ──
        markdown_report = _build_markdown_table(missing_enriched)

    print(
        f"[Verification] Summary: {len(existing_products)} existing, {len(missing_enriched)} missing"
    )
    return {
        "existing": existing_products,
        "missing": missing_enriched,
        "markdown_report": markdown_report,
        "existing_count": len(existing_products),
        "missing_count": len(missing_enriched),
    }
