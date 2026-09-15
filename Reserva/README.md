# Sistema de Reservas (Flask)

Este repositorio contiene una aplicación Flask para la gestión de préstamos, reservas y
estadísticas de un sistema universitario.

## Requisitos

* Python 3.10+ (3.11 recomendado)
* PostgreSQL 12+
* `psycopg2-binary`, `Flask`, `SQLAlchemy`, etc. (lista en `requirements.txt`)

## Preparación del entorno (Windows)

```powershell
cd <ruta del proyecto>
.\start.ps1        # crea venv, instala dependencias y arranca la app
```

El script `start.ps1` también se puede usar para regresar a un estado limpio si no
se han definido las variables de entorno.

## Arranque manual

1. Crear/activar un virtualenv:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Instalar dependencias:

   ```powershell
   pip install -r requirements.txt
   ```

3. Definir `DATABASE_URL` (o use la predeterminada). Si la contraseña contiene
   caracteres especiales, **no olvide URL‑codificarlos**. Puede usar el script
   `gen_database_url.py` para generarla.

4. Ejecutar cualquiera de los lanzadores:

   * `python run.py`        – realiza verificación de conexión
   * `python run_app.py`    – fija variables y arranca
   * `python run_with_postgres.py` – muestra advertencias de sanitización

   Todos ejecutan el servidor en `http://localhost:5000`.

## Diagnóstico

Ejecute `python diagnose_env.py` para inspeccionar versiones de Python/lib y
recibir avisos sobre la URL de la base de datos.

## Notas

* El código principal reside en `app_improved.py`, la versión refactorizada.
* La clase `Config` ahora normaliza el valor de `DATABASE_URL` para que no
  falle cuando la contraseña incluye símbolos.
* Se crea un usuario administrador por defecto en el primer arranque; cambie
  sus credenciales inmediatamente.
---

## ✨ Características Mejoradas

### 🔄 División Automática por Jornadas
Los préstamos que cruzan múltiples jornadas académicas (MAÑANA/TARDE/NOCHE) se 
dividen automáticamente en segmentos:
- **Ejemplo:** Un préstamo de 11:00-15:00 genera 2 registros (MAÑANA y TARDE)
- Mejora reportes y análisis estadísticos por jornada
- Implementado en `services/prestamo_service.py → dividir_prestamo_por_jornadas()`

### 📊 Importación/Exportación de Datos
- **Exportación:** Excel, CSV en módulos de préstamos, reservas y profesores
  - Rutas: `/prestamos/exportar/<formato>`, `/reservas/exportar/<formato>`, etc.
- **Importación:** Subida de archivos Excel para cargar datos masivos
  - Ruta global: `/importar_datos` (requiere rol admin)
  - Plantilla descargable: `/descargar_plantilla_importacion`

### 🔒 Seguridad Mejorada
- Validación robusta de cédulas, emails y contraseñas
- Manejo seguro de URLs con caracteres especiales en contraseña
- Logging de intentos fallidos y accesos exitosos
- Gestión segura de tokens de sesión

### � Alertas y Notificaciones
* Flash en pantalla y envío de correo cuando hay préstamos vencidos o reservas próximas.
* Se incluye un script `scripts/alert_report.py` para generar informes periódicos (cron/Task Scheduler).
* Compatible con WebSocket (Flask-SocketIO): el footer ya contiene un cliente que muestra alertas cuando se crea una reserva o se modifica inventario.

### �🚀 Optimizaciones de Rendimiento
- Índices optimizados en base de datos
- Consultas SQL eficientes (sin N+1 queries)
- Caché de constantes del sistema
- Servicios modularizados para lógica de negocio

### 📈 Módulo de Estadísticas
- Navegación dedicada con enlace **Estadísticas** visible según permisos
- Acceso rápido desde el dashboard principal con tarjetas resúmen
- Incluye dashboard ampliado, historial, exportación y APIs JSON