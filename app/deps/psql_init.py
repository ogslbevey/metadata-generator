import dotenv
import os
import asyncpg
import asyncio
from typing import Optional
import logging

dotenv.load_dotenv()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

POSTGRESQL_PASSWORD = os.getenv("POSTGRESQL_PASSWORD")
POSTGRESQL_USER = os.getenv("POSTGRESQL_USER")
POSTGRESQL_HOST = os.getenv("POSTGRESQL_HOST")
POSTGRESQL_DB = os.getenv("POSTGRESQL_DB")
POSTGRESQL_HOST_PORT = os.getenv("POSTGRESQL_PORT", "5432")
POSTGRESQL_PUBLIC_URL = os.getenv("POSTGRESQL_PUBLIC_URL")



async def init_pg_pool():
    if POSTGRESQL_PUBLIC_URL:
        logger.info("Initializing PostgreSQL pool with public URL")
        return await asyncpg.create_pool(
            dsn=POSTGRESQL_PUBLIC_URL,
            min_size=1,
            max_size=10,
        )
    else:
        logger.info("Initializing PostgreSQL pool with individual connection parameters")
        return await asyncpg.create_pool(
            user=POSTGRESQL_USER,
            password=POSTGRESQL_PASSWORD,
            host=POSTGRESQL_HOST,
            port=POSTGRESQL_HOST_PORT,
            database=POSTGRESQL_DB,
            min_size=1,
            max_size=10,
        )
    

async def close_pg_pool(pool: Optional[asyncpg.Pool]) -> None:
    if pool:
        await pool.close()