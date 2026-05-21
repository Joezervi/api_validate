Customer uploads PO PDF
        ↓
FastAPI upload endpoint
        ↓
Celery background worker
        ↓
Customer-specific parser
        ↓
Insert staging data
        ↓
Validate SKU
        ↓
Create draft products
        ↓
Create approval queue
        ↓
Generate Excel report
        ↓
Frontend polls task result
        ↓
Download Excel