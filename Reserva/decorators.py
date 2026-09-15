"""
Decoradores para la aplicación Flask.

ADVERTENCIA: Este módulo reexporta los decoradores definidos en `auth.py`.
Importa directamente desde `auth.py` en código nuevo:

    from auth import login_required, admin_required, permiso_requerido, sede_requerida

Este archivo existe solo por compatibilidad y puede eliminarse en el futuro.
"""

import warnings
import functools

# Reexportar todos los decoradores reales desde auth.py
from auth import (
    login_required,
    admin_required,
    permiso_requerido,
    sede_requerida,
    cargar_permisos_usuario,
)


def _deprecado(nombre_original: str, f):
    """Envuelve un decorador reexportado para emitir advertencia de deprecación en uso."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        warnings.warn(
            f"Importar '{nombre_original}' desde 'decorators' está deprecado. "
            f"Usa 'from auth import {nombre_original}' en su lugar.",
            DeprecationWarning,
            stacklevel=2,
        )
        return f(*args, **kwargs)
    return wrapper


__all__ = [
    "login_required",
    "admin_required",
    "permiso_requerido",
    "sede_requerida",
    "cargar_permisos_usuario",
]
