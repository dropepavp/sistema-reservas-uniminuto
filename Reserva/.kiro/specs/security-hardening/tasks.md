# Plan de Implementación: Security Hardening

## Visión General

Implementación incremental de las 7 mejoras de seguridad para la aplicación Flask "Reserva".
Cada tarea construye sobre la anterior, terminando con la integración completa y los tests.
El enfoque es quirúrgico: cambios mínimos y localizados sin romper la funcionalidad existente.

## Tareas

- [x] 1. Crear `extensions.py` con extensiones centralizadas
  - Crear `Reserva/extensions.py` con instancias de `SQLAlchemy`, `CSRFProtect` y `Limiter`
  - Usar `key_func=get_remote_address` y `default_limits=["200 per minute"]` en el Limiter
  - Este módulo evita imports circulares entre `database.py`, `app.py` y los blueprints
  - _Requisitos: 4.1, 6.1, 6.4_

- [x] 2. Refactorizar `config.py`: eliminar credenciales hardcodeadas y validar entorno
  - [x] 2.1 Implementar `_build_safe_db_uri(raw_url)` en `config.py`
    - Parsear la URL con `urlparse`, codificar el password con `quote_plus` y reconstruir la URI
    - Lanzar `ValueError` si la URL no es parseable
    - _Requisitos: 2.2, 2.3, 2.4_

  - [ ]* 2.2 Escribir test de propiedad para `_build_safe_db_uri`
    - **Propiedad 2: Caracteres especiales en contraseñas son codificados correctamente**
    - **Valida: Requisitos 2.2, 2.3**

  - [x] 2.3 Eliminar todos los valores por defecto hardcodeados en `Config`
    - `DATABASE_URL` ausente → `RuntimeError` con mensaje descriptivo
    - `FLASK_SECRET_KEY` ausente → `RuntimeError` con mensaje descriptivo
    - Eliminar la cadena `'postgresql://postgres:Allison2023secure@...'` y `sqlite:///fallback_internal.db`
    - Asignar `SQLALCHEMY_DATABASE_URI = _build_safe_db_uri(os.environ['DATABASE_URL'])`
    - _Requisitos: 1.1, 1.2, 1.4_

  - [ ]* 2.4 Escribir test unitario para validación de variables de entorno
    - Verificar que `create_app()` lanza `RuntimeError` cuando `DATABASE_URL` está ausente
    - Verificar que `create_app()` lanza `RuntimeError` cuando `FLASK_SECRET_KEY` está ausente
    - _Requisitos: 1.1, 1.2, 1.4_

  - [x] 2.5 Agregar flags de cookies de sesión en las clases de configuración
    - `Config`: `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = 'Lax'`, `PERMANENT_SESSION_LIFETIME = timedelta(hours=8)`
    - `ProductionConfig`: `SESSION_COOKIE_SECURE = True`
    - `DevelopmentConfig`: `SESSION_COOKIE_SECURE = False`
    - `TestingConfig`: `RATELIMIT_ENABLED = False`
    - _Requisitos: 5.1, 5.2, 5.3, 5.4, 5.5, 6.6_

  - [ ]* 2.6 Escribir tests unitarios para configuración de cookies
    - Verificar `ProductionConfig.SESSION_COOKIE_SECURE == True`
    - Verificar `DevelopmentConfig.SESSION_COOKIE_SECURE == False`
    - Verificar `PERMANENT_SESSION_LIFETIME <= timedelta(hours=8)`
    - Verificar `TestingConfig.RATELIMIT_ENABLED == False`
    - _Requisitos: 5.1, 5.2, 5.4, 5.5, 6.6_

- [x] 3. Refactorizar `database.py`: eliminar `CustomSQLAlchemy`
  - Eliminar la clase `CustomSQLAlchemy` y su `init_app` personalizado
  - Eliminar el `os.environ.pop('DATABASE_URL', None)` al inicio del módulo
  - Importar `db` desde `extensions.py` en lugar de instanciar `SQLAlchemy()` localmente
  - Mantener todos los modelos y la función `init_db` sin cambios
  - _Requisitos: 2.1, 2.2_

  - [ ]* 3.1 Escribir test unitario para verificar que `db` es `SQLAlchemy` estándar
    - Verificar que `db` es instancia de `flask_sqlalchemy.SQLAlchemy` (no subclase)
    - Verificar que la clase `CustomSQLAlchemy` ya no existe en `database.py`
    - _Requisitos: 2.1_

- [x] 4. Checkpoint — Verificar que la app arranca correctamente
  - Asegurarse de que todos los tests pasan hasta este punto, preguntar al usuario si hay dudas.

- [x] 5. Actualizar `app.py`: integrar extensiones, CSRF, Limiter y error handlers
  - [x] 5.1 Importar `db`, `csrf`, `limiter` desde `extensions.py` en lugar de `database.py`
    - Actualizar el import de `db` para que venga de `extensions`
    - Llamar `csrf.init_app(app)` y `limiter.init_app(app)` en la función de creación de la app
    - _Requisitos: 4.1, 6.4_

  - [x] 5.2 Registrar los error handlers 400, 403, 404 y 500 en `app.py`
    - Handler 400: log `warning` + render `errors/400.html`
    - Handler 403: log `warning` + render `errors/403.html`
    - Handler 404: render `errors/404.html` (sin log de warning para no saturar)
    - Handler 500: log `error` con `exc_info=True` + `db.session.rollback()` + render `errors/500.html`
    - _Requisitos: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 5.3 Escribir tests unitarios para los error handlers
    - Verificar que una ruta inexistente devuelve 404 con `Content-Type: text/html`
    - Verificar que los handlers 400, 403, 404, 500 están registrados en la app
    - Verificar que la respuesta 404 no contiene `Traceback` ni rutas internas
    - _Requisitos: 7.1, 7.2, 7.3, 7.5_

  - [ ]* 5.4 Escribir test de propiedad para error handlers
    - **Propiedad 6: Los manejadores de error devuelven HTML con el código HTTP correcto**
    - **Valida: Requisitos 7.1, 7.2, 7.3, 7.5**

  - [ ]* 5.5 Escribir test de propiedad para logging de errores
    - **Propiedad 7: Los manejadores de error registran el error en el log del servidor**
    - **Valida: Requisitos 7.4**

- [x] 6. Agregar rate limiting en `blueprints/auth.py` y rutas críticas
  - [x] 6.1 Importar `limiter` desde `extensions.py` en `blueprints/auth.py`
    - Decorar la ruta `/login` con `@limiter.limit("10 per minute")`
    - Activar `session.permanent = True` dentro del bloque de login exitoso
    - _Requisitos: 6.1, 6.2, 5.4_

  - [ ]* 6.2 Escribir test de propiedad para rate limiting en login
    - **Propiedad 5: El rate limiting aplica los límites configurados por IP**
    - **Valida: Requisitos 6.1, 6.2, 6.3, 6.4**

  - [ ]* 6.3 Escribir tests unitarios para CSRF en login
    - Verificar que un POST a `/login` sin token CSRF devuelve 400
    - Verificar que un POST a `/login` con token CSRF válido no devuelve 400
    - _Requisitos: 4.1, 4.3_

  - [ ]* 6.4 Escribir test de propiedad para protección CSRF
    - **Propiedad 3: La protección CSRF rechaza peticiones sin token válido**
    - **Valida: Requisitos 4.1, 4.3**

  - [ ]* 5.6 Escribir test de propiedad para cookies de sesión
    - **Propiedad 4: Las cookies de sesión tienen los flags de seguridad configurados**
    - **Valida: Requisitos 5.1, 5.2, 5.3**

- [x] 7. Crear templates de error
  - Crear `Reserva/templates/errors/400.html` extendiendo `base.html` con mensaje amigable
  - Crear `Reserva/templates/errors/403.html` extendiendo `base.html` con mensaje amigable
  - Crear `Reserva/templates/errors/404.html` extendiendo `base.html` con mensaje amigable
  - Crear `Reserva/templates/errors/500.html` extendiendo `base.html` con mensaje amigable
  - Ningún template debe exponer trazas de stack, rutas internas ni versiones de dependencias
  - _Requisitos: 7.1, 7.2, 7.3, 7.6_

- [x] 8. Crear `.env.example` y actualizar `.gitignore`
  - Crear `Reserva/.env.example` con todas las variables requeridas documentadas, sin valores reales
  - Actualizar `Reserva/.gitignore` (o crearlo si no existe) con: `.env`, `check_*.py`, `test_*.py`, `add_*.py`, `actualizar_*.py`, `app_improved.py`
  - _Requisitos: 1.5, 1.6, 3.1_

  - [ ]* 8.1 Escribir tests unitarios para `.env.example` y `.gitignore`
    - Verificar que `.env.example` existe y contiene `DATABASE_URL` y `FLASK_SECRET_KEY`
    - Verificar que `.gitignore` contiene `.env` y los patrones de scripts de utilidad
    - _Requisitos: 1.5, 1.6, 3.1_

- [x] 9. Actualizar `requirements.txt`
  - Agregar `flask-wtf>=1.2.0`, `flask-limiter>=3.5.0`, `python-dotenv>=1.0.0`, `hypothesis>=6.0.0`
  - _Requisitos: 4.1, 6.1_

- [x] 10. Checkpoint final — Asegurarse de que todos los tests pasan
  - Ejecutar la suite completa de tests, preguntar al usuario si hay dudas antes de cerrar.

## Notas

- Las tareas marcadas con `*` son opcionales y pueden omitirse para un MVP más rápido
- Cada tarea referencia requisitos específicos para trazabilidad
- Los checkpoints garantizan validación incremental
- Los tests de propiedades usan `hypothesis` con mínimo 100 ejemplos por propiedad
- Los tests unitarios validan ejemplos concretos y casos borde
- El orden de las tareas es importante: `extensions.py` primero para evitar imports circulares
