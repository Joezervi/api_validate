class BaseParser:
    """Base class for PO PDF parsers.

    Subclasses must implement parse(), which accepts either:
      - A file path (str or PathLike)  — local disk / Docker
      - Raw bytes                       — in-memory / Vercel serverless
    """

    def parse(self, pdf_source):
        """Parse a PO PDF and return a list of product dicts.

        Parameters
        ----------
        pdf_source : str | bytes
            File path on disk, or raw PDF bytes.

        Returns
        -------
        list[dict]  — each dict has at minimum {"sku": str, "product_name": str}
        """
        raise NotImplementedError
