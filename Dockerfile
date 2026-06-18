# --- Etapa 1: compilar la app React (Vite) ---
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Etapa 2: backend Django que sirve la API y la app React ---
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Código del proyecto (sin .env ni node_modules; ver .dockerignore)
COPY . .
# Trae el build del frontend desde la etapa anterior
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Recolecta los estáticos (incluida la app React). No necesita base de datos.
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Migra, carga los datos la primera vez (bootstrap idempotente) y levanta Gunicorn.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py bootstrap_itaca && gunicorn config.wsgi --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 120"]
