FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY scripts ./scripts
# The float "best" LSTM model is more accurate than the integer model the
# distro package ships; the app picks it up from ./tessdata automatically.
RUN sh scripts/fetch_tessdata.sh
COPY app ./app

ENV CORS_ORIGINS=*
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
