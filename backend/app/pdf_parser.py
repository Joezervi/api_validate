import pdfplumber
import re

def extract_products(pdf_path):

    products = []

    with pdfplumber.open(pdf_path) as pdf:

        for page in pdf.pages:

            tables = page.extract_tables()

            for table in tables:

                for row in table:

                    if not row:
                        continue

                    row_text = " ".join([str(cell) for cell in row if cell])

                    # Extract SKU
                    match = re.search(r'([A-Z0-9\-]{3,})', row_text)

                    if match:

                        sku = match.group(1)

                        products.append({
                            "sku": sku,
                            "row": row_text
                        })

    return products
