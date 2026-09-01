
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

def _extract_io_from_span(span: Any) -> tuple[Any, Any]:
    """
    Best-effort extraction of (input, output) from an MLflow span.

    Tries:
      - span.inputs / span.outputs (newer/structured)
      - span.attributes["mlflow.spanInputs"] / ["mlflow.spanOutputs"] (JSON strings)
      - span.attributes["mlflow.spanInputs"] / ["mlflow.spanOutputs"] (dict-like)
    """
    attrs = getattr(span, "attributes", None) or {}

    def _extract_from_attr(key: str) -> Any:
        raw = attrs.get(key)
        if raw is None:
            return None

        # Sometimes stored as a JSON string
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                return None

        # Often looks like {"input": ...} or {"output": ...}
        if isinstance(raw, dict):
            # Prefer exact field if present; otherwise return whole dict
            if "input" in raw:
                return raw.get("input")
            if "output" in raw:
                return raw.get("output")
            
            return raw

        return raw

    # Inputs
    span_input = getattr(span, "inputs", None)
    if span_input is None:
        span_input = _extract_from_attr("mlflow.spanInputs")

    # Outputs
    span_output = getattr(span, "outputs", None)
    if span_output is None:
        span_output = _extract_from_attr("mlflow.spanOutputs")
    
    return span_input, span_output

def find_mlflow_spans_with_inputs(
    client: MlflowClient,
    trace_id_mlflow: str,
    target_name: str,
    assessment_name: Optional[str] = None,
    assessment_type: Optional[str] = None
) -> list[dict]:
    tr = client.get_trace(trace_id_mlflow)
   
    spans = getattr(getattr(tr, "data", None), "spans", None) or []
    
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for s in spans:
        if getattr(s, "name", None) != target_name:
            continue
        # if assessment_name or assessment_type:
        #     assessment = tr.search_assessments(
        #         span_id=s.span_id,
        #         type=assessment_type,
        #         name=assessment_name

        #     )
        #     if not assessment:
        #         continue
        
        key = (trace_id_mlflow, s.span_id)
        if key in seen:
            continue
        seen.add(key)
        
        span_input, span_output = _extract_io_from_span(s)
        
        out.append(
            {
                "trace_id": trace_id_mlflow,
                "span_id": s.span_id,
                "parent_id": s.parent_id,
                "name": s.name,
                "input": span_input,
                "output": span_output,
                # "assessment": assessment,
            }
        )

    return out



def get_traces_by_run_id(target_run_id: str) -> pd.DataFrame:
    """
    Retrieves all traces associated with a specific MLflow run ID.

    Args:
        target_run_id: The ID of the MLflow run.

    Returns:
        A pandas DataFrame containing the traces associated with the run.
    """
    filter_string = f"trace.run_id = '{target_run_id}'"
    
    # Use mlflow.search_traces() with the filter string
    # By default, it returns a pandas DataFrame
    traces_df = mlflow.search_traces(filter_string=filter_string)
    return traces_df 


def build_traces_organized(mlflow_client, run_id: str,assessment_type:str= "expectation",assessment_name:str="Found") -> pd.DataFrame:
    run = mlflow_client.get_run(run_id)
 
        
    run_type = run.data.params.get("type")
    
    traces_df = get_traces_by_run_id(run_id)
    trace_ids = set(traces_df["trace_id"])
   
    spans = [
        span
        for trace_id in trace_ids
        for span in find_mlflow_spans_with_inputs(
            mlflow_client,
            trace_id_mlflow=trace_id,
            target_name=f"assessment-{run_type}",
           
        )
    ]
    

    spans_df = pd.json_normalize(spans, sep=".")
    # logger.info(spans_df.head())
    # logger.info(spans_df.columns)
    spans_df.columns = spans_df.columns.str.replace(r"^input\.eov\.?", "", regex=True)
    
    try:
        df = spans_df.explode("citation", ignore_index=True)
        c = pd.json_normalize(df["citation"]).add_prefix("citation.")
        spans_df = pd.concat([df.drop(columns=["citation"]), c], axis=1)
        spans_df = spans_df.rename(columns=lambda c: c.replace("citation.citation_texte", "citation"))
        spans_df["citation"] = spans_df["citation"].apply(
            lambda x: split_citation_list_if_needed(x) if isinstance(x,list) else []
        )
        spans_df['confiance_level']=spans_df['confiance'].apply(_confidence_weight)
        try:
            spans_df = spans_df.sort_values(by=["eov", "similarity"], ascending=False).reset_index(drop=True)
        except KeyError as e:
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