from pydantic import BaseModel
from typing import List, Optional, Dict

# =============================================================================
# FEEDBACK ITEM SCHEMAS
# =============================================================================

class FeedbackItem(BaseModel):
    eov: str
    accept: str
    justification: Optional[str] = None


class MissingEOVItem(BaseModel):
    eov: str
    comment: Optional[str] = None


class KeywordFeedbackItem(BaseModel):
    keyword: str
    accept: str  # "accept" or "reject"
    justification: Optional[str] = None


class MetadataFeedbackItem(BaseModel):
    metadata_field: str
    accept: str
    user_correction: Optional[str] = None


# =============================================================================
# USER FEEDBACK SCHEMAS
# =============================================================================

class UserFeedback_EOV(BaseModel):
    file_name: str
    revision_date: str
    feedback: List[FeedbackItem]
    missing_eovs: List[MissingEOVItem]
    user_context: str


class MetadataFeedback(BaseModel):
    file_name: str
    revision_date: str
    metadata_feedback: List[MetadataFeedbackItem]
    keywords_feedback: Dict[str, List[KeywordFeedbackItem]]
    user_context: str


# =============================================================================
# CONSTANTS
# =============================================================================

POSSIBLE_EOVS = [
    'État de la mer', 'Contraintes sur la surface océanique', 'Glace de mer', 'Niveau marin',
    'Température de surface', 'Température sous la surface', 'Courants de surface',
    'Courants sous la surface', 'Salinité de surface', 'Salinité sous la surface',
    'Flux de chaleur océanique de surface', "Pression au fond de l'océan", 'Oxygène',
    'Nutriments', 'Carbone inorganique', 'Traceurs transitoires', 'Matière particulaire',
    "Protoxyde d'azote", "Isotopes stables du carbone", "Carbone organique dissous",
    "Biomasse et diversité phytoplanctonique", "Biomasse et diversité zooplanctonique",
    "Abondance et diversité de poissons", "Abondance et distribution de tortues, oiseaux et mammifères marins",
    "Composition et couverture des coraux durs", "Composition et couverture des herbiers marins",
    "Composition et couverture de la canopée de macroalgues", "Mangrove cover and composition",
    "Biomasse et diversité microbienne", "Abondance et distribution des invertébrés",
    "Couleur des océans", "Débris marins", "Paysage acoustique des océans", 'Autre'
]
