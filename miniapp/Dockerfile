FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt* ./
RUN pip install --no-cache-dir fastapi uvicorn aiosqlite openai python-dotenv || \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# DB stored on mounted volume
ENV DB_PATH=/app/data/threewords.db
RUN mkdir -p /app/data

EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
