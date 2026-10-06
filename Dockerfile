# Ambiente Linux equivalente ao do Render, para reproduzir o deploy no próprio computador.
#   docker build -t healthos .
#   docker run --rm -p 8000:8000 -e SECRET_KEY=dev -e SEED_DEMO_DATA=True healthos
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DATABASE_URL=sqlite:///./app.db \
    APP_TIMEZONE=America/Belem

# Base de fusos horários (para APP_TIMEZONE); a imagem slim pode não trazê-la.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8000
# Mesmo comando de start do Render (render.yaml).
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
