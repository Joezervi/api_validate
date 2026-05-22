"""
Product checker — delegates to the 6‑step Data Verification Specialist.
"""

from app.verification import verify_products


async def process_products(products, customer_name, po_number=None):
    """Run full SKU verification: existing match, missing enrich, Markdown report."""
    result = await verify_products(products, customer_name, po_number)
    return result
