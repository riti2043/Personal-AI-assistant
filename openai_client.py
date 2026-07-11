import os
import time
from functools import wraps
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings

# Load environment variables
load_dotenv()
MAX_REQUESTS = int(os.getenv("MAX_REQUESTS_PER_MINUTE"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY"))

# intializing Chat model
chat_model= ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model_name=os.getenv("GROQ_MODEL_NAME", "qwen/qwen3.6-27b"),
    temperature=float(os.getenv("GROQ_TEMPERATURE", 0.7)),
    max_tokens=int(os.getenv("GROQ_MAX_TOKENS", 1000))
)

# initializing Embedding model

embedding_model = HuggingFaceEmbeddings(
    model_name=os.getenv("DEFAULT_EMBEDDING_MODEL")
)

# Rate Limiter
request_timestamps: list[float] = []

def rate_limit(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        global request_timestamps

        current_time = time.time()

        request_timestamps = [
            t for t in request_timestamps
            if current_time - t < 60
        ]

        if len(request_timestamps) >= MAX_REQUESTS:
            wait_time = 60 - (current_time - request_timestamps[0])
            print(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
            time.sleep(wait_time)

        request_timestamps.append(time.time())

        return func(*args, **kwargs)

    return wrapper

# Retry Decorator

def retry(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)

            except Exception as e:
                print(
                    f"Attempt {attempt + 1} failed: {e}"
                )

                if attempt == MAX_RETRIES - 1:
                    raise

                time.sleep(RETRY_DELAY)

    return wrapper