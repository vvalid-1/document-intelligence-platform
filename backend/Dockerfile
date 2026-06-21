FROM python:3.11-slim

WORKDIR /app

RUN addgroup --gid 1000 appgroup && \
    adduser --uid 1000 --gid 1000 --no-create-home --disabled-password appuser && \
    mkdir -p /app/uploads && chown 1000:1000 /app/uploads

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-fra \
    tesseract-ocr-ara \
    poppler-utils \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY tests/ ./tests/
COPY pyproject.toml .

USER 1000:1000

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
