# Diseño Técnico: Security Hardening

## Visión General

Este documento describe el diseño técnico para endurecer la seguridad de la aplicación Flask
"Reserva". Las 7 mejoras abordan las vulnerabilidades más críticas: credenciales expuestas en
código fuente, workaround frágil de conexión a BD, scripts de utilidad en el repositorio,
ausencia de protección CSRF, cookies de sesión inseguras, falta de rate limiting y páginas de
error que exponen información interna.

El enfoque es quirúrgico: cada cambio es mínimo y localizado para no romper la funcionalidad
existente. No se reescribe la aplicación; se refuerza lo que ya existe.

---

## Arquitectura

La aplicación sigue una arquitectura Flask con blueprints. Los cambios de seguridad se
distribuyen en capas:

```mermaid
graph TD
    subgraph "Capa de Configuración"
        ENV[".env / Variables de entorno"]
        CFG["config.py (Config classes)"]
        ENV --> CFG
    end

    subgraph "Capa de Arranque"
        APP["app.py (create_app)"]
        DB["database.py (SQLAlchemy estándar)"]
        CFG --> APP
        DB --> APP
    end

    subgraph "Capa de Seguridad (nueva)"
        CSRF["Flask-WTF CSRFProtect"]
        LIMITER["Flask-Limiter"]
        COOKIES["SESSION_COOKIE_* flags"]
        APP --> CSRF
        APP --> LIMITER
        APP --> COOKIES
    end

    subgraph "Capa de Rutas"
        AUTH_BP["blueprints/auth.py (login)"]
        OTHER_BP["Otros blueprints"]
        LIMITER --> AUTH_BP
        LIMITER --> OTHER_BP
    end

    subgraph "Capa de Presentación"
        ERR["Error handlers (400/403/404/500)"]
        TEMPLATES["templates/errors/"]
        ERR --> TEMPLATES
    end
```

### Flujo de arranque seguro

```mermaid
sequenceDiagram
    participant OS as Sistema Operativo
    participant ENV as .env
    participant CFG as config.py
    participant APP as app.py

    OS->>ENV: Lee DATABASE_URL, FLASK_SECRET_KEY
    ENV->>CFG: Variables disponibles en os.environ
    CFG->>CFG: Valida que DATABASE_URL exista
    alt DATABASE_URL ausente
        CFG->>APP: Lanza RuntimeError
        APP->>OS: Proceso termina con error crítico
    else DATABASE_URL presente
        CFG->>CFG: Codifica password con quote_plus
        CFG->>APP: SQLALCHEMY_DATABASE_URI válida
        APP->>APP: Inicializa db, CSRF, Limiter
        APP->>OS: Aplicación lista
    end
```

---

## Componentes e Interfaces

### 1. Gestión de Credenciales (`config.py`)

**Cambios:**
- Eliminar todos los valores por defecto hardcodeados (`Allison2023secure`, `sistema_reserva`, etc.)
- `DATABASE_URL` ausente → `RuntimeError` en tiempo de arranque
- `FLASK_SECRET_KEY` ausente → `RuntimeError` en tiempo de arranque
- La función `build_database_uri` construye la URI codificando el password con `quote_plus`

```python
# Antes (inseguro)
_raw_db = os.environ.get('DATABASE_URL', 'postgresql://postgres:Allison2023secure@...')

# Después (seguro)
_raw_db = os.environ.get('DATABASE_URL')
if not _raw_db:
    raise RuntimeError("DATABASE_URL no está definida. La aplicación no puede arrancar.")
```

**Archivo `.env.example`** (nuevo, en raíz del proyecto):
```
DATABASE_URL=postgresql://usuario:contraseña@host:5432/nombre_bd
FLASK_SECRET_KEY=cambia_esto_por_un_valor_aleatorio_seguro
FLASK_CONFIG=production
ADMIN_USER=admin
ADMIN_EMAIL=admin@tudominio.com
ADMIN_PASSWORD=
SUPERADMIN_DOCUMENTS=
SMTP_SERVER=
SMTP_PORT=25
```

### 2. Refactorización de `CustomSQLAlchemy` (`database.py`)

**Cambios:**
- Eliminar la clase `CustomSQLAlchemy` y su `init_app` personalizado
- Eliminar el `os.environ.pop('DATABASE_URL', None)` al inicio del módulo
- Usar `flask_sqlalchemy.SQLAlchemy` directamente
- La URI ya llega correctamente codificada desde `config.py`

```python
# Antes
class CustomSQLAlchemy(SQLAlchemy):
    def init_app(self, app, **kwargs): ...  # workaround frágil

db = CustomSQLAlchemy()

# Después
db = SQLAlchemy()  # estándar, sin subclase
```

La codificación del password se centraliza en `config.py`:

```python
# config.py
from urllib.parse import urlparse, quote_plus

def _build_safe_db_uri(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    if parsed.password:
        safe_pwd = quote_plus(parsed.password)
        netloc = f"{parsed.username}:{safe_pwd}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        return f"{parsed.scheme}://{netloc}{parsed.path}"
    return raw_url
```

### 3. `.gitignore` y Scripts de Utilidad

**Patrones a agregar en `.gitignore`:**
```
# Variables de entorno
.env

# Scripts de utilidad / diagnóstico
check_*.py
test_*.py
add_*.py
actualizar_*.py
app_improved.py
```

Los scripts que deban mantenerse para desarrollo deben leer credenciales desde `.env`:
```python
# Patrón recomendado para scripts de utilidad
from dotenv import load_dotenv
load_dotenv()
DATABASE_URL = os.environ['DATABASE_URL']  # falla explícitamente si no está definida
```

### 4. Protección CSRF (`Flask-WTF`)

**Instalación:** `pip install flask-wtf`

**Inicialización en `app.py`:**
```python
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    csrf.init_app(app)
    ...
```

**En templates HTML** (macro reutilizable en `base.html`):
```html
<form method="POST">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    ...
</form>
```

**Para rutas JSON/API** (header `X-CSRFToken`):
```javascript
// En el JS del cliente
fetch('/api/endpoint', {
    method: 'POST',
    headers: {
        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
});
```

**Exención de rutas API internas** (si aplica):
```python
@csrf.exempt
@api_bp.route('/webhook', methods=['POST'])
def webhook(): ...
```

Flask-WTF rechaza automáticamente con HTTP 400 cualquier POST/PUT/PATCH/DELETE sin token válido.

### 5. Flags de Seguridad en Cookies de Sesión (`config.py`)

```python
class Config:
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True

class DevelopmentConfig(Config):
    SESSION_COOKIE_SECURE = False  # permite HTTP local
```

En `app.py`, activar sesiones permanentes al hacer login:
```python
# blueprints/auth.py, dentro del bloque de login exitoso
from flask import make_response
session.permanent = True  # activa PERMANENT_SESSION_LIFETIME
```

### 6. Rate Limiting (`Flask-Limiter`)

**Instalación:** `pip install flask-limiter`

**Inicialización en `app.py`:**
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute"],
    storage_uri="memory://",  # en producción usar Redis: "redis://localhost:6379"
)

def create_app(config_name='default'):
    ...
    limiter.init_app(app)
```

**Límites específicos por ruta:**
```python
# blueprints/auth.py
from extensions import limiter  # módulo centralizado de extensiones

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login(): ...
```

```python
# blueprints/prestamos.py, blueprints/reservas.py
@prestamos_bp.route('/nuevo_prestamo', methods=['POST'])
@limiter.limit("60 per minute")
def nuevo_prestamo(): ...
```

**Deshabilitar en tests:**
```python
class TestingConfig(Config):
    RATELIMIT_ENABLED = False
```

**Módulo `extensions.py`** (nuevo, para evitar imports circulares):
```python
# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per minute"])
```

### 7. Páginas de Error Personalizadas

**Registro de handlers en `app.py`:**
```python
@app.errorhandler(400)
def bad_request(e):
    app.logger.warning("HTTP 400: %s", e)
    return render_template('errors/400.html'), 400

@app.errorhandler(403)
def forbidden(e):
    app.logger.warning("HTTP 403: %s", e)
    return render_template('errors/403.html'), 403

@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    app.logger.error("HTTP 500: %s", e, exc_info=True)
    db.session.rollback()
    return render_template('errors/500.html'), 500
```

**Estructura de templates:**
```
templates/
  errors/
    400.html
    403.html
    404.html
    500.html
```

Cada template extiende `base.html` y muestra un mensaje amigable sin trazas de stack.
En modo DEBUG, Flask ya muestra el debugger de Werkzeug automáticamente, por lo que los
handlers de 500 solo se activan en producción.

---

## Modelos de Datos

No se requieren cambios en los modelos de base de datos. Todos los cambios son de configuración,
middleware y presentación.

**Variables de entorno requeridas** (contrato de configuración):

| Variable | Requerida | Descripción |
|---|---|---|
| `DATABASE_URL` | Sí | URI completa de PostgreSQL |
| `FLASK_SECRET_KEY` | Sí | Clave secreta para firmar sesiones y tokens CSRF |
| `FLASK_CONFIG` | No | `development` / `production` / `testing` (default: `development`) |
| `ADMIN_USER` | No | Documento del admin inicial (default: `admin`) |
| `ADMIN_EMAIL` | No | Email del admin inicial |
| `ADMIN_PASSWORD` | No | Password del admin inicial (si vacío, se genera uno aleatorio) |
| `SUPERADMIN_DOCUMENTS` | No | Documentos separados por coma con rol superadmin |
| `RATELIMIT_STORAGE_URI` | No | URI de Redis para rate limiting en producción |

**Dependencias nuevas a agregar en `requirements.txt`:**
```
flask-wtf>=1.2.0
flask-limiter>=3.5.0
python-dotenv>=1.0.0
```

---

## Propiedades de Corrección

*Una propiedad es una característica o comportamiento que debe mantenerse verdadero en todas las
ejecuciones válidas del sistema — esencialmente, una declaración formal sobre lo que el sistema
debe hacer. Las propiedades sirven como puente entre las especificaciones legibles por humanos y
las garantías de corrección verificables por máquinas.*

### Propiedad 1: Variables de entorno requeridas causan fallo de arranque si están ausentes

*Para cualquier* estado del entorno donde `DATABASE_URL` o `FLASK_SECRET_KEY` no estén definidas,
la función de creación de la aplicación (`create_app`) debe lanzar una excepción en lugar de
arrancar con valores por defecto hardcodeados.

**Valida: Requisitos 1.1, 1.2, 1.4**

---

### Propiedad 2: Caracteres especiales en contraseñas son codificados correctamente en la URI

*Para cualquier* string de contraseña que contenga caracteres especiales (`@`, `:`, `/`, `+`,
`%`, espacios, etc.), la función `_build_safe_db_uri` debe producir una URI que sea parseable
por `urllib.parse.urlparse` sin pérdida de información, y cuyo componente `password` al
decodificarse con `unquote` sea igual a la contraseña original.

**Valida: Requisitos 2.2, 2.3**

---

### Propiedad 3: La protección CSRF rechaza peticiones sin token válido

*Para cualquier* ruta de la aplicación que acepte métodos POST, PUT, PATCH o DELETE, una
petición enviada sin un token CSRF válido (o sin el header `X-CSRFToken` para rutas JSON)
debe recibir una respuesta con código HTTP 400, y la petición no debe ser procesada.

**Valida: Requisitos 4.1, 4.3**

---

### Propiedad 4: Las cookies de sesión tienen los flags de seguridad configurados

*Para cualquier* respuesta de login exitoso, el header `Set-Cookie` de la cookie de sesión
debe contener los atributos `HttpOnly` y `SameSite=Lax`. En entorno de producción, debe
contener adicionalmente el atributo `Secure`.

**Valida: Requisitos 5.1, 5.2, 5.3**

---

### Propiedad 5: El rate limiting aplica los límites configurados por IP

*Para cualquier* IP que envíe más peticiones de las permitidas en el período configurado
(10/min al login, 60/min a endpoints de creación, 200/min global), la petición que excede
el límite debe recibir una respuesta con código HTTP 429.

**Valida: Requisitos 6.1, 6.2, 6.3, 6.4**

---

### Propiedad 6: Los manejadores de error devuelven HTML con el código HTTP correcto

*Para cualquier* condición de error HTTP (400, 403, 404, 500), la respuesta debe tener el
código HTTP correspondiente y el `Content-Type` debe ser `text/html`. La respuesta no debe
contener trazas de stack de Python ni rutas internas del sistema de archivos.

**Valida: Requisitos 7.1, 7.2, 7.3, 7.5**

---

### Propiedad 7: Los manejadores de error registran el error en el log del servidor

*Para cualquier* error HTTP manejado (400, 403, 404, 500), el manejador correspondiente debe
invocar el logger de la aplicación con el detalle del error, de modo que la información de
diagnóstico quede disponible en los logs del servidor sin exponerse al cliente.

**Valida: Requisitos 7.4**

---

## Manejo de Errores

### Errores de configuración (arranque)

| Condición | Comportamiento |
|---|---|
| `DATABASE_URL` ausente | `RuntimeError` con mensaje descriptivo, proceso termina |
| `FLASK_SECRET_KEY` ausente | `RuntimeError` con mensaje descriptivo, proceso termina |
| URI de BD no parseable | `ValueError` en `_build_safe_db_uri`, proceso termina |
| Fallo de conexión a PostgreSQL | SQLAlchemy lanza error en primera query, no en arranque |

### Errores en tiempo de ejecución

| Condición | Comportamiento |
|---|---|
| Ruta no encontrada | Handler 404 → `templates/errors/404.html` |
| Acceso denegado | Handler 403 → `templates/errors/403.html` |
| Token CSRF inválido | Flask-WTF → Handler 400 → `templates/errors/400.html` |
| Error interno no controlado | Handler 500 → `templates/errors/500.html` + rollback de sesión BD |
| Límite de rate superado | Flask-Limiter → HTTP 429 con mensaje de tiempo de espera |

### Principios de manejo de errores

- **No exponer información interna**: Los templates de error no muestran trazas, rutas de
  archivos ni versiones de dependencias.
- **Logging completo en servidor**: Todos los errores se registran con `exc_info=True` para
  diagnóstico interno.
- **Rollback en errores 500**: El handler de 500 hace `db.session.rollback()` para evitar
  transacciones colgadas.
- **Modo DEBUG**: En desarrollo, Flask/Werkzeug muestra el debugger interactivo en lugar de
  los templates de error personalizados.

---

## Estrategia de Testing

### Enfoque dual: tests unitarios + tests basados en propiedades

Los tests unitarios verifican ejemplos concretos y casos borde. Los tests de propiedades
verifican invariantes universales sobre rangos de entradas generadas aleatoriamente. Ambos
son complementarios y necesarios.

**Librería de property-based testing:** `hypothesis` (Python)

```
pip install hypothesis
```

### Tests unitarios (ejemplos y casos borde)

**`tests/test_config.py`**
- Verifica que `create_app()` lanza `RuntimeError` cuando `DATABASE_URL` está ausente
- Verifica que `create_app()` lanza `RuntimeError` cuando `FLASK_SECRET_KEY` está ausente
- Verifica que `ProductionConfig.SESSION_COOKIE_SECURE == True`
- Verifica que `DevelopmentConfig.SESSION_COOKIE_SECURE == False`
- Verifica que `TestingConfig` tiene `RATELIMIT_ENABLED == False`
- Verifica que `PERMANENT_SESSION_LIFETIME <= timedelta(hours=8)`
- Verifica que el archivo `.env.example` existe y contiene las variables requeridas
- Verifica que `.gitignore` contiene `.env` y los patrones de scripts de utilidad

**`tests/test_csrf.py`**
- Verifica que un POST a `/login` sin token CSRF devuelve 400
- Verifica que un POST a `/login` con token CSRF válido es procesado (no 400)
- Verifica que un POST JSON con header `X-CSRFToken` válido es aceptado

**`tests/test_error_handlers.py`**
- Verifica que una ruta inexistente devuelve 404 con HTML
- Verifica que el handler 500 está registrado
- Verifica que los handlers 400, 403, 404, 500 están registrados en la app

**`tests/test_database.py`**
- Verifica que `db` es instancia de `SQLAlchemy` (no subclase)
- Verifica que `CustomSQLAlchemy` no existe en `database.py`

### Tests de propiedades (Hypothesis)

Cada test de propiedad debe ejecutarse con un mínimo de 100 iteraciones.
Formato de etiqueta: `Feature: security-hardening, Property N: <texto>`

**`tests/test_properties.py`**

```python
from hypothesis import given, settings, strategies as st

# Feature: security-hardening, Property 2: Password special chars encoded correctly
@given(st.text(min_size=1, alphabet=st.characters(blacklist_categories=('Cs',))))
@settings(max_examples=100)
def test_password_encoding_round_trip(password):
    """Para cualquier contraseña, _build_safe_db_uri produce una URI
    cuya contraseña decodificada es igual a la original."""
    from urllib.parse import urlparse, unquote
    from config import _build_safe_db_uri
    raw = f"postgresql://user:{password}@localhost:5432/db"
    safe = _build_safe_db_uri(raw)
    parsed = urlparse(safe)
    assert unquote(parsed.password) == password

# Feature: security-hardening, Property 3: CSRF rejects requests without token
@given(st.sampled_from(['/login', '/nuevo_prestamo', '/nueva_reserva']))
@settings(max_examples=100)
def test_csrf_rejects_post_without_token(route):
    """Para cualquier ruta POST, una petición sin token CSRF devuelve 400."""
    with app.test_client() as client:
        response = client.post(route, data={})
        assert response.status_code == 400

# Feature: security-hardening, Property 5: Rate limiting enforces limits
@given(st.integers(min_value=11, max_value=50))
@settings(max_examples=100)
def test_login_rate_limit_exceeded(num_requests):
    """Para cualquier número de peticiones > 10 al login desde la misma IP,
    al menos una debe recibir 429."""
    with app.test_client() as client:
        responses = [client.post('/login', data={'usuario': 'x', 'contraseña': 'y'})
                     for _ in range(num_requests)]
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes

# Feature: security-hardening, Property 6: Error handlers return HTML with correct code
@given(st.sampled_from(['/ruta-que-no-existe-abc123', '/otra-ruta-inexistente-xyz']))
@settings(max_examples=100)
def test_404_returns_html(path):
    """Para cualquier ruta inexistente, la respuesta es 404 con Content-Type HTML."""
    with app.test_client() as client:
        response = client.get(path)
        assert response.status_code == 404
        assert b'<html' in response.data.lower() or b'<!doctype' in response.data.lower()
        assert b'Traceback' not in response.data
```

### Cobertura esperada

| Requisito | Tipo de test | Archivo |
|---|---|---|
| 1.1, 1.2 | Unitario + Propiedad 1 | `test_config.py`, `test_properties.py` |
| 1.5, 1.6 | Unitario (ejemplo) | `test_config.py` |
| 2.1 | Unitario (ejemplo) | `test_database.py` |
| 2.2, 2.3 | Propiedad 2 | `test_properties.py` |
| 3.1 | Unitario (ejemplo) | `test_config.py` |
| 4.1, 4.3 | Propiedad 3 | `test_properties.py` |
| 4.5 | Unitario (ejemplo) | `test_csrf.py` |
| 5.1, 5.3 | Propiedad 4 | `test_properties.py` |
| 5.2, 5.4, 5.5 | Unitario (ejemplo) | `test_config.py` |
| 6.1, 6.3, 6.4 | Propiedad 5 | `test_properties.py` |
| 6.6 | Unitario (ejemplo) | `test_config.py` |
| 7.1–7.3, 7.5 | Propiedad 6 | `test_properties.py` |
| 7.4 | Propiedad 7 | `test_properties.py` |
| 7.6 | Unitario (ejemplo) | `test_error_handlers.py` |
