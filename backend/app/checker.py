from app.db import get_pool


async def process_products(products, customer_name):

    pool = await get_pool()

    existing_products = []
    missing_products = []

    async with pool.acquire() as conn:

        for item in products:
            sku = item["sku"]
            product_name = item["product_name"]
            # staging
            await conn.execute(
                """
                INSERT INTO product_staging (
                    customer_name,
                    sku,
                    product_name
                )
                VALUES ($1, $2, $3)
                """,
                customer_name,
                sku,
                product_name,
            )
            existing = await conn.fetchrow(
                """
                SELECT *
                FROM product_info
                WHERE sku = $1
                """,
                sku,
            )

            if existing:
                # Add all fields for frontend/Excel
                existing_products.append(
                    {
                        "sku": existing["sku"],
                        "product_name": existing.get("product") or product_name,
                        "category": existing.get("category", ""),
                        "price": existing.get("price", ""),
                    }
                )
            else:
                missing_products.append(
                    {
                        "sku": sku,
                        "product_name": product_name,
                        "category": "",
                        "price": "",
                    }
                )
                # draft
                draft = await conn.fetchrow(
                    """
                    INSERT INTO product_draft (
                        sku,
                        product_name,
                        customer
                    )
                    VALUES ($1, $2, $3)
                    RETURNING id
                    """,
                    sku,
                    product_name,
                    customer_name,
                )
                # approval queue
                await conn.execute(
                    """
                    INSERT INTO approval_queue (
                        reference_type,
                        reference_id,
                        assigned_to
                    )
                    VALUES (
                        'product_draft',
                        $1,
                        'product-team'
                    )
                    """,
                    draft["id"],
                )

    return {"existing": existing_products, "missing": missing_products}
