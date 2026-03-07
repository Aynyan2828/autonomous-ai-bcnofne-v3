FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy
WORKDIR /app
COPY browser-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Playwrightのブラウザをインストール(Chromiumのみ等、軽量化も可能)
# RUN playwright install chromium
COPY shared/ ./shared/
COPY browser-agent/ ./browser-agent/
ENV PYTHONPATH=/app
CMD ["uvicorn", "browser-agent.main:app", "--host", "0.0.0.0", "--port", "8009"]
