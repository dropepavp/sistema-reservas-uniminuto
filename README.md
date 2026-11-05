# Sistema de Reservas y Gestión Universitaria 

[![CI Pipeline - Docker Build & Test](https://github.com/dropepavp/sistema-reservas-uniminuto/actions/workflows/ci.yml/badge.svg)](https://github.com/dropepavp/sistema-reservas-uniminuto/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![PostgreSQL 15](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://www.postgresql.org/)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://docs.docker.com/compose/)

Aplicación web empresarial desarrollada en **Flask / Python** y **PostgreSQL** para la gestión integral de préstamos, reservas de salas de cómputo y aulas, control de inventario de equipos tecnológicos y registro de asistencia docente en **UNIMINUTO**.

---

## 🐳 Despliegue con Docker y Docker Compose (Entrega Proyecto 1)

El sistema se encuentra contenerizado en una arquitectura multi-contenedor aislada y orquestada:

* **Contenedor 1 (`web`):** Aplicación Flask construida a partir de una imagen base oficial con versión fija (`python:3.11-slim`), con puerto `5000` expuesto y verificación de salud (`HEALTHCHECK`).
* **Contenedor 2 (`db`):** Base de datos relacional oficial `postgres:15-alpine`, configurada mediante variables de entorno y con volumen persistente (`db_data`).
* **Red Dedicada (`reserva_network`):** Red bridge propia que permite la comunicación interna entre contenedores mediante resolución de nombres DNS.
* **Comunicación Interna (Criterio 5):** La aplicación `web` se comunica con la base de datos usando estrictamente el nombre del servicio `@db:5432` (**sin usar localhost ni IPs fijas**).
* **Seguridad (Criterio 6 ):** Archivos `.dockerignore` y `.env.example`. Las contraseñas y secretos no se suben al repositorio.
* **Integración Continua (CI - Criterio 7 ):** Pipeline automatizado en GitHub Actions (`.github/workflows/ci.yml`) que construye y valida los contenedores en cada `push` o `pull_request`.

---

## 🏛️ Diagrama de Arquitectura de Red y Contenedores

```text
+---------------------------------------------------------------------------------+
|                        RED VIRTUAL DOCKER (reserva_network)                     |
|                                                                                 |
|   +--------------------------+                     +-------------------------+  |
|   |   CONTENEDOR 1: 'web'    |                     |   CONTENEDOR 2: 'db'    |  |
|   |                          |                     |                         |  |
|   |  - Imagen: python:3.11   |   Resolución DNS    |  - Imagen: postgres:15  |  |
|   |  - Framework: Flask      | ------------------> |  - Motor: PostgreSQL    |  |
|   |  - Driver: psycopg/psycopg2    host: 'db'      |  - Puerto int: 5432     |  |
|   |  - Healthcheck: /login   |     puerto: 5432    |  - Healthcheck: pg_ready|  |
|   +--------------------------+                     +-------------------------+  |
|                |                                                |               |
|      Mapeo de Puerto: 5000:5000                                 |               |
+----------------|------------------------------------------------|---------------+
                 |                                                |
                 v                                                v
      Host Local (Navegador)                           Volumen Persistente:
       http://localhost:5000                                db_data
```

---

## 🚀 Guía Rápida de Despliegue

### Requisitos Previos
1. Tener instalado [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / macOS / Linux).
2. Git instalado en el sistema.

### Instrucciones para levantar los contenedores

#### 1. Clonar el Repositorio
```bash
git clone https://github.com/dropepavp/sistema-reservas-uniminuto.git
cd sistema-reservas-uniminuto/Reserva
```

#### 2. Configurar Variables de Entorno
Copia el archivo de plantilla `.env.example` para generar tu archivo `.env` local:
```powershell
# En Windows PowerShell:
Copy-Item .env.example .env

# En Linux / macOS / Bash:
cp .env.example .env
```

#### 3. Construir y Levantar los Contenedores
Ejecuta el siguiente comando para construir la imagen y levantar ambos servicios en segundo plano:
```bash
docker compose up --build -d
```

#### 4. Verificar el Estado de los Contenedores
Ambos contenedores deben figurar en estado `healthy`:
```bash
docker ps
```

#### 5. Verificar la Comunicación de Ida y Vuelta (Criterio 5)
Ejecuta el script de verificación que realiza una operación real de escritura y lectura en PostgreSQL a través de la red interna de Docker:
```powershell
Get-Content scripts/verify_docker_network.py | docker exec -i reserva_web python -
```

#### 6. Acceder a la Aplicación
Abre tu navegador web e ingresa a:
👉 **http://localhost:5000**

---

## 📂 Estructura del Proyecto

```text
sistema-reservas-uniminuto/
│
├── .github/
│   └── workflows/
│       └── ci.yml               # Pipeline de Integración Continua (CI)
│
├── Reserva/                     # Directorio principal del servicio
│   ├── blueprints/              # Módulos de la aplicación Flask
│   ├── scripts/                 # Scripts de utilidad y verificación de red
│   ├── static/                  # Archivos estáticos (CSS, JS, imágenes)
│   ├── templates/               # Plantillas HTML Jinja2
│   ├── Dockerfile               # Configuración Contenedor 1 (Web)
│   ├── docker-compose.yml       # Orquestación Multi-Contenedor (Web + DB)
│   ├── .dockerignore            # Exclusión de archivos no deseados
│   ├── .env.example             # Plantilla de variables de entorno seguras
│   ├── requirements.txt         # Dependencias de Python fijadas
│   ├── app.py                   # Fábrica de la aplicación Flask
│   └── run.py                   # Punto de entrada de la aplicación
│
└── README.md                    # Documentación principal del repositorio
```

---

## 🛠️ Comandos de Monitoreo y Diagnóstico

* **Ver logs en tiempo real del servicio web:**
  ```bash
  docker compose logs -f web
  ```
* **Ver logs de la base de datos:**
  ```bash
  docker compose logs -f db
  ```
* **Inspeccionar la red compartida:**
  ```bash
  docker network inspect reserva_network
  ```
* **Detener los servicios:**
  ```bash
  docker compose down
  ```
* **Detener y eliminar volúmenes (reinicio limpio):**
  ```bash
  docker compose down -v
  ```
