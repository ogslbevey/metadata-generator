import pytest
import asyncio
import logging

@pytest.mark.asyncio
async def test_extract_table(client):
    session_id = "test-session-123"  # Replace with an actual session ID for testing
    payload={"data":[
        {
            "id": 1,
            "caption": "Table 1",
            "page_number": 1,
            "table": [
            [
              "",
              "Taux de déplacement annuel (m/an) \nSecteur de lapointeà Boisvert",
              None,
              None,
              None,
              ""
            ],
            [
              "Station",
              "1964-\n2019",
              "1964-\n1982",
              "1982-\n1996",
              "1996-\n2012",
              "2012-\n2019"
            ],
         ]
        },
        {
         "id":2,
        "caption": "Table 1",
        "page_number": 1,
        "table":[
           [
            "115",
            "-0,19",
            "-1,08",
            "-1,14",
            "-1,42",
            "6,38"
          ]
        ]

        },
        {
         "id":3,
        "caption": "Table 3",
        "page_number": 1,
        "table":[
           ["115",
             "NA",
             "NA",
             "NA",
           ]]
        }
    ],
    "model": {
        "model_name": "gpt-4.1",
        "temperature": 0.1
    
    }
    }
    response = await client.post(f"/extract/table/{session_id}", json=payload)
    logging.info(f"Response status code: {response.status_code}")
    logging.info(f"Response JSON: {response.json()}")
    assert response.status_code == 200