# syntax=docker/dockerfile:1
# Lean API image. OCR_ENGINE=tesseract (default) | paddle
ARG OCR_ENGINE=tesseract
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LABLEDGER_DATA_DIR=/data

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ARG OCR_ENGINE
RUN if [ "$OCR_ENGINE" = "tesseract" ]; then \
      apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
      && rm -rf /var/lib/apt/lists/*; \
    elif [ "$OCR_ENGINE" = "paddle" ]; then \
      echo "PaddleOCR deps installed at pip layer"; \
    else \
      echo "Unknown OCR_ENGINE=$OCR_ENGINE" && exit 1; \
    fi

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$OCR_ENGINE" = "paddle" ]; then \
         pip install --no-cache-dir paddlepaddle==2.6.2 paddleocr==2.8.1; \
       fi

COPY . .
RUN mkdir -p /data

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host ${BIND_HOST:-0.0.0.0} --port 8000"]
