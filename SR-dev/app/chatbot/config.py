import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

load_dotenv()

PWC_API_KEY = os.getenv("PWC_API_KEY")
PWC_URL = os.getenv("PWC_URL")
# Primary/final-answer model (quality-first).
LLM_MODEL_OPUS = os.getenv("LLM_MODEL_OPUS")
# Fast model for routing/classification/rewrite steps.
LLM_MODEL_GPT_MINI = os.getenv("LLM_MODEL_GPT_MINI")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
# Backward-compatible alias used by parts of runtime (e.g. token estimator).
LLM_MODEL = LLM_MODEL_OPUS

llm = ChatOpenAI(
    api_key=PWC_API_KEY,
    model=LLM_MODEL_OPUS,
    base_url=PWC_URL,
)

fast_llm = ChatOpenAI(
    api_key=PWC_API_KEY,
    model=LLM_MODEL_GPT_MINI or LLM_MODEL_OPUS,
    base_url=PWC_URL,
)

# Embeddings using same PWC credentials (Azure OpenAI–compatible endpoint)
embeddings = OpenAIEmbeddings(
    api_key=PWC_API_KEY,
    openai_api_base=PWC_URL,
    model=EMBEDDING_MODEL,
)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7688")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")