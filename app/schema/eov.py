
from pydantic import BaseModel, Field, field_validator,field_serializer
from typing import List, Optional, Union
from pandas import json_normalize
import pandas as pd
import json
import re
from enum import Enum
import codecs
import unicodedata
import logging



ELLIPSIS_MARKER = re.compile(r"\s*(?:\[\.\.\.\]|\.\.\.|…)\s*")

def split_if_ellipsis(text: str) -> list[str]:
    if not isinstance(text, str):
        return []
    
    text = text.replace("\xa0", " ")  # normalize spaces
    
    if not ELLIPSIS_MARKER.search(text):
        return [text.strip()]
    
    return [p.strip() for p in ELLIPSIS_MARKER.split(text) if p.strip()]

def has_ellipsis(text: str) -> bool:
    return isinstance(text, str) and bool(ELLIPSIS_MARKER.search(text))

def split_citation_list_if_needed(citations: list[str]) -> list[str]:
    parts = []
    for c in citations:
        parts.extend(split_if_ellipsis(c))
    return parts
AssessmentValue = Union[bool, float, str]
# =============================================================================
# CITATION MODELS
# =============================================================================
def _confidence_weight(conf: str) -> int:
    # Map common FR/EN confidence labels to weights
    if not conf:
        return 1
    c = (conf)
    mapping = {
        'très élevé':4, 
        'élevé':3,
        'moyen':2, 
        'faible':1
    }
    # try direct mapping first
    if c in mapping:
        return mapping[c]
    else:
        return 1
    
def _confidence_label(weight: int) -> str:
    reverse_mapping = {
        4:'très élevé', 
        3:'élevé',
        2:'moyen', 
        1:'faible'
    }
    return reverse_mapping.get(weight, 'faible')



from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

EOVName = Literal[
    # Physique
    "État de la mer",
    "Contraintes sur la surface océanique",
    "Glace de mer",
    "Niveau marin",
    "Température de surface",
    "Température sous la surface",
    "Courants de surface",
    "Courants sous la surface",
    "Salinité de surface",
    "Salinité sous la surface",
    "Flux de chaleur océanique de surface",
    "Pression au fond de l'océan",
    # Biogéochimie
    "Oxygène",
    "Nutriments",
    "Carbone inorganique",
    "Traceurs transitoires",
    "Matière particulaire",
    "Protoxyde d'azote",
    "Isotopes stables du carbone",
    "Carbone organique dissous",
    # Biologie et écosystèmes
    "Biomasse et diversité phytoplanctonique",
    "Biomasse et diversité zooplanctonique",
    "Abondance et diversité de poissons",
    "Abondance et distribution de tortues, oiseaux et mammifères marins",
    "Composition et couverture des coraux durs",
    "Composition et couverture des herbiers marins",
    "Composition et couverture de la canopée de macroalgues",
    "Couverture et composition des mangroves",
    "Biomasse et diversité microbienne",
    "Abondance et distribution des invertébrés",
    # Interdisciplinaire
    "Couleur des océans",
    "Débris marins",
    "Paysage acoustique des océans",
    # Autre
    "Autre",
]

Confiance = Literal["très élevé", "élevé", "moyen", "faible"]
CONFIANCE_ORDER = {"très élevé": 0, "élevé": 1, "moyen": 2, "faible": 3}

class Citation(BaseModel):
    citation_texte: List[str] = Field(
        description="Extraits copiés mot pour mot du texte, sans les modifier. "
                    "Un élément par extrait ; ne pas utiliser « ... » pour relier deux extraits."
    )

  

class EOVWithReason(BaseModel):
    eov: EOVName = Field(description="Nom exact d'un EOV de la liste autorisée.")
    raison: str = Field(description="Explication détaillée en français justifiant ce choix.")
    citation: List[str] = Field(description="Citations exactes du texte qui justifient cet EOV.")
    confiance: Confiance = Field(description="Niveau de confiance pour cet EOV.")
    @field_validator("citation", mode="before")
    @classmethod
    def normalize_citation(cls, v):
        # Single string -> list
        if isinstance(v, str):
            return [v]
        # Flatten legacy format: [{"citation_texte": [...]}, ...]
        if isinstance(v, list):
            flat = []
            for item in v:
                if isinstance(item, dict) and "citation_texte" in item:
                    texts = item["citation_texte"]
                    flat.extend([texts] if isinstance(texts, str) else texts)
                else:
                    flat.append(item)
            return flat
        return v

class EOVWithCitations(BaseModel):
    liste_eov: List[EOVWithReason] = Field(
        description="EOV identifiés, du plus au moins probable. Liste vide si aucun EOV."
    )

    # @model_validator(mode="after")
    # def sort_by_confidence(self):
    #     self.liste_eov.sort(key=lambda e: CONFIANCE_ORDER[e.confiance])
    #     return self



# if __name__ == "__main__":
#     # Example usage
#     example = EOVWithCitations(
#         liste_eov=[
#             EOVWithReason(
#                 eov="État de la mer",
#                 raison="Le texte mentionne des conditions de mer agitées.",
#                 citation=[Citation(citation_texte=["Le navire a affronté une mer agitée."])],
#                 confiance="élevé"
#             ),
#             EOVWithReason(
#                 eov="Température de surface",
#                 raison="Le texte indique des variations de température à la surface.",
#                 citation=[Citation(citation_texte=["La température de surface a augmenté de 2°C."])],
#                 confiance="moyen"
#             )
#         ]
#     )
#     print(example.model_dump())