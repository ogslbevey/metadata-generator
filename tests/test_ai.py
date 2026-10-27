import logging

import pytest

logger = logging.getLogger(__name__)

TEXT = (
    "A station to collect CTD data (Station B) was done for JHC in order to "
    "calibrate the multibeam sonar system. The MVP is being worked on and "
    "should be available within a day or two."
)

TEXT_MODELS = [
    {"provider": "openai", "model": "gpt-5.4-nano"},

    
    ]
  

# Successful extractions: these call real LLM APIs
SUCCESS_CASES = [
    # pytest.param(
    #     "metadata",
    #     {"model": TEXT_MODELS, "text": TEXT, "hash": "test_hash", "source": "test_source"},
    #     1,
    #     id="metadata-two-models",
    # ),
    # pytest.param(
    #     "eov",
    #     {"model": TEXT_MODELS, "text": TEXT, "hash": "test_hash", "source": "test_source"},
    #     1,
    #     id="eov-two-models",
    # ),
    pytest.param(
        "table",
        {
            "hash": "dd6153a13e17e6c4cf32de91c548f25a2df787806a5f29193d8a8569c17c3199",  # must already be uploaded to Redis upload the document first either from frontend or via the pytest ./test/test.py
            "pages": {"200": {"provider": "google", "model": "gemini-3.5-flash-lite"},
                    #   "201": {"provider": "google", "model": "gemini-3.5-flash-lite"}
                      },
        },
        1,
        id="table-one-page",
    ),
]


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("extraction_type, payload, expected_results", SUCCESS_CASES)
async def test_extract_success(client, extraction_type, payload, expected_results):
    response = await client.post(f"/extract/{extraction_type}", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    logger.info(body['results'])
    # logger.info("%s response: %s", extraction_type, body)

    # assert body["type"] == extraction_type
  
    # assert len(body["results"]) == expected_results
    # logger.info("Results: %s", body["results"])
    # for result in body["results"]:
    #     assert result["error"] is None, f"{result['model']} failed: {result['error']}"
    #     assert result["output"] is not None

    # if extraction_type == "table":
    #     assert "urls" in body
    #     returned_pages = {str(r["page"]) for r in body["results"]}
    #     assert returned_pages == set(payload["pages"])


