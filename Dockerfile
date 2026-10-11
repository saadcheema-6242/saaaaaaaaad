FROM python:3.12-slim

# Tesseract OCR engine — required by PassportEye for reading the MRZ.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hosting platforms inject the port via $PORT (Render, Railway, Fly, …).
# Hugging Face Spaces expects 7860 — set app_port accordingly in its README.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
