FROM python:3.11-slim
WORKDIR /app
COPY storage-manager/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ ./shared/
COPY storage-manager/ ./storage-manager/
ENV PYTHONPATH=/app
CMD ["uvicorn", "storage-manager.main:app", "--host", "0.0.0.0", "--port", "8008"]
