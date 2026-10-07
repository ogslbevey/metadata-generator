from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from app.schema.eov import EOVWithCitations
from app.schema.metadata import MetadataSchemaCIOOS
from mlflow.client import MlflowClient
from mlflow.entities.model_registry import PromptVersion
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, MessagesState, START, END
import pymupdf 
import mlflow 
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


model=None

def get_model(model_name:str):
    global model
    if model is None:
        if model_name.startswith("openai:"):
            model = ChatOpenAI(model_name.split(":")[1])
        elif model_name.startswith("anthropic:"):
            model = ChatAnthropic(model_name.split(":")[1])
        
        else:
            raise ValueError(f"Unsupported model name: {model_name}")
    return model

def get_prompt(state: MessagesState, prompt_name: str, mlflow_client: MlflowClient) -> dict:
   

    prompt = mlflow.genai.load_prompt(f"prompts:/{prompt_name}@ref")
    langchain_prompt = ChatPromptTemplate.from_messages(prompt.to_single_brace_format())
    system_message = langchain_prompt.format_messages()[0]
    
    return {"messages": [system_message]}

def add_text(state: MessagesState, text: str) -> dict:

    return {"messages": HumanMessage(content=text)}

