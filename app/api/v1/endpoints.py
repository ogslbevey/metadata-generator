# Import necessary libraries
from fastapi import FastAPI, HTTPException
from langserve import add_routes
from pydantic import BaseModel
from typing import List, Optional
from sklearn.metrics import confusion_matrix, classification_report, precision_score, recall_score, f1_score
import pandas as pd
import mlflow
from mlflow.langchain.langchain_tracer import MlflowLangchainTracer
from datetime import datetime
import os

# Core schemas and services
from app.schemas.metadata import MetadataSchemaCIOOS
from app.schemas.eov import UserFeedback
from app.schemas.feedback import FeedbackItem, UserFeedback, POSSIBLE_EOVS
from app.services.metadata_transform import transform_metadata_to_full
from app.core.chain_setup_eov import model_eov, chain_eov
from app.core.chain_setup_metadata import chain_MetadataSchemaCIOOS

# Utilities
#from app.utils.mlflow_logger import log_user_feedback

# Initialize MLflow
mlflow.set_tracking_uri("http://host.docker.internal:8080")

# Initialize FastAPI application
app = FastAPI(
    title="LangChain Server",
    version="1.0",
    description="A simple API server using LangChain's Runnable interfaces",
)

# Add LangChain routes for metadata and EOV chains
add_routes(app, chain_MetadataSchemaCIOOS, path="/chain_MetadataSchemaCIOOS")
add_routes(app, chain_eov, path="/chain_eov")


# Endpoint to generate full metadata JSON schema
@app.post("/generate_full_metadata_json/")
async def generate_full_metadata(metadata: MetadataSchemaCIOOS):
    """
    Transform provided metadata into a full JSON schema.

    Args:
        metadata (MetadataSchemaCIOOS): Metadata input in the specified schema.
    
    Returns:
        Transformed metadata in full JSON schema format.
    """
    return transform_metadata_to_full(metadata)


# Endpoint to handle user feedback and log to MLflow
@app.post("/submit_feedback_eov")
def submit_feedback(feedback: UserFeedback):
    """
    Process user feedback and log data to MLflow.

    Args:
        feedback (UserFeedback): Feedback details including file metadata and EOV details.
    
    Returns:
        dict: Success message indicating feedback submission and logging.
    """
    try:
        # Print the received payload for debugging
        print("Received Payload:", feedback.dict())

        # Set up MLflow experiment
        experiment_name = "User Feedback"
        experiment = mlflow.get_experiment_by_name(experiment_name)

        if experiment and experiment.lifecycle_stage == "deleted":
            mlflow.tracking.MlflowClient().restore_experiment(experiment.experiment_id)
        elif not experiment:
            mlflow.create_experiment(experiment_name)

        mlflow.set_experiment(experiment_name)

        # Start an MLflow run
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        run_name = f"User Feedback {current_time}"

        with mlflow.start_run(run_name=run_name) as run:
            # Log metadata and context
            mlflow.log_param("file_name", feedback.file_name)
            mlflow.log_param("file_revision_date", feedback.revision_date)
            mlflow.log_param("user_context", feedback.user_context)

            # Log LangChain model as code
            chain_path = "./app/core/chain_setup_eov.py"
            model_info = mlflow.langchain.log_model(
                lc_model=chain_path,
                artifact_path="langchain_model"
            )
            print(f"LangChain model logged: {model_info}")

            # Identify confusion matrix components
            all_possible_eovs = set(POSSIBLE_EOVS)
            true_positives = [item.eov for item in feedback.feedback if item.eov in POSSIBLE_EOVS and item.accept.lower() == "yes"]
            false_negatives = [eov for eov in feedback.missing_eovs if eov in POSSIBLE_EOVS]
            false_positives = [item.eov for item in feedback.feedback if item.eov in POSSIBLE_EOVS and item.accept.lower() == "no"]
            true_negatives = list(all_possible_eovs - set(true_positives) - set(false_negatives) - set(false_positives))

            # Calculate precision, recall, and F1 score
            precision = len(true_positives) / (len(true_positives) + len(false_positives)) if (len(true_positives) + len(false_positives)) > 0 else 0
            recall = len(true_positives) / (len(true_positives) + len(false_negatives)) if (len(true_positives) + len(false_negatives)) > 0 else 0
            f1_score_val = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

            # Log metrics
            mlflow.log_metric("precision", round(precision, 2))
            mlflow.log_metric("recall", round(recall, 2))
            mlflow.log_metric("f1_score", round(f1_score_val, 2))

            # Create evaluation table
            eval_data = []
            for eov in POSSIBLE_EOVS:
                eval_data.append({
                    "EOV Name": eov,
                    "True Positive": eov in true_positives,
                    "False Positive": eov in false_positives,
                    "True Negative": eov in true_negatives,
                    "False Negative": eov in false_negatives,
                })

            eval_df = pd.DataFrame(eval_data)

            # Save evaluation table
            evaluation_dir = "evaluation"
            os.makedirs(evaluation_dir, exist_ok=True)
            eval_table_path = os.path.join(evaluation_dir, "evaluation_table.csv")
            eval_df.to_csv(eval_table_path, index=False)
            mlflow.log_artifact(eval_table_path)

            # Log confusion matrix components
            conf_matrix_artifact = {
                "true_positives": true_positives,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                "true_negatives": true_negatives,
            }
            mlflow.log_dict(conf_matrix_artifact, "evaluation/confusion_matrix_components.json")

        return {"message": "Feedback and model successfully submitted to MLflow."}

    except Exception as e:
        print(f"Error during submit_feedback_eov: {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
