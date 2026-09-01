import pytest
import asyncio
import logging
from app.utils.mlflow_utils import get_traces_by_run_id
from app.api.search import search
logger = logging.getLogger(__name__)

data=[{'liste_eov': [{'eov': 
'Abondance et distribution de tortues, oiseaux et mammifères marins', 
'raison': "Le rapport fournit une liste détaillée et des observations précises sur la présence, la diversité et l'abondance d'oiseaux aquatiques et de mammifères marins (Phoque commun) dans la baie de Mille-Vaches et les marais de Pointe-au-Boisvert et Le Goulet. Il mentionne explicitement le nombre d'espèces recensées, des effectifs pour certaines espèces, des observations de colonies, ainsi que la présence d'espèces menacées ou vulnérables. Ces informations dépassent le simple contexte et constituent le cœur du rapport, avec des données quantitatives et qualitatives sur la faune avienne et les mammifères marins.", 'citation': [{'citation_texte': ['Au total, plus de 226 espèces ont été recensées dans le secteur (CIMS, comm. pers.).', 'Une trentaine de Bernaches du Canada et une quinzaine d’Oies blanches estivantes ont déjà été observées, fait exceptionnel semblant toutefois se répéter au cours des dernières années (Naturam Environnement 1998; (CIMS), comm. pers.).', 'À l’été 1999, plus de 200 jeunes eiders et quelques adultes ont pu être aperçus le long du rivage de Pointe-au-Boisvert.', 'Simard (1999) rapporte la présence de 46 de ces phoques dans ce secteur lors des inventaires aériens réalisés entre 1995 et 1997.', 'Dans le secteur entourant le marais, se retrouvent enfin 4 espèces susceptibles d’être désignées menacées ou vulnérables (Beaulieu 1992).']}], 'confiance': 'très élevé'}, {'eov': 'Abondance et diversité de poissons', 'raison': "Le texte mentionne explicitement la présence d'une frayère à capelan et la reproduction de l’Épinoche à trois épines en grand nombre, avec des observations de concentrations de larves. Ces informations sont précises et concernent la présence et la reproduction de poissons, ce qui correspond à l’EOV sur l’abondance et la diversité de poissons.", 'citation': [{'citation_texte': ['Outre la frayère à capelan située tout au long de la plage de Pointe-au-Boisvert (Génivar s.d.), le secteur marin est composé d’abondantes ressources biologiques, particulièrement au niveau des invertébrés.', 'Les Épinoches à trois épines, les gammares et d’autres petits invertébrés aquatiques s’y retrouvent en grand nombre.', 'L’Épinoche à trois épines y fraie en grand nombre, comme le démontre la concentration impressionnante de larves retrouvées dans ce canal à l’été 1999.']}], 'confiance': 'élevé'}, {'eov': 'Abondance et distribution des invertébrés', 'raison': 'Le rapport indique la présence de plus de 26 espèces d’invertébrés colonisant l’estran de la batture, ainsi que des communautés importantes de Macomes balthiques et Myes communes (clams). Il mentionne aussi la cueillette de mollusques (myes) et la présence de gammares et autres invertébrés aquatiques en grand nombre. Ces éléments constituent des données sur l’abondance et la diversité des invertébrés.', 'citation': [{'citation_texte': ['Plus de 26 espèces coloniseraient l’estran de la batture (Université Laval comm. pers.; Comité ZIP de la rive nord de l’estuaire, comm. pers.).', 'On retrouve notamment d’importantes communautés à Macomes balthiques et Myes communes (clams) (Naturam Environnement 1998; Génivar s.d.; BIOREX 1996).', 'Les Épinoches à trois épines, les gammares et d’autres petits invertébrés aquatiques s’y retrouvent en grand nombre.']}], 'confiance': 'élevé'}, {'eov': 'Composition et couverture des herbiers marins', 'raison': 'Le texte fournit des données quantitatives sur la superficie des marais salés et des herbaçaies salées, ainsi que sur la composition floristique (espèces dominantes et associées). Il mentionne également la présence d’un herbier discontinu de Zostères marines utilisé par les Bernaches cravants. Ces informations détaillées sur la composition et la couverture des herbiers marins justifient l’identification de cet EOV.', 'citation': [{'citation_texte': ['Les marais salés présents dans le secteur de la baie de Mille-Vaches (figure 3.1) occupent une superficie de plus de 288 ha au total, dont 184 ha d’herbaçaie salée et 104 ha de marais à spartine alterniflore (Dryade, 1980).', 'Selon l’inventaire réalisé à l’été 1999, l’herbaçaie salée de ces deux marais est caractérisée par une dominance de Plantain maritime et de Glaux maritime, accompagnés d’une dizaine d’autres espèces végétales typiques des marais, dont la Limonie de Nash.', 'Les Bernaches cravants s’y arrêtent également au printemps, se nourrissant dans le petit herbier discontinu de Zostères marines, situé le long de la pointe au Boisvert, face à la pointe à Émile (Boisseau 1998).']}], 'confiance': 'élevé'}]}]

@pytest.mark.asyncio
async def test_extract_mlflow(client,app):
    hash="9cd27112fafb"
    run_id="test_run_id"
    opensearch_client = app.state.opensearch_client
    for d in data:
        list_eov=d['liste_eov']
        for eov_item in list_eov:
            eov=eov_item['eov']
           
            citations=eov_item['citation']
            for citation_item in citations:
                citation_texts=citation_item['citation_texte']
                for citation_text in citation_texts:
                    query = citation_text
                    result = await search(opensearch_client, doc_hash=hash, query=query)
                    logger.info(f"Query: {query}")
                    logger.info(f"Search Result: {result}")
                    assert result["similarity"] > 0.5, f"Similarity too low for query: {query}"