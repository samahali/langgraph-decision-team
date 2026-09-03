import os

os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ.setdefault("THREAD_ACCESS_SECRET", "test-thread-access-secret-32-characters")
