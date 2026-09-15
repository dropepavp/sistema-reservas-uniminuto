"""
Configuración de Flasgger / Swagger UI
=======================================

Define la especificación OpenAPI 3.0 base y la configuración de la interfaz
Swagger UI disponible en /apidocs.
"""

SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs",
}

SWAGGER_TEMPLATE = {
    "openapi": "3.0.3",
    "info": {
        "title": "Sistema de Préstamos y Reservas — API REST",
        "description": (
            "API RESTful completa del sistema de préstamos y reservas de equipos "
            "tecnológicos para la institución UNIMINUTO.\n\n"
            "## Autenticación\n"
            "Todos los endpoints protegidos requieren un token JWT enviado en el "
            "header `Authorization: Bearer <token>`.\n\n"
            "Obtén tu token en `POST /api/v1/auth/login`."
        ),
        "version": "1.0.0",
        "contact": {
            "name": "UNIMINUTO — Laboratorio de Tecnología",
            "email": "soporte@uniminuto.edu",
        },
        "license": {
            "name": "MIT",
        },
    },
    "servers": [
        {"url": "http://localhost:5000", "description": "Servidor de desarrollo"},
    ],
    "components": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Token JWT obtenido en /api/v1/auth/login",
            }
        },
        "schemas": {
            # ── Entidades base ──────────────────────────────────────────────
            "Profesor": {
                "type": "object",
                "properties": {
                    "cedula": {"type": "string", "example": "12345678"},
                    "nombre": {"type": "string", "example": "Juan Pérez"},
                    "programa": {"type": "string", "example": "Ingeniería de Sistemas"},
                    "telefono": {"type": "string", "example": "3001234567"},
                    "email": {"type": "string", "example": "jperez@uniminuto.edu"},
                },
            },
            "Equipo": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 1},
                    "nombre": {"type": "string", "example": "Laptop HP ProBook"},
                    "categoria": {"type": "string", "example": "Portátil"},
                    "estado": {
                        "type": "string",
                        "enum": ["disponible", "prestado", "mantenimiento"],
                        "example": "disponible",
                    },
                    "numero_inventario": {"type": "string", "example": "INV-001"},
                },
            },
            "Prestamo": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 10},
                    "profesor_cedula": {"type": "string", "example": "12345678"},
                    "equipo_id": {"type": "integer", "example": 1},
                    "fecha_prestamo": {
                        "type": "string",
                        "format": "date-time",
                        "example": "2026-08-13T10:00:00",
                    },
                    "fecha_devolucion": {
                        "type": "string",
                        "format": "date",
                        "example": "2026-08-14",
                    },
                    "jornada": {
                        "type": "string",
                        "enum": ["mañana", "tarde", "noche"],
                        "example": "mañana",
                    },
                    "estado": {
                        "type": "string",
                        "enum": ["prestado", "devuelto"],
                        "example": "prestado",
                    },
                    "observaciones": {"type": "string", "example": ""},
                },
            },
            "Reserva": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 5},
                    "profesor_cedula": {"type": "string", "example": "12345678"},
                    "tipo_recurso": {"type": "string", "example": "sala_computo"},
                    "fecha": {"type": "string", "format": "date", "example": "2026-08-14"},
                    "hora_inicio": {"type": "string", "example": "08:00"},
                    "estado": {
                        "type": "string",
                        "enum": ["activa", "cancelada", "completada"],
                        "example": "activa",
                    },
                },
            },
            # ── Respuestas genéricas ────────────────────────────────────────
            "SuccessResponse": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "message": {"type": "string", "example": "Operación exitosa"},
                },
            },
            "ErrorResponse": {
                "type": "object",
                "properties": {
                    "error": {"type": "string", "example": "Descripción del error"},
                    "code": {"type": "string", "example": "ERROR_CODE"},
                },
            },
            "Pagination": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer", "example": 1},
                    "per_page": {"type": "integer", "example": 50},
                    "total": {"type": "integer", "example": 120},
                    "pages": {"type": "integer", "example": 3},
                },
            },
        },
    },
    "security": [{"BearerAuth": []}],
    "tags": [
        {"name": "Autenticación", "description": "Login y validación de tokens JWT"},
        {"name": "Profesores", "description": "CRUD completo de profesores"},
        {"name": "Equipos", "description": "Consulta del inventario de equipos"},
        {"name": "Préstamos", "description": "Gestión de préstamos de equipos"},
        {"name": "Reservas", "description": "Consulta de reservas de recursos"},
        {"name": "Sistema", "description": "Health check, métricas y webhooks"},
    ],
}
