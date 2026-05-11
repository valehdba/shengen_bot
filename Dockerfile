# syntax=docker/dockerfile:1.7
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app

# Install deps first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Persistent volumes will overlay these
RUN mkdir -p data logs sessions

# Bot is the default; docker-compose overrides this for the dashboard service
CMD ["python", "-m", "src.bot"]
