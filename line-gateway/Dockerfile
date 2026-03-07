FROM python:3.11-slim
WORKDIR /app
COPY line-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ ./shared/
COPY line-gateway/ ./line-gateway/
ENV PYTHONPATH=/app
CMD ["uvicorn", "line-gateway.main:app", "--host", "0.0.0.0", "--port", "8001"]
