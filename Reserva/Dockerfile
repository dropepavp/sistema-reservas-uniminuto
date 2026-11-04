# ==============================================================================
# Dockerfile - Servicio Web (Sistema de Reservas UNIMINUTO)
# Imagen base oficial de Python con versión fija (Cumplimiento Criterio 2)
# ==============================================================================
FROM python:3.11-slim

# Metadatos del contenedor
LABEL maintainer="UNIMINUTO"
LABEL description="Contenedor de aplicacion web Flask - Sistema de Reservas y Gestion"

# Variables de entorno de Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_RUN_HOST=0.0.0.0 \
    FLASK_RUN_PORT=5000

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema requeridas para psycopg2 y utilidades de red
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para aprovechar la cache de capas de Docker
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el codigo fuente de la aplicacion
COPY . .

# Exponer el puerto de la aplicacion (Cumplimiento Criterio 2)
EXPOSE 5000

# Verificacion de salud del contenedor
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:5000/login || exit 1

# Comando de inicio del contenedor (Cumplimiento Criterio 2)
CMD ["python", "run.py"]

