FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TESSERACT_LANGS=eng+deu+ces+slk+fra+spa+ita+pol+nld+por+ara+hin+jpn+chi_sim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-deu \
    tesseract-ocr-ces \
    tesseract-ocr-slk \
    tesseract-ocr-fra \
    tesseract-ocr-spa \
    tesseract-ocr-ita \
    tesseract-ocr-pol \
    tesseract-ocr-nld \
    tesseract-ocr-por \
    tesseract-ocr-ara \
    tesseract-ocr-hin \
    tesseract-ocr-jpn \
    tesseract-ocr-chi-sim \
    wkhtmltopdf \
    libgl1 \
    libglib2.0-0 \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    fonts-dejavu-core \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8050
EXPOSE 8050

CMD ["sh", "-c", "gunicorn invoice_app.app:server --bind 0.0.0.0:${PORT} --workers ${WEB_CONCURRENCY:-1} --threads 4 --timeout 180"]
