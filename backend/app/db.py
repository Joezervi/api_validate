import asyncpg
from app.config import DATABASE_URL

pool = None

async def get_pool():

    global pool

    if pool is None:

        pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=20
        )

    return pool
