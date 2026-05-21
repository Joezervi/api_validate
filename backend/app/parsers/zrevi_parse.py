import pdfplumber
from app.parsers.base import BaseParser

class ZerviParser(BaseParser):

    def parse(self, pdf_path):

        products = []

        with pdfplumber.open(pdf_path) as pdf:

            for page in pdf.pages:

                tables = page.extract_tables()

                for table in tables:

                    for row in table:

                        if not row:
                            continue

                        if len(row) < 4:
                            continue

                        sku = row[0]

                        product_name = row[3]

                        if sku and product_name:

                            products.append({
                                "sku": sku.strip(),
                                "product_name": product_name.strip()
                            })

        return products
