# PO Checker Flow (Implemented)

1. **Customer uploads PO PDF** - Frontend uses `/upload-po` FastAPI endpoint (POST)
3. **Parse customer PO** - worker uses customer-specific parser (currently only 'zervi')
4. **Extract SKU rows** - Parser extracts SKU and product name from PDF
5. **Insert staging data** - Each row inserted into `product_staging` table
6. **Validate against ERP product table** - Check if SKU exists in `product_info`
7. **Create missing product drafts** - If SKU missing, insert into `product_draft`
8. **Create approval tasks** - Add to `approval_queue` for product team
9. **Generate Excel report** - task creates Excel with 'Existing SKU' and 'Missing SKU' sheets
10. **Frontend polls task result** - Frontend calls `/task/{task_id}` to check status
11. **Return result** - When done, backend returns Excel filename
12. **Preview in React UI** - Frontend displays existing/missing SKUs (if returned)
13. **Download Excel** - Frontend calls `/download/{filename}` to get Excel report

## Endpoints

- `POST /upload-po` — Upload PDF, returns `task_id`
- `GET /task/{task_id}` — Poll task status/result
- `GET /download/{filename}` — Download Excel report

## Background Processing
- Postgres for all data storage

## Notes

- Only 'zervi' parser is implemented (see backend/app/parsers/zrevi_parse.py)
- Frontend expects Excel file and lists of existing/missing SKUs
- All services orchestrated via docker-compose

```
DATABASE

CREATE TABLE product_info (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(100) UNIQUE,
    barcode VARCHAR(20) UNIQUE,
    product VARCHAR(255),
    category VARCHAR(100),
    customer VARCHAR(100),
    price NUMERIC,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE product_category (
    id SERIAL PRIMARY KEY,
    product VARCHAR(255),
    category VARCHAR(100),
    customer VARCHAR(100),
    price NUMERIC,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE product_staging (
    id SERIAL PRIMARY KEY,

    customer_name VARCHAR(100),

    po_number VARCHAR(100),

    sku VARCHAR(100),

    product_name TEXT,

    qty INTEGER,

    unit_price NUMERIC,

    status VARCHAR(50) DEFAULT 'pending',

    uploaded_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE product_draft (

    id SERIAL PRIMARY KEY,

    sku VARCHAR(100),

    product_name TEXT,

    category VARCHAR(100),

    customer VARCHAR(100),

    source_po VARCHAR(100),

    approval_status VARCHAR(50)
        DEFAULT 'waiting_approval',

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE approval_queue (

    id SERIAL PRIMARY KEY,

    reference_type VARCHAR(50),

    reference_id INTEGER,

    assigned_to VARCHAR(100),

    status VARCHAR(50) DEFAULT 'pending',

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE customer_parser_rules (
    id SERIAL PRIMARY KEY,
    customer_name VARCHAR(100),
    sku_column INTEGER,
    product_column INTEGER,
    qty_column INTEGER,
    price_column INTEGER
);

```
