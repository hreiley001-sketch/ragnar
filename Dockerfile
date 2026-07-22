FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

# Shell entrypoint migrates Postgres/Supabase then starts uvicorn.
# Hosts that inject $PORT (Render/Railway/Fly/etc.) are respected.
CMD ["sh", "-c", "/app/docker-entrypoint.sh"]
