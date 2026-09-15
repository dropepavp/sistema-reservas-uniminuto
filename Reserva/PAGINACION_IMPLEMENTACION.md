# 📄 Guía de Implementación de Paginación

## ¿Por qué Paginar?

### Problema Actual
```python
# ❌ Carga TODOS los registros en memoria
prestamos = PrestamoEquipo.query.all()  # Si hay 10,000 registros = muy lento
```

### Beneficios de Paginar
- ✅ Carga solo 50 registros por página
- ✅ Interfaz más rápida
- ✅ Menor uso de memoria
- ✅ Mejor UX (navegación intuitiva)
- ✅ Escalable a millones de registros

---

## Implementación en Flask-SQLAlchemy

### Sintaxis Básica

```python
# Query con paginación
page = request.args.get('page', 1, type=int)
per_page = 50

paginated = PrestamoEquipo.query.paginate(
    page=page,
    per_page=per_page,
    error_out=False  # No lanzar error si página no existe
)

# Acceder a los datos
items = paginated.items          # Lista de registros
total = paginated.total          # Total de registros
pages = paginated.pages          # Número de páginas
has_next = paginated.has_next    # ¿Hay página siguiente?
has_prev = paginated.has_prev    # ¿Hay página anterior?
```

---

## Ejemplos Prácticos

### Ejemplo 1: Préstamos con Paginación

**Archivo: `blueprints/prestamos.py`**

```python
@prestamos_bp.route('/')
@login_required
@permiso_requerido('prestamos', 'ver')
def prestamos_main():
    """Página principal con lista paginada de préstamos."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Query con optimización
        from sqlalchemy.orm import joinedload
        query = PrestamoEquipo.query.options(
            joinedload(PrestamoEquipo.profesor),
            joinedload(PrestamoEquipo.inventario)
        )
        
        # Agregar filtros según rolVOLE
        if session.get('rol') not in ('admin', 'superadmin'):
            query = query.filter_by(usuario_id=session.get('usuario'))
        
        # Ordenar y paginar
        paginated = query.order_by(
            PrestamoEquipo.fecha_inicio.desc()
        ).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return render_template(
            'prestamos.html',
            items=paginated.items,
            page=page,
            pages=paginated.pages,
            total=paginated.total,
            has_next=paginated.has_next,
            has_prev=paginated.has_prev,
            next_page=paginated.next_num,
            prev_page=paginated.prev_num
        )
    except Exception as e:
        current_app.logger.error(f"Error: {e}")
        flash('Error al cargar préstamos', 'danger')
        return render_template('prestamos.html', items=[], page=1, pages=0)
```

### Ejemplo 2: Reservas Paginadas

**Archivo: `blueprints/reservas.py`**

```python
@reservas_bp.route('/')
@login_required
@permiso_requerido('reservas', 'ver')
def reservas_main():
    """Página de reservas con paginación."""
    page = request.args.get('page', 1, type=int)
    per_page = 30  # Menos por página que prestamos
    
    from sqlalchemy.orm import joinedload
    from sqlalchemy import and_
    
    # Filtrar solo reservas futuras
    hoy = date.today()
    query = Reserva.query.filter(
        and_(
            Reserva.estado == 'activa',
            Reserva.fecha >= hoy
        )
    ).options(
        joinedload(Reserva.profesor),
        joinedload(Reserva.sede)
    )
    
    # Paginación
    paginated = query.order_by(
        Reserva.fecha.asc()
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    return render_template(
        'reservas.html',
        reservas=paginated.items,
        pagination=paginated
    )
```

### Ejemplo 3: Inventario Paginado con Búsqueda

**Archivo: `blueprints/inventario.py`**

```python
@inventario_bp.route('/')
@login_required
def inventario_main():
    """Inventario con paginación y búsqueda."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    per_page = 50
    
    from sqlalchemy.orm import joinedload
    from sqlalchemy import or_
    
    query = Inventario.query.options(
        joinedload(Inventario.bodega),
        joinedload(Inventario.categoria)
    )
    
    # Búsqueda
    if search:
        query = query.filter(
            or_(
                Inventario.item.ilike(f'%{search}%'),
                Inventario.numero_inventario.ilike(f'%{search}%'),
                Inventario.serial.ilike(f'%{search}%')
            )
        )
    
    # Paginación
    paginated = query.order_by(
        Inventario.numero_inventario.desc()
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    return render_template(
        'inventario.html',
        items=paginated.items,
        search=search,
        pagination=paginated
    )
```

---

## Template Jinja2 - Mostrar Paginación

### Patrón HTML Estándar

```html
<!-- Tabla con datos paginados -->
<div class="table-container">
    <table class="table">
        <thead>
            <tr>
                <th>Descripción</th>
                <th>Cantidad</th>
                <th>Acciones</th>
            </tr>
        </thead>
        <tbody>
            {% for item in items %}
                <tr>
                    <td>{{ item.nombre }}</td>
                    <td>{{ item.cantidad }}</td>
                    <td>
                        <a href="{{ url_for('editar', id=item.id) }}" 
                           class="btn btn-sm btn-primary">Editar</a>
                    </td>
                </tr>
            {% else %}
                <tr>
                    <td colspan="3" class="text-center">No hay registros</td>
                </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<!-- Controles de paginación -->
<nav aria-label="Page navigation">
    <ul class="pagination justify-content-center">
        
        <!-- Anterior -->
        {% if has_prev %}
            <li class="page-item">
                <a class="page-link" href="{{ url_for(request.endpoint, page=prev_page) }}">
                    ← Anterior
                </a>
            </li>
        {% else %}
            <li class="page-item disabled">
                <span class="page-link">← Anterior</span>
            </li>
        {% endif %}
        
        <!-- Números de página -->
        {% for p in pagination.iter_pages(left_edge=1, right_edge=1, left_margin=1, right_margin=1) %}
            {% if p %}
                {% if p == page %}
                    <li class="page-item active">
                        <span class="page-link">{{ p }}</span>
                    </li>
                {% else %}
                    <li class="page-item">
                        <a class="page-link" href="{{ url_for(request.endpoint, page=p) }}">
                            {{ p }}
                        </a>
                    </li>
                {% endif %}
            {% else %}
                <li class="page-item disabled">
                    <span class="page-link">...</span>
                </li>
            {% endif %}
        {% endfor %}
        
        <!-- Siguiente -->
        {% if has_next %}
            <li class="page-item">
                <a class="page-link" href="{{ url_for(request.endpoint, page=next_page) }}">
                    Siguiente →
                </a>
            </li>
        {% else %}
            <li class="page-item disabled">
                <span class="page-link">Siguiente →</span>
            </li>
        {% endif %}
    </ul>
</nav>

<!-- Información de paginación -->
<div class="text-center text-muted small mt-3">
    Mostrando página {{ page }} de {{ pages }} ({{ total }} registros totales)
</div>
```

### Componente Reutilizable

```html
<!-- templates/components/pagination.html -->
{% macro render_pagination(pagination, endpoint, **kwargs) %}
    {% if pagination.pages > 1 %}
        <nav aria-label="Page navigation">
            <ul class="pagination justify-content-center">
                
                {% if pagination.has_prev %}
                    <li class="page-item">
                        <a class="page-link" 
                           href="{{ url_for(endpoint, page=pagination.prev_num, **kwargs) }}">
                            ← Anterior
                        </a>
                    </li>
                {% else %}
                    <li class="page-item disabled">
                        <span class="page-link">← Anterior</span>
                    </li>
                {% endif %}
                
                {% for p in pagination.iter_pages() %}
                    {% if p %}
                        {% if p == pagination.page %}
                            <li class="page-item active">
                                <span class="page-link">{{ p }}</span>
                            </li>
                        {% else %}
                            <li class="page-item">
                                <a class="page-link" 
                                   href="{{ url_for(endpoint, page=p, **kwargs) }}">
                                    {{ p }}
                                </a>
                            </li>
                        {% endif %}
                    {% else %}
                        <li class="page-item disabled">
                            <span class="page-link">...</span>
                        </li>
                    {% endif %}
                {% endfor %}
                
                {% if pagination.has_next %}
                    <li class="page-item">
                        <a class="page-link" 
                           href="{{ url_for(endpoint, page=pagination.next_num, **kwargs) }}">
                            Siguiente →
                        </a>
                    </li>
                {% else %}
                    <li class="page-item disabled">
                        <span class="page-link">Siguiente →</span>
                    </li>
                {% endif %}
            </ul>
        </nav>
    {% endif %}
{% endmacro %}
```

**Uso en templates:**
```html
{% from 'components/pagination.html' import render_pagination %}

<!-- Tu contenido -->
<table>...</table>

<!-- Paginación -->
{{ render_pagination(pagination, 'prestamos.prestamos_main', search=search) }}
```

---

## API JSON con Paginación

```python
@api_bp.route('/prestamos', methods=['GET'])
@login_required
def api_prestamos():
    """API que retorna préstamos en JSON con paginación."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    paginated = PrestamoEquipo.query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    return jsonify({
        'data': [item.to_dict() for item in paginated.items],
        'pagination': {
            'current_page': page,
            'total_pages': paginated.pages,
            'total_items': paginated.total,
            'per_page': per_page,
            'has_next': paginated.has_next,
            'has_prev': paginated.has_prev
        }
    })
```

**Response:**
```json
{
  "data": [
    {"id": 1, "profesor": "Juan", ...},
    {"id": 2, "profesor": "María", ...}
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 20,
    "total_items": 1000,
    "per_page": 50,
    "has_next": true,
    "has_prev": false
  }
}
```

---

## Consideraciones Importantes

### 1. **Tamaño de Página Recomendado**

| Tipo de Data | Registros/Página | Justificación |
|--------------|-----------------|---------------|
| Listados grandes | 50 | Balance entre perf y UX |
| Tablas densas | 25-30 | Menos scroll |
| Cuadrículas (cards) | 12-16 | Responsive design |
| DataTables con búsqueda | 100 | Puede cargar más |

### 2. **Cuidado con Ordenamientos**

```python
# ✅ BUENO - Ordenar siempre antes de paginar
query.order_by(Model.fecha.desc()).paginate()

# ❌ MALO - Ordenar después da resultados inconsistentes
query.paginate().order_by(Model.fecha)
```

### 3. **Combinar con Filtros**

```python
# ✅ BUENO - Filtros, luego orden, luego paginación
query = Model.query.filter(...)
query = query.order_by(...)
paginated = query.paginate(...)
```

### 4. **Parámetros en URL**

```python
# Preservar parámetros al cambiar página
url_for('endpoint', page=2, search=search_term, status=status)
```

---

## ✅ Checklist de Implementación

- [ ] Identificar todas las rutas con `.all()` sin paginación
- [ ] Priorizar por volumen de datos (las más grandes primero)
- [ ] Agregar `paginate()` a las queries
- [ ] Actualizar templates para mostrar controles de paginación
- [ ] Preservar parámetros de búsqueda en paginación
- [ ] Probar con datos reales (1000+ registros)
- [ ] Validar performance antes/después
- [ ] Documentar cambios

---

## Archivos a Modificar

| Archivo | Prioridad | Registros Típicos |
|---------|-----------|------------------|
| `blueprints/prestamos.py` | 🔴 ALTA | 1000+ |
| `blueprints/reservas.py` | 🔴 ALTA | 500+ |
| `blueprints/inventario.py` | 🔴 ALTA | 500+ |
| `blueprints/admin.py` | 🟡 MEDIA | 200+ |
| `blueprints/bitacora.py` | 🟡 MEDIA | 10000+ |
| `blueprints/estadisticas.py` | 🟢 BAJA | Depende |

---

**Guía de Paginación - Sistema de Reservas**  
Implementación típica: 2-3 horas para todos los endpoints
