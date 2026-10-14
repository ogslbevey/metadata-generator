
import pandas as pd
import mlflow 
from mlflow.client import MlflowClient
from typing import Any, Union,Optional,List
from pydantic import BaseModel
import json
from mlflow.entities import Assessment,Feedback
from mlflow.entities.assessment import AssessmentSource, AssessmentSourceType
from app.schema.eov import split_citation_list_if_needed, split_if_ellipsis,_confidence_weight
import logging 

logger=logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

AssessmentValue = Union[bool, float, str]

class ExpectedValue(BaseModel):
    eov:Optional[List[str]]=None
    confiance:Optional[Optional[str]]=None
 
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



def get_traces_by_run_id(mlflow_client, run_id: str):
    run = mlflow_client.get_run(run_id)
    traces = mlflow.search_traces(
        locations=[run.info.experiment_id],
        run_id=run_id,
        return_type="list",
    )
    return run, traces


def get_all_spans(mlflow_client, run_id: str,filter_by: str = "main-") -> pd.DataFrame:
    run, traces = get_traces_by_run_id(mlflow_client, run_id)

    rows = []
    for trace in traces:
        tags = trace.info.tags or {}

        for span in trace.data.spans:
            if filter_by and span.name.startswith(filter_by):
                continue
           
            rows.append({
                "trace_id": trace.info.trace_id,
                "span_id": span.span_id,
                "parent_id": span.parent_id,
                "name": span.name,
                "inputs": span.inputs,
                "outputs": span.outputs,
               
            })

    return pd.DataFrame(rows)

def build_traces_organized_eov(mlflow_client, run_id: str) -> pd.DataFrame:
    run = mlflow_client.get_run(run_id)
    run_type = run.data.params.get("type")
    rows=get_all_spans(mlflow_client, run_id)
    
    spans_df = pd.json_normalize(rows.to_dict(orient="records"), sep=".")
   
    spans_df.columns = spans_df.columns.str.replace(r"^inputs\.data\.?", "", regex=True)
    if run_type=="eov":
        try:
            spans_df['confiance_level']=spans_df['confiance'].apply(_confidence_weight)
            spans_df = spans_df.sort_values(by=["eov", "confiance_level"], ascending=False).reset_index(drop=True)
            # spans_df.drop(columns=["confiance_level"], inplace=True)
        
        except KeyError as e:
            print(f"KeyError occurred: {e}")
            
    
    return spans_df


def add_feedback(trace_id,span_id,value: AssessmentValue|ExpectedValue,assessment_name,username="yagmur@example.com",comment:str=""):
    if isinstance(value, ExpectedValue):
        value={
            # "eov": value.eov or [],
            "confiance": value.confiance or ""
        }
   
    feedback = Feedback(
        name=assessment_name,
        value=value,
        rationale=comment,
        source=AssessmentSource(
            source_type="HUMAN",
            source_id=username,
        ),
        
        span_id=span_id
    )
    mlflow.log_assessment(trace_id=trace_id,assessment=feedback)







# def build_all_spans(mlflow_client, run_id: str) -> pd.DataFrame:
#     run, traces = get_traces_by_run_id(mlflow_client, run_id)

#     rows = []
#     for trace in traces:
#         tags = trace.info.tags or {}

#         for span in trace.data.spans:
#             if span.name.startswith("main-"):
#                 continue

#             rows.append({
#                 "trace_id": trace.info.trace_id,
#                 "span_id": span.span_id,
#                 "parent_id": span.parent_id,
#                 "name": span.name,
       
#                 "status": getattr(span.status, "status_code", None),
#                 "inputs": span.inputs,
#                 "outputs": span.outputs,
#                 "attributes": span.attributes,
#             })

#     return pd.DataFrame(rows)

# def explode_eovs(df: pd.DataFrame, col: str = "inputs") -> pd.DataFrame:
#     """One row per EOV, with the EOV's fields (eov, raison, citations, ...) as columns."""
#     eov_lists = df[col].map(lambda o: ((o or {}).get("data") or {}).get("liste_eov") or [])
#     logger.info(eov_lists.head())
#     exploded = (
#         df.drop(columns=[col])
#           .assign(eov_item=eov_lists)
#           .explode("eov_item", ignore_index=True)
#           .dropna(subset=["eov_item"])
#           .reset_index(drop=True)
#     )
#     fields = pd.json_normalize(exploded["eov_item"].tolist())
#     return pd.concat([exploded.drop(columns="eov_item"), fields], axis=1)