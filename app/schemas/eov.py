from pydantic import BaseModel
from typing import List


class Citation(BaseModel):
    citation_texte: str


class EOVWithReason(BaseModel):
    eov: str
    raison: str
    citation: List[Citation]


class EOVWithCitations(BaseModel):
    liste_eov: List[EOVWithReason]
