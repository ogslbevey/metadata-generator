from pydantic import BaseModel, Field, ConfigDict
from typing import Annotated, Union,List
from pydantic import BaseModel, Field


class TableSchema(BaseModel):
    id:str = Field(..., description="Table identifier")
    model_config = ConfigDict(extra="forbid")  # good practice
    caption: str = Field(..., description="Table caption/title")
    columns: List[str] = Field(..., description="Header names in order")
    rows: List[List[str]] = Field(..., description="Row values aligned with columns")

class ListOfTables(BaseModel):
    tables: List[TableSchema] = Field(..., description="List of extracted tables")




class BBox(BaseModel):
    x0: float = Field(ge=0, le=1, description="Left edge as a fraction of page width (0 = left, 1 = right)")
    y0: float = Field(ge=0, le=1, description="Top edge as a fraction of page height (0 = top, 1 = bottom)")
    x1: float = Field(ge=0, le=1, description="Right edge as a fraction of page width")
    y1: float = Field(ge=0, le=1, description="Bottom edge as a fraction of page height")


class TableWithCaption(BaseModel):
    caption: str = Field(
        description="Table caption text, or empty string if none",
    )
    table: list[list[str]] = Field(
        description="Table cells as rows of text, row-major order",
    )
    bboxes: list[BBox] = Field(
        description="Bounding boxes of the table; usually one, more if it spans multiple regions",
    )


class TablesResult(BaseModel):
    tables: list[TableWithCaption]