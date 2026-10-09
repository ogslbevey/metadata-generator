
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

def setup_mlflow()-> MlflowClient:
    
    uri = os.getenv("MLFLOW_TRACKING_URI")
    if uri:
        mlflow.set_tracking_uri(uri)
    mlflow.set_experiment("observia")
    # mlflow.langchain.autolog()
    
    # mlflow.openai.autolog()
    client=MlflowClient()
    logger.info(f"MLflow client set up with tracking URI: {mlflow.get_tracking_uri()}")
    logger.info("MLFLOW_TRACKING_URI env=%s", os.getenv("MLFLOW_TRACKING_URI"))
    logger.info("MLFLOW_REGISTRY_URI env=%s", os.getenv("MLFLOW_REGISTRY_URI"))
    logger.info("mlflow.get_tracking_uri()=%s", mlflow.get_tracking_uri())
    return client