"""
Módulo centralizado de autenticación y autorización.
Proporciona decoradores reutilizables para proteger rutas.
"""
from functools import wraps
from flask import session, redirect, flash, url_for


def login_required(f):
    """Decorador para proteger rutas que requieren inicio de sesión."""
    @wraps(f)
    def login_wrapper(*args, **kwargs):
        if session.get('usuario') is None:
            return redirect('/login')
        return f(*args, **kwargs)
    return login_wrapper


def admin_required(f):
    """Decorador para proteger rutas que requieren rol de administrador."""
    @wraps(f)
    def admin_wrapper(*args, **kwargs):
        if session.get('rol') not in ('admin', 'superadmin'):
            flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return admin_wrapper


def permiso_requerido(modulo: str, accion: str):
    """Decorador para validar permisos por módulo y acción (crear, editar, eliminar, ver)."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if session.get('usuario') is None:
                return redirect('/login')

            if session.get('rol') in ('admin', 'superadmin'):
                return f(*args, **kwargs)

            from database import UserPermission
            usuario_doc = session.get('usuario')
            permiso = UserPermission.query.filter_by(usuario_documento=usuario_doc, modulo=modulo).first()

            if accion == 'ver':
                if not permiso:
                    flash('No tienes permisos para acceder a este módulo.', 'danger')
                    return redirect(url_for('index'))
                return f(*args, **kwargs)

            if not permiso:
                flash('No tienes permisos para realizar esta acción.', 'danger')
                return redirect(url_for('index'))

            attr_map = {
                'crear': 'puede_crear',
                'editar': 'puede_editar',
                'eliminar': 'puede_eliminar',
            }
            attr_name = attr_map.get(accion)
            if not attr_name or not getattr(permiso, attr_name, False):
                flash('No tienes permisos para realizar esta acción.', 'danger')
                return redirect(url_for('index'))

            return f(*args, **kwargs)

        return wrapper

    return decorator

def sede_requerida(f):
    """Decorador para proteger rutas que requieren una sede activa en sesión."""
    @wraps(f)
    def sede_wrapper(*args, **kwargs):
        if session.get('sede_id') is None:
            return redirect('/seleccionar-sede')
        return f(*args, **kwargs)
    return sede_wrapper


def cargar_permisos_usuario(documento):
    """Carga los permisos de un usuario en la sesión actual."""
    from database import UserPermission
    
    if session.get('rol') in ('admin', 'superadmin'):
        full_access = {
            'ver': True,
            'crear': True,
            'editar': True,
            'eliminar': True,
        }
        session['mod_access'] = {
            'prestamos': dict(full_access),
            'reservas': dict(full_access),
            'inventario': dict(full_access),
            'profesores': dict(full_access),
            'estadisticas': dict(full_access),
            'bitacora': dict(full_access),
            'salas_computo': dict(full_access),
            'usuarios': dict(full_access),
        }
        return session['mod_access']

    permisos = UserPermission.query.filter_by(usuario_documento=documento).all()
    
    mod_access = {}
    for p in permisos:
        mod_access[p.modulo] = {
            'ver': True, # Si existe el registro, al menos tiene 'ver'
            'crear': p.puede_crear,
            'editar': p.puede_editar,
            'eliminar': p.puede_eliminar
        }
    
    session['mod_access'] = mod_access
    return mod_access
