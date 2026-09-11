FROM python:3.12-slim
WORKDIR /app
# poppler-utils provides the `pdftotext` binary the analyzer shells out to (via
# `pdftotext -bbox`) for fast, positioned text extraction from the architectural PDFs.
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
