FROM python:3.11-slim
WORKDIR /app
COPY gui/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ ./shared/
COPY gui/ ./gui/
ENV PYTHONPATH=/app
CMD ["uvicorn", "gui.main:app", "--host", "0.0.0.0", "--port", "8010"]
