from typing import List, Optional, Union
from pydantic import BaseModel, Field


class TablePayload(BaseModel):
    id:int
    caption:str
    page_number:int
    table: list[list[Optional[str]]]


class ModelParameters(BaseModel):
    model_name: str="gpt-4.1"
    temperature: float=0.1
    top_p: Optional[float] = None
    reasoning_effort: Optional[str] = None
    prompt_uri: Optional[str] = None

class TableExtractionRequestPayload(BaseModel):
    data: List[TablePayload]
    model: ModelParameters

class EovExtractionPayload(BaseModel):
    model: ModelParameters
    text: str
    runs: Optional[int] = Field(default=1, description="Number of times to run the extraction for robustness")
    seeds: Optional[List[int]] = None
    hash: str
    source: Optional[str] = Field(default=None, description="The source of the document batch.")


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
