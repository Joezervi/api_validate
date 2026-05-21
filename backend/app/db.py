import asyncpg
from urllib.parse import urlparse, parse_qs
from app.config import DATABASE_URL


_pool = None


def _parse_dsn(url):
    """Parse DATABASE_URL and extract ssl mode for asyncpg."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    # asyncpg doesn't read sslmode from the URL query string.
    # Strip it so we can pass it as a keyword argument instead.
    sslmode = None
    if "sslmode" in query:
        sslmode = query["sslmode"][0]

    # Rebuild the DSN without the query string (or keep only supported params)
    clean_url = parsed._replace(query="").geturl()

    return clean_url, sslmode


async def get_pool():
    global _pool

    if _pool is None:
        dsn, sslmode = _parse_dsn(DATABASE_URL)

        ssl_kwarg = None
        if sslmode in ("require", "prefer", "verify-ca", "verify-full"):
            # asyncpg uses True for "require" and a context for stricter modes
            ssl_kwarg = True if sslmode == "require" else sslmode

        _pool = await asyncpg.create_pool(
            dsn,
            min_size=1,
            max_size=20,
            ssl=ssl_kwarg,
        )

    return _pool
