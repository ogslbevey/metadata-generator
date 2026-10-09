import tiktoken
from anthropic import AsyncAnthropic
from app.schema.payload import ModelParameters
import logging
import hashlib
import asyncio
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
_prompt_token_cache: dict[tuple[str, str, str], int] = {}
_prompt_token_locks: dict[tuple[str, str, str], asyncio.Lock] = {}

anthropic_client = AsyncAnthropic()  # Use the environment variable ANTHROPIC_API_KEY


def count_openai_tokens(text: str, model: str) -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:                          # newer models tiktoken doesn't know yet
        enc = tiktoken.get_encoding("o200k_base")
    return len(enc.encode(text))


async def count_anthropic_tokens(system: str, model: str) -> int:
    # The API needs at least one message; "." adds only a couple of tokens
    r = await anthropic_client.messages.count_tokens(
        model=model, system=system, messages=[{"role": "user", "content": "."}]
    )
    return r.input_tokens



async def system_prompt_tokens(params: ModelParameters, prompt: str) -> int | None:
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
    key = (params.provider, params.model, prompt_hash)

    if key in _prompt_token_cache:                       # fast path, no lock
        return _prompt_token_cache[key]

    lock = _prompt_token_locks.setdefault(key, asyncio.Lock())
    async with lock:
        if key not in _prompt_token_cache:               # another request may have filled it
            try:
                if params.provider == "openai":
                    _prompt_token_cache[key] = count_openai_tokens(prompt, params.model)
                elif params.provider == "anthropic":
                    _prompt_token_cache[key] = await count_anthropic_tokens(prompt, params.model)
            except Exception as e:
                logger.warning("Token count failed for %s/%s: %r", params.provider, params.model, e)
                return None
    return _prompt_token_cache.get(key)