"""
Blueprint para funciones administrativas y gestión de usuarios auxiliares.
Requiere permisos de administrador para todas las operaciones.
"""
from flask import Blueprint, render_template, request, redirect, flash, jsonify, send_file, url_for, session, current_app
import io
import pandas as pd
import re
from datetime import datetime, date, timedelta
from utils.export_helpers import exportar_df_excel, exportar_df_csv
from database import (
    db,
    Auxiliar,
    AuxiliarSede,
    Profesor,
    Sede,
    Bodega,
    Inventario,
    PrestamoEquipo,
    Reserva,
    Festivo,
    CategoriaInventario,
    UserPermission,
    AuditLog,
    registrar_auditoria,
)
from validators import DataValidator
from werkzeug.security import generate_password_hash
from sqlalchemy import func, desc, asc, or_
from config import SystemConstants
from auth import login_required, admin_required
from services.admin_service import AdminService

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

PERMISSION_MODULES = [
    'prestamos',
    'reservas',
    'inventario',
    'profesores',
    'salas_computo',
    'colaboradores',
    'estadisticas',
    'bitacora',
    'mantenimiento',
    'usuarios',
    'entregas_turno'
]

ROLE_PRESETS = {
    'superadmin': {
        'nombre': 'Super Administrador',
        'badge': 'danger',
        'descripcion': 'Control total e irrestricto en todos los módulos y sedes de la institución.',
        'permisos': {m: {'ver': True, 'crear': True, 'editar': True, 'eliminar': True} for m in PERMISSION_MODULES}
    },
    'admin': {
        'nombre': 'Administrador de Sede',
        'badge': 'primary',
        'descripcion': 'Gestión integral de operaciones y control de recursos en su sede.',
        'permisos': {m: {'ver': True, 'crear': True, 'editar': True, 'eliminar': True} for m in PERMISSION_MODULES}
    },
    'auxiliar': {
        'nombre': 'Auxiliar Operativo / Soporte TI',
        'badge': 'info',
        'descripcion': 'Operación diaria: Préstamos, Reservas, Salas y registro de Bitácora.',
        'permisos': {
            'prestamos': {'ver': True, 'crear': True, 'editar': True, 'eliminar': False},
            'reservas': {'ver': True, 'crear': True, 'editar': True, 'eliminar': False},
            'inventario': {'ver': True, 'crear': False, 'editar': True, 'eliminar': False},
            'profesores': {'ver': True, 'crear': True, 'editar': False, 'eliminar': False},
            'salas_computo': {'ver': True, 'crear': True, 'editar': True, 'eliminar': False},
            'colaboradores': {'ver': True, 'crear': False, 'editar': False, 'eliminar': False},
            'estadisticas': {'ver': True, 'crear': False, 'editar': False, 'eliminar': False},
            'bitacora': {'ver': True, 'crear': True, 'editar': False, 'eliminar': False},
        }
    },
    'docente': {
        'nombre': 'Docente / Solicitante',
        'badge': 'success',
        'descripcion': 'Consulta y radicación de solicitudes de préstamos y reserva de aulas.',
        'permisos': {
            'prestamos': {'ver': True, 'crear': True, 'editar': False, 'eliminar': False},
            'reservas': {'ver': True, 'crear': True, 'editar': False, 'eliminar': False},
            'inventario': {'ver': False, 'crear': False, 'editar': False, 'eliminar': False},
            'profesores': {'ver': True, 'crear': False, 'editar': False, 'eliminar': False},
            'salas_computo': {'ver': True, 'crear': False, 'editar': False, 'eliminar': False},
            'colaboradores': {'ver': False, 'crear': False, 'editar': False, 'eliminar': False},
            'estadisticas': {'ver': False, 'crear': False, 'editar': False, 'eliminar': False},
            'bitacora': {'ver': False, 'crear': False, 'editar': False, 'eliminar': False},
        }
    },
    'auditoria': {
        'nombre': 'Auditor / Revisor',
        'badge': 'warning',
        'descripcion': 'Acceso de solo lectura para supervisión, trazabilidad y reportes.',
        'permisos': {m: {'ver': True, 'crear': False, 'editar': False, 'eliminar': False} for m in PERMISSION_MODULES}
    }
}

@admin_bp.route('/impersonate/<documento>')
@login_required
@admin_required
def impersonate_user(documento):
    """Permite al admin simular temporalmente la sesión de un usuario de menor jerarquía."""
    try:
        usuario_objetivo = Auxiliar.query.get_or_404(documento)

        rol_actual    = session.get('rol')          # rol de quien ejecuta la acción
        rol_objetivo  = usuario_objetivo.rol        # rol del usuario a impersonar

        # ── Jerarquía: superadmin > admin > auxiliar ─────────────────────────
        # Un admin solo puede impersonar auxiliares.
        # Un superadmin puede impersonar admins y auxiliares.
        # Nadie puede impersonarse a sí mismo.
        JERARQUIA = {'superadmin': 2, 'admin': 1, 'auxiliar': 0}
        nivel_actual   = JERARQUIA.get(rol_actual,  -1)
        nivel_objetivo = JERARQUIA.get(rol_objetivo, -1)

        if usuario_objetivo.documento == session.get('usuario'):
            flash('No puedes impersonarte a ti mismo.', 'warning')
            return redirect(url_for('admin.usuarios_main'))

        if nivel_objetivo >= nivel_actual:
            flash(
                f'No tienes permiso para impersonar a un usuario con rol "{rol_objetivo}". '
                'Solo puedes simular usuarios de menor jerarquía.',
                'danger'
            )
            registrar_auditoria(
                modulo='admin',
                entidad_tipo='Auxiliar',
                entidad_id=documento,
                accion='IMPERSONAR_DENEGADO',
                usuario_documento=session.get('usuario', ''),
                usuario_nombre=session.get('nombre_completo', ''),
                descripcion=(
                    f"Intento de impersonación denegado: "
                    f"{session.get('nombre_completo')} ({rol_actual}) "
                    f"→ {usuario_objetivo.nombre_completo} ({rol_objetivo})"
                )
            )
            return redirect(url_for('admin.usuarios_main'))

        # ── Guardar sesión original (solo la primera vez) ─────────────────────
        if 'admin_original_doc' not in session:
            session['admin_original_doc']      = session.get('usuario')
            session['admin_original_nombre']   = session.get('nombre_completo')
            session['admin_original_rol']      = session.get('rol')
            session['admin_original_permisos'] = session.get('mod_access', {})

        # ── Cambiar a la sesión del objetivo ──────────────────────────────────
        session['usuario']         = usuario_objetivo.documento
        session['nombre_completo'] = usuario_objetivo.nombre_completo
        session['rol']             = usuario_objetivo.rol

        from auth import cargar_permisos_usuario
        cargar_permisos_usuario(usuario_objetivo.documento)

        registrar_auditoria(
            modulo='admin',
            entidad_tipo='Auxiliar',
            entidad_id=documento,
            accion='IMPERSONAR',
            usuario_documento=session['admin_original_doc'],
            usuario_nombre=session['admin_original_nombre'],
            descripcion=(
                f"{session['admin_original_nombre']} ({rol_actual}) "
                f"impersonó a {usuario_objetivo.nombre_completo} ({rol_objetivo})"
            )
        )

        flash(
            f'Simulando sesión como: {usuario_objetivo.nombre_completo} '
            f'(rol: {usuario_objetivo.rol}).',
            'info'
        )
        return redirect(url_for('index'))

    except Exception as e:
        current_app.logger.error('Error al impersonar usuario %s: %s', documento, e)
        flash('Error al intentar cambiar de modo.', 'danger')
        return redirect(url_for('admin.usuarios_main'))


@admin_bp.route('/revert-impersonation')
@login_required
def revert_impersonation():
    """Vuelve a la sesión original del administrador que inició la impersonación."""
    if 'admin_original_doc' not in session:
        flash('No hay una sesión de administrador original para restaurar.', 'warning')
        return redirect(url_for('index'))

    # Restaurar sesión original
    session['usuario']        = session['admin_original_doc']
    session['nombre_completo']= session['admin_original_nombre']
    session['rol']            = session['admin_original_rol']
    session['mod_access']     = session['admin_original_permisos']

    registrar_auditoria(
        modulo='admin',
        entidad_tipo='Sesion',
        entidad_id=session['usuario'],
        accion='REVERTIR_IMPERSONACION',
        usuario_documento=session['usuario'],
        usuario_nombre=session['nombre_completo'],
        descripcion=f"{session['nombre_completo']} revirtió la impersonación y recuperó su sesión original."
    )

    # Limpiar rastros de impersonación
    session.pop('admin_original_doc',      None)
    session.pop('admin_original_nombre',   None)
    session.pop('admin_original_rol',      None)
    session.pop('admin_original_permisos', None)

    flash('Has vuelto a tu sesión de Administrador.', 'success')
    return redirect(url_for('admin.usuarios_main'))


# === GESTIÓN DE USUARIOS ===
@admin_bp.route('/usuarios')
@login_required
@admin_required
def usuarios_main():
    """Página principal de gestión de usuarios y roles."""
    try:
        rol_filtro = request.args.get('rol', '')
        sede_filtro = request.args.get('sede_id', '')
        estado_filtro = request.args.get('estado', '')
        busqueda = request.args.get('busqueda', '')
        ordenar_por = request.args.get('ordenar', 'nombre_completo')
        orden = request.args.get('orden', 'asc')

        usuarios = AdminService.obtener_usuarios_filtrados(request.args)
        todos_usuarios = Auxiliar.query.all()

        stats = {
            'total_usuarios': len(todos_usuarios),
            'total_admins': len([u for u in todos_usuarios if u.rol in ('admin', 'superadmin')]),
            'total_auxiliares': len([u for u in todos_usuarios if u.rol == 'auxiliar']),
            'total_docentes': len([u for u in todos_usuarios if u.rol == 'docente']),
            'total_auditoria': len([u for u in todos_usuarios if u.rol == 'auditoria']),
            'total_activos': len([u for u in todos_usuarios if getattr(u, 'activo', True)]),
            'total_inactivos': len([u for u in todos_usuarios if not getattr(u, 'activo', True)]),
        }

        sedes = Sede.query.all()

        return render_template('admin_usuarios.html',
                             usuarios=usuarios,
                             sedes=sedes,
                             stats=stats,
                             permission_modules=PERMISSION_MODULES,
                             role_presets=ROLE_PRESETS,
                             filtros={
                                 'rol': rol_filtro,
                                 'sede_id': sede_filtro,
                                 'estado': estado_filtro,
                                 'busqueda': busqueda,
                                 'ordenar': ordenar_por,
                                 'orden': orden
                             })

    except Exception as e:
        current_app.logger.error(f"Error al cargar usuarios: {e}")
        flash('Error al cargar los usuarios.', 'danger')
        return render_template('admin_usuarios.html', usuarios=[], sedes=[], stats={}, filtros={}, permission_modules=PERMISSION_MODULES, role_presets=ROLE_PRESETS)

@admin_bp.route('/usuarios/agregar', methods=['POST'])
@login_required
@admin_required
def agregar_usuario():
    """Agrega un nuevo usuario auxiliar."""
    try:
        datos = request.json
        
        # Validar documento
        doc_valid, doc_value, doc_error = DataValidator.validate_cedula(datos.get('documento'))
        if not doc_valid:
            return jsonify({'success': False, 'message': doc_error}), 400
        
        # Verificar que no exista
        if Auxiliar.query.get(str(doc_value)):
            return jsonify({'success': False, 'message': 'Ya existe un usuario con ese documento'}), 409
        
        # Validar nombre completo
        nombre_valid, nombre_error = DataValidator.validate_string_field(
            datos.get('nombre_completo'), 'Nombre completo', min_length=3, max_length=150
        )
        if not nombre_valid:
            return jsonify({'success': False, 'message': nombre_error}), 400
        
        # Validar email
        email_valid, email_error = DataValidator.validate_email(datos.get('correo'))
        if not email_valid:
            return jsonify({'success': False, 'message': email_error}), 400
        
        # Verificar que el email no esté en uso
        if Auxiliar.query.filter_by(correo=datos.get('correo').strip().lower()).first():
            return jsonify({'success': False, 'message': 'El correo ya está registrado'}), 409
        
        # Validar contraseña
        pwd_valid, pwd_error = DataValidator.validate_password(datos.get('contraseña'))
        if not pwd_valid:
            return jsonify({'success': False, 'message': pwd_error}), 400
        
        # Validar rol
        rol = datos.get('rol', 'auxiliar')
        if rol not in ['superadmin', 'admin', 'auxiliar']:
            return jsonify({'success': False, 'message': 'Rol no válido'}), 400
        
        # Crear el usuario
        nuevo_usuario = Auxiliar(
            documento=str(doc_value),
            nombre_completo=datos.get('nombre_completo').strip(),
            correo=datos.get('correo').strip().lower(),
            contraseña=generate_password_hash(datos.get('contraseña')),
            rol=rol,
            sede_id=datos.get('sede_id') if datos.get('sede_id') else None
        )
        
        db.session.add(nuevo_usuario)
        db.session.commit()

        registrar_auditoria(
            modulo='admin',
            entidad_tipo='Usuario',
            entidad_id=nuevo_usuario.documento,
            accion='CREAR',
            descripcion=f'Creación de usuario {nuevo_usuario.nombre_completo} ({nuevo_usuario.documento})',
            datos_antes=None,
            datos_despues={
                'documento': nuevo_usuario.documento,
                'nombre_completo': nuevo_usuario.nombre_completo,
                'correo': nuevo_usuario.correo,
                'rol': nuevo_usuario.rol,
                'sede_id': nuevo_usuario.sede_id,
            }
        )

        return jsonify({
            'success': True,
            'message': 'Usuario agregado exitosamente',
            'usuario_id': nuevo_usuario.documento
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@admin_bp.route('/usuarios/<documento>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@admin_required
def gestionar_usuario(documento):
    """Obtiene, actualiza o elimina un usuario."""
    usuario = Auxiliar.query.get_or_404(documento)
    
    if request.method == 'GET':
        # Obtener datos del usuario
        usuario_data = {
            'documento': usuario.documento,
            'nombre_completo': usuario.nombre_completo,
            'correo': usuario.correo,
            'rol': usuario.rol
        }
        return jsonify({'success': True, 'usuario': usuario_data})
    
    elif request.method == 'PUT':
        # Actualizar usuario
        try:
            datos = request.json

            datos_antes = {
                'nombre_completo': usuario.nombre_completo,
                'correo': usuario.correo,
                'rol': usuario.rol,
                'sede_id': usuario.sede_id,
            }

            # Prevenir que un admin/superadmin se cambie el rol a sí mismo
            if documento == session.get('usuario') and datos.get('rol') not in ('admin', 'superadmin'):
                return jsonify({
                    'success': False, 
                    'message': 'No puedes cambiar tu propio rol a no-administrador'
                }), 403
            
            # Validar nombre completo
            nombre_valid, nombre_error = DataValidator.validate_string_field(
                datos.get('nombre_completo'), 'Nombre completo', min_length=3, max_length=150
            )
            if not nombre_valid:
                return jsonify({'success': False, 'message': nombre_error}), 400
            
            # Validar email
            email_valid, email_error = DataValidator.validate_email(datos.get('correo'))
            if not email_valid:
                return jsonify({'success': False, 'message': email_error}), 400
            
            # Verificar que el email no esté en uso por otro usuario
            otro_usuario = Auxiliar.query.filter(
                Auxiliar.correo == datos.get('correo').strip().lower(),
                Auxiliar.documento != documento
            ).first()
            if otro_usuario:
                return jsonify({'success': False, 'message': 'El correo ya está registrado'}), 409
            
            # Validar rol
            rol = datos.get('rol', 'auxiliar')
            if rol not in ['superadmin', 'admin', 'auxiliar']:
                return jsonify({'success': False, 'message': 'Rol no válido'}), 400
            
            # Actualizar campos básicos
            usuario.nombre_completo = datos.get('nombre_completo').strip()
            usuario.correo = datos.get('correo').strip().lower()
            usuario.rol = datos.get('rol', 'auxiliar')
            usuario.sede_id = datos.get('sede_id') if datos.get('sede_id') else None
            # Actualizar contraseña si se proporciona
            if 'contraseña' in datos and datos['contraseña']:
                pwd_valid, pwd_error = DataValidator.validate_password(datos['contraseña'])
                if not pwd_valid:
                    return jsonify({'success': False, 'message': pwd_error}), 400
                usuario.contraseña = generate_password_hash(datos['contraseña'])
            
            db.session.commit()

            datos_despues = {
                'nombre_completo': usuario.nombre_completo,
                'correo': usuario.correo,
                'rol': usuario.rol,
                'sede_id': usuario.sede_id,
            }

            registrar_auditoria(
                modulo='usuarios',
                entidad_tipo='Auxiliar',
                entidad_id=usuario.documento,
                accion='EDITAR',
                descripcion=f'Edición de usuario {usuario.nombre_completo} ({usuario.documento})',
                datos_antes=datos_antes,
                datos_despues=datos_despues
            )

            return jsonify({'success': True, 'message': 'Usuario actualizado exitosamente'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500
    
    elif request.method == 'DELETE':
        # Eliminar usuario
        try:
            # Prevenir que un admin se elimine a sí mismo
            if documento == session.get('usuario'):
                return jsonify({
                    'success': False,
                    'message': 'No puedes eliminar tu propia cuenta'
                }), 403
            
            # Verificar si es el último administrador
            total_admins = Auxiliar.query.filter_by(rol='admin').count()
            if usuario.rol == 'admin' and total_admins <= 1:
                return jsonify({
                    'success': False,
                    'message': 'No se puede eliminar el último administrador del sistema'
                }), 400
            
            datos_antes = {
                'documento': usuario.documento,
                'nombre_completo': usuario.nombre_completo,
                'correo': usuario.correo,
                'rol': usuario.rol,
                'sede_id': usuario.sede_id,
            }

            db.session.delete(usuario)
            db.session.commit()

            registrar_auditoria(
                modulo='usuarios',
                entidad_tipo='Auxiliar',
                entidad_id=documento,
                accion='ELIMINAR',
                descripcion=f'Eliminación de usuario {datos_antes["nombre_completo"]} ({documento})',
                datos_antes=datos_antes,
                datos_despues=None
            )

            return jsonify({'success': True, 'message': 'Usuario eliminado exitosamente'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@admin_bp.route('/api/roles/presets', methods=['GET'])
@login_required
@admin_required
def api_roles_presets():
    """Retorna las plantillas predefinidas de roles y permisos."""
    return jsonify({'success': True, 'presets': ROLE_PRESETS, 'modules': PERMISSION_MODULES})


@admin_bp.route('/usuarios/<documento>/estado', methods=['PUT'])
@login_required
@admin_required
def cambiar_estado_usuario(documento):
    """Activa o desactiva la cuenta de un usuario."""
    try:
        usuario = Auxiliar.query.get_or_404(documento)

        if documento == session.get('usuario'):
            return jsonify({'success': False, 'message': 'No puedes desactivar tu propia cuenta activa.'}), 403

        datos = request.get_json(silent=True) or {}
        nuevo_estado = bool(datos.get('activo', not getattr(usuario, 'activo', True)))

        estado_ant = getattr(usuario, 'activo', True)
        usuario.activo = nuevo_estado
        db.session.commit()

        registrar_auditoria(
            modulo='usuarios',
            entidad_tipo='Auxiliar',
            entidad_id=documento,
            accion='CAMBIAR_ESTADO',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Cuenta de {usuario.nombre_completo} {"ACTIVADA" if nuevo_estado else "DESACTIVADA"}',
            datos_antes={'activo': estado_ant},
            datos_despues={'activo': nuevo_estado}
        )

        return jsonify({
            'success': True,
            'message': f'Usuario {"activado" if nuevo_estado else "desactivado"} exitosamente.',
            'activo': nuevo_estado
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error cambiando estado de usuario: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/usuarios/<documento>/reset-password', methods=['POST'])
@login_required
@admin_required
def resetear_password_usuario(documento):
    """Restablece la contraseña de un usuario."""
    try:
        usuario = Auxiliar.query.get_or_404(documento)
        datos = request.get_json(silent=True) or {}
        nueva_clave = datos.get('nueva_contraseña', '').strip()

        if not nueva_clave:
            import secrets, string
            letras = string.ascii_letters
            digitos = string.digits
            simbolos = "!@#$"
            parte1 = ''.join(secrets.choice(letras) for _ in range(5))
            parte2 = ''.join(secrets.choice(digitos) for _ in range(3))
            parte3 = ''.join(secrets.choice(simbolos) for _ in range(2))
            lista_chars = list(parte1 + parte2 + parte3)
            secrets.SystemRandom().shuffle(lista_chars)
            nueva_clave = ''.join(lista_chars)

        pwd_valid, pwd_error = DataValidator.validate_password(nueva_clave)
        if not pwd_valid:
            return jsonify({'success': False, 'message': pwd_error}), 400

        usuario.contraseña = generate_password_hash(nueva_clave)
        db.session.commit()

        registrar_auditoria(
            modulo='usuarios',
            entidad_tipo='Auxiliar',
            entidad_id=documento,
            accion='RESET_PASSWORD',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Restablecimiento de contraseña para {usuario.nombre_completo}'
        )

        return jsonify({
            'success': True,
            'message': 'Contraseña restablecida con éxito.',
            'password_generada': nueva_clave
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error restableciendo contraseña: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/usuarios/<documento>/sedes', methods=['GET', 'POST'])
@login_required
@admin_required
def gestionar_sedes_usuario(documento):
    """Obtiene o asigna sedes a un usuario."""
    usuario = Auxiliar.query.get_or_404(documento)

    if request.method == 'GET':
        sedes_asignadas = []
        for asig in usuario.sedes_asignadas:
            if asig.sede:
                sedes_asignadas.append({'id': asig.sede.id, 'nombre': asig.sede.nombre})
        return jsonify({'success': True, 'sedes': sedes_asignadas})

    elif request.method == 'POST':
        try:
            datos = request.get_json(silent=True) or {}
            sede_id = datos.get('sede_id')
            if not sede_id:
                return jsonify({'success': False, 'message': 'ID de sede requerido'}), 400

            existe = AuxiliarSede.query.filter_by(usuario_documento=documento, sede_id=int(sede_id)).first()
            if existe:
                return jsonify({'success': False, 'message': 'La sede ya está asignada al usuario.'}), 409

            nueva_asig = AuxiliarSede(usuario_documento=documento, sede_id=int(sede_id))
            db.session.add(nueva_asig)
            db.session.commit()

            return jsonify({'success': True, 'message': 'Sede asignada correctamente.'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/usuarios/<documento>/sedes/<int:sede_id>', methods=['DELETE'])
@login_required
@admin_required
def eliminar_sede_usuario(documento, sede_id):
    """Revoca la asignación de una sede a un usuario."""
    try:
        asig = AuxiliarSede.query.filter_by(usuario_documento=documento, sede_id=sede_id).first()
        if asig:
            db.session.delete(asig)
            db.session.commit()
        return jsonify({'success': True, 'message': 'Sede revocada exitosamente.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/usuarios/<documento>/permisos', methods=['GET', 'PUT'])
@login_required
@admin_required
def gestionar_permisos_usuario(documento):
    """Obtiene o actualiza los permisos granulares de un usuario."""
    usuario = Auxiliar.query.get_or_404(documento)

    if request.method == 'GET':
        permisos_por_modulo = {m: {'ver': False, 'crear': False, 'editar': False, 'eliminar': False} for m in PERMISSION_MODULES}
        permisos_db = UserPermission.query.filter_by(usuario_documento=documento).all()
        for p in permisos_db:
            if p.modulo in permisos_por_modulo:
                permisos_por_modulo[p.modulo]['ver'] = getattr(p, 'puede_ver', True)
                permisos_por_modulo[p.modulo]['crear'] = p.puede_crear
                permisos_por_modulo[p.modulo]['editar'] = p.puede_editar
                permisos_por_modulo[p.modulo]['eliminar'] = p.puede_eliminar
        return jsonify({'success': True, 'permisos': permisos_por_modulo})

    elif request.method == 'PUT':
        try:
            datos = request.json or {}
            permisos_entrada = datos.get('permisos', datos)

            permisos_antes = {
                p.modulo: {
                    'ver': getattr(p, 'puede_ver', True),
                    'crear': p.puede_crear,
                    'editar': p.puede_editar,
                    'eliminar': p.puede_eliminar,
                }
                for p in UserPermission.query.filter_by(usuario_documento=documento).all()
            }

            for modulo in PERMISSION_MODULES:
                valores = permisos_entrada.get(modulo, {})
                ver_flag = bool(valores.get('ver', False))
                crear_flag = bool(valores.get('crear', False))
                editar_flag = bool(valores.get('editar', False))
                eliminar_flag = bool(valores.get('eliminar', False))

                perm = UserPermission.query.filter_by(usuario_documento=documento, modulo=modulo).first()
                if not ver_flag and not (crear_flag or editar_flag or eliminar_flag):
                    if perm is not None:
                        db.session.delete(perm)
                    continue

                if perm is None:
                    perm = UserPermission(
                        usuario_documento=documento,
                        modulo=modulo,
                        puede_ver=ver_flag,
                        puede_crear=crear_flag,
                        puede_editar=editar_flag,
                        puede_eliminar=eliminar_flag,
                    )
                    db.session.add(perm)
                else:
                    perm.puede_ver = ver_flag
                    perm.puede_crear = crear_flag
                    perm.puede_editar = editar_flag
                    perm.puede_eliminar = eliminar_flag

            db.session.commit()
            session.pop('mod_access_cache', None)

            permisos_despues = {
                p.modulo: {
                    'ver': getattr(p, 'puede_ver', True),
                    'crear': p.puede_crear,
                    'editar': p.puede_editar,
                    'eliminar': p.puede_eliminar,
                }
                for p in UserPermission.query.filter_by(usuario_documento=documento).all()
            }

            registrar_auditoria(
                modulo='usuarios',
                entidad_tipo='PermisosUsuario',
                entidad_id=usuario.documento,
                accion='EDITAR',
                usuario_documento=session.get('usuario', ''),
                usuario_nombre=session.get('nombre_completo', ''),
                descripcion=f'Actualización de permisos para usuario {usuario.nombre_completo} ({usuario.documento})',
                datos_antes=permisos_antes,
                datos_despues=permisos_despues
            )

            return jsonify({'success': True, 'message': 'Permisos actualizados correctamente'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500


# === GESTIÓN DE FESTIVOS ===
@admin_bp.route('/festivos')
@login_required
@admin_required
def festivos_main():
    """Página principal de gestión de días festivos."""
    try:
        # Obtener festivos ordenados por fecha
        festivos = Festivo.query.order_by(Festivo.fecha).all()
        
        # Separar en pasados y futuros
        hoy = date.today()
        festivos_futuros = [f for f in festivos if f.fecha >= hoy]
        festivos_pasados = [f for f in festivos if f.fecha < hoy]
        
        return render_template('admin_festivos.html',
                             festivos_futuros=festivos_futuros,
                             festivos_pasados=festivos_pasados)
                             
    except Exception as e:
        flash('Error al cargar los días festivos.', 'danger')
        return render_template('admin_festivos.html', festivos_futuros=[], festivos_pasados=[])

@admin_bp.route('/festivos/agregar', methods=['POST'])
@login_required
@admin_required
def agregar_festivo():
    """Agrega un nuevo día festivo."""
    try:
        datos = request.json
        
        # Validar fecha
        fecha_valid, fecha_obj, fecha_error = DataValidator.validate_date(datos.get('fecha'))
        if not fecha_valid:
            return jsonify({'success': False, 'message': fecha_error}), 400
        
        # Verificar que no exista
        if Festivo.query.get(fecha_obj):
            return jsonify({'success': False, 'message': 'Ya existe un festivo en esa fecha'}), 409
        
        # Validar descripción
        desc_valid, desc_error = DataValidator.validate_string_field(
            datos.get('descripcion'), 'Descripción', min_length=3, max_length=200
        )
        if not desc_valid:
            return jsonify({'success': False, 'message': desc_error}), 400
        
        # Crear el festivo
        nuevo_festivo = Festivo(
            fecha=fecha_obj,
            descripcion=datos.get('descripcion').strip()
        )
        
        db.session.add(nuevo_festivo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Día festivo agregado exitosamente',
            'festivo': {
                'fecha': fecha_obj.strftime('%Y-%m-%d'),
                'descripcion': nuevo_festivo.descripcion
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@admin_bp.route('/festivos/<fecha>', methods=['DELETE'])
@login_required
@admin_required
def eliminar_festivo(fecha):
    """Elimina un día festivo."""
    try:
        fecha_valid, fecha_obj, fecha_error = DataValidator.validate_date(fecha)
        if not fecha_valid:
            return jsonify({'success': False, 'message': fecha_error}), 400
        
        festivo = Festivo.query.get_or_404(fecha_obj)
        
        db.session.delete(festivo)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Día festivo eliminado exitosamente'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

# === CONFIGURACIÓN DEL SISTEMA ===
@admin_bp.route('/configuracion')
@login_required
@admin_required
def configuracion_sistema():
    """Página de configuración general del sistema."""
    try:
        # Estadísticas generales del sistema
        stats = {
            'total_usuarios': Auxiliar.query.count(),
            'total_profesores': db.session.execute(db.text("SELECT COUNT(*) FROM profesores")).scalar(),
            'total_inventario': db.session.execute(db.text("SELECT COUNT(*) FROM inventario")).scalar(),
            'total_prestamos': PrestamoEquipo.query.count(),
            'total_reservas': Reserva.query.count(),
            'prestamos_activos': PrestamoEquipo.query.filter_by(estado='Prestado').count(),
            'reservas_activas': Reserva.query.filter_by(estado='Activa').count(),
            'festivos_configurados': Festivo.query.count()
        }
        
        # Estado de la base de datos
        try:
            db.session.execute(db.text("SELECT 1")).scalar()
            db_status = 'Conectado'
        except Exception as e:
            current_app.logger.warning("Error de conexión a BD en configuracion_sistema: %s", e)
            db_status = 'Error de conexión'
        
        # Información del sistema
        sistema_info = {
            'db_status': db_status,
            'version': '2.0.0',
            'ambiente': 'Desarrollo' if current_app.config.get('DEBUG') else 'Producción',
            'ultimo_respaldo': 'No disponible'  # Aquí podrías implementar lógica de respaldos
        }
        
        return render_template('admin_configuracion.html',
                             stats=stats,
                             sistema_info=sistema_info)
                             
    except Exception as e:
        flash('Error al cargar la configuración del sistema.', 'danger')
        return render_template('admin_configuracion.html', stats={}, sistema_info={})

# === RESPALDOS Y EXPORTACIONES ===
@admin_bp.route('/respaldo/completo')
@login_required
@admin_required
def backup_sistema():
    """Genera un respaldo completo del sistema en un Excel con múltiples hojas."""
    try:
        # ── Usuarios ──────────────────────────────────────────────────────────
        usuarios_df = pd.DataFrame(
            db.session.execute(db.text(
                "SELECT documento, nombre_completo, correo, rol "
                "FROM auxiliares ORDER BY nombre_completo"
            )).fetchall(),
            columns=['documento', 'nombre_completo', 'correo', 'rol']
        )

        # ── Profesores ────────────────────────────────────────────────────────
        profesores_df = pd.DataFrame(
            db.session.execute(db.text(
                "SELECT cedula, nombre_completo, correo, telefono, programa "
                "FROM profesores ORDER BY nombre_completo"
            )).fetchall(),
            columns=['cedula', 'nombre_completo', 'correo', 'telefono', 'programa']
        )

        # ── Inventario ────────────────────────────────────────────────────────
        inventario_df = pd.DataFrame(
            db.session.execute(db.text(
                "SELECT categoria, item, marca_modelo, serial, activo_fijo, "
                "numero_inventario, ubicacion_permanente, estado, observaciones "
                "FROM inventario ORDER BY categoria, item"
            )).fetchall(),
            columns=['categoria', 'item', 'marca_modelo', 'serial',
                     'activo_fijo', 'numero_inventario', 'ubicacion_permanente',
                     'estado', 'observaciones']
        )

        # ── Préstamos (últimos 1000) ───────────────────────────────────────────
        prestamos_df = pd.DataFrame(
            db.session.execute(db.text(
                "SELECT cedula_profesor, nombre_profesor, equipo_prestado, "
                "numero_inventario_equipo, ubicacion, fecha_prestamo, jornada, "
                "hora_inicio, hora_fin, auxiliar_entrega, auxiliar_recibe, "
                "fecha_devolucion, hora_devolucion_real, estado, observaciones "
                "FROM prestamos_equipos "
                "ORDER BY fecha_prestamo DESC, id_prestamo DESC LIMIT 1000"
            )).fetchall(),
            columns=['cedula_profesor', 'nombre_profesor', 'equipo_prestado',
                     'numero_inventario_equipo', 'ubicacion', 'fecha_prestamo',
                     'jornada', 'hora_inicio', 'hora_fin', 'auxiliar_entrega',
                     'auxiliar_recibe', 'fecha_devolucion', 'hora_devolucion_real',
                     'estado', 'observaciones']
        )

        # ── Reservas (últimas 1000) ───────────────────────────────────────────
        reservas_df = pd.DataFrame(
            db.session.execute(db.text(
                "SELECT cedula_profesor, nombre_profesor, nrc, recurso_tipo, "
                "recurso_nombre, fecha, jornada, hora_inicio, hora_fin, "
                "tipo_reserva, estado, observaciones "
                "FROM reservas ORDER BY fecha DESC, id_reserva DESC LIMIT 1000"
            )).fetchall(),
            columns=['cedula_profesor', 'nombre_profesor', 'nrc', 'recurso_tipo',
                     'recurso_nombre', 'fecha', 'jornada', 'hora_inicio', 'hora_fin',
                     'tipo_reserva', 'estado', 'observaciones']
        )

        # ── Festivos ──────────────────────────────────────────────────────────
        festivos_df = pd.DataFrame(
            db.session.execute(db.text(
                "SELECT fecha, descripcion FROM festivos ORDER BY fecha"
            )).fetchall(),
            columns=['fecha', 'descripcion']
        )

        return exportar_df_excel(
            usuarios_df,
            sheet_name='Auxiliares',
            prefix='respaldo_completo',
            extra_sheets=[
                (profesores_df, 'Profesores'),
                (inventario_df, 'Inventario'),
                (prestamos_df,  'Prestamos'),
                (reservas_df,   'Reservas'),
                (festivos_df,   'Festivos'),
            ],
        )

    except Exception as e:
        current_app.logger.error('Error al generar respaldo completo: %s', e)
        flash(f'Error al generar el respaldo completo: {str(e)}', 'danger')
        return redirect(url_for('admin.configuracion_sistema'))

# === LOGS DEL SISTEMA ===
@admin_bp.route('/logs')
@login_required
@admin_required
def ver_logs():
    """Muestra el historial de auditoría del sistema."""
    try:
        modulo_filtro = request.args.get('modulo', '')
        usuario_filtro = request.args.get('usuario', '')

        query = AuditLog.query
        if modulo_filtro:
            query = query.filter(AuditLog.modulo == modulo_filtro)
        if usuario_filtro:
            query = query.filter(AuditLog.usuario_documento == usuario_filtro)

        logs_db = query.order_by(AuditLog.fecha.desc(), AuditLog.hora.desc()).limit(500).all()

        logs = []
        for log in logs_db:
            timestamp = f"{log.fecha.strftime('%Y-%m-%d')} {log.hora.strftime('%H:%M:%S')}"
            mensaje = f"[{log.modulo.upper()}] {log.accion}: {log.descripcion or ''}"
            logs.append(
                {
                    'timestamp': timestamp,
                    'nivel': 'INFO',
                    'mensaje': mensaje,
                    'usuario': f"{log.usuario_documento} - {log.usuario_nombre}",
                }
            )

        return render_template('admin_logs.html', logs=logs)
    except Exception as e:
        flash('Error al cargar los logs del sistema.', 'danger')
        return render_template('admin_logs.html', logs=[])

# === GESTIÓN DE SEDES Y BODEGAS ===
@admin_bp.route('/sedes_bodegas')
@admin_bp.route('/sedes_y_bodegas')
@login_required
@admin_required
def sedes_bodegas_main():
    """Página principal de configuración de sedes, bodegas y categorías."""
    try:
        sedes = Sede.query.order_by(Sede.nombre).all()
        bodegas = Bodega.query.order_by(Bodega.nombre).all()
        categorias = CategoriaInventario.query.order_by(CategoriaInventario.nombre).all()
        return render_template('admin_sedes_bodegas.html', sedes=sedes, bodegas=bodegas, categorias=categorias)
    except Exception as e:
        flash(f'Error al cargar configuración: {str(e)}', 'danger')
        return redirect(url_for('admin.configuracion_sistema'))

@admin_bp.route('/categorias/agregar', methods=['POST'])
@login_required
@admin_required
def agregar_categoria():
    """Agrega una nueva categoría de inventario."""
    try:
        nombre = request.form.get('nombre', '').strip()
        if not nombre:
            flash('El nombre de la categoría es requerido.', 'warning')
            return redirect(url_for('admin.sedes_bodegas_main'))
        
        # Verificar si existe
        if CategoriaInventario.query.filter_by(nombre=nombre).first():
            flash(f'La categoría "{nombre}" ya existe.', 'warning')
            return redirect(url_for('admin.sedes_bodegas_main'))
            
        nueva_cat = CategoriaInventario(nombre=nombre)
        db.session.add(nueva_cat)
        db.session.commit()
        flash(f'Categoría "{nombre}" agregada exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al agregar categoría: {str(e)}', 'danger')
    return redirect(url_for('admin.sedes_bodegas_main'))

@admin_bp.route('/categorias/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_required
def eliminar_categoria(id):
    """Elimina una categoría si no tiene items asociados."""
    try:
        cat = CategoriaInventario.query.get(id)
        if not cat:
            flash('Categoría no encontrada.', 'danger')
            return redirect(url_for('admin.sedes_bodegas_main'))
            
        # Verificar si hay items con esa categoría
        has_items = Inventario.query.filter_by(categoria=cat.nombre).first()
        if has_items:
            flash(f'No se puede eliminar la categoría "{cat.nombre}" porque tiene equipos asociados en el inventario.', 'warning')
            return redirect(url_for('admin.sedes_bodegas_main'))
            
        db.session.delete(cat)
        db.session.commit()
        flash('Categoría eliminada exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar categoría: {str(e)}', 'danger')
    return redirect(url_for('admin.sedes_bodegas_main'))

@admin_bp.route('/sedes/agregar', methods=['POST'])
@login_required
@admin_required
def agregar_sede():
    """Agrega una nueva sede."""
    is_json = request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    try:
        data = request.get_json(silent=True) or request.form
        nombre = (data.get('nombre') or '').strip().upper()
        if not nombre:
            msg = 'El nombre de la sede es requerido.'
            if is_json:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'warning')
            return redirect(url_for('admin.sedes_bodegas_main'))
        
        if Sede.query.filter_by(nombre=nombre).first():
            msg = f'La sede "{nombre}" ya existe.'
            if is_json:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'warning')
            return redirect(url_for('admin.sedes_bodegas_main'))
        
        nueva_sede = Sede(nombre=nombre)
        db.session.add(nueva_sede)
        db.session.commit()
        
        msg = f'Sede "{nombre}" agregada exitosamente.'
        if is_json:
            return jsonify({'success': True, 'message': msg, 'id': nueva_sede.id, 'nombre': nueva_sede.nombre})
        flash(msg, 'success')
    except Exception as e:
        db.session.rollback()
        msg = f'Error al agregar sede: {str(e)}'
        if is_json:
            return jsonify({'success': False, 'message': msg}), 500
        flash(msg, 'danger')
    
    return redirect(url_for('admin.sedes_bodegas_main'))

@admin_bp.route('/bodegas/agregar', methods=['POST'])
@login_required
@admin_required
def agregar_bodega():
    """Agrega una nueva bodega vinculada a una sede."""
    is_json = request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    try:
        data = request.get_json(silent=True) or request.form
        nombre = (data.get('nombre') or '').strip().upper()
        sede_id = data.get('sede_id')
        
        if not nombre or not sede_id:
            msg = 'Nombre y Sede son requeridos.'
            if is_json:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'warning')
            return redirect(url_for('admin.sedes_bodegas_main'))
        
        sede = Sede.query.get(int(sede_id)) if str(sede_id).isdigit() else None
        if not sede:
            msg = 'Sede no válida.'
            if is_json:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'danger')
            return redirect(url_for('admin.sedes_bodegas_main'))
            
        nueva_bodega = Bodega(nombre=nombre, sede_id=sede.id)
        db.session.add(nueva_bodega)
        db.session.commit()
        
        msg = f'Bodega "{nombre}" agregada a {sede.nombre} exitosamente.'
        if is_json:
            return jsonify({'success': True, 'message': msg, 'id': nueva_bodega.id, 'nombre': nueva_bodega.nombre})
        flash(msg, 'success')
    except Exception as e:
        db.session.rollback()
        msg = f'Error al agregar bodega: {str(e)}'
        if is_json:
            return jsonify({'success': False, 'message': msg}), 500
        flash(msg, 'danger')
    
    return redirect(url_for('admin.sedes_bodegas_main'))

@admin_bp.route('/sedes/editar', methods=['POST'])
@login_required
@admin_required
def editar_sede():
    """Modifica el nombre de una sede."""
    is_json = request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    try:
        data = request.get_json(silent=True) or request.form
        id = data.get('id')
        nuevo_nombre = (data.get('nombre') or '').strip().upper()
        
        sede = Sede.query.get(int(id)) if id and str(id).isdigit() else None
        if not sede:
            msg = 'Sede no encontrada.'
            if is_json:
                return jsonify({'success': False, 'message': msg}), 404
            flash(msg, 'danger')
            return redirect(url_for('admin.sedes_bodegas_main'))
            
        if not nuevo_nombre:
            msg = 'El nombre es requerido.'
            if is_json:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'warning')
            return redirect(url_for('admin.sedes_bodegas_main'))

        # Verificar si ya existe otra sede con ese nombre
        existente = Sede.query.filter_by(nombre=nuevo_nombre).first()
        if existente and existente.id != sede.id:
            msg = f'Ya existe otra sede con el nombre "{nuevo_nombre}".'
            if is_json:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'warning')
            return redirect(url_for('admin.sedes_bodegas_main'))

        sede.nombre = nuevo_nombre
        db.session.commit()
        msg = 'Sede actualizada exitosamente.'
        if is_json:
            return jsonify({'success': True, 'message': msg})
        flash(msg, 'success')
        
    except Exception as e:
        db.session.rollback()
        msg = f'Error al editar sede: {str(e)}'
        if is_json:
            return jsonify({'success': False, 'message': msg}), 500
        flash(msg, 'danger')
    
    return redirect(url_for('admin.sedes_bodegas_main'))

@admin_bp.route('/sedes/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_required
def eliminar_sede(id):
    """Elimina una sede si no tiene bodegas vinculadas."""
    try:
        sede = Sede.query.get(id)
        if not sede:
            flash('Sede no encontrada.', 'danger')
            return redirect(url_for('admin.sedes_bodegas_main'))
            
        # Verificar si tiene bodegas
        if len(sede.bodegas) > 0:
            flash('No se puede eliminar una sede que tiene bodegas asociadas. Elimine primero las bodegas.', 'warning')
            return redirect(url_for('admin.sedes_bodegas_main'))

        # Verificar si tiene usuarios
        usuarios_asociados = Auxiliar.query.filter_by(sede_id=id).count()
        if usuarios_asociados > 0:
            flash('No se puede eliminar una sede que tiene auxiliares asignados.', 'warning')
            return redirect(url_for('admin.sedes_bodegas_main'))

        db.session.delete(sede)
        db.session.commit()
        flash('Sede eliminada exitosamente.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar sede: {str(e)}', 'danger')
    
    return redirect(url_for('admin.sedes_bodegas_main'))

@admin_bp.route('/bodegas/editar', methods=['POST'])
@login_required
@admin_required
def editar_bodega():
    """Modifica una bodega."""
    is_json = request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    try:
        data = request.get_json(silent=True) or request.form
        id = data.get('id')
        nuevo_nombre = (data.get('nombre') or '').strip().upper()
        nueva_sede_id = data.get('sede_id')
        
        bodega = Bodega.query.get(int(id)) if id and str(id).isdigit() else None
        if not bodega:
            msg = 'Bodega no encontrada.'
            if is_json:
                return jsonify({'success': False, 'message': msg}), 404
            flash(msg, 'danger')
            return redirect(url_for('admin.sedes_bodegas_main'))
            
        if not nuevo_nombre or not nueva_sede_id:
            msg = 'Nombre y Sede son requeridos.'
            if is_json:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'warning')
            return redirect(url_for('admin.sedes_bodegas_main'))

        bodega.nombre = nuevo_nombre
        bodega.sede_id = int(nueva_sede_id)
        db.session.commit()
        msg = 'Bodega actualizada exitosamente.'
        if is_json:
            return jsonify({'success': True, 'message': msg})
        flash(msg, 'success')
        
    except Exception as e:
        db.session.rollback()
        msg = f'Error al editar bodega: {str(e)}'
        if is_json:
            return jsonify({'success': False, 'message': msg}), 500
        flash(msg, 'danger')
    
    return redirect(url_for('admin.sedes_bodegas_main'))

@admin_bp.route('/bodegas/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_required
def eliminar_bodega(id):
    """Elimina una bodega si no tiene items."""
    try:
        bodega = Bodega.query.get(id)
        if not bodega:
            flash('Bodega no encontrada.', 'danger')
            return redirect(url_for('admin.sedes_bodegas_main'))
            
        # Verificar si tiene items
        if len(bodega.items) > 0:
            flash('No se puede eliminar una bodega que tiene items de inventario asociados.', 'warning')
            return redirect(url_for('admin.sedes_bodegas_main'))

        db.session.delete(bodega)
        db.session.commit()
        flash('Bodega eliminada exitosamente.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar bodega: {str(e)}', 'danger')
    
    return redirect(url_for('admin.sedes_bodegas_main'))

@admin_bp.route('/api/bodegas/<int:sede_id>')
@login_required
def get_bodegas_by_sede(sede_id):
    """API para obtener bodegas filtradas por sede."""
    try:
        bodegas = Bodega.query.filter_by(sede_id=sede_id).all()
        return jsonify([{'id': b.id, 'nombre': b.nombre} for b in bodegas])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === IMPORTACIÓN DE DATOS ===

@admin_bp.route('/importar')
@login_required
@admin_required
def importar_datos():
    """Página principal de importación de usuarios e inventario."""
    return render_template('importar_datos.html')


# --- Plantillas descargables ---

@admin_bp.route('/importar/plantilla/usuarios')
@login_required
@admin_required
def plantilla_usuarios():
    """Descarga una plantilla Excel vacía para importar usuarios."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df = pd.DataFrame(columns=[
            'documento', 'nombre_completo', 'correo', 'contrasena', 'rol'
        ])
        # Fila de ejemplo
        ejemplo = pd.DataFrame([{
            'documento': '12345678',
            'nombre_completo': 'Nombre Apellido',
            'correo': 'usuario@email.com',
            'contrasena': 'Contrasena1',
            'rol': 'auxiliar'
        }])
        pd.concat([df, ejemplo], ignore_index=True).to_excel(
            writer, sheet_name='Usuarios', index=False
        )
        # Hoja de instrucciones
        inst = pd.DataFrame([
            ['INSTRUCCIONES PARA IMPORTAR USUARIOS'],
            [''],
            ['Columna       | Descripción'],
            ['documento     | Número de cédula o código de usuario (mín. 3 caracteres)'],
            ['nombre_completo | Nombre y apellido completo (mín. 3 caracteres)'],
            ['correo        | Correo electrónico válido (único en el sistema)'],
            ['contrasena    | Contraseña: mín. 8 caracteres, al menos 1 letra y 1 número'],
            ['rol           | "admin" o "auxiliar" (si se omite, se asigna "auxiliar")'],
            [''],
            ['NOTAS IMPORTANTES:'],
            ['- Si el documento ya existe en el sistema, la fila se OMITE (no se reemplaza).'],
            ['- Si el correo ya está registrado, la fila se OMITE.'],
            ['- Las filas con errores de formato se reportan pero no se importan.'],
        ])
        inst.to_excel(writer, sheet_name='Instrucciones', index=False, header=False)

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name='plantilla_usuarios.xlsx',
        as_attachment=True
    )


@admin_bp.route('/importar/plantilla/inventario')
@login_required
@admin_required
def plantilla_inventario():
    """Descarga una plantilla Excel vacía para importar inventario."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df = pd.DataFrame(columns=[
            'categoria', 'item', 'marca_modelo', 'serial',
            'activo_fijo', 'numero_inventario', 'ubicacion_permanente',
            'estado', 'observaciones'
        ])
        ejemplo = pd.DataFrame([{
            'categoria': 'TECNOLOGÍA',
            'item': 'Laptop',
            'marca_modelo': 'Dell Latitude 5520',
            'serial': 'SN-001',
            'activo_fijo': 'AF-001',
            'numero_inventario': 'INV-001',
            'ubicacion_permanente': 'Bodega Principal',
            'estado': 'Disponible',
            'observaciones': ''
        }])
        pd.concat([df, ejemplo], ignore_index=True).to_excel(
            writer, sheet_name='Inventario', index=False
        )
        # Hoja de instrucciones
        estados_validos = 'Disponible | En Préstamo | En Mantenimiento | En Reparación | De Baja'
        inst = pd.DataFrame([
            ['INSTRUCCIONES PARA IMPORTAR INVENTARIO'],
            [''],
            ['Columna               | Descripción'],
            ['categoria             | Categoría del equipo (ej: TECNOLOGÍA, AUDIOVISUAL)'],
            ['item                  | Nombre del equipo (requerido)'],
            ['marca_modelo          | Marca y modelo (opcional)'],
            ['serial                | Número de serie (opcional)'],
            ['activo_fijo           | Código de activo fijo (opcional)'],
            ['numero_inventario     | Código de inventario ÚNICO (requerido)'],
            ['ubicacion_permanente  | Ubicación física del equipo (opcional)'],
            [f'estado               | Estado del equipo. Valores válidos: {estados_validos}'],
            ['observaciones         | Notas adicionales (opcional)'],
            [''],
            ['NOTAS IMPORTANTES:'],
            ['- Si el numero_inventario ya existe en el sistema, la fila se OMITE (no se reemplaza).'],
            ['- Las filas con errores de formato se reportan pero no se importan.'],
            ['- El estado por defecto es "Disponible" si se deja vacío.'],
        ])
        inst.to_excel(writer, sheet_name='Instrucciones', index=False, header=False)

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name='plantilla_inventario.xlsx',
        as_attachment=True
    )


# --- Endpoints de importación ---

@admin_bp.route('/importar/usuarios', methods=['POST'])
@login_required
@admin_required
def importar_usuarios():
    """Procesa un archivo Excel/CSV para importar usuarios.
    No reemplaza usuarios existentes; reporta errores por fila."""
    archivo = request.files.get('archivo_usuarios')
    if not archivo or archivo.filename == '':
        flash('No se seleccionó ningún archivo.', 'warning')
        return redirect(url_for('admin.importar_datos'))

    ext = archivo.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('xlsx', 'xls', 'csv'):
        flash('Formato de archivo no válido. Use .xlsx, .xls o .csv.', 'danger')
        return redirect(url_for('admin.importar_datos'))

    try:
        contenido = archivo.read()
        buf = io.BytesIO(contenido)

        if ext == 'csv':
            df = pd.read_csv(buf, dtype=str)
        else:
            df = pd.read_excel(buf, sheet_name='Usuarios', dtype=str)

        df.columns = [c.strip().lower() for c in df.columns]

        # Columnas requeridas
        requeridas = {'documento', 'nombre_completo', 'correo', 'contrasena'}
        faltantes = requeridas - set(df.columns)
        if faltantes:
            flash(
                f'El archivo no tiene las columnas requeridas: {", ".join(sorted(faltantes))}. '
                f'Descarga la plantilla y vuelve a intentarlo.',
                'danger'
            )
            return redirect(url_for('admin.importar_datos'))

        from werkzeug.security import generate_password_hash

        insertados = []
        omitidos = []
        errores = []

        def normalizar_numero_inventario(v):
            s = str(v or '').strip()
            if not s or s.lower() == 'nan':
                return ''
            # Excel a veces convierte enteros a float (ej: 1.0)
            if re.fullmatch(r'\d+\.0+', s):
                try:
                    return str(int(float(s)))
                except Exception:
                    return s
            return s

        for idx, row in df.iterrows():
            fila = idx + 2  # +2 porque la fila 1 es encabezado y pandas es 0-indexed

            doc = str(row.get('documento', '') or '').strip()
            nombre = str(row.get('nombre_completo', '') or '').strip()
            correo = str(row.get('correo', '') or '').strip().lower()
            pwd = str(row.get('contrasena', '') or '').strip()
            rol = str(row.get('rol', 'auxiliar') or 'auxiliar').strip().lower()

            # Saltar filas completamente vacías
            if not doc and not nombre and not correo:
                continue

            row_errors = []

            # Validaciones básicas
            if not doc or len(doc) < 3:
                row_errors.append('documento inválido (mín. 3 caracteres)')
            if not nombre or len(nombre) < 3:
                row_errors.append('nombre_completo inválido (mín. 3 caracteres)')
            if not correo or '@' not in correo:
                row_errors.append('correo inválido')
            if not pwd or len(pwd) < 8 or not any(c.isdigit() for c in pwd) or not any(c.isalpha() for c in pwd):
                row_errors.append('contrasena inválida (mín. 8 chars, letra y número)')
            if rol not in ('admin', 'auxiliar'):
                rol = 'auxiliar'  # Corregir silenciosamente

            if row_errors:
                errores.append({'fila': fila, 'doc': doc, 'razones': row_errors})
                continue

            # Verificar duplicados
            if Auxiliar.query.get(doc):
                omitidos.append({'fila': fila, 'doc': doc, 'razon': 'documento ya existe'})
                continue
            if Auxiliar.query.filter_by(correo=correo).first():
                omitidos.append({'fila': fila, 'doc': doc, 'razon': 'correo ya registrado'})
                continue

            # Insertar
            nuevo = Auxiliar(
                documento=doc,
                nombre_completo=nombre,
                correo=correo,
                contraseña=generate_password_hash(pwd),
                rol=rol,
            )
            db.session.add(nuevo)
            insertados.append({'fila': fila, 'doc': doc, 'nombre': nombre})

        db.session.commit()

        registrar_auditoria(
            modulo='admin',
            entidad_tipo='importacion_usuarios',
            accion='IMPORTAR',
            descripcion=f'Importación masiva: {len(insertados)} insertados, {len(omitidos)} omitidos, {len(errores)} con error',
        )
        db.session.commit()

        return render_template(
            'importar_datos.html',
            resultado_usuarios={
                'insertados': insertados,
                'omitidos': omitidos,
                'errores': errores,
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error('Error en importacion de usuarios: %s', e, exc_info=True)
        flash(f'Error al procesar el archivo: {str(e)}', 'danger')
        return redirect(url_for('admin.importar_datos'))


@admin_bp.route('/importar/inventario', methods=['POST'])
@login_required
@admin_required
def importar_inventario():
    """Procesa un archivo Excel/CSV para importar inventario.
    No reemplaza ítems existentes; reporta errores por fila."""
    archivo = request.files.get('archivo_inventario')
    if not archivo or archivo.filename == '':
        flash('No se seleccionó ningún archivo.', 'warning')
        return redirect(url_for('admin.importar_datos'))

    ext = archivo.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('xlsx', 'xls', 'csv'):
        flash('Formato de archivo no válido. Use .xlsx, .xls o .csv.', 'danger')
        return redirect(url_for('admin.importar_datos'))

    ESTADOS_VALIDOS = {'Disponible', 'En Préstamo', 'En Mantenimiento', 'En Reparación', 'De Baja'}

    try:
        contenido = archivo.read()
        buf = io.BytesIO(contenido)

        if ext == 'csv':
            df = pd.read_csv(buf, dtype=str)
        else:
            df = pd.read_excel(buf, sheet_name='Inventario', dtype=str)

        df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]

        # Columnas requeridas (solo item es obligatorio, el número se genera automáticamente)
        requeridas = {'item'}
        faltantes = requeridas - set(df.columns)
        if faltantes:
            flash(
                f'El archivo no tiene las columnas requeridas: {", ".join(sorted(faltantes))}. '
                f'Descarga la plantilla y vuelve a intentarlo.',
                'danger'
            )
            return redirect(url_for('admin.importar_datos'))

        insertados = []
        omitidos = []
        errores = []

        def normalizar_numero_inventario(v):
            s = str(v or '').strip()
            if not s or s.lower() == 'nan':
                return ''
            # Excel a veces convierte enteros a float (ej: 1.0)
            if re.fullmatch(r'\d+\.0+', s):
                try:
                    return str(int(float(s)))
                except Exception:
                    return s
            return s

        def generar_consecutivo_por_categoria(categoria, item_nombre):
            """Genera un número de inventario consecutivo único basado en las 3 primeras letras del item."""
            # Priorizar el nombre del item sobre la categoría
            if item_nombre and item_nombre.strip():
                # Limpiar el nombre del item (quitar espacios, caracteres especiales)
                nombre_limpio = re.sub(r'[^A-Za-z0-9]+', '', item_nombre.upper())
                # Tomar solo las 3 primeras letras
                base = nombre_limpio[:3] if len(nombre_limpio) >= 3 else nombre_limpio.ljust(3, 'X')
            elif categoria and categoria.strip():
                nombre_limpio = re.sub(r'[^A-Za-z0-9]+', '', categoria.upper())
                base = nombre_limpio[:3] if len(nombre_limpio) >= 3 else nombre_limpio.ljust(3, 'X')
            else:
                base = 'ITM'
            
            # Buscar el último consecutivo para esta base
            patron = f"{base}%"
            ultimos = db.session.query(Inventario.numero_inventario)\
                .filter(Inventario.numero_inventario.like(patron))\
                .all()
            
            # Extraer números y encontrar el máximo
            max_num = 0
            for (num_inv,) in ultimos:
                # Extraer solo los dígitos al final
                match = re.search(r'(\d+)$', num_inv)
                if match:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
            
            nuevo_num = max_num + 1
            
            # Generar el nuevo número con formato de 2 dígitos (01, 02, 03...)
            return f"{base}{nuevo_num:02d}"

        for idx, row in df.iterrows():
            fila = idx + 2

            item = str(row.get('item', '') or '').strip()
            num_inv_excel = normalizar_numero_inventario(row.get('numero_inventario', ''))
            categoria = str(row.get('categoria', '') or '').strip() or 'GENERAL'
            marca_modelo = str(row.get('marca_modelo', '') or '').strip() or None
            serial = str(row.get('serial', '') or '').strip() or None
            activo_fijo = str(row.get('activo_fijo', '') or '').strip() or None
            ubicacion = str(row.get('ubicacion_permanente', '') or '').strip() or None
            estado = str(row.get('estado', '') or '').strip() or 'Disponible'
            observaciones = str(row.get('observaciones', '') or '').strip() or None

            # Saltar filas vacías
            if not item:
                continue

            row_errors = []

            if not item or len(item) < 2:
                row_errors.append('item inválido (mín. 2 caracteres)')
            if estado not in ESTADOS_VALIDOS:
                row_errors.append(f'estado "{estado}" no válido. Use: {", ".join(sorted(ESTADOS_VALIDOS))}')

            if row_errors:
                errores.append({'fila': fila, 'num_inv': num_inv_excel or 'N/A', 'razones': row_errors})
                continue

            # GENERAR CONSECUTIVO AUTOMÁTICO (ignorar el número del Excel)
            num_inv = generar_consecutivo_por_categoria(categoria, item)

            nuevo = Inventario(
                categoria=categoria,
                item=item,
                marca_modelo=marca_modelo,
                serial=serial,
                activo_fijo=activo_fijo,
                numero_inventario=num_inv,
                ubicacion_permanente=ubicacion,
                estado=estado,
                observaciones=observaciones,
            )
            db.session.add(nuevo)
            insertados.append({'fila': fila, 'num_inv': num_inv, 'item': item})

        db.session.commit()

        registrar_auditoria(
            modulo='inventario',
            entidad_tipo='ImportacionMasiva',
            entidad_id='importacion_inventario',
            accion='IMPORTAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Importación masiva inventario: {len(insertados)} insertados, {len(omitidos)} omitidos, {len(errores)} con error',
        )
        db.session.commit()

        return render_template(
            'importar_datos.html',
            resultado_inventario={
                'insertados': insertados,
                'omitidos': omitidos,
                'errores': errores,
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error('Error en importacion de inventario: %s', e, exc_info=True)
        flash(f'Error al procesar el archivo: {str(e)}', 'danger')
        return redirect(url_for('admin.importar_datos'))


@admin_bp.route('/importar/plantilla/profesores')
@login_required
@admin_required
def plantilla_profesores():
    """Descarga una plantilla Excel vacía para importar profesores."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df = pd.DataFrame(columns=['Cedula', 'Nombre_Completo', 'Correo', 'Telefono', 'Programa'])
        df.loc[0] = ['12345678', 'Juan Perez Ejemplo', 'juan.perez@uniminuto.edu.co', '3001234567', 'Ingeniería de Sistemas']
        df.to_excel(writer, index=False, sheet_name='Profesores')
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='plantilla_profesores.xlsx'
    )


@admin_bp.route('/importar/profesores', methods=['POST'])
@login_required
@admin_required
def importar_profesores():
    """Procesa un archivo Excel/CSV para importar profesores."""
    archivo = request.files.get('archivo_profesores')
    if not archivo or archivo.filename == '':
        flash('No se seleccionó ningún archivo.', 'warning')
        return redirect(url_for('admin.importar_datos'))

    ext = archivo.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('xlsx', 'xls', 'csv'):
        flash('Formato de archivo no válido. Use .xlsx, .xls o .csv.', 'danger')
        return redirect(url_for('admin.importar_datos'))

    try:
        contenido = archivo.read()
        buf = io.BytesIO(contenido)

        if ext == 'csv':
            # read first to check separator
            df = pd.read_csv(buf, sep=';', dtype=str, encoding='utf-8-sig')
            if len(df.columns) == 1:
                buf.seek(0)
                df = pd.read_csv(buf, sep=',', dtype=str, encoding='utf-8-sig')
        else:
            df = pd.read_excel(buf, sheet_name='Profesores', dtype=str)

        # Convert to standard casing just to be sure
        df.columns = [c.strip().lower() for c in df.columns]
        
        insertados = []
        omitidos = []
        errores = []

        for idx, row in df.iterrows():
            fila = idx + 2
            
            # extract matching lower-cased columns or fallback to dict keys
            cedula = str(row.get('cedula', '') or '').strip()
            nombre = str(row.get('nombre_completo', '') or '').strip()
            correo = str(row.get('correo', '') or '').strip()
            telefono = str(row.get('telefono', '') or '').strip()
            programa = str(row.get('programa', '') or '').strip()

            # Skip first row if it's the example
            if idx == 0 and 'ejemplo' in nombre.lower():
                continue

            if not cedula and not nombre:
                continue

            row_errors = []
            if not cedula or len(cedula) < 5:
                row_errors.append('Cédula inválida (mínimo 5 caracteres)')
            if not nombre or len(nombre) < 3:
                row_errors.append('Nombre inválido')

            if row_errors:
                errores.append({'fila': fila, 'num_inv': cedula, 'razones': row_errors})
                continue

            # Check duplication
            if Profesor.query.get(cedula):
                omitidos.append({'fila': fila, 'num_inv': cedula, 'razon': 'Cédula de profesor ya existe'})
                continue

            # Validar campos opcionales con los métodos que ya existen en DataValidator
            validaciones_extra = []

            nombre_valid, nombre_error = DataValidator.validate_string_field(
                nombre, 'Nombre completo', min_length=3, max_length=150
            )
            if not nombre_valid:
                validaciones_extra.append(nombre_error)

            if correo:
                email_valid, email_error = DataValidator.validate_email(correo)
                if not email_valid:
                    validaciones_extra.append(email_error)

            if telefono:
                phone_valid, phone_error = DataValidator.validate_phone(telefono)
                if not phone_valid:
                    validaciones_extra.append(phone_error)

            if programa:
                prog_valid, prog_error = DataValidator.validate_string_field(
                    programa, 'Programa', required=False, max_length=100
                )
                if not prog_valid:
                    validaciones_extra.append(prog_error)

            if validaciones_extra:
                errores.append({'fila': fila, 'num_inv': cedula, 'razones': validaciones_extra})
                continue

            nuevo = Profesor(
                cedula=cedula,
                nombre_completo=nombre,
                correo=correo if correo else None,
                telefono=telefono if telefono else None,
                programa=programa if programa else None
            )
            db.session.add(nuevo)
            insertados.append({'fila': fila, 'num_inv': cedula, 'item': nombre})

        db.session.commit()

        registrar_auditoria(
            modulo='profesores',
            entidad_tipo='ImportacionMasiva',
            entidad_id='importacion_profesores',
            accion='IMPORTAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Importación masiva: {len(insertados)} insertados, {len(omitidos)} omitidos, {len(errores)} con error',
        )
        db.session.commit()

        return render_template(
            'importar_datos.html',
            resultado_profesores={
                'insertados': insertados,
                'omitidos': omitidos,
                'errores': errores,
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error('Error en importacion de profesores: %s', e, exc_info=True)
        flash(f'Error al procesar el archivo: {str(e)}', 'danger')
        return redirect(url_for('admin.importar_datos'))


@admin_bp.route('/importar/plantilla/salas-computo')
@login_required
@admin_required
def plantilla_salas_computo():
    """Descarga una plantilla Excel vacía para importar clases de salas de cómputo."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df = pd.DataFrame(columns=[
            'Fecha_YYYY-MM-DD', 'Hora_Inicio_HH:MM', 'Hora_Fin_HH:MM', 'Salon', 
            'Nombre_Profesor', 'Materia', 'Asistencia', 'Horas_Academicas', 
            'Jornada', 'Num_Estudiantes', 'Programa', 'Modalidad', 'Observaciones'
        ])
        df.loc[0] = [
            '2025-05-10', '08:00', '10:00', 'A-201', 
            'Juan Perez', 'Contabilidad', 'No', '2', 
            'MAÑANA', '25', 'Administración', 'Presencial', 'Ejemplo no borrar si no se reemplaza todo el archivo'
        ]
        df.to_excel(writer, index=False, sheet_name='SalasComputo')
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='plantilla_salas_computo.xlsx'
    )


@admin_bp.route('/importar/salas-computo', methods=['POST'])
@login_required
@admin_required
def importar_salas_computo():
    """Procesa un archivo Excel/CSV para importar clases de salas de cómputo."""
    from database import ClaseSalaComputo
    
    archivo = request.files.get('archivo_alas_computo')
    if not archivo or archivo.filename == '':
        flash('No se seleccionó ningún archivo.', 'warning')
        return redirect(url_for('admin.importar_datos'))

    ext = archivo.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('xlsx', 'xls', 'csv'):
        flash('Formato de archivo no válido. Use .xlsx, .xls o .csv.', 'danger')
        return redirect(url_for('admin.importar_datos'))

    try:
        contenido = archivo.read()
        buf = io.BytesIO(contenido)

        if ext == 'csv':
            df = pd.read_csv(buf, sep=';', dtype=str, encoding='utf-8-sig')
            if len(df.columns) == 1:
                buf.seek(0)
                df = pd.read_csv(buf, sep=',', dtype=str, encoding='utf-8-sig')
        else:
            df = pd.read_excel(buf, sheet_name='SalasComputo', dtype=str)

        # Normalize column names slightly
        df.columns = [c.strip().lower() for c in df.columns]
        
        insertados = []
        omitidos = []
        errores = []

        for idx, row in df.iterrows():
            fila = idx + 2
            
            # Helper to safely extract column values
            def get_col(names, default=''):
                for n in names:
                    if n in df.columns:
                        return str(row[n] if pd.notna(row[n]) else default).strip()
                return default

            fecha_str = get_col(['fecha_yyyy-mm-dd', 'fecha'])
            h_inicio = get_col(['hora_inicio_hh:mm', 'hora_inicio'])
            h_fin = get_col(['hora_fin_hh:mm', 'hora_fin'])
            salon = get_col(['salon', 'salón'])
            profesor = get_col(['nombre_profesor', 'profesor'])
            materia = get_col(['materia'])
            
            # Additional fields
            asistencia = get_col(['asistencia'], 'No')
            h_acad = get_col(['horas_academicas', 'horas académicas'], '0')
            jornada = get_col(['jornada'])
            num_estuid = get_col(['num_estudiantes', 'estudiantes'], '0')
            programa = get_col(['programa'])
            modalidad = get_col(['modalidad'])
            observaciones = get_col(['observaciones'])

            if idx == 0 and 'ejemplo' in observaciones.lower():
                continue

            if not fecha_str and not salon and not profesor:
                continue

            row_errors = []
            
            # Try to parse date and time
            try:
                # Handle possible excel formatting if it wasn't strictly string
                # We expect YYYY-MM-DD
                fecha_val = datetime.strptime(fecha_str[:10], '%Y-%m-%d').date()
            except ValueError:
                row_errors.append(f"Fecha '{fecha_str}' inválida. Use YYYY-MM-DD")
                fecha_val = None

            try:
                # Handle HH:MM
                h_inicio_val = datetime.strptime(h_inicio[:5], '%H:%M').time()
            except ValueError:
                row_errors.append(f"Hora de Inicio '{h_inicio}' inválida. Use HH:MM")
                h_inicio_val = None

            try:
                h_fin_val = datetime.strptime(h_fin[:5], '%H:%M').time()
            except ValueError:
                row_errors.append(f"Hora de Fin '{h_fin}' inválida. Use HH:MM")
                h_fin_val = None
                
            if h_inicio_val and h_fin_val and h_inicio_val >= h_fin_val:
                row_errors.append('La hora de inicio debe ser anterior a la hora de fin')

            if not salon:
                row_errors.append('Salón es requerido')
            if not profesor:
                row_errors.append('Profesor es requerido')
            if not materia:
                row_errors.append('Materia es requerida')

            if row_errors:
                errores.append({'fila': fila, 'num_inv': salon or 'N/A', 'razones': row_errors})
                continue

            # Convert nums
            try:
                ha_val = float(h_acad) if h_acad else None
            except ValueError:
                ha_val = None
                
            try:
                ne_val = int(float(num_estuid)) if num_estuid else None
            except ValueError:
                ne_val = None

            nuevo = ClaseSalaComputo(
                fecha=fecha_val,
                hora_inicio=h_inicio_val,
                hora_fin=h_fin_val,
                salon=salon,
                nombre_profesor=profesor,
                materia=materia,
                asistencia=asistencia if asistencia.lower() in ['sí', 'si', 's', 'yes', 'y'] else 'No',
                horas_academicas=ha_val,
                jornada=jornada.upper() if jornada else None,
                num_estudiantes=ne_val,
                programa=programa,
                modalidad=modalidad.capitalize() if modalidad else None,
                observaciones=observaciones,
                estado='Programada'
            )
            db.session.add(nuevo)
            insertados.append({'fila': fila, 'num_inv': salon, 'item': materia})

        db.session.commit()

        registrar_auditoria(
            modulo='salas_computo',
            entidad_tipo='ImportacionMasiva',
            entidad_id='importacion_salas',
            accion='IMPORTAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Importación masiva: {len(insertados)} insertados, {len(omitidos)} omitidos, {len(errores)} con error',
        )
        db.session.commit()

        return render_template(
            'importar_datos.html',
            resultado_salas_computo={
                'insertados': insertados,
                'omitidos': omitidos,
                'errores': errores,
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error('Error en importacion de salas de computo: %s', e, exc_info=True)
        flash(f'Error al procesar el archivo: {str(e)}', 'danger')
        return redirect(url_for('admin.importar_datos'))


@admin_bp.route('/usuarios/<doc>/sedes', methods=['GET'])
@login_required
@admin_required
def listar_sedes_usuario(doc):
    """Lista las sedes asignadas a un auxiliar."""
    auxiliar = Auxiliar.query.get_or_404(doc)
    asignaciones = AuxiliarSede.query.filter_by(usuario_documento=doc).all()
    sedes = [{'id': a.sede_id, 'nombre': a.sede.nombre} for a in asignaciones]
    return jsonify({'success': True, 'sedes': sedes, 'documento': doc})


@admin_bp.route('/usuarios/<doc>/sedes', methods=['POST'])
@login_required
@admin_required
def asignar_sede_usuario(doc):
    """Asigna una sede a un auxiliar. Idempotente: si ya existe, retorna 200 sin error."""
    auxiliar = Auxiliar.query.get_or_404(doc)
    datos = request.json or {}
    sede_id = datos.get('sede_id')
    if not sede_id:
        return jsonify({'success': False, 'message': 'sede_id es requerido'}), 400

    sede = Sede.query.get(int(sede_id))
    if not sede:
        return jsonify({'success': False, 'message': 'Sede no encontrada'}), 404

    existente = AuxiliarSede.query.filter_by(
        usuario_documento=doc, sede_id=int(sede_id)
    ).first()
    if existente:
        return jsonify({'success': True, 'message': 'La sede ya estaba asignada'}), 200

    nueva = AuxiliarSede(usuario_documento=doc, sede_id=int(sede_id))
    db.session.add(nueva)

    registrar_auditoria(
        modulo='admin',
        entidad_tipo='AuxiliarSede',
        entidad_id=doc,
        accion='ASIGNAR_SEDE',
        usuario_documento=session.get('usuario', ''),
        usuario_nombre=session.get('nombre_completo', ''),
        descripcion=f'Asignación de sede {sede.nombre} al auxiliar {doc}',
        datos_antes=None,
        datos_despues={'sede_id': int(sede_id), 'sede_nombre': sede.nombre}
    )

    db.session.commit()
    return jsonify({'success': True, 'message': f'Sede {sede.nombre} asignada correctamente'}), 201


@admin_bp.route('/usuarios/<doc>/sedes/<int:sid>', methods=['DELETE'])
@login_required
@admin_required
def revocar_sede_usuario(doc, sid):
    """Revoca el acceso de un auxiliar a una sede."""
    asignacion = AuxiliarSede.query.filter_by(
        usuario_documento=doc, sede_id=sid
    ).first_or_404()

    sede = Sede.query.get(sid)
    sede_nombre = sede.nombre if sede else str(sid)

    registrar_auditoria(
        modulo='admin',
        entidad_tipo='AuxiliarSede',
        entidad_id=doc,
        accion='REVOCAR_SEDE',
        usuario_documento=session.get('usuario', ''),
        usuario_nombre=session.get('nombre_completo', ''),
        descripcion=f'Revocación de sede {sede_nombre} al auxiliar {doc}',
        datos_antes={'sede_id': sid, 'sede_nombre': sede_nombre},
        datos_despues=None
    )

    db.session.delete(asignacion)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Acceso a sede {sede_nombre} revocado'}), 200


# Función auxiliar para importar la aplicación Flask en el contexto de logs
def get_app():
    from flask import current_app
    return current_app
