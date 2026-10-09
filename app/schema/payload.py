from enum import Enum
from typing import List, Optional, Union,Literal, Any
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

class ModelParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["openai", "anthropic"]
    model: str
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    reasoning_effort: Optional[Literal["low", "medium", "high"]] = None
    extra_params: dict[str, Any] = Field(default_factory=dict)   # passed to the API as-is

    def to_llm(self) -> dict:
        kwargs = self.model_dump(
            exclude={"provider", "reasoning_effort", "extra_params"}, exclude_none=True
        )
        model_kwargs = dict(self.extra_params)

        if self.reasoning_effort:
            if self.provider == "openai":
                kwargs["reasoning_effort"] = self.reasoning_effort
            elif self.provider == "anthropic":
                model_kwargs["output_config"] = {"effort": self.reasoning_effort}

        if model_kwargs:
            kwargs["model_kwargs"] = model_kwargs
        return kwargs
    
class ExtractionTypes(Enum):
    eov = "eov"
    table = "table"
    metadata = "metadata"

class ExtractionPayload(BaseModel):
    model: list[ModelParameters] = Field(..., description="List of model parameters for the extraction process.")
    text: Optional[str] = Field(default=None, description="The text content to be processed.")
    runs: Optional[int] = Field(default=1, description="Number of times to run the extraction for robustness")
    seeds: Optional[List[int]] = None
    hash: str
    source: Optional[str] = Field(default=None, description="The source of the document batch.")
    dpi: Optional[int] = Field(default=300, description="The DPI of the document, if applicable.")
    pages: Optional[List[int]] = Field(default=None, description="List of page numbers to process, if applicable.")



class ExpectedValue(BaseModel):
    eov:Optional[List[str]]=None
    confiance:Optional[Optional[str]]=None

AssessmentValue = Union[bool, float, str]
class CommentItem(BaseModel):
    trace_id: str
    span_id: str
    comment: Optional[str] = ""
    value: AssessmentValue | ExpectedValue
 

class ExpectedItem(BaseModel):
    trace_id: str
    span_id: str
    value: ExpectedValue
class MissingEovItem(BaseModel):
    eov: str
    confidenceLevel: str
    reason: str
    citation: str


class MissingEov(BaseModel):
    data:List[MissingEovItem] 
    username: Optional[str] = "anonymous"
    assessment_name: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    
class Comment(BaseModel):
    data:List[CommentItem] 
    username: Optional[str] = "anonymous"
    assessment_name: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

class InsertDocRequest(BaseModel):
    text: str = Field(..., description="The text content of the document to be inserted.")
    id: int=Field(..., description="A unique identifier for the document.")
    start_offset: Optional[int] = Field(None, description="The starting character offset of the chunk in the original document.")
    end_offset: Optional[int] = Field(None, description="The ending character offset of the chunk in the original document.")

class InsertDocsRequest(BaseModel):
    texts: List[InsertDocRequest] 
    hash:str=Field(..., description="A unique hash for the document batch.")
    delete_existing: bool = False
    source: Optional[str] = None
