from fastapi import APIRouter, UploadFile, File, HTTPException,Form, Depends, Request
import mlflow
from app.utils.mlflow_utils import build_traces_organized,add_feedback,Comment,MissingEov
import logging
router = APIRouter(prefix="/mlflow", tags=["mlflow"])
import logging
logger = logging.getLogger(__name__)


@router.get("/mlflow/{run_id}")
async def get_mlflow_traces_organized(
    run_id: str,
    request: Request,
):  
    mlflow_client = request.app.state.mlflow_client
    run = mlflow_client.get_run(run_id)
    type_of_extraction = run.data.params.get("type", "unknown")
    
    logger.info(f"Fetching MLflow traces for run_id: {run_id} with type: {type_of_extraction}")
    res=build_traces_organized(mlflow_client, run_id)
   
    return {
        "type": type_of_extraction,
        "results": res.to_dict(orient="split")
    }
    
@router.post("/add_comment", response_model=dict)
async def add_comment(
    request: Request,
    payload:Comment|MissingEov
    
):
    r: redis.Redis = request.app.state.redis_client
    if not payload.data:
        raise HTTPException(status_code=404, detail="Data should include")
    username=payload.username or "anonymous"
    assessment_name=payload.assessment_name or "Comment"
    
    if assessment_name=="Expected":
        for item in payload.data:
            add_feedback(
                trace_id=item.trace_id,
                span_id=item.span_id,
                comment=None,
                value=item.value,
                assessment_name=assessment_name,
                username=username
            )
    elif assessment_name=="Comment":
        for item in payload.data:
            add_feedback(
                trace_id=item.trace_id,
                span_id=item.span_id,
                comment=item.comment,
                value=item.value,
                assessment_name=assessment_name,
                username=username
            )
    else:
        trace_id=payload.trace_id
        span_id=payload.span_id
        for item in payload.data:
            add_feedback(
                trace_id=trace_id,
                span_id=span_id,
                
                value={"citation":item.citation,"eov":item.eov,"confidence_level":item.confidenceLevel,"raison":item.reason},
                assessment_name=assessment_name,
                username=username
            )

    return {"status":"ok"}

