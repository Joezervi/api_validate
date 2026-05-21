import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:evNwZ4OBJYDO8t-9VHqHr@zervi-pgvector-u34072.vm.elestio.app/odoo_api?sslmode=require"
)

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0"
)
