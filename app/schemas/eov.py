from pydantic import BaseModel, Field
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
    confiance: str = Field(..., description="Niveau de confiance pour ce choix d'EOV : très élevé, élevé, moyen, faible")

class EOVWithCitations(BaseModel):
    liste_eov: List[EOVWithReason]
