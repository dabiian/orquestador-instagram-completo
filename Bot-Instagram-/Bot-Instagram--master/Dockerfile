FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Bogota

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.docker.txt .

RUN python -m pip install --upgrade pip setuptools wheel

RUN python -m pip install --no-cache-dir -r requirements.docker.txt

COPY . .

CMD ["python", "main.py"]