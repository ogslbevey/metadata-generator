from langchain_core.prompts import ChatPromptTemplate
from app.core.models import model
from app.core.prompts import prompt_MetadataSchemaCIOOS, prompt_eov
from app.schemas.metadata import MetadataSchemaCIOOS
from app.schemas.eov import EOVWithCitations

# 1. Création du template de prompt pour MetadataSchemaCIOOS
# Configuration d'un template de prompt en spécifiant les messages système et utilisateur
prompt_template_MetadataSchemaCIOOS = ChatPromptTemplate.from_messages([
    ('system', prompt_MetadataSchemaCIOOS),  
    ('user', '{text}')  
])

# 2. Création du template de prompt pour EOV
# Configuration d'un template similaire mais adapté aux EOV
prompt_template_eov = ChatPromptTemplate.from_messages([
    ('system', prompt_eov), 
    ('user', '{text}')  
])

# 3. Création de la chaîne pour MetadataSchemaCIOOS
# Combinaison du template de prompt avec un modèle pour produire une sortie structurée
chain_MetadataSchemaCIOOS = prompt_template_MetadataSchemaCIOOS | model.with_structured_output(
    schema=MetadataSchemaCIOOS,  
    method='json_schema', 
)

# 4. Création de la chaîne pour EOV
# Configuration similaire mais adaptée au traitement des EOV
chain_eov = prompt_template_eov | model.with_structured_output(
    schema=EOVWithCitations,  
    method='json_schema',  
)