# Sistema de Reservas y Gestión Universitaria (UNIMINUTO)

Aplicación web empresarial desarrollada en **Flask / Python** y **PostgreSQL** para la gestión integral de préstamos, reservas de salas de cómputo y aulas, control de inventario de equipos tecnológicos y registro de asistencia docente.

---

## 🐳 Despliegue con Docker y Docker Compose (Entrega Proyecto 1)

Este proyecto está completamente contenerizado siguiendo las mejores prácticas de la industria y los criterios de evaluación de integración continua:
* **Contenedor 1 (`web`):** Aplicación Flask construida a partir de una imagen base oficial con versión fija (`python:3.11-slim`), con puerto `5000` expuesto y verificación de salud (`HEALTHCHECK`).
* **Contenedor 2 (`db`):** Base de datos relacional oficial `postgres:15-alpine`, configurada mediante variables de entorno y con volumen persistente (`reserva_db_data`).
* **Red Dedicada (`reserva_network`):** Red bridge propia que permite la comunicación interna entre contenedores mediante resolución de nombres DNS.
* **Comunicación Interna:** La aplicación `web` se comunica con la base de datos usando estrictamente el nombre del servicio `@db:5432` (**sin usar localhost ni IPs fijas**).
* **Seguridad:** Archivos `.dockerignore` y `.env.example`. Las contraseñas y secretos no se suben al repositorio.
* **Integración Continua (CI):** Pipeline automatizado en GitHub Actions (`.github/workflows/ci.yml`) que construye y valida los contenedores en cada `push` o `pull_request`.

---

### Requisitos Previos

1. Tener instalado [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / macOS / Linux).
2. Git instalado en el sistema.

---

### Guía Rápida de Despliegue

#### 1. Clonar el Repositorio
```bash
git clone https://github.com/dropepavp/sistema-reservas-uniminuto.git
cd sistema-reservas-uniminuto
```

#### 2. Configurar Variables de Entorno
Copia el archivo de plantilla `.env.example` para generar tu archivo `.env`:
```powershell
# En Windows PowerShell:
Copy-Item .env.example .env

# En Linux / macOS / Bash:
cp .env.example .env
```

#### 3. Construir y Levantar los Contenedores
Ejecuta el siguiente comando para construir la imagen del contenedor web y levantar ambos servicios en segundo plano:
```bash
docker compose up --build -d
```

#### 4. Verificar el Estado de los Contenedores
```bash
docker compose ps
```
Ambos contenedores (`reserva_db` y `reserva_web`) deben mostrar el estado **Up (healthy)**.

#### 5. Acceder a la Aplicación
Abre tu navegador web e ingresa a:
👉 **http://localhost:5000**

Credenciales por defecto:
* **Documento / Usuario:** `80140666` (o `admin`)
* **Contraseña:** `Allison2.023*`

---

### Comandos de Evidencia y Diagnóstico (Para Informe PDF)

| Comando | Propósito / Evidencia |
| :--- | :--- |
| `docker build -t reserva-web:latest .` | Captura de la construcción de la imagen web sin errores. |
| `docker compose up -d` | Captura del levantamiento de la red, volumen y los dos servicios. |
| `docker ps` | Evidencia de los dos contenedores activos (`reserva_web` y `reserva_db`). |
| `docker network inspect reserva_network` | Demuestra que ambos contenedores comparten la misma red privada. |
| `docker compose logs web` | Muestra la conexión exitosa de Flask hacia `db:5432`. |
| `docker compose down` | Detiene y remueve los contenedores manteniendo los datos persistentes. |

---

## 💻 Ejecución Local Tradicional (Sin Docker)

Si deseas ejecutar el proyecto directamente en tu entorno Python local:

1. Crear y activar entorno virtual:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Instalar dependencias:
   ```powershell
   pip install -r requirements.txt
   ```
3. Ejecutar la aplicación:
   ```powershell
   python run.py
   ```
4. Acceder en `http://localhost:5000`.
