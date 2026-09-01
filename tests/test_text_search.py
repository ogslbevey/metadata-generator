import pytest
import asyncio
import logging

@pytest.mark.asyncio
async def test_extract_table(client):
     
    payload = {"document_id": "d27599cd-649c-4113-a4cd-c30aa66764c0:3b3ce98d67d4",
               "query":"La partie ouest du banc de Portneuf abrite un important banc coquillier dont la superficie s’élevait à 9,6 km2 à la fin des années 1990 (Naturam Environnement, 2001) La mye commune (Mya arenaria) y est la principale espèce. Des concentrations de myes avaient aussi signalées près de l’extrémité sud de la flèche de sable ainsi qu’au large de la pointe des Fortin. Une grande concentration de macome baltique (Macoma baltica) est aussi présente du côté nord du banc (dans la baie) et de mésodesme arctique (Mesodesma arctatum) au sud du banc et à la pointe des Fortin (Naturam Environnement, 2001). Enfin, notons que dans les marelles, les densités de gammares sont relativement élevées et qu’on note la présence de littorine rugueuse (Littorina saxatilis) dans les chenaux du marais."}
    response = await client.post(f"/search/search", json=payload)
    logging.info(f"Response status code: {response.status_code}")
    logging.info(f"Response JSON: {response.json()}")
    assert response.status_code == 200