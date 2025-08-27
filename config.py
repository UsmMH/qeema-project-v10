
import os

# Weaviate configuration
WEAVIATE_URL = os.environ.get("WEAVIATE_URL", "http://weaviate:8080")

# OpenAI configuration
OPENAI_APIKEY = os.environ.get("OPENAI_APIKEY", "")
OPENAI_MODEL = "gpt-4.1"
OPENAI_MAX_TOKENS = 1000,000
OPENAI_TEMPERATURE = 0.7

# App configuration
DEFAULT_EVENT_LIMIT = 6
MAX_EVENT_LIMIT = 20
