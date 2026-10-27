
import os,re
import mlflow 
import logging
from mlflow.client import MlflowClient
import pandas as pd
import json
from typing import Any
from mlflow.entities import Assessment,Feedback
from mlflow.entities.assessment import AssessmentSource, AssessmentSourceType

from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.info(mlflow.__version__)
logger.info("MLflow initialized.")
def setup_mlflow() -> MlflowClient:
    uri = os.environ["MLFLOW_TRACKING_URI"]
    mlflow.set_tracking_uri(uri)                      # global: used by autolog and traces
    mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT", "observia_extraction"))
    # mlflow.langchain.autolog()
    return MlflowClient(tracking_uri=uri)