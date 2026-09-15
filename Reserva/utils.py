"""
Utilidades generales para la aplicación.

ADVERTENCIA: `registrar_auditoria` vive en `database.py` y persiste registros
en la tabla `audit_log` de la base de datos.  Este módulo la reexporta para
evitar que importaciones accidentales de `utils` silencien registros críticos.

En código nuevo importa siempre desde la fuente real:

    from database import registrar_auditoria
"""

# Reexportar la implementación real que persiste en BD.
# Si alguien importa `from utils import registrar_auditoria`, obtiene
# exactamente la misma función que `from database import registrar_auditoria`.
from database import registrar_auditoria  # noqa: F401  (reexportación intencional)

__all__ = ["registrar_auditoria"]
