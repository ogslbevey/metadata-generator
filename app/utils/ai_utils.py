import os
from dotenv import load_dotenv
from transformers import AutoTokenizer, AutoModelForTokenClassification
from huggingface_hub import snapshot_download
MODEL_ID = os.getenv("MODEL_ID", "iiiorg/piiranha-v1-detect-personal-information")
MODEL_DIR = os.getenv("MODEL_DIR", "/models/piiranha-v1")



def load_model():
    # Downloads only missing/incomplete files; no-op if everything is there.
    snapshot_download(repo_id=MODEL_ID, local_dir=MODEL_DIR)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForTokenClassification.from_pretrained(MODEL_DIR, device_map="auto")
    return tokenizer, model

