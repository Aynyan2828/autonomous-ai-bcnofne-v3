FROM python:3.11-slim
WORKDIR /app
COPY diary-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ ./shared/
COPY llm/ ./llm/
COPY config/ ./config/
COPY prompts/ ./prompts/
COPY diary-service/ ./diary-service/
ENV PYTHONPATH=/app
CMD ["uvicorn", "diary-service.main:app", "--host", "0.0.0.0", "--port", "8004"]
