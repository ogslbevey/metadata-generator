import redis.asyncio as redis
import os
import dotenv
from redis.commands.json.path import Path

dotenv.load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")



def init_redis():
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return redis_client



async def close_redis(client: redis.Redis) -> None:
    if client:
        await client.aclose()
    

async def exists_redis_key(key: str, redis_client) -> bool:
    return (await redis_client.exists(key)) > 0

async def insert_windows(client: redis.Redis, doc_id: str, blocks: list[dict], window_size: int = 2):
    for i in range(len(blocks) - window_size + 1):
        window_blocks = blocks[i:i + window_size]

        key = f"pdfwindow:{doc_id}:{window_blocks[0]['block_id']}-{window_blocks[-1]['block_id']}"
        payload = {
            "doc_id": doc_id,
            "page": window_blocks[0]["page"],
            "block_start": window_blocks[0]["block_id"],
            "block_end": window_blocks[-1]["block_id"],
            "block_ids": [str(b["block_id"]) for b in window_blocks],
            "text_raw": "\n".join(b["text"] for b in window_blocks),
            "text_norm": normalize_for_match(" ".join(b["text"] for b in window_blocks)),
        }
        await client.json().set(key, Path.root_path(), payload)

async def create_index(client: redis.Redis) -> None:
    try:
        await client.execute_command(
            "FT.CREATE", "idx:pdf",
            "ON", "JSON",
            "PREFIX", "1", "pdfblock:",
            "SCHEMA",
            "$.doc_id", "AS", "doc_id", "TAG",
            "$.page", "AS", "page", "NUMERIC",
            "$.block_id", "AS", "block_id", "TAG",
            "$.char_start", "AS", "char_start", "NUMERIC",
            "$.char_end", "AS", "char_end", "NUMERIC",
            "$.text_raw", "AS", "text_raw", "TEXT",
            "$.text_norm", "AS", "text_norm", "TEXT",
        )
    except Exception as e:
        if "Index already exists" not in str(e):
            raise



async def insert_blocks(client: redis.Redis, doc_id: str, blocks: list[dict]) -> None:
    for block in blocks:
        redis_key = f"pdfblock:{doc_id}:{block['page']}:{block['block_id']}"
        payload = {
            "doc_id": doc_id,
            "page": block["page"],
            "block_id": str(block["block_id"]),
            "char_start": block["char_start"],
            "char_end": block["char_end"],
            "text_raw": block["text"],
            "text_norm": normalize_for_match(block["text"]),
        }
        await client.json().set(redis_key, Path.root_path(), payload)

async def search(query: str, client: redis.Redis):
    norm_query = normalize_for_match(query)

    escaped = norm_query.replace("\\", "\\\\").replace('"', '\\"')
    q = f'@text_norm:("{escaped}")'

    print("QUERY:", repr(q))

    results = await client.execute_command(
        "FT.SEARCH",
        "idx:pdf",
        q,
        "DIALECT",
        2,
    )

    print(results)
    return results





  


