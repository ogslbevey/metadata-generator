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
# 1. Model configuration
# model_metadata = ChatOpenAI(
#         model="gpt-4o-2024-08-06",
#         temperature=0.1,
#         seed=42,
#      disable_streaming=True
# )

# model_metadata = ChatOpenAI(
#         model="o1-2024-12-17",
#         reasoning_effort="high",
# )

model_metadata = ChatOpenAI(
        model="o3-mini-2025-01-31",
        reasoning_effort="medium",
)

# Metadata Prompt
prompt_MetadataSchemaCIOOS_v1 = f'''
    Vous êtes un expert en extraction de données non structurées maritimes. Votre tâche est d'extraire les informations strictement présentes dans le texte fourni et de remplir les champs de la structure de données demandée, en français et en anglais, selon la définition de la classe ci-dessous.

    IMPORTANT :
    - Ne fournissez pas d'informations si elles ne sont pas clairement présentes dans le texte fourni.
    - Si une information n'est pas disponible dans le texte, marquez le champ comme "Non disponible".
    - Ne faites aucune supposition ou extrapolation.
    - Conservez la mise en forme exacte demandée.

    Voici une description des paramètres à remplir :

    - **title** : Le titre recommandé en français doit répondre aux questions "Quoi", "Où", et "Quand". Il doit être suffisamment précis pour permettre à l'utilisateur de comprendre le contenu sans ouvrir le jeu de données. Le titre ne doit pas contenir d'acronymes, de caractères spéciaux ou utiliser une terminologie spécialisée. Ce titre sera affiché dans le Catalogue de données de l'Observatoire global du Saint-Laurent (OGSL).

    - **title_translated** : Traduction exacte du titre en anglais. Si la traduction n'est pas disponible, marquez comme "Non disponible".

    - **resource_type** : Le type de ressource, à choisir parmi les options suivantes : 'Base de données', 'Livre', 'Modèle', 'Préimpression', 'Rapport', 'Logiciel', 'Texte', 'Autre'. Ne choisissez pas un thème qui n'est pas explicitement mentionné dans le texte.

    - **theme** : Le thème principal des documents, à choisir parmi les options suivantes : 'Oceanographic', 'Biological', 'Other'. Ne choisissez pas un thème qui n'est pas explicitement mentionné dans le texte.

    - **auteurs** : Les auteurs du document. Listez uniquement les auteurs mentionnés clairement. Si aucune information sur les auteurs n'est disponible, indiquez "Non disponible".

    - **summary** : Ce champ contient le résumé du jeu de données, qui sera publié dans le Catalogue de données de l'OGSL. Le résumé doit être accessible à tout type d'utilisateur, en évitant les termes trop techniques. Il doit comporter au moins 300 mots et au maximum 500 mots. Si des informations nécessaires ne sont pas disponibles, indiquez "Certaines informations sont manquantes".

      Suggestions pour structurer le résumé :
        - **Quoi** : Quelles variables ont été mesurées ?
        - **Quand** : Quelle est la couverture temporelle des données ? Fréquence des mesures/observations ?
        - **Où** : Quelle est la couverture spatiale des données ? Nom/lieu des sites d'échantillonnages, laboratoire, etc.
        - **Comment** : Quels équipements, procédures, ou protocoles ont été utilisés ? Quelles sont les méthodes d'assurance et de contrôle de qualité ?
        - **Qui** : Qui a participé au projet (participants, personnel) ?
        - **Pourquoi** : Quel est le contexte de collecte des données ? Comment ces données répondent-elles à une problématique ?

      Ne commencez pas le texte par "ce document". Parlez directement du jeu de données ou du projet.

    - **summary_translated** : Traduction exacte du résumé en anglais. Si la traduction n'est pas disponible, marquez comme "Non disponible".

    - **mots_clés** : Les mots clés sont un moyen efficace de catégoriser vos données pour permettre aux utilisateurs ou à d'autres systèmes d'accéder à tous les jeux de données partageant une même caractéristique.

    Vous pouvez choisir un mot clé prédéfini de la liste suivante. Vous pouvez aussi créer votre propre mot clé en rédigeant un texte libre en anglais ou en français (vérifiez toujours si son équivalent existe dans la liste déroulante afin de diminuer le risque d'écriture multiple d'un même mot clé -ex: phoque Vs Phoques-).

        "en": "abundance and biomass", "fr": "abondance et biomasse"
        "en": "sea access", "fr": "accès à la mer"
        "en": "decision making", "fr": "aide à la décision"
        "en": "protected areas", "fr": "aires protégées"
        "en": "knowledge improvement", "fr": "amélioration des connaissances"
        "en": "land-use planning", "fr": "aménagement du territoire"
        "en": "water purification", "fr": "assainissement des eaux"
        "en": "striped bass", "fr": "bar rayé"
        "en": "watershed", "fr": "bassin versant"
        "en": "habitat characterization", "fr": "caractérisation des habitats"
        "en": "coastal characterization", "fr": "caractérisation des rives"
        "en": "climate change", "fr": "changement climatique"
        "en": "resource conservation", "fr": "conservation des ressources"
        "en": "water consumption", "fr": "consommation d'eau"
        "en": "sea currents", "fr": "courant marin"
        "en": "crustacean", "fr": "crustacé"
        "en": "sustainable development", "fr": "développement durable"
        "en": "sampling", "fr": "échantillonnage"
        "en": "marine mammal", "fr": "mammifères marins"
        "en": "wetlands", "fr": "milieux humides"
        "en": "water quality", "fr": "qualité de l'eau"
        "en": "remote sensing", "fr": "télédétection"
        "en": "water temperature", "fr": "température de l'eau"
        "en": "wind", "fr": "vents"
        "en": "coastal zone", "fr": "zone côtière"

    - **langue** : Indiquez la langue principale des données : 'fr' pour Français ou 'en' pour Anglais. Ne faites pas de supposition.

    - **date_debut** : Indiquez la date du début de collecte de données dans le document. Fournissez la date selon le format Jour-Mois-Année (XX-XX-XXXX). Si l'information n'est pas disponible dans le texte, marquez-la comme "Non disponible" et ne faites aucune supposition.
    
    - **date_fin** : Indiquez la date de fin de collecte de données dans le document. Fournissez la date selon le format Jour-Mois-Année (XX-XX-XXXX). Si l'information n'est pas disponible dans le texte, marquez-la comme "Non disponible" et ne faites aucune supposition.  

    - **spatial** : Quelle est l'étendue géographique du jeu de données? Fournir les coordonnées de délimitation - Est, Ouest, Nord, Sud en degrés décimaux. Si l'information n'est pas disponible dans le texte, marquez-la comme "Non disponible" et ne faites aucune supposition.  

    Rappelez-vous : Si l'information n'est pas disponible dans le texte, marquez-la comme "Non disponible" et ne faites aucune supposition.
'''


# Prompt Template Creation
# 1. Create a template for MetadataSchemaCIOOS
prompt_template_MetadataSchemaCIOOS = ChatPromptTemplate.from_messages([
    ('system', prompt_MetadataSchemaCIOOS_v1),
    ('user', '{text}')
])

# Chain Creation
# 1. Combine the MetadataSchemaCIOOS prompt template with the ChatOpenAI model to produce structured output
chain_MetadataSchemaCIOOS = prompt_template_MetadataSchemaCIOOS | model_metadata.with_structured_output(
    MetadataSchemaCIOOS,
)

# Register Chain with MLflow
# Use MLflow to register the chain for MetadataSchemaCIOOS
mlflow.models.set_model(chain_MetadataSchemaCIOOS)
