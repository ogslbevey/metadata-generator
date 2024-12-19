from fastapi import FastAPI 
from app.core.chain_setup import chain_MetadataSchemaCIOOS, chain_eov 
from langserve import add_routes  
from app.schemas.metadata import MetadataSchemaCIOOS  
from app.services.metadata_transform import transform_metadata_to_full  
from fastapi import Body 

# Définition de l'application FastAPI
# Création de l'objet `FastAPI` avec des métadonnées descriptives comme le titre, la version, et une description
app = FastAPI(
    title="LangChain Server",
    version="1.0",
    description="A simple API server using LangChain's Runnable interfaces",
)

# Ajoute une route spécifique à `chain_MetadataSchemaCIOOS` avec le chemin "/chain_MetadataSchemaCIOOS"
add_routes(
    app,  # Application FastAPI où la route est ajoutée
    chain_MetadataSchemaCIOOS,  # Chaîne LangChain définie pour traiter certaines données
    path="/chain_MetadataSchemaCIOOS",  # Chemin où la chaîne est accessible
)

# Ajoute une autre route pour `chain_eov` avec le chemin "/chain_eov"
add_routes(
    app,  # Application FastAPI où la route est ajoutée
    chain_eov,  # Une autre chaîne LangChain définie
    path="/chain_eov",  # Chemin où cette chaîne est accessible
)

# Ajout d'une route pour convertir des métadonnées en JSON complet
# Cette route accepte une requête POST à l'URL "/generate_full_metadata_json/"
@app.post("/generate_full_metadata_json/")
async def generate_full_metadata(metadata: MetadataSchemaCIOOS):
    """
    Fonction pour transformer les métadonnées fournies dans un schéma complet JSON.
    
    :param metadata: Objet de type `MetadataSchemaCIOOS` validé via Pydantic
    :return: Métadonnées transformées dans un format complet
    """
    return transform_metadata_to_full(metadata)
