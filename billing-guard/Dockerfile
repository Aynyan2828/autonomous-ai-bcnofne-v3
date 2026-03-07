FROM python:3.11-slim
WORKDIR /app
COPY billing-guard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# contextがルート(.)になっているのでsharedがコピー可能
COPY shared/ ./shared/
COPY billing-guard/ ./billing-guard/
ENV PYTHONPATH=/app
CMD ["uvicorn", "billing-guard.main:app", "--host", "0.0.0.0", "--port", "8002"]
