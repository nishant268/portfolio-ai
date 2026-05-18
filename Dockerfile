FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY portfolio_ai/ portfolio_ai/
COPY backend/ backend/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e "."

RUN mkdir -p /data
ENV DATA_DIR=/data

EXPOSE 8000
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
