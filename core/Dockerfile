FROM python:3.11-slim
WORKDIR /app
COPY core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ ./shared/
COPY llm/ ./llm/
COPY config/ ./config/
COPY prompts/ ./prompts/
COPY core/ ./core/
ENV PYTHONPATH=/app
CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8000"]
