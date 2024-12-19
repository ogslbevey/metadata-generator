# Example test file, adjust as needed
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_metadata_chain():
    response = client.post("/v1/chain_MetadataSchemaCIOOS",
                           json={"text": "test data"})
    assert response.status_code == 200


def test_eov_chain():
    response = client.post("/v1/chain_eov", json={"text": "test data"})
    assert response.status_code == 200
