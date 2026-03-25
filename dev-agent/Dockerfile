FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY dev-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pyyaml

# ソースコードとワークスペースのマウントポイント
RUN mkdir -p /app/src /app/workspace

COPY shared/ ./shared/
COPY llm/ ./llm/
COPY config/ ./config/
COPY prompts/ ./prompts/
COPY dev-agent/ ./dev-agent/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "dev-agent.main:app", "--host", "0.0.0.0", "--port", "8013"]
