from pydantic import BaseModel
from typing import List, Optional

# =============================================================================
# CITATION MODELS
# =============================================================================

class Citation(BaseModel):
    citation_texte: str

# =============================================================================
# EOV MODELS
# =============================================================================

class EOVWithReason(BaseModel):
    eov: str
    raison: str
    citation: List[Citation]

class EOVWithCitations(BaseModel):
    liste_eov: List[EOVWithReason]
