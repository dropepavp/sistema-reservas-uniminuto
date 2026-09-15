# 📚 Guía de Documentación OpenAPI/Swagger

## Estado Actual

```python
# swagger_config.py existe pero está incompleto
# Los blueprints no tienen docstrings OpenAPI
```

---

## Instalación

```bash
# Ya está instalado pero verificar versión
pip install flasgger>=0.9.7
```

---

## Patrón de Documentación

### Estructura Básica

```python
@blueprint.route('/endpoint', methods=['GET', 'POST'])
def mi_funcion():
    """
    Una descripción corta del endpoint.
    
    ---
    tags:
      - nombre_del_modulo
    parameters:
      - name: parametro1
        in: query
        type: string
        required: true
        description: Descripción del parámetro
    responses:
      200:
        description: Descripción de respuesta exitosa
        schema:
          type: object
          properties:
            id:
              type: integer
            nombre:
              type: string
      400:
        description: Validación fallida
      401:
        description: No autorizado
      500:
        description: Error del servidor
    """
    # Implementación
    return jsonify({'resultado': 'ok'})
```

---

## Ejemplos Prácticos

### 1. Endpoint GET - Listar Recursos

```python
# blueprints/prestamos.py

@prestamos_bp.route('/', methods=['GET'])
@login_required
@permiso_requerido('prestamos', 'ver')
def prestamos_main():
    """
    Obtiene lista de préstamos activos paginados.
    
    ---
    tags:
      - Préstamos
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
        description: Número de página (comienza en 1)
      - name: per_page
        in: query
        type: integer
        default: 50
        description: Registros por página
      - name: estado
        in: query
        type: string
        enum: ['Activo', 'Devuelto', 'Cancelado']
        description: Filtrar por estado
      - name: profesor_cedula
        in: query
        type: string
        description: Filtrar por cédula del profesor
    responses:
      200:
        description: Lista de préstamos obtenida exitosamente
        schema:
          type: object
          properties:
            items:
              type: array
              items:
                type: object
                properties:
                  id_prestamo:
                    type: integer
                    example: 123
                  cedula_profesor:
                    type: string
                    example: "1001001001"
                  nombre_profesor:
                    type: string
                    example: "Juan Pérez"
                  fecha_inicio:
                    type: string
                    format: date
                    example: "2026-08-14"
                  hora_inicio:
                    type: string
                    example: "08:00"
                  estado:
                    type: string
                    enum: ['Activo', 'Devuelto', 'Cancelado']
                    example: "Activo"
            pagination:
              type: object
              properties:
                page:
                  type: integer
                pages:
                  type: integer
                total:
                  type: integer
      401:
        description: No autorizado - requiere login
      403:
        description: Sin permisos para ver préstamos
    security:
      - session: []
    """
    # Implementación existente
    pass
```

### 2. Endpoint POST - Crear Recurso

```python
# blueprints/prestamos.py

@prestamos_bp.route('/crear', methods=['POST'])
@login_required
@permiso_requerido('prestamos', 'crear')
def crear_prestamo():
    """
    Crea un nuevo préstamo de equipos.
    
    ---
    tags:
      - Préstamos
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - profesor_cedula
            - equipos
            - fecha_inicio
            - hora_inicio
            - hora_fin
          properties:
            profesor_cedula:
              type: string
              example: "1001001001"
              description: Cédula del profesor
            equipos:
              type: array
              items:
                type: integer
              example: [1, 2, 3]
              description: IDs de equipos a prestar
            fecha_inicio:
              type: string
              format: date
              example: "2026-08-15"
              description: Fecha de inicio del préstamo
            hora_inicio:
              type: string
              example: "08:00"
              description: Hora de inicio (HH:MM)
            hora_fin:
              type: string
              example: "12:00"
              description: Hora de fin (HH:MM)
            observaciones:
              type: string
              description: Observaciones opcionales
    responses:
      201:
        description: Préstamo creado exitosamente
        schema:
          type: object
          properties:
            id_prestamo:
              type: integer
              example: 456
            mensaje:
              type: string
              example: "Préstamo creado exitosamente"
      400:
        description: Datos inválidos
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Equipo no disponible"
      401:
        description: No autorizado
      403:
        description: Sin permisos
      409:
        description: Conflicto - equipo ya prestado
    security:
      - session: []
    """
    # Implementación existente
    pass
```

### 3. Endpoint PUT - Actualizar Recurso

```python
# blueprints/prestamos.py

@prestamos_bp.route('/editar/<int:prestamo_id>', methods=['PUT'])
@login_required
@permiso_requerido('prestamos', 'editar')
def editar_prestamo(prestamo_id):
    """
    Actualiza un préstamo existente.
    
    ---
    tags:
      - Préstamos
    parameters:
      - name: prestamo_id
        in: path
        type: integer
        required: true
        example: 123
        description: ID del préstamo a actualizar
      - name: body
        in: body
        schema:
          type: object
          properties:
            estado:
              type: string
              enum: ['Activo', 'Devuelto', 'Cancelado']
              example: "Devuelto"
            observaciones:
              type: string
            fecha_devolucion:
              type: string
              format: date
            hora_devolucion:
              type: string
    responses:
      200:
        description: Préstamo actualizado
        schema:
          type: object
          properties:
            mensaje:
              type: string
              example: "Préstamo actualizado exitosamente"
      400:
        description: Datos inválidos
      404:
        description: Préstamo no encontrado
      409:
        description: No se puede cambiar a este estado
    security:
      - session: []
    """
    # Implementación
    pass
```

### 4. Endpoint DELETE - Eliminar Recurso

```python
# blueprints/prestamos.py

@prestamos_bp.route('/eliminar/<int:prestamo_id>', methods=['DELETE'])
@login_required
@permiso_requerido('prestamos', 'eliminar')
def eliminar_prestamo(prestamo_id):
    """
    Elimina un préstamo.
    
    ---
    tags:
      - Préstamos
    parameters:
      - name: prestamo_id
        in: path
        type: integer
        required: true
        example: 123
    responses:
      200:
        description: Préstamo eliminado
        schema:
          type: object
          properties:
            mensaje:
              type: string
              example: "Préstamo eliminado exitosamente"
      404:
        description: Préstamo no encontrado
      409:
        description: No se puede eliminar este préstamo
    security:
      - session: []
    """
    # Implementación
    pass
```

### 5. Endpoint JSON - Devolver JSON

```python
# blueprints/api.py

@api_bp.route('/prestamos', methods=['GET'])
@login_required
def api_list_prestamos():
    """
    API para obtener préstamos en JSON.
    
    Útil para frontends JavaScript y aplicaciones móviles.
    
    ---
    tags:
      - API
    produces:
      - application/json
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 50
        maximum: 200
      - name: estado
        in: query
        type: string
    responses:
      200:
        description: Lista de préstamos
        schema:
          type: object
          properties:
            data:
              type: array
              items:
                $ref: '#/definitions/Prestamo'
            pagination:
              type: object
              properties:
                page:
                  type: integer
                total:
                  type: integer
                pages:
                  type: integer
      401:
        description: No autorizado
    """
    # Implementación
    pass
```

---

## Definiciones Reutilizables (Schemas)

```python
# Agregar a swagger_config.py

SWAGGER_CONFIG = {
    'swagger': '2.0',
    'info': {
        'title': 'API Sistema de Reservas UNIMINUTO',
        'version': '1.0.0',
        'description': 'API para gestión de reservas, préstamos e inventario',
        'contact': {
            'name': 'UNIMINUTO',
            'url': 'https://www.uniminuto.edu'
        }
    },
    'basePath': '/api',
    'definitions': {
        'Prestamo': {
            'type': 'object',
            'required': ['id_prestamo', 'cedula_profesor', 'fecha_inicio'],
            'properties': {
                'id_prestamo': {'type': 'integer'},
                'cedula_profesor': {'type': 'string'},
                'nombre_profesor': {'type': 'string'},
                'fecha_inicio': {'type': 'string', 'format': 'date'},
                'hora_inicio': {'type': 'string'},
                'estado': {'type': 'string', 'enum': ['Activo', 'Devuelto']},
                'observaciones': {'type': 'string'}
            }
        },
        'Reserva': {
            'type': 'object',
            'required': ['id_reserva', 'cedula_profesor', 'recurso_nombre', 'fecha'],
            'properties': {
                'id_reserva': {'type': 'integer'},
                'cedula_profesor': {'type': 'string'},
                'nombre_profesor': {'type': 'string'},
                'recurso_nombre': {'type': 'string'},
                'recurso_tipo': {'type': 'string'},
                'fecha': {'type': 'string', 'format': 'date'},
                'hora_inicio': {'type': 'string'},
                'hora_fin': {'type': 'string'},
                'nrc': {'type': 'string'},
                'estado': {'type': 'string'}
            }
        },
        'Inventario': {
            'type': 'object',
            'required': ['id', 'item', 'categoria'],
            'properties': {
                'id': {'type': 'integer'},
                'item': {'type': 'string'},
                'categoria': {'type': 'string'},
                'marca_modelo': {'type': 'string'},
                'serial': {'type': 'string'},
                'numero_inventario': {'type': 'string'},
                'estado': {'type': 'string'},
                'bodega': {'type': 'string'}
            }
        }
    },
    'securityDefinitions': {
        'session': {
            'type': 'apiKey',
            'name': 'session',
            'in': 'cookie',
            'description': 'Sesión de usuario (cookie)'
        }
    }
}

SWAGGER_TEMPLATE = {
    'swagger': '2.0',
    'basePath': '/api'
}
```

---

## Acceder a Documentación

Una vez configurada, accede en:
```
http://localhost:5000/apidocs
```

---

## ✅ Checklist de Documentación

- [ ] Agregar docstrings OpenAPI a endpoints GET
- [ ] Documentar endpoints POST/PUT/DELETE
- [ ] Definir schemas reutilizables
- [ ] Documentar parámetros de query
- [ ] Incluir ejemplos de respuesta
- [ ] Documentar códigos de error (400, 401, 403, 404, 500)
- [ ] Probar documentación en `/apidocs`
- [ ] Generar PDF/HTML para cliente

---

## Módulos a Documentar

| Blueprint | Prioridad | Endpoints |
|-----------|-----------|-----------|
| prestamos | 🔴 ALTA | GET, POST, PUT, DELETE |
| reservas | 🔴 ALTA | GET, POST, PUT, DELETE |
| inventario | 🔴 ALTA | GET, POST, PUT |
| admin | 🟡 MEDIA | GET, POST (permisos) |
| estadisticas | 🟡 MEDIA | GET (gráficos) |
| api | 🟢 BAJA | GET (JSON) |

---

**Guía de Documentación Swagger/OpenAPI**  
Documentación es clave para equipos y usuarios de la API
