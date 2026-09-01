import pytest
import asyncio
import logging

@pytest.mark.asyncio
async def test_extract_table(client):
    text = """
    Rapport de caractérisation :  
    Les marais littoraux d’importance à Longue- Rive  
    © Comité ZIP de la Rive Nord de l’Estuaire (Comité ZIP RNE)  Site web : www.zipnord.qc.ca  
    Tél. : 418 296 0404  31, avenue Marquette  G4Z 1K4, Baie-Comeau, QC, Canada  Imprimé au Canada  Référence à citer :  
    """

    response = await client.post(
        "/detect/sensitive_info",
        json={"text": text} 
    )

    logging.info(f"Response status code: {response.status_code}")
    logging.info(f"Response JSON: {response.json()}")

    assert response.status_code == 200