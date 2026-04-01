# syntax=docker/dockerfile:1
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential gcc g++ cmake && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install --default-timeout=5000 --retries=50 --index-url=https://pypi.python.org/simple -r requirements.txt

COPY . .

# Expose port and start standard uvicorn server
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
