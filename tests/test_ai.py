import pytest
import asyncio
import logging
from app.utils.ai_utils import get_model, get_prompt,add_text
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from functools import partial
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_ai(client, app):
    """Test the AI functionality."""
    res=await client.get("/models/")
    assert res.status_code == 200
    res_json = res.json()
    logger.info(f"List of models: {res_json}")
    # mlflow_client = app.state.mlflow_client

    # builder = StateGraph(MessagesState)
    # builder.add_node(
    #     "get_prompt",
    #     partial(get_prompt, prompt_name="eov", mlflow_client=mlflow_client),
    # )
    # builder.add_node(
    #     "add_text",
    #     partial(add_text, text="What is the capital of France?"),
    # )
    # builder.add_edge(START, "get_prompt")
    # builder.add_edge("get_prompt", "add_text")
    # builder.add_edge("add_text", END)
    # graph = builder.compile()

    # result = await graph.ainvoke({"messages": []})
    # logger.info(result["messages"])
