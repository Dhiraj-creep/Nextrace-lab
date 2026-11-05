import os

# Default tests to local runtime so pytest runs do not conflict with Docker containers
os.environ.setdefault("NEXTRACE_RUNTIME", "local")
