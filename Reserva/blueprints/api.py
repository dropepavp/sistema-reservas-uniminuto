"""
Blueprint de API REST
====================

API RESTful completa para integración externa con el sistema de préstamos y reservas.
Incluye autenticación JWT, documentación automática y rate limiting.

Funcionalidades:
- Endpoints REST completos para todos los recursos
- Autenticación JWT con tokens
- Documentación automática OpenAPI/Swagger
- Rate limiting por endpoint
- Webhooks para notificaciones
- Versionado de API
- Middleware de logging y auditoría
"""

from flask import Blueprint, request, jsonify, current_app
from functools import wraps
import jwt
from datetime import datetime, timedelta
import sqlite3
import hashlib
import time
from collections import defaultdict
import json
import uuid

# Crear blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# Rate limiting storage (en producción usar Redis)
rate_limit_storage = defaultdict(list)

def get_db_connection():
    """Obtener conexión a la base de datos"""
    conn = sqlite3.connect('sistema_prestamos.db')
    conn.row_factory = sqlite3.Row
    return conn

def generate_jwt_token(user_data, expires_hours=24):
    """Generar token JWT"""
    payload = {
        'user_id': user_data.get('documento'),
        'user_type': user_data.get('rol', 'api'),
        'exp': datetime.utcnow() + timedelta(hours=expires_hours),
        'iat': datetime.utcnow(),
        'sub': user_data.get('documento')
    }
    
    secret_key = current_app.config.get('SECRET_KEY', 'mi_clave_secreta_2023')
    return jwt.encode(payload, secret_key, algorithm='HS256')

def verify_jwt_token(token):
    """Verificar token JWT"""
    try:
        secret_key = current_app.config.get('SECRET_KEY', 'mi_clave_secreta_2023')
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_api_auth(f):
    """Decorador para requerir autenticación JWT"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({
                'error': 'Token de autorización requerido',
                'code': 'MISSING_TOKEN'
            }), 401
        
        # Remover 'Bearer ' del inicio si existe
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = verify_jwt_token(token)
        if not payload:
            return jsonify({
                'error': 'Token inválido o expirado',
                'code': 'INVALID_TOKEN'
            }), 401
        
        request.current_user = payload
        return f(*args, **kwargs)
    
    return decorated_function

def rate_limit(max_requests=100, window_minutes=15):
    """Decorador para rate limiting"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            endpoint = request.endpoint
            key = f"{client_ip}:{endpoint}"
            
            current_time = time.time()
            window_start = current_time - (window_minutes * 60)
            
            # Limpiar requests antiguos
            rate_limit_storage[key] = [
                req_time for req_time in rate_limit_storage[key]
                if req_time > window_start
            ]
            
            # Verificar límite
            if len(rate_limit_storage[key]) >= max_requests:
                return jsonify({
                    'error': 'Límite de requests excedido',
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'retry_after': window_minutes * 60
                }), 429
            
            # Agregar request actual
            rate_limit_storage[key].append(current_time)
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def log_api_request():
    """Middleware para logging de requests API"""
    # En producción, usar un sistema de logging más robusto
    pass

# ============================================================================
# AUTENTICACIÓN ENDPOINTS
# ============================================================================

@api_bp.route('/auth/login', methods=['POST'])
@rate_limit(max_requests=10, window_minutes=5)
def auth_login():
    """
    Autenticar usuario y obtener token JWT.
    ---
    tags:
      - Autenticación
    summary: Login con documento y contraseña
    security: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [documento, password]
            properties:
              documento:
                type: string
                example: "12345678"
              password:
                type: string
                format: password
                example: "mi_clave_secreta"
    responses:
      200:
        description: Token JWT generado exitosamente
        content:
          application/json:
            schema:
              type: object
              properties:
                success: {type: boolean}
                token: {type: string}
                user:
                  $ref: '#/components/schemas/Profesor'
                expires_in: {type: integer, example: 86400}
      400:
        description: Datos de entrada inválidos
        content:
          application/json:
            schema: {$ref: '#/components/schemas/ErrorResponse'}
      401:
        description: Credenciales incorrectas
        content:
          application/json:
            schema: {$ref: '#/components/schemas/ErrorResponse'}
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'Datos JSON requeridos',
                'code': 'INVALID_DATA'
            }), 400
        
        documento = data.get('documento')
        password = data.get('password')
        
        if not documento or not password:
            return jsonify({
                'error': 'Documento y contraseña requeridos',
                'code': 'MISSING_CREDENTIALS'
            }), 400
        
        conn = get_db_connection()
        
        # Verificar usuario en tabla usuarios
        user = conn.execute(
            "SELECT * FROM usuarios WHERE documento = ?",
            (documento,)
        ).fetchone()
        
        if not user:
            conn.close()
            return jsonify({
                'error': 'Credenciales inválidas',
                'code': 'INVALID_CREDENTIALS'
            }), 401
        
        # Verificar contraseña (hasheada)
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if user['password'] != password_hash:
            conn.close()
            return jsonify({
                'error': 'Credenciales inválidas',
                'code': 'INVALID_CREDENTIALS'
            }), 401
        
        conn.close()
        
        # Generar token
        user_data = {
            'documento': user['documento'],
            'nombre': user['nombre'],
            'rol': user['rol']
        }
        
        token = generate_jwt_token(user_data)
        
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'documento': user['documento'],
                'nombre': user['nombre'],
                'rol': user['rol']
            },
            'expires_in': 24 * 60 * 60  # 24 horas en segundos
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Error en autenticación: {str(e)}',
            'code': 'AUTH_ERROR'
        }), 500

@api_bp.route('/auth/validate', methods=['GET'])
@require_api_auth
def auth_validate():
    """
    Validar token JWT actual.
    ---
    tags:
      - Autenticación
    summary: Verificar que el token enviado en Authorization sigue siendo válido
    responses:
      200:
        description: Token válido
        content:
          application/json:
            schema:
              type: object
              properties:
                success: {type: boolean}
                user: {type: object}
                message: {type: string}
      401:
        description: Token inválido o expirado
        content:
          application/json:
            schema: {$ref: '#/components/schemas/ErrorResponse'}
    """
    return jsonify({
        'success': True,
        'user': request.current_user,
        'message': 'Token válido'
    })

# ============================================================================
# PROFESORES ENDPOINTS
# ============================================================================

@api_bp.route('/profesores', methods=['GET'])
@require_api_auth
@rate_limit(max_requests=200, window_minutes=15)
def get_profesores():
    """
    Listar profesores con paginación y filtros.
    ---
    tags:
      - Profesores
    summary: Obtener lista paginada de profesores
    parameters:
      - name: page
        in: query
        schema: {type: integer, default: 1}
        description: Número de página
      - name: per_page
        in: query
        schema: {type: integer, default: 50, maximum: 100}
        description: Resultados por página (máx. 100)
      - name: search
        in: query
        schema: {type: string}
        description: Buscar por nombre o cédula
      - name: programa
        in: query
        schema: {type: string}
        description: Filtrar por programa académico
    responses:
      200:
        description: Lista de profesores obtenida exitosamente
        content:
          application/json:
            schema:
              type: object
              properties:
                success: {type: boolean}
                data:
                  type: array
                  items: {$ref: '#/components/schemas/Profesor'}
                pagination: {$ref: '#/components/schemas/Pagination'}
      401:
        description: No autorizado
        content:
          application/json:
            schema: {$ref: '#/components/schemas/ErrorResponse'}
    """
    try:
        # Parámetros de query
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        search = request.args.get('search', '')
        programa = request.args.get('programa', '')
        
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        
        # Construir query con filtros
        query = "SELECT * FROM profesores WHERE 1=1"
        params = []
        
        if search:
            query += " AND (nombre LIKE ? OR cedula LIKE ?)"
            params.extend([f'%{search}%', f'%{search}%'])
        
        if programa:
            query += " AND programa = ?"
            params.append(programa)
        
        # Total de registros
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        total = conn.execute(count_query, params).fetchone()[0]
        
        # Datos paginados
        query += " ORDER BY nombre LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        
        profesores = conn.execute(query, params).fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': [dict(p) for p in profesores],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Error al obtener profesores: {str(e)}',
            'code': 'GET_PROFESORES_ERROR'
        }), 500

@api_bp.route('/profesores/<cedula>', methods=['GET'])
@require_api_auth
@rate_limit(max_requests=300, window_minutes=15)
def get_profesor(cedula):
    """
    Obtener un profesor específico por cédula.
    ---
    tags:
      - Profesores
    summary: Detalle de un profesor incluyendo sus estadísticas
    parameters:
      - name: cedula
        in: path
        required: true
        schema: {type: string}
        description: Número de cédula del profesor
    responses:
      200:
        description: Datos del profesor encontrado
        content:
          application/json:
            schema:
              type: object
              properties:
                success: {type: boolean}
                data:
                  allOf:
                    - $ref: '#/components/schemas/Profesor'
                    - type: object
                      properties:
                        estadisticas:
                          type: object
                          properties:
                            prestamos_activos: {type: integer}
                            prestamos_historicos: {type: integer}
                            reservas_activas: {type: integer}
      404:
        description: Profesor no encontrado
        content:
          application/json:
            schema: {$ref: '#/components/schemas/ErrorResponse'}
    """
    try:
        conn = get_db_connection()
        
        profesor = conn.execute(
            "SELECT * FROM profesores WHERE cedula = ?",
            (cedula,)
        ).fetchone()
        
        if not profesor:
            conn.close()
            return jsonify({
                'error': 'Profesor no encontrado',
                'code': 'PROFESOR_NOT_FOUND'
            }), 404
        
        # Obtener estadísticas del profesor
        stats = conn.execute("""
            SELECT 
                COUNT(CASE WHEN p.estado = 'prestado' THEN 1 END) as prestamos_activos,
                COUNT(CASE WHEN p.estado = 'devuelto' THEN 1 END) as prestamos_historicos,
                COUNT(CASE WHEN r.estado = 'activa' THEN 1 END) as reservas_activas
            FROM profesores pr
            LEFT JOIN prestamos p ON pr.cedula = p.profesor_cedula
            LEFT JOIN reservas r ON pr.cedula = r.profesor_cedula
            WHERE pr.cedula = ?
        """, (cedula,)).fetchone()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                **dict(profesor),
                'estadisticas': dict(stats) if stats else {}
            }
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Error al obtener profesor: {str(e)}',
            'code': 'GET_PROFESOR_ERROR'
        }), 500

@api_bp.route('/profesores', methods=['POST'])
@require_api_auth
@rate_limit(max_requests=50, window_minutes=15)
def create_profesor():
    """
    Crear un nuevo profesor.
    ---
    tags:
      - Profesores
    summary: Registrar un nuevo profesor en el sistema
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [cedula, nombre, programa]
            properties:
              cedula: {type: string, example: "87654321"}
              nombre: {type: string, example: "María López"}
              programa: {type: string, example: "Administración de Empresas"}
              telefono: {type: string, example: "3109876543"}
              email: {type: string, example: "mlopez@uniminuto.edu"}
    responses:
      201:
        description: Profesor creado exitosamente
        content:
          application/json:
            schema:
              type: object
              properties:
                success: {type: boolean}
                message: {type: string}
                data: {$ref: '#/components/schemas/Profesor'}
      409:
        description: El profesor ya existe
        content:
          application/json:
            schema: {$ref: '#/components/schemas/ErrorResponse'}
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'Datos JSON requeridos',
                'code': 'INVALID_DATA'
            }), 400
        
        required_fields = ['cedula', 'nombre', 'programa']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'error': f'Campo {field} requerido',
                    'code': 'MISSING_FIELD'
                }), 400
        
        conn = get_db_connection()
        
        # Verificar si ya existe
        existing = conn.execute(
            "SELECT cedula FROM profesores WHERE cedula = ?",
            (data['cedula'],)
        ).fetchone()
        
        if existing:
            conn.close()
            return jsonify({
                'error': 'Profesor ya existe',
                'code': 'PROFESOR_EXISTS'
            }), 409
        
        # Insertar nuevo profesor
        conn.execute("""
            INSERT INTO profesores (cedula, nombre, programa, telefono, email)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data['cedula'],
            data['nombre'],
            data['programa'],
            data.get('telefono', ''),
            data.get('email', '')
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Profesor creado exitosamente',
            'data': {
                'cedula': data['cedula'],
                'nombre': data['nombre']
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'error': f'Error al crear profesor: {str(e)}',
            'code': 'CREATE_PROFESOR_ERROR'
        }), 500

# ============================================================================
# EQUIPOS ENDPOINTS
# ============================================================================

@api_bp.route('/equipos', methods=['GET'])
@require_api_auth
@rate_limit(max_requests=200, window_minutes=15)
def get_equipos():
    """
    Listar equipos del inventario con filtros.
    ---
    tags:
      - Equipos
    summary: Obtener equipos disponibles o filtrados por categoría y estado
    parameters:
      - name: categoria
        in: query
        schema: {type: string}
        description: Filtrar por categoría (ej. Portátil, Tablet)
      - name: estado
        in: query
        schema:
          type: string
          enum: [disponible, prestado, mantenimiento]
        description: Filtrar por estado del equipo
      - name: disponibles_solo
        in: query
        schema: {type: boolean, default: false}
        description: Si es true, devuelve solo equipos disponibles
    responses:
      200:
        description: Lista de equipos obtenida exitosamente
        content:
          application/json:
            schema:
              type: object
              properties:
                success: {type: boolean}
                data:
                  type: array
                  items: {$ref: '#/components/schemas/Equipo'}
                total: {type: integer}
    """
    try:
        categoria = request.args.get('categoria', '')
        estado = request.args.get('estado', '')
        disponibles_solo = request.args.get('disponibles_solo', 'false').lower() == 'true'
        
        conn = get_db_connection()
        
        query = "SELECT * FROM equipos WHERE 1=1"
        params = []
        
        if categoria:
            query += " AND categoria = ?"
            params.append(categoria)
        
        if estado:
            query += " AND estado = ?"
            params.append(estado)
        
        if disponibles_solo:
            query += " AND estado = 'disponible'"
        
        query += " ORDER BY nombre"
        
        equipos = conn.execute(query, params).fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': [dict(e) for e in equipos],
            'total': len(equipos)
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Error al obtener equipos: {str(e)}',
            'code': 'GET_EQUIPOS_ERROR'
        }), 500

@api_bp.route('/equipos/<int:equipo_id>', methods=['GET'])
@require_api_auth
@rate_limit(max_requests=300, window_minutes=15)
def get_equipo(equipo_id):
    """
    Obtener un equipo específico con su historial reciente.
    ---
    tags:
      - Equipos
    summary: Detalle de un equipo y sus últimos 10 préstamos
    parameters:
      - name: equipo_id
        in: path
        required: true
        schema: {type: integer}
        description: ID numérico del equipo
    responses:
      200:
        description: Datos del equipo con historial de préstamos
        content:
          application/json:
            schema:
              type: object
              properties:
                success: {type: boolean}
                data:
                  allOf:
                    - $ref: '#/components/schemas/Equipo'
                    - type: object
                      properties:
                        historial_reciente:
                          type: array
                          items: {$ref: '#/components/schemas/Prestamo'}
      404:
        description: Equipo no encontrado
        content:
          application/json:
            schema: {$ref: '#/components/schemas/ErrorResponse'}
    """
    try:
        conn = get_db_connection()
        
        equipo = conn.execute(
            "SELECT * FROM equipos WHERE id = ?",
            (equipo_id,)
        ).fetchone()
        
        if not equipo:
            conn.close()
            return jsonify({
                'error': 'Equipo no encontrado',
                'code': 'EQUIPO_NOT_FOUND'
            }), 404
        
        # Obtener historial de préstamos
        historial = conn.execute("""
            SELECT p.*, pr.nombre as profesor_nombre
            FROM prestamos p
            JOIN profesores pr ON p.profesor_cedula = pr.cedula
            WHERE p.equipo_id = ?
            ORDER BY p.fecha_prestamo DESC
            LIMIT 10
        """, (equipo_id,)).fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                **dict(equipo),
                'historial_reciente': [dict(h) for h in historial]
            }
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Error al obtener equipo: {str(e)}',
            'code': 'GET_EQUIPO_ERROR'
        }), 500

# ============================================================================
# PRÉSTAMOS ENDPOINTS
# ============================================================================

@api_bp.route('/prestamos', methods=['GET'])
@require_api_auth
@rate_limit(max_requests=200, window_minutes=15)
def get_prestamos():
    """
    Listar préstamos con filtros opcionales.
    ---
    tags:
      - Préstamos
    summary: Obtener historial de préstamos filtrado
    parameters:
      - name: estado
        in: query
        schema:
          type: string
          enum: [prestado, devuelto]
        description: Estado del préstamo
      - name: profesor_cedula
        in: query
        schema: {type: string}
        description: Filtrar por cédula del profesor
      - name: fecha_desde
        in: query
        schema: {type: string, format: date}
        description: Fecha de inicio del rango (YYYY-MM-DD)
      - name: fecha_hasta
        in: query
        schema: {type: string, format: date}
        description: Fecha de fin del rango (YYYY-MM-DD)
    responses:
      200:
        description: Lista de préstamos
        content:
          application/json:
            schema:
              type: object
              properties:
                success: {type: boolean}
                data:
                  type: array
                  items: {$ref: '#/components/schemas/Prestamo'}
                total: {type: integer}
    """
    try:
        estado = request.args.get('estado', '')
        profesor_cedula = request.args.get('profesor_cedula', '')
        fecha_desde = request.args.get('fecha_desde', '')
        fecha_hasta = request.args.get('fecha_hasta', '')
        
        conn = get_db_connection()
        
        query = """
            SELECT p.*, pr.nombre as profesor_nombre, e.nombre as equipo_nombre
            FROM prestamos p
            JOIN profesores pr ON p.profesor_cedula = pr.cedula
            JOIN equipos e ON p.equipo_id = e.id
            WHERE 1=1
        """
        params = []
        
        if estado:
            query += " AND p.estado = ?"
            params.append(estado)
        
        if profesor_cedula:
            query += " AND p.profesor_cedula = ?"
            params.append(profesor_cedula)
        
        if fecha_desde:
            query += " AND DATE(p.fecha_prestamo) >= ?"
            params.append(fecha_desde)
        
        if fecha_hasta:
            query += " AND DATE(p.fecha_prestamo) <= ?"
            params.append(fecha_hasta)
        
        query += " ORDER BY p.fecha_prestamo DESC"
        
        prestamos = conn.execute(query, params).fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': [dict(p) for p in prestamos],
            'total': len(prestamos)
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Error al obtener préstamos: {str(e)}',
            'code': 'GET_PRESTAMOS_ERROR'
        }), 500

@api_bp.route('/prestamos', methods=['POST'])
@require_api_auth
@rate_limit(max_requests=100, window_minutes=15)
def create_prestamo():
    """
    Registrar un nuevo préstamo de equipo.
    ---
    tags:
      - Préstamos
    summary: Crear préstamo — verifica disponibilidad del equipo automáticamente
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [profesor_cedula, equipo_id, fecha_devolucion]
            properties:
              profesor_cedula: {type: string, example: "12345678"}
              equipo_id: {type: integer, example: 3}
              fecha_devolucion: {type: string, format: date, example: "2026-08-14"}
              jornada:
                type: string
                enum: [mañana, tarde, noche]
                default: mañana
              observaciones: {type: string, example: ""}
    responses:
      201:
        description: Préstamo creado exitosamente
        content:
          application/json:
            schema: {$ref: '#/components/schemas/SuccessResponse'}
      404:
        description: Profesor o equipo no encontrado
        content:
          application/json:
            schema: {$ref: '#/components/schemas/ErrorResponse'}
      409:
        description: Equipo no disponible
        content:
          application/json:
            schema: {$ref: '#/components/schemas/ErrorResponse'}
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'Datos JSON requeridos',
                'code': 'INVALID_DATA'
            }), 400
        
        required_fields = ['profesor_cedula', 'equipo_id', 'fecha_devolucion']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'error': f'Campo {field} requerido',
                    'code': 'MISSING_FIELD'
                }), 400
        
        conn = get_db_connection()
        
        # Verificar que el profesor existe
        profesor = conn.execute(
            "SELECT cedula FROM profesores WHERE cedula = ?",
            (data['profesor_cedula'],)
        ).fetchone()
        
        if not profesor:
            conn.close()
            return jsonify({
                'error': 'Profesor no encontrado',
                'code': 'PROFESOR_NOT_FOUND'
            }), 404
        
        # Verificar que el equipo existe y está disponible
        equipo = conn.execute(
            "SELECT id, estado FROM equipos WHERE id = ?",
            (data['equipo_id'],)
        ).fetchone()
        
        if not equipo:
            conn.close()
            return jsonify({
                'error': 'Equipo no encontrado',
                'code': 'EQUIPO_NOT_FOUND'
            }), 404
        
        if equipo['estado'] != 'disponible':
            conn.close()
            return jsonify({
                'error': 'Equipo no disponible',
                'code': 'EQUIPO_NOT_AVAILABLE'
            }), 409
        
        # Crear préstamo
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO prestamos 
            (profesor_cedula, equipo_id, fecha_prestamo, fecha_devolucion, 
             jornada, estado, observaciones)
            VALUES (?, ?, ?, ?, ?, 'prestado', ?)
        """, (
            data['profesor_cedula'],
            data['equipo_id'],
            fecha_actual,
            data['fecha_devolucion'],
            data.get('jornada', 'mañana'),
            data.get('observaciones', '')
        ))
        
        prestamo_id = cursor.lastrowid
        
        # Actualizar estado del equipo
        conn.execute(
            "UPDATE equipos SET estado = 'prestado' WHERE id = ?",
            (data['equipo_id'],)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Préstamo creado exitosamente',
            'data': {
                'id': prestamo_id,
                'profesor_cedula': data['profesor_cedula'],
                'equipo_id': data['equipo_id']
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'error': f'Error al crear préstamo: {str(e)}',
            'code': 'CREATE_PRESTAMO_ERROR'
        }), 500

@api_bp.route('/prestamos/<int:prestamo_id>/devolver', methods=['PUT'])
@require_api_auth
@rate_limit(max_requests=100, window_minutes=15)
def devolver_prestamo(prestamo_id):
    """
    Registrar la devolución de un préstamo activo.
    ---
    tags:
      - Préstamos
    summary: Marcar un préstamo como devuelto y liberar el equipo
    parameters:
      - name: prestamo_id
        in: path
        required: true
        schema: {type: integer}
        description: ID del préstamo a devolver
    requestBody:
      required: false
      content:
        application/json:
          schema:
            type: object
            properties:
              observaciones: {type: string, example: "Devuelto en perfecto estado"}
    responses:
      200:
        description: Devolución registrada exitosamente
        content:
          application/json:
            schema:
              type: object
              properties:
                success: {type: boolean}
                message: {type: string}
                data:
                  type: object
                  properties:
                    id: {type: integer}
                    fecha_devolucion_real: {type: string, format: date-time}
      404:
        description: Préstamo no encontrado o ya devuelto
        content:
          application/json:
            schema: {$ref: '#/components/schemas/ErrorResponse'}
    """
    try:
        data = request.get_json() or {}
        
        conn = get_db_connection()
        
        # Verificar que el préstamo existe y está activo
        prestamo = conn.execute(
            "SELECT * FROM prestamos WHERE id = ? AND estado = 'prestado'",
            (prestamo_id,)
        ).fetchone()
        
        if not prestamo:
            conn.close()
            return jsonify({
                'error': 'Préstamo no encontrado o ya devuelto',
                'code': 'PRESTAMO_NOT_FOUND'
            }), 404
        
        fecha_devolucion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Actualizar préstamo
        conn.execute("""
            UPDATE prestamos 
            SET estado = 'devuelto', 
                fecha_devolucion_real = ?,
                observaciones_devolucion = ?
            WHERE id = ?
        """, (
            fecha_devolucion,
            data.get('observaciones', ''),
            prestamo_id
        ))
        
        # Actualizar estado del equipo
        conn.execute(
            "UPDATE equipos SET estado = 'disponible' WHERE id = ?",
            (prestamo['equipo_id'],)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Préstamo devuelto exitosamente',
            'data': {
                'id': prestamo_id,
                'fecha_devolucion_real': fecha_devolucion
            }
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Error al devolver préstamo: {str(e)}',
            'code': 'DEVOLVER_PRESTAMO_ERROR'
        }), 500

# ============================================================================
# RESERVAS ENDPOINTS
# ============================================================================

@api_bp.route('/reservas', methods=['GET'])
@require_api_auth
@rate_limit(max_requests=200, window_minutes=15)
def get_reservas():
    """
    Listar reservas con filtros de fecha, recurso y estado.
    ---
    tags:
      - Reservas
    summary: Obtener reservas activas o históricas
    parameters:
      - name: fecha_desde
        in: query
        schema: {type: string, format: date}
        description: Fecha de inicio del rango
      - name: fecha_hasta
        in: query
        schema: {type: string, format: date}
        description: Fecha de fin del rango
      - name: tipo_recurso
        in: query
        schema: {type: string}
        description: Tipo de recurso reservado (ej. sala_computo, auditorio)
      - name: estado
        in: query
        schema:
          type: string
          enum: [activa, cancelada, completada]
          default: activa
        description: Estado de las reservas
    responses:
      200:
        description: Lista de reservas
        content:
          application/json:
            schema:
              type: object
              properties:
                success: {type: boolean}
                data:
                  type: array
                  items: {$ref: '#/components/schemas/Reserva'}
                total: {type: integer}
    """
    try:
        fecha_desde = request.args.get('fecha_desde', '')
        fecha_hasta = request.args.get('fecha_hasta', '')
        tipo_recurso = request.args.get('tipo_recurso', '')
        estado = request.args.get('estado', 'activa')
        
        conn = get_db_connection()
        
        query = """
            SELECT r.*, p.nombre as profesor_nombre
            FROM reservas r
            JOIN profesores p ON r.profesor_cedula = p.cedula
            WHERE 1=1
        """
        params = []
        
        if fecha_desde:
            query += " AND r.fecha >= ?"
            params.append(fecha_desde)
        
        if fecha_hasta:
            query += " AND r.fecha <= ?"
            params.append(fecha_hasta)
        
        if tipo_recurso:
            query += " AND r.tipo_recurso = ?"
            params.append(tipo_recurso)
        
        if estado:
            query += " AND r.estado = ?"
            params.append(estado)
        
        query += " ORDER BY r.fecha DESC, r.hora_inicio ASC"
        
        reservas = conn.execute(query, params).fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': [dict(r) for r in reservas],
            'total': len(reservas)
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Error al obtener reservas: {str(e)}',
            'code': 'GET_RESERVAS_ERROR'
        }), 500

# ============================================================================
# WEBHOOKS Y NOTIFICACIONES
# ============================================================================

@api_bp.route('/webhooks/register', methods=['POST'])
@require_api_auth
@rate_limit(max_requests=10, window_minutes=60)
def register_webhook():
    """
    Registrar un webhook para recibir notificaciones de eventos.
    ---
    tags:
      - Sistema
    summary: Suscribir una URL externa a eventos del sistema
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [url, events]
            properties:
              url:
                type: string
                format: uri
                example: "https://mi-app.com/webhook"
              events:
                type: array
                items:
                  type: string
                  enum: [prestamo.creado, prestamo.devuelto, reserva.creada]
                example: ["prestamo.creado", "prestamo.devuelto"]
    responses:
      201:
        description: Webhook registrado exitosamente
        content:
          application/json:
            schema:
              type: object
              properties:
                success: {type: boolean}
                data:
                  type: object
                  properties:
                    webhook_id: {type: string, format: uuid}
                    url: {type: string}
                    events:
                      type: array
                      items: {type: string}
      400:
        description: URL o eventos no proporcionados
        content:
          application/json:
            schema: {$ref: '#/components/schemas/ErrorResponse'}
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'Datos JSON requeridos',
                'code': 'INVALID_DATA'
            }), 400
        
        url = data.get('url')
        events = data.get('events', [])
        
        if not url or not events:
            return jsonify({
                'error': 'URL y eventos requeridos',
                'code': 'MISSING_WEBHOOK_DATA'
            }), 400
        
        # En producción, guardar en base de datos
        webhook_id = str(uuid.uuid4())
        
        return jsonify({
            'success': True,
            'message': 'Webhook registrado exitosamente',
            'data': {
                'webhook_id': webhook_id,
                'url': url,
                'events': events
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'error': f'Error al registrar webhook: {str(e)}',
            'code': 'REGISTER_WEBHOOK_ERROR'
        }), 500

# ============================================================================
# DOCUMENTACIÓN API
# ============================================================================

@api_bp.route('/docs', methods=['GET'])
def api_docs():
    """Documentación automática de la API (OpenAPI/Swagger)"""
    openapi_spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Sistema de Préstamos y Reservas API",
            "version": "1.0.0",
            "description": "API REST completa para el sistema de préstamos y reservas"
        },
        "servers": [
            {"url": "/api/v1", "description": "Servidor principal"}
        ],
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                }
            }
        },
        "security": [{"BearerAuth": []}],
        "paths": {
            "/auth/login": {
                "post": {
                    "tags": ["Autenticación"],
                    "summary": "Autenticar usuario y obtener token JWT",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "documento": {"type": "string"},
                                        "password": {"type": "string"}
                                    },
                                    "required": ["documento", "password"]
                                }
                            }
                        }
                    }
                }
            },
            "/profesores": {
                "get": {
                    "tags": ["Profesores"],
                    "summary": "Obtener lista de profesores",
                    "parameters": [
                        {"name": "page", "in": "query", "schema": {"type": "integer"}},
                        {"name": "per_page", "in": "query", "schema": {"type": "integer"}},
                        {"name": "search", "in": "query", "schema": {"type": "string"}},
                        {"name": "programa", "in": "query", "schema": {"type": "string"}}
                    ]
                },
                "post": {
                    "tags": ["Profesores"],
                    "summary": "Crear nuevo profesor",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "cedula": {"type": "string"},
                                        "nombre": {"type": "string"},
                                        "programa": {"type": "string"},
                                        "telefono": {"type": "string"},
                                        "email": {"type": "string"}
                                    },
                                    "required": ["cedula", "nombre", "programa"]
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    return jsonify(openapi_spec)

# ============================================================================
# HEALTH CHECK Y MÉTRICAS
# ============================================================================

@api_bp.route('/health', methods=['GET'])
def health_check():
    """
    Estado de salud del sistema.
    ---
    tags:
      - Sistema
    summary: Health check — verifica conectividad de la base de datos
    security: []
    responses:
      200:
        description: Sistema saludable
        content:
          application/json:
            schema:
              type: object
              properties:
                status: {type: string, example: healthy}
                timestamp: {type: string, format: date-time}
                version: {type: string, example: "1.0.0"}
                database: {type: string, example: connected}
      500:
        description: Sistema con problemas
        content:
          application/json:
            schema:
              type: object
              properties:
                status: {type: string, example: unhealthy}
                error: {type: string}
    """
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'database': 'connected'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }), 500

@api_bp.route('/metrics', methods=['GET'])
@require_api_auth
def api_metrics():
    """
    Métricas básicas de uso de la API.
    ---
    tags:
      - Sistema
    summary: Estadísticas de requests activos y versión del API
    responses:
      200:
        description: Métricas del sistema
        content:
          application/json:
            schema:
              type: object
              properties:
                success: {type: boolean}
                data:
                  type: object
                  properties:
                    requests_count: {type: integer}
                    active_tokens: {type: string}
                    uptime: {type: string}
                    version: {type: string, example: "1.0.0"}
    """
    return jsonify({
        'success': True,
        'data': {
            'requests_count': len(rate_limit_storage),
            'active_tokens': 'N/A',  # En producción implementar contador
            'uptime': 'N/A',  # En producción implementar uptime
            'version': '1.0.0'
        }
    })