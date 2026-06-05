FROM python:3.11-slim-bookworm

WORKDIR /app

# System deps for Pillow (image analysis)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run requires a process listening on PORT (default 8080)
EXPOSE 8080

CMD ["python", "entrypoint.py"]
