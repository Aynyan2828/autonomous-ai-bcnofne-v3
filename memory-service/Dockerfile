FROM python:3.11-slim
WORKDIR /app
COPY memory-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ ./shared/
COPY llm/ ./llm/
COPY config/ ./config/
COPY prompts/ ./prompts/
COPY memory-service/ ./memory-service/
ENV PYTHONPATH=/app
CMD ["uvicorn", "memory-service.main:app", "--host", "0.0.0.0", "--port", "8003"]
