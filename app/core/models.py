from langchain_openai import ChatOpenAI

model = ChatOpenAI(
    model="gpt-4o-2024-08-06",
    temperature=0.1,
    seed=42
)
