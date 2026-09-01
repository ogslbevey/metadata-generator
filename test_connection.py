from opensearchpy import OpenSearch, helpers
import os

from dotenv import load_dotenv
from opensearchpy import AsyncOpenSearch
upper_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
print (f"Upper directory: {upper_directory}")
load_dotenv(os.path.join(upper_directory, '.env'))  # Load environment variables from





async def test_opensearch_connection():
    async with AsyncOpenSearch(
        hosts=[{"host":os.environ.get("OPENSEARCH_HOST"), "port": int(os.environ.get("OPENSEARCH_PORT"))}],
        http_auth=("admin", os.environ.get("OPENSEARCH_PASSWORD")),
        use_ssl=True,
        verify_certs=False,      # demo self-signed cert; set True + ca_certs in prod
        ssl_show_warn=False,
    ) as async_client:
        response = await async_client.info()
        print(response)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_opensearch_connection())