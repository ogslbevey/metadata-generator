from pydantic import BaseModel
from typing import List, Optional


class Citation(BaseModel):
    citation_texte: str


class EOVWithReason(BaseModel):
    eov: str
    raison: str
    citation: List[Citation]


class EOVWithCitations(BaseModel):
    liste_eov: List[EOVWithReason]


class Feedback(BaseModel):
    eov: str
    accept: str  # "yes" ou "no"
    justification: Optional[str]

class UserFeedback(BaseModel):
    feedback: List[Feedback]
    missing_eovs: List[str]
