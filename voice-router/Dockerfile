FROM python:3.11-slim
WORKDIR /app
COPY voice-router/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ ./shared/
COPY voice-router/ ./voice-router/
ENV PYTHONPATH=/app
CMD ["uvicorn", "voice-router.main:app", "--host", "0.0.0.0", "--port", "8007"]
