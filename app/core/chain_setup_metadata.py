# Imports
# 1. LangChain core components
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.callbacks import MlflowCallbackHandler
from langchain_core.prompts import ChatPromptTemplate
from app.schemas.eov import EOVWithCitations
from langchain_community.callbacks import MlflowCallbackHandler
import mlflow.models  # Import MLflow models
from langchain_openai import ChatOpenAI

# 2. Application-specific imports
from app.schemas.metadata import MetadataSchemaCIOOS

# 3. MLflow imports
import mlflow.models  # Import MLflow models

# 4. Standard Python libraries
from datetime import datetime

# Model Configuration
model = ChatOpenAI(
    model="gpt-4o-2024-08-06",
    temperature=0.1,
    seed=42,
    disable_streaming=True
)

# Metadata Prompt
prompt_MetadataSchemaCIOOS = '''
    Vous êtes un expert en extraction de données structurées maritimes. Votre tâche est d'extraire les informations strictement présentes dans le texte fourni et de remplir les champs de la structure de données demandée, en français et en anglais, selon la définition de la classe ci-dessous.

    IMPORTANT :
    - Ne fournissez pas d'informations si elles ne sont pas clairement présentes dans le texte fourni.
    - Si une information n'est pas disponible dans le texte, marquez le champ comme "Non disponible".
    - Ne faites aucune supposition ou extrapolation.
    - Conservez la mise en forme exacte demandée.
    
    # (The rest of the detailed prompt here...)
'''

# Prompt Template Creation
# 1. Create a template for MetadataSchemaCIOOS
prompt_template_MetadataSchemaCIOOS = ChatPromptTemplate.from_messages([
    ('system', prompt_MetadataSchemaCIOOS),
    ('user', '{text}')
])

# Chain Creation
# 1. Combine the MetadataSchemaCIOOS prompt template with the ChatOpenAI model to produce structured output
chain_MetadataSchemaCIOOS = prompt_template_MetadataSchemaCIOOS | model.with_structured_output(
    schema=MetadataSchemaCIOOS,
    method='json_schema',
)

# Register Chain with MLflow
# Use MLflow to register the chain for MetadataSchemaCIOOS
mlflow.models.set_model(chain_MetadataSchemaCIOOS)
