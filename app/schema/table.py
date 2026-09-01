from pydantic import BaseModel, Field, ConfigDict
from typing import List

class TableSchema(BaseModel):
    id:str = Field(..., description="Table identifier")
    model_config = ConfigDict(extra="forbid")  # good practice
    caption: str = Field(..., description="Table caption/title")
    columns: List[str] = Field(..., description="Header names in order")
    rows: List[List[str]] = Field(..., description="Row values aligned with columns")

class ListOfTables(BaseModel):
    tables: List[TableSchema] = Field(..., description="List of extracted tables")