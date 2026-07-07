FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e ".[dev,tactical,graph]"

EXPOSE 8741

FROM base AS server
CMD ["python", "-m", "uvicorn", "kawkab.cloud.server:app", "--host", "0.0.0.0", "--port", "8741"]

FROM base AS api
CMD ["python", "-m", "uvicorn", "kawkab.api.api_v1:router", "--host", "0.0.0.0", "--port", "8742"]

FROM base AS full
CMD ["python", "-m", "kawkab"]
