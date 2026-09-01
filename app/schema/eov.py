
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

# Split citation text if it contains ellipsis for searchability and traceability, but keep the original text as well for reference
class Citation(BaseModel):
    citation_texte: list[str]

    @field_validator("citation_texte", mode="before")
    @classmethod
    def validate_citation_texte(cls, v):
        if isinstance(v, str):
            return split_if_ellipsis(v)
        return v
   


class EOVWithReason(BaseModel):
    eov: str
    raison: str
    citation: List[Citation]
    confiance: str
    
   
    

class EOVWithCitations(BaseModel):
    liste_eov: List[EOVWithReason]
    
    
class ChatResponse(BaseModel):
    data: EOVWithCitations  # or List[EOVWithCitations] if you prefer
    seed: Optional[int] = None




if __name__ == "__main__":
    # Example usage
    citation="Présentation du système de gestion des données des eaux coquillières par Yves Lamontagne et Martin Rodrigue, Environnement Canada ... L’implantation de ce système répond aux besoins opérationnels des ministères impliqués dans le"
    citation_obj = Citation(citation_texte=citation)
    print(citation_obj)