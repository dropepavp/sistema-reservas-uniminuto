# 🗄️ Optimización de Base de Datos - Índices y Queries

## Estado Actual

```python
# database.py - Algunos índices existen, pero muchos faltan

class Inventario(db.Model):
    __tablename__ = 'inventario'
    categoria: Mapped[str] = mapped_column(String, index=True)
    item: Mapped[str] = mapped_column(String, index=True)
    numero_inventario: Mapped[str] = mapped_column(
        String, nullable=True, unique=True, index=True
    )
    # ❌ FALTAN índices en: estado, bodega_id, fecha_creacion
```

---

## 1. Índices Faltantes Críticos

### Análisis de Queries Comunes

```python
# QUERY 1: Listar préstamos activos
PrestamoEquipo.query.filter_by(estado='Activo').all()
# ❌ Sin índice en 'estado' = full table scan

# QUERY 2: Buscar por profesor
PrestamoEquipo.query.filter_by(cedula_profesor='123').all()
# ❌ Sin índice en 'cedula_profesor' = full table scan

# QUERY 3: Filtrar por fecha
Reserva.query.filter(Reserva.fecha >= hoy).all()
# ❌ Sin índice en 'fecha' = full table scan

# QUERY 4: Filtrar por sede
Inventario.query.filter_by(bodega_id=1).all()
# ✅ Tiene índice (FK)
```

### Solución: Agregar Índices

```python
# database.py - Actualizar modelos

class PrestamoEquipo(db.Model):
    __tablename__ = 'prestamos_equipos'
    
    # ... columnas existentes ...
    estado: Mapped[str] = mapped_column(
        String, 
        index=True  # ✅ NUEVO - Índice en estado
    )
    cedula_profesor: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('profesores.cedula'),
        index=True  # ✅ NUEVO - Índice en cédula
    )
    fecha_inicio: Mapped[date] = mapped_column(
        Date,
        index=True  # ✅ NUEVO - Índice en fecha
    )
    fecha_devolucion: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        index=True  # ✅ NUEVO
    )
    usuario_id: Mapped[Optional[str]] = mapped_column(
        String,
        index=True  # ✅ NUEVO - Para filtrar por usuario
    )
    # Índice compuesto para búsquedas frecuentes
    __table_args__ = (
        Index('idx_prestamo_estado_fecha', 'estado', 'fecha_inicio'),
        Index('idx_prestamo_profesor_estado', 'cedula_profesor', 'estado'),
    )


class Reserva(db.Model):
    __tablename__ = 'reservas'
    
    # ... columnas existentes ...
    estado: Mapped[str] = mapped_column(
        String,
        index=True  # ✅ NUEVO
    )
    fecha: Mapped[date] = mapped_column(
        Date,
        index=True  # ✅ NUEVO
    )
    sede_id: Mapped[int] = mapped_column(
        ForeignKey('sedes.id'),
        index=True  # ✅ NUEVO
    )
    cedula_profesor: Mapped[int] = mapped_column(
        Integer,
        index=True  # ✅ NUEVO
    )
    __table_args__ = (
        Index('idx_reserva_fecha_sede', 'fecha', 'sede_id'),
        Index('idx_reserva_profesor_estado', 'cedula_profesor', 'estado'),
    )


class Inventario(db.Model):
    __tablename__ = 'inventario'
    
    # ... columnas existentes ...
    estado: Mapped[str] = mapped_column(
        String,
        index=True  # ✅ NUEVO
    )
    bodega_id: Mapped[int] = mapped_column(
        ForeignKey('bodegas.id'),
        index=True  # ✅ YA EXISTE por FK
    )
    categoria: Mapped[str] = mapped_column(
        String,
        index=True  # ✅ YA EXISTE
    )
    # Índice compuesto para búsquedas por estado y bodega
    __table_args__ = (
        Index('idx_inventario_estado_bodega', 'estado', 'bodega_id'),
    )


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    # ... columnas existentes ...
    usuario_documento: Mapped[str] = mapped_column(
        String,
        index=True  # ✅ NUEVO - Filtrar por usuario
    )
    fecha_cambio: Mapped[datetime] = mapped_column(
        DateTime,
        index=True  # ✅ NUEVO - Filtrar por rango de fechas
    )
    modulo: Mapped[str] = mapped_column(
        String,
        index=True  # ✅ NUEVO
    )
    __table_args__ = (
        Index('idx_auditlog_usuario_fecha', 'usuario_documento', 'fecha_cambio'),
    )
```

---

## 2. Crear Migración Alembic

```bash
# Generar migración
flask db migrate -m "Agregar índices para optimización"

# Revisar archivo generado en migrations/versions/
# Debe contener:
# - Index('idx_prestamo_estado_fecha', 'estado', 'fecha_inicio')
# - Index('idx_prestamo_profesor_estado', 'cedula_profesor', 'estado')
# etc.

# Aplicar migración
flask db upgrade

# Validar en PostgreSQL
\d prestamos_equipos
# Debería mostrar los nuevos índices
```

---

## 3. Análisis de Performance - EXPLAIN PLAN

```sql
-- PostgreSQL - Verificar si la query usa el índice

EXPLAIN ANALYZE
SELECT * FROM prestamos_equipos
WHERE estado = 'Activo'
AND fecha_inicio >= '2026-08-14';

-- ✅ Si usa índice, debería mostrar:
-- Bitmap Index Scan on idx_prestamo_estado_fecha
-- Filter: (fecha_inicio >= '2026-08-14'::date)

-- ❌ Si hace full scan:
-- Seq Scan on prestamos_equipos
-- Filter: (estado = 'Activo'::text) AND ...
```

---

## 4. Índices Compuestos (Multi-columna)

### Cuándo Usarlos

```python
# Query común:
PrestamoEquipo.query.filter(
    PrestamoEquipo.estado == 'Activo',
    PrestamoEquipo.fecha_inicio >= hoy
).all()

# ✅ Crear índice compuesto
Index('idx_prestamo_estado_fecha', 'estado', 'fecha_inicio')

# Orden importa:
# - Poner primero el que filtra más (estado)
# - Luego el que filtra menos (fecha)
```

### Mejores Prácticas

```python
# ✅ BUENO - Coincide con WHERE clause
Index('idx_prestamo_estado_fecha', 'estado', 'fecha_inicio')
# query: WHERE estado = ? AND fecha_inicio >= ?

# ❌ MALO - Orden inverso
Index('idx_prestamo_fecha_estado', 'fecha_inicio', 'estado')
# query: WHERE estado = ? AND fecha_inicio >= ?
# No usa el índice eficientemente

# ✅ MEJOR - Incluir columnas del SELECT
Index('idx_prestamo_estado_fecha_id', 'estado', 'fecha_inicio', 'id')
# Si el query solo necesita id, estado, fecha: "index-only scan"
```

---

## 5. Monitoreo de Índices

```python
# services/database_service.py - Script de análisis

class DatabaseService:
    """Servicio para monitoreo de BD."""
    
    @staticmethod
    def get_slow_queries():
        """Obtiene queries lentas (> 100ms)."""
        from flask import current_app
        from database import db
        
        # PostgreSQL
        query = """
        SELECT query, calls, mean_exec_time
        FROM pg_stat_statements
        WHERE mean_exec_time > 100
        ORDER BY mean_exec_time DESC
        LIMIT 10;
        """
        
        result = db.session.execute(query)
        return result.fetchall()
    
    @staticmethod
    def get_unused_indexes():
        """Obtiene índices no utilizados (para eliminarlos)."""
        from database import db
        
        query = """
        SELECT indexname, idx_scan
        FROM pg_stat_user_indexes
        WHERE idx_scan = 0
        ORDER BY pg_relation_size(indexrelid) DESC;
        """
        
        result = db.session.execute(query)
        return result.fetchall()
    
    @staticmethod
    def analyze_table(table_name):
        """Analiza tabla para optimizar caché del query planner."""
        from database import db
        
        db.session.execute(f"ANALYZE {table_name};")
        db.session.commit()


# blueprints/admin.py - Panel de diagnóstico
@admin_bp.route('/diagnostico/bd')
@admin_required
def diagnostico_bd():
    """Panel de diagnóstico de BD."""
    from services.database_service import DatabaseService
    
    slow_queries = DatabaseService.get_slow_queries()
    unused_indexes = DatabaseService.get_unused_indexes()
    
    return render_template('admin/diagnostico_bd.html',
        slow_queries=slow_queries,
        unused_indexes=unused_indexes
    )
```

---

## 6. Configuración de PostgreSQL

```ini
# postgresql.conf - Optimizaciones

# Caché de queries
shared_buffers = 256MB          # 25% RAM disponible
effective_cache_size = 1GB      # 50-75% RAM disponible
work_mem = 64MB                 # RAM por operación
maintenance_work_mem = 64MB

# Query Planner
random_page_cost = 1.1          # Para SSD
effective_io_concurrency = 200  # Para SSD

# Logging
log_statement = 'all'           # Log todas las queries
log_duration = true             # Log tiempo ejecución
log_min_duration_statement = 100 # Solo > 100ms
```

---

## 7. Checklist de Índices

```
Tabla: prestamos_equipos
- [x] estado (individual)
- [x] cedula_profesor (individual)
- [x] fecha_inicio (individual)
- [x] fecha_devolucion (individual)
- [x] usuario_id (individual)
- [x] (estado, fecha_inicio) - compuesto
- [x] (cedula_profesor, estado) - compuesto

Tabla: reservas
- [x] estado (individual)
- [x] fecha (individual)
- [x] sede_id (individual)
- [x] cedula_profesor (individual)
- [x] (fecha, sede_id) - compuesto
- [x] (cedula_profesor, estado) - compuesto

Tabla: inventario
- [x] estado (individual)
- [x] categoria (individual)
- [x] numero_inventario (único)
- [x] bodega_id (FK)
- [x] (estado, bodega_id) - compuesto

Tabla: audit_logs
- [x] usuario_documento (individual)
- [x] fecha_cambio (individual)
- [x] modulo (individual)
- [x] (usuario_documento, fecha_cambio) - compuesto
```

---

## 8. Impacto Esperado

| Scenario | Sin Índices | Con Índices | Mejora |
|----------|------------|------------|--------|
| Listar 100 prestamos | 250ms | 5ms | **50x** ⚡ |
| Filtrar por profesor | 300ms | 8ms | **37x** ⚡ |
| Buscar por rango fechas | 400ms | 10ms | **40x** ⚡ |
| Listar auditoría (10k) | 1000ms | 20ms | **50x** ⚡ |
| Inserción (con índices) | 10ms | 15ms | -33% (trade-off) |

**Trade-off:** Inserciones ligeramente más lentas (15ms vs 10ms) pero MUCHO más rápidas lecturas.

---

## ✅ Plan de Implementación

```bash
# 1. Revisar models en database.py
# 2. Agregar índices a modelos
# 3. Generar migración
# 4. Probar en desarrollo
# 5. Medir performance con EXPLAIN
# 6. Aplicar en producción
# 7. Monitorear con DatabaseService

# Tiempo estimado: 3-4 horas
```

---

**Guía de Índices y Optimización BD**  
ROI: Muy Alto | Impacto: Crítico | Complejidad: Media
