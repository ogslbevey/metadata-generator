from pydantic import BaseModel
from typing import List, Optional

# Define schemas for feedback items and user feedback
class FeedbackItem(BaseModel):
    eov: str
    accept: str
    justification: Optional[str] = None


class UserFeedback(BaseModel):
    file_name: str
    revision_date: str
    feedback: List[FeedbackItem]
    missing_eovs: List[str]
    response_time: float
    user_context: str


# Predefined list of possible EOVs
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