# 🚀 Caché y Performance Avanzada

## Estado Actual

```python
# ❌ Sin caché - Mismo dato se calcula múltiples veces
def obtener_sedes():
    return Sede.query.all()  # Query a BD cada vez

# En cada request de diferentes usuarios
sedes = obtener_sedes()  # Query 1
sedes = obtener_sedes()  # Query 2
sedes = obtener_sedes()  # Query 3
# ... puede ser 100+ queries del mismo dato
```

---

## 1. Caché de Permisos (CRÍTICO)

### Problema Actual

```python
# En app.py - línea 95
cached = session.get('mod_access_cache')
if cached is not None:
    return {'mod_access': cached}

# Leer del cache de sesión si está disponible
from database import UserPermission
perms = UserPermission.query.filter_by(usuario_documento=usuario).all()
```

**Problema:** Se cachea en sesión pero se invalida en cada sesión nueva

### Solución: Redis/Cache Distribuida

```python
# utils/cache_manager.py
from flask_caching import Cache
from flask import current_app

cache = Cache()

class PermissionCache:
    """Gestor de caché de permisos."""
    
    KEY_PREFIX = "permisos:"
    TTL = 3600  # 1 hora
    
    @staticmethod
    def get_user_permisos(usuario_doc):
        """Obtiene permisos con caché."""
        cache_key = f"{PermissionCache.KEY_PREFIX}{usuario_doc}"
        
        # Intentar obtener del caché
        permisos = cache.get(cache_key)
        if permisos is not None:
            current_app.logger.debug(f"Permisos caché hit: {usuario_doc}")
            return permisos
        
        # Si no está en caché, obtener de BD
        from database import UserPermission
        permisos = UserPermission.query.filter_by(
            usuario_documento=usuario_doc
        ).all()
        
        # Guardar en caché
        cache.set(cache_key, permisos, timeout=PermissionCache.TTL)
        current_app.logger.debug(f"Permisos caché miss: {usuario_doc}")
        
        return permisos
    
    @staticmethod
    def invalidar(usuario_doc):
        """Invalida caché cuando cambian permisos."""
        cache_key = f"{PermissionCache.KEY_PREFIX}{usuario_doc}"
        cache.delete(cache_key)
        current_app.logger.info(f"Permisos caché invalidado: {usuario_doc}")
    
    @staticmethod
    def invalidar_todo():
        """Invalida todo caché de permisos (admin)."""
        cache.delete_many(*[
            f"{PermissionCache.KEY_PREFIX}*"
        ])


# blueprints/admin.py - Cuando se actualizan permisos
@admin_bp.route('/permisos/usuario/<documento>', methods=['POST'])
def actualizar_permisos_usuario(documento):
    """Actualiza permisos y invalida caché."""
    try:
        # ... código de actualización ...
        db.session.commit()
        
        # Invalida caché
        PermissionCache.invalidar(documento)
        
        flash('Permisos actualizados', 'success')
    except Exception as e:
        current_app.logger.error(f"Error: {e}")
```

### Instalación

```bash
pip install flask-caching
# Para usar Redis como backend (recomendado)
pip install redis
```

### Configuración en `config.py`

```python
class Config:
    # ... configuración existente ...
    
    # Caché
    CACHE_TYPE = 'redis'  # O 'simple' para desarrollo
    CACHE_REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_DEFAULT_TIMEOUT = 3600
    CACHE_KEY_PREFIX = 'uniminuto_cache:'
```

### Inicializar en `extensions.py`

```python
from flask_caching import Cache

cache = Cache()

# En app.py
from extensions import cache
cache.init_app(app)
```

---

## 2. Caché de Constantes del Sistema

```python
# config.py - Variables que no cambian

class SystemConstants:
    """Constantes cacheadas del sistema."""
    
    # ❌ ANTES - Se cargan cada request
    SALONES = ['A101', 'A102', 'A103', ...]
    JORNADAS = ['MAÑANA', 'TARDE', 'NOCHE']
    
    # ✅ DESPUÉS - Con caché y validación
    @staticmethod
    @cache.cached(timeout=86400)  # 24 horas
    def get_salones():
        """Obtiene lista de salones desde BD (cacheada)."""
        from database import Recurso
        salones = Recurso.query.filter_by(
            tipo='Salón',
            activo=True
        ).with_entities(Recurso.nombre).all()
        return [s[0] for s in salones]
    
    @staticmethod
    @cache.cached(timeout=86400)
    def get_jornadas():
        """Obtiene jornadas."""
        return [
            {'nombre': 'MAÑANA', 'inicio': '06:00', 'fin': '12:30'},
            {'nombre': 'TARDE', 'inicio': '12:30', 'fin': '19:00'},
            {'nombre': 'NOCHE', 'inicio': '19:00', 'fin': '22:00'}
        ]
```

### Invalidar caché cuando cambien datos

```python
# blueprints/admin.py
@admin_bp.route('/recursos/agregar', methods=['POST'])
def agregar_recurso():
    """Agrega recurso e invalida caché."""
    try:
        # ... código ...
        db.session.add(recurso)
        db.session.commit()
        
        # Invalidar caché de constantes
        from extensions import cache
        cache.delete('get_salones')
        cache.delete('get_jornadas')
        
        flash('Recurso agregado', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error: {e}")
```

---

## 3. Caché de Queries Frecuentes

```python
# services/estadisticas_service.py
from extensions import cache

class EstadisticasService:
    """Servicio con caché de estadísticas."""
    
    @staticmethod
    @cache.cached(timeout=1800)  # 30 minutos
    def obtener_resumen_hoy():
        """Resumen del día (caché 30 min)."""
        from database import PrestamoEquipo, Reserva
        
        hoy = date.today()
        prestamos_hoy = PrestamoEquipo.query.filter(
            PrestamoEquipo.fecha_inicio == hoy
        ).count()
        
        reservas_hoy = Reserva.query.filter(
            Reserva.fecha == hoy
        ).count()
        
        return {
            'prestamos': prestamos_hoy,
            'reservas': reservas_hoy
        }
    
    @staticmethod
    def invalidar_resumen():
        """Invalida caché (llamar cuando haya cambios)."""
        from extensions import cache
        cache.delete('EstadisticasService.obtener_resumen_hoy')


# blueprints/prestamos.py - Invalidar después de crear
@prestamos_bp.route('/crear', methods=['POST'])
def crear_prestamo():
    """Crea préstamo e invalida caché."""
    try:
        # ... código de creación ...
        db.session.commit()
        
        # Invalidar caché de estadísticas
        from services.estadisticas_service import EstadisticasService
        EstadisticasService.invalidar_resumen()
        
        flash('Préstamo creado', 'success')
    except Exception as e:
        pass
```

---

## 4. Reducir Tamaño de Sesión

```python
# ❌ MALO - Guardar datos grandes en sesión
session['sedes'] = Sede.query.all()  # Serializa lista completa

# ✅ BUENO - Guardar solo IDs/mínimo dato
session['sede_id'] = usuario.sede_id
session['permisos'] = ['prestamos', 'reservas']  # Solo nombres
```

---

## 5. Comprimir Assets Estáticos

```python
# requirements.txt
flask-compress>=1.13

# app.py
from flask_compress import Compress
Compress(app)

# Beneficio: CSS/JS se comprimen automáticamente
# Reducción: 70-80% de tamaño
```

---

## 6. CDN para Assets Estáticos (Opcional)

```html
<!-- templates/base.html -->

<!-- ❌ ANTES - Servir localmente -->
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">

<!-- ✅ DESPUÉS - Con CDN (ej: CloudFront) -->
{% if config.ENV == 'production' %}
    <link rel="stylesheet" href="https://cdn.uniminuto.edu/css/style.css">
{% else %}
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
{% endif %}
```

---

## 7. Estrategia de Caché por Tipo de Dato

| Dato | Caché | TTL | Invalidar |
|------|-------|-----|-----------|
| Permisos | Redis | 1h | Al cambiar |
| Constantes | Redis | 24h | Manual |
| Estadísticas | Redis | 30min | Al crear registro |
| Sedes/Bodegas | Redis | 6h | Manual |
| Sesión Usuario | Cookie | 8h | Logout |

---

## ✅ Implementación Rápida

```bash
# 1. Instalar
pip install flask-caching redis flask-compress

# 2. Configurar en config.py
CACHE_TYPE = 'redis'

# 3. Inicializar en extensions.py
cache = Cache()

# 4. Usar en servicios
@cache.cached(timeout=3600)
def funcion():
    pass

# 5. Invalidar cuando sea necesario
cache.delete('key')
```

---

## Impacto Esperado

| Métrica | Antes | Después | Mejora |
|---------|-------|---------|--------|
| Queries permisos | 100+ | 1 | **-99%** |
| Tiempo carga | 500ms | 100ms | **5x** |
| BD CPU | Alto | Bajo | **Significativa** |
| Escalabilidad | 100 users | 1000+ users | **10x** |

---

**Guía de Caché y Performance**  
ROI: Alto | Implementación: 3-4 horas | Impacto: Crítico
