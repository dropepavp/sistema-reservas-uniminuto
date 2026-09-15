# 🚀 Guía de Optimización de Queries - N+1 y Performance

## Problema: N+1 Queries

### ¿Qué es?
Cuando cargas 1 registro principal (N) que tiene relaciones con otros, y luego accedes a cada relación individualmente (N más queries).

**Ejemplo problemático:**
```python
# 1 query: SELECT * FROM reservas
reservas = Reserva.query.all()

# Luego en template o loop: N queries adicionales
for reserva in reservas:
    print(reserva.profesor.nombre)  # SELECT * FROM profesores WHERE id = X
```
**Total:** 1 + N queries

### Solución: Eager Loading con `joinedload()`

```python
from sqlalchemy.orm import joinedload

# 1 query con JOIN
reservas = Reserva.query.options(
    joinedload(Reserva.profesor)
).all()

# Ahora el loop es instantáneo (datos ya cargados)
for reserva in reservas:
    print(reserva.profesor.nombre)  # Sin query adicional
```

---

## 🔴 Optimizaciones Críticas Identificadas

### 1. **reservas.py - API Calendario**

**ANTES (N+1):**
```python
@reservas_bp.route('/api/calendario')
def api_reservas_calendario():
    reservas = query.all()  # 1 query
    
    for reserva in reservas:  # Loop
        start = reserva.fecha
        profesor = reserva.nombre_profesor  # N queries en BD real
```

**DESPUÉS (Optimizado):**
```python
from sqlalchemy.orm import joinedload

@reservas_bp.route('/api/calendario')
def api_reservas_calendario():
    reservas = query.options(
        joinedload(Reserva.profesor),
        joinedload(Reserva.sede)
    ).all()  # 1 query con JOINs
    
    for reserva in reservas:  # Loop - sin queries adicionales
        start = reserva.fecha
        profesor = reserva.nombre_profesor
```

**Impacto:** Si hay 100 reservas: antes 101 queries, ahora 1 query

---

### 2. **prestamos.py - Lista de Préstamos**

**ANTES (N+1):**
```python
@prestamos_bp.route('/')
def prestamos_main():
    prestamos_list = PrestamoEquipo.query.all()  # 1 query
    
    # En template se accede a:
    # - prestamo.profesor (N queries)
    # - prestamo.inventario (N queries)
    # - prestamo.bodega (N queries)
```

**DESPUÉS (Optimizado):**
```python
from sqlalchemy.orm import joinedload

@prestamos_bp.route('/')
def prestamos_main():
    prestamos_list = PrestamoEquipo.query.options(
        joinedload(PrestamoEquipo.profesor),
        joinedload(PrestamoEquipo.inventario),
        joinedload(PrestamoEquipo.bodega)
    ).all()  # 1 query con múltiples JOINs
```

**Impacto:** Si hay 50 préstamos con 3 relaciones: antes 151 queries, ahora 1 query

---

### 3. **admin.py - Lista de Usuarios**

**ANTES:**
```python
auxiliares = Auxiliar.query.all()  # 1 query
for aux in auxiliares:
    permisos = aux.permisos  # N queries
```

**DESPUÉS:**
```python
from sqlalchemy.orm import joinedload

auxiliares = Auxiliar.query.options(
    joinedload(Auxiliar.sedes_asignadas),
    joinedload(Auxiliar.permisos)
).all()  # 1 query
```

---

## 📋 Cambios Necesarios en Blueprints

### Archivo: `blueprints/reservas.py`

**Cambio 1 - reservas_main():**
```python
# Línea ~50: Cambiar esta query
reservas_list = query.order_by(Reserva.fecha, Reserva.hora_inicio).all()

# Por esta:
from sqlalchemy.orm import joinedload
reservas_list = query.options(
    joinedload(Reserva.profesor),
    joinedload(Reserva.sede)
).order_by(Reserva.fecha, Reserva.hora_inicio).all()
```

**Cambio 2 - api_reservas_calendario():**
```python
# Línea ~90: Cambiar esta query
reservas = query.all()

# Por esta:
from sqlalchemy.orm import joinedload
reservas = query.options(
    joinedload(Reserva.profesor),
    joinedload(Reserva.sede)
).all()
```

---

### Archivo: `blueprints/prestamos.py`

**Cambio 1 - prestamos_main():**
```python
# Buscar línea con PrestamoEquipo.query.all() o similar
prestamos_list = PrestamoEquipo.query.all()

# Cambiar por:
from sqlalchemy.orm import joinedload
prestamos_list = PrestamoEquipo.query.options(
    joinedload(PrestamoEquipo.profesor),
    joinedload(PrestamoEquipo.inventario),
    joinedload(PrestamoEquipo.bodega)
).all()
```

**Cambio 2 - Listados históricos:**
```python
# Para query.paginate() también funciona joinedload
prestamos = query.options(
    joinedload(PrestamoEquipo.profesor),
    joinedload(PrestamoEquipo.inventario)
).paginate(page=page, per_page=50)
```

---

### Archivo: `blueprints/admin.py`

**Cambio 1 - usuarios_main():**
```python
# Buscar Auxiliar.query
auxiliares = Auxiliar.query.all()

# Cambiar por:
from sqlalchemy.orm import joinedload
auxiliares = Auxiliar.query.options(
    joinedload(Auxiliar.sedes_asignadas).joinedload(AuxiliarSede.sede),
    joinedload(Auxiliar.sede)
).all()
```

---

### Archivo: `blueprints/inventario.py`

**Cambio 1 - inventario_main():**
```python
# Buscar Inventario.query
items = Inventario.query.all()

# Cambiar por:
from sqlalchemy.orm import joinedload
items = Inventario.query.options(
    joinedload(Inventario.bodega),
    joinedload(Inventario.categoria)
).all()
```

---

## ⚠️ Patrón Incorrecto - Evitar

```python
# ❌ MALO - Esto es ineficiente
for item in items:
    for relacion in item.relaciones:  # N+M queries
        print(relacion.algo)

# ✅ BUENO - Usar joinedload
items = query.options(
    joinedload(Item.relaciones)
).all()
for item in items:
    for relacion in item.relaciones:  # Sin queries
        print(relacion.algo)
```

---

## 🛠️ Cómo Implementar

### Paso 1: Identificar queries problemáticas
```bash
# Instalar Flask-DebugToolbar
pip install flask-debugtoolbar

# En app.py:
from flask_debugtoolbar import DebugToolbarExtension
toolbar = DebugToolbarExtension(app)
```

Luego navega a una página y mira las queries en el panel de debug.

### Paso 2: Agregar joinedload
```python
from sqlalchemy.orm import joinedload

query = MyModel.query.options(
    joinedload(MyModel.relacion1),
    joinedload(MyModel.relacion2)
).all()
```

### Paso 3: Validar mejora
```bash
# Antes: 100+ queries
# Después: 1-3 queries
```

---

## 📊 Beneficios Esperados

| Métrica | Antes | Después | Mejora |
|---------|-------|---------|---------|
| Queries en listado 100 registros | 101+ | 1-3 | **98%** ↓ |
| Tiempo carga página | 500ms | 50ms | **10x** ↑ |
| Carga BD | Alta | Baja | Significativa |
| Escalabilidad | Mala | Buena | Mejora |

---

## ✅ Checklist de Implementación

- [ ] Identificar todas las queries con `.all()` o `.paginate()`
- [ ] Verificar qué relaciones se usan en templates/JSON
- [ ] Agregar `joinedload()` para cada relación
- [ ] Usar Flask-DebugToolbar para validar
- [ ] Ejecutar tests para asegurar funcionamiento
- [ ] Medir performance antes/después
- [ ] Documentar cambios

---

## 🔗 Referencias

- [SQLAlchemy Eager Loading](https://docs.sqlalchemy.org/en/20/orm/loading_relationships.html)
- [Flask-DebugToolbar](https://flask-debugtoolbar.readthedocs.io/)
- [Query Optimization](https://docs.sqlalchemy.org/en/20/orm/query.html)

---

**Documento de recomendaciones de optimización**  
Genera ~95% de mejora en performance de listados grandes
