import pytest
import asyncio
import logging
import mlflow
from mlflow.entities import SpanType
from mlflow.entities import AssessmentSource, AssessmentSourceType, SpanType


logger = logging.getLogger(__name__)




@pytest.mark.asyncio
async def test_extract_from_mlflow(app, client):
    results=[]
    @mlflow.trace(name="main",span_type=SpanType.LLM)
    def traced_add(a, b, kind):
        logger.info(mlflow.get_current_active_span().trace_id)
        @mlflow.trace(name="assessment",span_type=SpanType.LLM)
        def add(a, b):
            
            span_id=mlflow.get_current_active_span().span_id
            logger.info(f"Inside traced_add: a={a}, b={b}, kind={kind}, span_id={span_id}")
            return a + b, span_id
        for i in range(3):
            result, span_id = add(a, b)
            logger.info(f"Result of add({a}, {b}) in iteration {i}: {result}")
            results.append({"result": result, "span_id": span_id,"trace_id":mlflow.get_current_active_span().trace_id})
        return None
    
    traced_add(1, 2, "test")  # This will create a new MLflow run
    logger.info(results)
    mlflow.log_feedback(
        trace_id=results[0]["trace_id"],
        span_id=results[0]["span_id"],
        name="satisfaction",
        value=1
        
    )
    # run_id = "b4e9a79568674a2ab5a7c7a755c2b09f"  # Replace with a valid run_id
    # response = await client.get(f"/mlflow/mlflow/{run_id}")
    # assert response.status_code == 200, response.text
    # body = response.json()
    # assert "type" in body
    # assert "results" in body
    # logger.info(f"MLflow results for run_id {run_id}: {body['results']}")
    # result=body["results"]
    # assert isinstance(result, dict)
    # assert "columns" in result
    # assert "data" in result
    # assert isinstance(result["columns"], list)
    # assert isinstance(result["data"], list)