# Import necessary libraries
from fastapi import FastAPI, HTTPException
from langserve import add_routes
from pydantic import BaseModel
from typing import List, Optional, Dict
from sklearn.metrics import confusion_matrix, classification_report, precision_score, recall_score, f1_score
import pandas as pd
import mlflow
from mlflow.langchain.langchain_tracer import MlflowLangchainTracer
from datetime import datetime
import os
import difflib
import sentry_sdk
from sentry_sdk import capture_exception


# Core schemas and services
from app.schemas.metadata import MetadataSchemaCIOOS
from app.schemas.feedback import FeedbackItem, UserFeedback_EOV, POSSIBLE_EOVS, KeywordFeedbackItem, MetadataFeedbackItem, MetadataFeedback
from app.services.metadata_transform import transform_metadata_to_full
from app.core.chain_setup_eov import model_eov, chain_eov
from app.core.chain_setup_metadata import model_metadata, chain_MetadataSchemaCIOOS

# Utilities
from app.utils.helpers import evaluate_keyword_feedback

SENTRY_DSN = os.getenv('SENTRY_DSN')
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")

# Initialize MLflow
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)


sentry_sdk.init(
    dsn=SENTRY_DSN,
    send_default_pii=False,
    traces_sample_rate=1.0,
)

# Initialize FastAPI application
app = FastAPI(
    title="LangChain Server",
    version="1.0",
    description="A simple API server using LangChain's Runnable interfaces",
)

# Add LangChain routes for metadata and EOV chains
add_routes(app, chain_MetadataSchemaCIOOS, path="/chain_MetadataSchemaCIOOS")
add_routes(app, chain_eov, path="/chain_eov")


# Endpoint to handle user eov feedback and log to MLflow
@app.post("/submit_feedback_eov")
def submit_eov_feedback(feedback: UserFeedback_EOV):
    """
    Process user feedback and log data to MLflow.

    Args:
        feedback (UserFeedback_EOV): Feedback details including file metadata and EOV details.
    
    Returns:
        dict: Success message indicating feedback submission and logging.
    """
    try:

        # Print the received payload for debugging
        print("Received Payload:", feedback.dict())

        # Set up MLflow experiment
        experiment_name = "User Feedback - EOVs"
        experiment = mlflow.get_experiment_by_name(experiment_name)

        if experiment and experiment.lifecycle_stage == "deleted":
            mlflow.tracking.MlflowClient().restore_experiment(experiment.experiment_id)
        elif not experiment:
            mlflow.create_experiment(experiment_name)

        mlflow.set_experiment(experiment_name)

        # Start an MLflow run
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        run_name = f"EOVs {current_time}"

        with mlflow.start_run(run_name=run_name) as run:

            # Save feedback data
            feedback_from_predicted_eovs = [item.dict() for item in feedback.feedback]
            missing_eovs_with_comments = [item.dict() for item in feedback.missing_eovs]

            # Log the JSON file to MLflow
            mlflow.log_dict(feedback_from_predicted_eovs, "raw_feedback_data/feedback_from_predicted_eovs.json")
            mlflow.log_dict(missing_eovs_with_comments, "raw_feedback_data/feedback_missing_eovs.json")

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
            false_negatives = [item.eov for item in feedback.missing_eovs if item.eov in POSSIBLE_EOVS]
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
            # Ensure the evaluation directory exists
            os.makedirs("evaluation", exist_ok=True)

            # Save the evaluation table to a CSV file
            eval_table_path = "evaluation/evaluation_table.csv"
            eval_df.to_csv(eval_table_path, index=False)

            # Log the CSV file as an artifact
            #mlflow.log_artifact(eval_table_path)
            mlflow.log_artifact(eval_table_path, artifact_path="evaluation")


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
        capture_exception(e)

        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Endpoint to handle user metadta feedback and log to MLflow
@app.post("/submit_feedback_metadata")
def submit_metadata_feedback(feedback: MetadataFeedback):
    """
    Process metadata and keyword feedback, log data to MLflow, and save LangChain model as code.
    This version includes a full evaluation of keyword feedback (including rejected items) and
    computes the accuracy rate between the API's proposals and the final accepted keywords.
    """
    try:
        print("Received Metadata Payload:", feedback.dict())

        # Process metadata feedback
        metadata_feedback = [item.dict() for item in feedback.metadata_feedback]

        # Process keyword feedback (les objets Pydantic reçus)
        keywords_feedback_en_objs = feedback.keywords_feedback.get("en", [])
        keywords_feedback_fr_objs = feedback.keywords_feedback.get("fr", [])


        keywords_feedback_en = [item.dict() for item in keywords_feedback_en_objs]
        keywords_feedback_fr = [item.dict() for item in keywords_feedback_fr_objs]

        print("Metadata Feedback:", metadata_feedback)
        print("Keywords EN Feedback:", keywords_feedback_en)
        print("Keywords FR Feedback:", keywords_feedback_fr)

        # Listes prédéfinies pour chaque langue (les propositions du modèle)
        predefined_keywords_fr = [
            "abondance et biomasse", "accès à la mer", "aide à la décision",
            "aires protégées", "amélioration des connaissances", "aménagement du territoire",
            "assainissement des eaux", "bar rayé", "bassin versant",
            "caractérisation des habitats", "caractérisation des rives",
            "changement climatique", "conservation des ressources", "consommation d'eau",
            "courant marin", "crustacé", "développement durable",
            "échantillonnage", "mammifères marins", "milieux humides",
            "qualité de l'eau", "télédétection", "température de l'eau", "vents", "zone côtière"
        ]
        predefined_keywords_en = [
            "abundance and biomass", "sea access", "decision making",
            "protected areas", "knowledge improvement", "land-use planning",
            "water purification", "striped bass", "watershed",
            "habitat characterization", "coastal characterization",
            "climate change", "resource conservation", "water consumption",
            "sea currents", "crustacean", "sustainable development",
            "sampling", "marine mammal", "wetlands",
            "water quality", "remote sensing", "water temperature", "wind", "coastal zone"
        ]

        # Evaluate keyword feedback for French and English
        evaluation_fr = evaluate_keyword_feedback(keywords_feedback_fr, predefined_keywords_fr)
        evaluation_en = evaluate_keyword_feedback(keywords_feedback_en, predefined_keywords_en)

        # Set up MLflow experiment for metadata feedback
        experiment_name = "User Feedback - Metadata"
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment and experiment.lifecycle_stage == "deleted":
            mlflow.tracking.MlflowClient().restore_experiment(experiment.experiment_id)
        elif not experiment:
            mlflow.create_experiment(experiment_name)
        mlflow.set_experiment(experiment_name)

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        run_name = f"Metadata Feedback {current_time}"

        with mlflow.start_run(run_name=run_name) as run:
            # Log raw metadata and keyword feedback to MLflow
            mlflow.log_dict(metadata_feedback, "raw_feedback_data/metadata_feedback.json")
            mlflow.log_dict(keywords_feedback_en, "raw_feedback_data/keywords_en_feedback.json")
            mlflow.log_dict(keywords_feedback_fr, "raw_feedback_data/keywords_fr_feedback.json")

            # Log contextual parameters
            mlflow.log_param("file_name", feedback.file_name)
            mlflow.log_param("file_revision_date", feedback.revision_date)
            mlflow.log_param("user_context", feedback.user_context)

            # Log LangChain model code artifact if exists
            model_code_path = "./app/core/chain_setup_metadata.py"
            if os.path.exists(model_code_path):
                mlflow.log_artifact(model_code_path, artifact_path="langchain_model_code")
                print(f"Logged LangChain model code from: {model_code_path}")
            else:
                print(f"Model code file not found at: {model_code_path}")

            # Calculate simple metrics for metadata feedback
            total_metadata = len(metadata_feedback)
            accepted_metadata = sum(1 for item in metadata_feedback if item.get("accept", "").lower() == "accept")
            rejected_metadata = total_metadata - accepted_metadata
            acceptance_rate_metadata = accepted_metadata / total_metadata if total_metadata > 0 else 0

            mlflow.log_metric("01-total_metadata", total_metadata)
            mlflow.log_metric("02-accepted_metadata", accepted_metadata)
            mlflow.log_metric("03-rejected_metadata", rejected_metadata)
            mlflow.log_metric("04-acceptance_rate_metadata", round(acceptance_rate_metadata, 2))

            # Keyword evaluation metrics for French
            mlflow.log_metric("05-keywords_total_keywords_fr", evaluation_fr["total_keywords"])
            mlflow.log_metric("06-keywords_api_accepted_count_fr", evaluation_fr["api_accepted_count"])
            mlflow.log_metric("07-keywords_manual_added_count_fr", evaluation_fr["manual_added_count"])
            mlflow.log_metric("08-keywords_final_true_count_fr", evaluation_fr["final_true_count"])
            mlflow.log_metric("09-keywords_count_rejected_fr", evaluation_fr["count_rejected"])
            mlflow.log_metric("10-keywords_accuracy_rate_fr", evaluation_fr["accuracy_rate"])

            # Keyword evaluation metrics for English
            mlflow.log_metric("11-keywords_total_keywords_en", evaluation_en["total_keywords"])
            mlflow.log_metric("12-keywords_api_accepted_count_en", evaluation_en["api_accepted_count"])
            mlflow.log_metric("13-keywords_manual_added_count_en", evaluation_en["manual_added_count"])
            mlflow.log_metric("14-keywords_final_true_count_en", evaluation_en["final_true_count"])
            mlflow.log_metric("15-keywords_count_rejected_en", evaluation_en["count_rejected"])
            mlflow.log_metric("16-keywords_accuracy_rate_en", evaluation_en["accuracy_rate"])



            # Log keyword evaluation results
            mlflow.log_dict(evaluation_fr, "evaluation/keywords_evaluation_fr.json")
            mlflow.log_dict(evaluation_en, "evaluation/keywords_evaluation_en.json")


            # Generate and log an evaluation table for metadata feedback
            eval_df_metadata = pd.DataFrame(metadata_feedback)
            os.makedirs("evaluation", exist_ok=True)
            metadata_eval_path = "evaluation/metadata_evaluation_table.csv"
            eval_df_metadata.to_csv(metadata_eval_path, index=False)
            mlflow.log_artifact(metadata_eval_path, artifact_path="evaluation")
            print("Logged evaluation table to MLflow.")

        return {"message": "Metadata and keywords feedback successfully submitted, including model code."}

    except Exception as e:
        print(f"Error during submit_feedback_metadata: {e}")
        capture_exception(e)
     
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
  
  
   
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



@app.get("/chain_eov_model_info")
def get_chain_eov_model_info():
    """
    Return the model name, reasoning effort, etc.
    so the user can see which underlying model is used.
    """
    return model_eov


@app.get("/chain_metadata_model_info")
def get_chain_metadata_model_info():
    """
    Return the model name, reasoning effort, etc.
    so the user can see which underlying model is used.
    """
    return model_metadata