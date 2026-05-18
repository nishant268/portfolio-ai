FROM python:3.11-slim

WORKDIR /app

# System deps for native Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache)
COPY pyproject.toml .
RUN pip install --no-cache-dir hatchling && pip install --no-cache-dir -e "." --no-build-isolation || \
    pip install --no-cache-dir \
        "fastapi>=0.115.0" "uvicorn[standard]>=0.32.0" "httpx>=0.27.0" \
        "pydantic>=2.9.0" "python-dotenv>=1.0.0" "sqlmodel>=0.0.22" \
        "aiosqlite>=0.20.0" "yfinance>=0.2.40" "pandas>=2.0.0" "numpy>=1.26.0" \
        "ta>=0.11.0" "feedparser>=6.0.0" "websockets>=12.0" \
        "langgraph>=0.2.0" "langchain>=0.3.0" "langchain-openai>=0.2.0" \
        "langchain-anthropic>=0.3.0" "langchain-google-genai>=2.0.0" \
        "kiteconnect>=5.0.0" "curl_cffi>=0.15.0" "stocknews>=0.7.0" \
        "rich>=13.0.0" "typer>=0.12.0"

# Copy source
COPY portfolio_ai/ portfolio_ai/
COPY backend/ backend/

# Data directory (mounted as Render persistent disk)
RUN mkdir -p /data
ENV DATA_DIR=/data

EXPOSE 8000

CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
