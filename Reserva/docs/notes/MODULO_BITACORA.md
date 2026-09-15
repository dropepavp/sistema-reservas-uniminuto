# 📋 Módulo de Bitácora de Movimientos

## Descripción General

El módulo de **Bitácora** registra y permite auditar todos los cambios realizados en el sistema por cada uno de los auxiliares/usuarios. Proporciona una trazabilidad completa de quién hizo qué, cuándo y qué cambió exactamente.

---

## 🎯 Características Principales

### 1. **Dashboard Central de Auditoría**
- **URL:** `/bitacora/`
- **Acceso:** Solo administradores
- **Funcionalidades:**
  - Visualización de todos los registros ordenados por fecha descendente
  - Filtros avanzados:
    - Por módulo (Préstamos, Reservas, Inventario, Profesores, Admin, Auth)
    - Por usuario (auxiliar específico)
    - Por tipo de acción (CREAR, EDITAR, ELIMINAR, DEVOLVER, CANCELAR, LOGIN, LOGOUT)
    - Por rango de fechas
  - Paginación de 50 registros por página
  - Búsqueda rápida de registros específicos

> 🔐 El sistema ahora también registra inicios/cierres de sesión bajo el módulo `auth`.
### 2. **Vista Detallada de Registros**
- **URL:** `/bitacora/detalles/<id>`
- **Muestra:**
  - Información completa del cambio realizado
  - Datos ANTES del cambio
  - Datos DESPUÉS del cambio
  - Diferencias lado a lado
  - Metadatos del movimiento (usuario, fecha, hora)

### 3. **Historial por Usuario**
- **URL:** `/bitacora/usuario/<documento>`
- **Información:**
  - Todos los movimientos de un usuario específico
  - Estadísticas:
    - Total de acciones realizadas
    - Módulos en los que participa
    - Tipos de acciones más frecuentes
  - Tabla detallada con acceso a detalles individuales

### 4. **Historial por Módulo**
- **URL:** `/bitacora/modulo/<modulo>`
- **Información:**
  - Todos los cambios en un módulo específico
  - Estadísticas:
    - Total de cambios en el módulo
    - Usuarios más activos en ese módulo
    - Tipos de acciones más frecuentes
  - Análisis de tendencias

### 5. **API de Estadísticas**
- **URL:** `/bitacora/api/estadisticas`
- **Método:** GET
- **Respuesta:** JSON con:
  - Total de registros en el sistema
  - Registros de los últimos 30 días
  - Distribución por módulo
  - Distribución por tipo de acción
  - Top 10 usuarios más activos
  - Tendencias de los últimos 7 días

---

## 🔧 Integración en los Módulos

### Usando el Helper de Auditoría

Para facilitar el registro de cambios, use la clase `AuditoriaHelper` del archivo `services/auditoria.py`:

#### Ejemplo 1: Registrar Creación de Préstamo

```python
from services.auditoria import AuditoriaHelper

@prestamos_bp.route('/crear', methods=['POST'])
def crear_prestamo():
    # ... código de creación ...
    prestamo = PrestamoEquipo(...)
    db.session.add(prestamo)
    db.session.commit()
    
    # Registrar auditoría
    AuditoriaHelper.registrar_creacion(
        modulo='prestamos',
        entidad_tipo='PrestamoEquipo',
        entidad_id=prestamo.id_prestamo,
        descripcion=f"Nuevo préstamo de {prestamo.equipo_prestado} a {prestamo.nombre_profesor}",
        datos={
            'profesor': prestamo.nombre_profesor,
            'equipo': prestamo.equipo_prestado,
            'fecha': str(prestamo.fecha_prestamo)
        }
    )
```

#### Ejemplo 2: Registrar Edición de Inventario

```python
from services.auditoria import AuditoriaHelper

@inventario_bp.route('/editar/<int:id>', methods=['POST'])
def editar_inventario(id):
    item = Inventario.query.get_or_404(id)
    
    # Guardar estado anterior
    datos_antes = {
        'estado': item.estado,
        'ubicacion': item.ubicacion_permanente
    }
    
    # Actualizar
    item.estado = request.form.get('estado')
    item.ubicacion_permanente = request.form.get('ubicacion')
    db.session.commit()
    
    # Registrar auditoría
    AuditoriaHelper.registrar_edicion(
        modulo='inventario',
        entidad_tipo='Inventario',
        entidad_id=item.id,
        descripcion=f"Se editó equipo: {item.item}",
        datos_antes=datos_antes,
        datos_despues={
            'estado': item.estado,
            'ubicacion': item.ubicacion_permanente
        }
    )
```

#### Ejemplo 3: Registrar Acción Especial (Devolución)

```python
from services.auditoria import AuditoriaHelper
from datetime import date

@prestamos_bp.route('/devolver/<int:id>', methods=['POST'])
def devolver_prestamo(id):
    prestamo = PrestamoEquipo.query.get_or_404(id)
    
    # Cambiar estado
    prestamo.estado = 'Devuelto'
    prestamo.fecha_devolucion = date.today()
    db.session.commit()
    
    # Registrar como acción especial
    AuditoriaHelper.registrar_accion_personalizada(
        modulo='prestamos',
        entidad_tipo='PrestamoEquipo',
        entidad_id=prestamo.id_prestamo,
        accion='DEVOLVER',
        descripcion=f"Devolución de {prestamo.equipo_prestado} del profesor {prestamo.nombre_profesor}",
        datos_despues={
            'estado': prestamo.estado,
            'fecha_devolucion': str(prestamo.fecha_devolucion)
        }
    )
```

---

## 📊 Estructura de Datos en la Bitácora

Cada registro en `AuditLog` contiene:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | Integer (PK) | Identificador único |
| `modulo` | String | Módulo afectado (prestamos, inventario, etc) |
| `entidad_tipo` | String | Tipo de entidad (PrestamoEquipo, Inventario, etc) |
| `entidad_id` | String | ID de la entidad específica |
| `accion` | String | CREAR, EDITAR, ELIMINAR, DEVOLVER, CANCELAR, etc |
| `usuario_documento` | String | Documento del usuario que realizó el cambio |
| `usuario_nombre` | String | Nombre del usuario (denormalizado) |
| `fecha` | Date | Fecha del cambio |
| `hora` | Time | Hora exacta del cambio |
| `descripcion` | Text | Descripción legible del cambio |
| `datos_antes` | Text (JSON) | Estado anterior (antes del cambio) |
| `datos_despues` | Text (JSON) | Estado nuevo (después del cambio) |

---

## 🔍 Casos de Uso

### 1. **Auditoría de Permisos**
Verificar qué cambios realizó un auxiliar específico:
- Ir a `/bitacora/usuario/<documento>`
- Ver todas las acciones con fecha/hora exacta
- Clic en detalles para ver qué cambió

### 2. **Investigación de Problemas**
Si un equipo desapareció o cambió de estado incorrectamente:
- Ir a `/bitacora/modulo/inventario`
- Buscar el equipo específico
- Ver todos los cambios registrados
- Identificar quién y cuándo hizo el cambio

### 3. **Reportes de Cumplimiento**
Generar reportes de auditoría para cumplimiento normativo:
- Usar los filtros de fecha
- Filtrar por módulo o usuario
- Exportar los datos (futura mejora)

### 4. **Análisis de Actividad**
Entender patrones de uso:
- API `/bitacora/api/estadisticas` proporciona:
  - Usuarios más activos
  - Módulos más usados
  - Tendencias de cambios

---

## 🚀 Activación en Módulos Existentes

### Checklist para Integrar Bitácora

Para cada módulo que maneje datos modificables:

- [ ] Importar `from services.auditoria import AuditoriaHelper`
- [ ] En rutas de creación: llamar `AuditoriaHelper.registrar_creacion()`
- [ ] En rutas de edición: llamar `AuditoriaHelper.registrar_edicion()`
- [ ] En rutas de eliminación: llamar `AuditoriaHelper.registrar_eliminacion()`
- [ ] En acciones especiales: llamar `AuditoriaHelper.registrar_accion_personalizada()`

### Módulos Prioritarios

1. **Préstamos** (prestamos_bp) - cambios de estado, devoluciones
2. **Profesores** (profesores_bp) - creación, edición, eliminación
3. **Inventario** (inventario_bp) - cambios de estado, ubicación
4. **Reservas** (reservas_bp) - creación, cancelación
5. **Admin** (admin_bp) - cambios de permisos, usuarios

---

## 📝 Acceso a la Bitácora

### Desde la Interfaz
- **Navbar:** Enlace "Bitácora" (solo visible para admin)
- **Dashboard:** Dashboard principal de auditoría

### Acceso Programático
```python
from database import AuditLog

# Consultar últimos cambios
logs = AuditLog.query.order_by(AuditLog.fecha.desc()).limit(10).all()

# Filtrar por usuario
logs_usuario = AuditLog.query.filter_by(usuario_documento='123456').all()

# Filtrar por módulo
logs_prestamos = AuditLog.query.filter_by(modulo='prestamos').all()

# Rango de fechas
from datetime import date, timedelta
logs_semana = AuditLog.query.filter(
    AuditLog.fecha >= date.today() - timedelta(days=7)
).all()
```

---

## � Exportación de Reportes

El dashboard incluye botones para exportar los resultados actuales a **Excel**, **CSV** o **PDF**. Los enlaces respetan los filtros aplicados (y se pueden invocar manualmente con parámetros GET).

**Rutas:**
- `GET /bitacora/export/excel`
- `GET /bitacora/export/csv`
- `GET /bitacora/export/pdf`

Los parámetros de filtro son los mismos que los del dashboard: `modulo`, `usuario`, `accion`, `fecha_inicio`, `fecha_fin`.

## ⏰ Informes periódicos y alertas

Se puede programar el script `scripts/alert_report.py` con cron/Task Scheduler para generar y enviar automáticamente un archivo Excel con la bitácora a los correos configurados en `ADMIN_EMAILS`.

Ejemplo de crontab:

```
0 6 * * * /path/to/venv/bin/python /path/to/Proyecto/Reserva/scripts/alert_report.py
```

El mismo servicio de alertas (`services/alert_service.py`) también permite comprobar préstamos vencidos y reservas próximas; estas verificaciones son invocadas en la ruta principal (`/`) para desplegar avisos en pantalla, y se puede configurar el envío de correo electrónico con `SMTP_*` en `config.py`.

## 🔔 Notificaciones en tiempo real

El servidor inicializa un `Socket.IO` simple y emite eventos cuando se crean reservas (`nueva_reserva`) o se modifican elementos del inventario (`inventario_cambiado`). Un pequeño script incluido en el footer de todas las páginas escucha estas señales y muestra un `alert()` básico; se puede extender con toasts o una UI más elaborada.

## �🔐 Seguridad y Permisos

- **Solo administradores** pueden acceder a la bitácora
- Los datos registrados son **inmutables** (solo lectura)
- Incluye metadata del usuario que realizó el cambio
- Captura fecha y hora exactas con precisión de segundos

---

## 🚀 Mejoras Futuras

- [ ] Restauración de versiones anteriores (undo)
- [ ] Alertas automáticas para cambios críticos
- [ ] Integración con SIEM para análisis de seguridad
- [ ] Compresión automática de registros antiguos
- [ ] Dashboard de tendencias más avanzado

---

## 📚 Archivos Relacionados

- **Blueprint:** `blueprints/bitacora.py`
- **Helper de Auditoría:** `services/auditoria.py`
- **Modelo de Base de Datos:** `database.py` (modelo `AuditLog`)
- **Plantillas:** `templates/bitacora/`
  - `dashboard.html` - Panel principal
  - `detalles.html` - Detalles de un registro
  - `movimientos_usuario.html` - Historial de usuario
  - `movimientos_modulo.html` - Historial de módulo

---

## 💡 Tips de Uso

1. **Búsqueda Avanzada:** Use múltiples filtros a la vez para búsquedas más precisas
2. **Detalles de Cambios:** Haga clic en el ícono 👁️ para ver exactamente qué cambió
3. **Seguimiento de Usuario:** Haga clic en el nombre del usuario para ver todo su historial
4. **Seguimiento de Módulo:** Haga clic en el módulo para ver actividad del módulo completo
5. **Análisis de Tendencias:** Use la API `/bitacora/api/estadisticas` para obtener datos en JSON

---

**Última actualización:** 26 de febrero de 2026
**Versión:** 1.0
