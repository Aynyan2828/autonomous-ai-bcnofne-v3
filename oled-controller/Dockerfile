FROM python:3.11-slim

# Install system dependencies required for RPi.GPIO and I2C
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    i2c-tools \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY oled-controller/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY oled-controller/ ./oled-controller/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "oled-controller.main:app", "--host", "0.0.0.0", "--port", "8011"]
