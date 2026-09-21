FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "for i in 1 2 3 4 5; do alembic upgrade head && break; if [ $i -eq 5 ]; then exit 1; fi; sleep 3; done && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
