"""
Blueprint de autenticación: login, registro, logout y cambio de contraseña.
"""
from flask import Blueprint, render_template, request, redirect, flash, session, url_for, jsonify
from extensions import db, limiter
from database import Auxiliar, registrar_auditoria
from config import AdminConfig
from auth import login_required
from services.auth_service import registrar_auxiliar, verificar_credenciales
from werkzeug.security import check_password_hash, generate_password_hash
from validators import DataValidator
from flask import current_app

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    """Registro de nuevos auxiliares."""
    if 'usuario' in session:
        return redirect('/')
    if request.method == 'POST':
        documento = request.form.get('usuario')
        nombre_completo = request.form.get('nombre_completo')
        correo = request.form.get('correo')
        contraseña = request.form.get('contraseña')

        if not all([documento, nombre_completo, correo, contraseña]):
            flash('Todos los campos son requeridos para el registro.', 'warning')
            return redirect('/registro')

        success, message = registrar_auxiliar(documento, nombre_completo, correo, contraseña, rol='auxiliar')
        if success:
            flash('Registro exitoso. Ahora puedes iniciar sesión.', 'success')
            return redirect('/login')
        flash(f'Error al registrar: {message}', 'danger')
        return redirect('/registro')
    return render_template('registro.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    """Inicio de sesión."""
    if 'usuario' in session:
        return redirect('/')
    if request.method == 'POST':
        documento = request.form.get('usuario')
        contraseña = request.form.get('contraseña')

        if not documento or not contraseña:
            flash('El documento y la contraseña son requeridos.', 'warning')
            return redirect('/login')

        if verificar_credenciales(documento, contraseña):
            usuario_data = Auxiliar.query.get(str(documento).strip())

            superadmins = current_app.config.get('SUPERADMIN_DOCUMENTS')
            if isinstance(superadmins, set) and usuario_data and usuario_data.documento in superadmins:
                try:
                    usuario_data.rol = 'superadmin'
                    db.session.commit()
                except Exception:
                    db.session.rollback()

            session['usuario'] = usuario_data.documento
            session['nombre_completo'] = usuario_data.nombre_completo or 'Usuario'
            session['rol'] = usuario_data.rol or 'auxiliar'

            # Cargar permisos del usuario para el Navbar
            from auth import cargar_permisos_usuario
            cargar_permisos_usuario(usuario_data.documento)

            # Registrar auditoría de login
            try:
                from database import registrar_auditoria
                from datetime import datetime
                registrar_auditoria(
                    modulo='auth',
                    entidad_tipo='Sesion',
                    entidad_id=usuario_data.documento,
                    accion='LOGIN',
                    usuario_documento=usuario_data.documento,
                    usuario_nombre=usuario_data.nombre_completo or '',
                    descripcion=f"Inicio de sesión a las {datetime.now().strftime('%H:%M:%S')}",
                    datos_antes=None,
                    datos_despues={'hora_login': datetime.now().strftime('%H:%M:%S')}
                )
                db.session.commit()
            except Exception:
                pass

            session.permanent = True

            # Determinar redirección según sedes asignadas
            from blueprints.sedes import obtener_sedes_usuario
            rol = session['rol']
            sedes = obtener_sedes_usuario(usuario_data.documento, rol)

            if rol in ('admin', 'superadmin'):
                session['sede_id'] = None
                session['sede_nombre'] = None
                session['puede_cambiar_sede'] = True
                flash('Inicio de sesión exitoso.', 'success')
                return redirect('/seleccionar-sede')

            if len(sedes) == 0:
                session.clear()
                flash('No tienes sedes asignadas. Contacta al administrador.', 'warning')
                return redirect('/login')

            if len(sedes) == 1:
                session['sede_id'] = sedes[0].id
                session['sede_nombre'] = sedes[0].nombre
                session['puede_cambiar_sede'] = False
                flash('Inicio de sesión exitoso.', 'success')
                return redirect('/')

            # Más de una sede
            session['sede_id'] = None
            session['sede_nombre'] = None
            session['puede_cambiar_sede'] = True
            flash('Inicio de sesión exitoso.', 'success')
            return redirect('/seleccionar-sede')
        flash('Credenciales incorrectas. Inténtalo de nuevo.', 'danger')
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Cierre de sesión."""
    # registrar auditoría de logout
    try:
        from database import registrar_auditoria
        from datetime import datetime
        usuario = session.get('usuario')
        nombre = session.get('nombre_completo', '')
        registrar_auditoria(
            modulo='auth',
            entidad_tipo='Sesion',
            entidad_id=usuario or '',
            accion='LOGOUT',
            usuario_documento=usuario or '',
            usuario_nombre=nombre,
            descripcion=f"Cierre de sesión a las {datetime.now().strftime('%H:%M:%S')}",
            datos_antes=None,
            datos_despues={'hora_logout': datetime.now().strftime('%H:%M:%S')}
        )
        db.session.commit()
    except Exception:
        pass

    session.clear()
    flash('Has cerrado sesión exitosamente.', 'success')
    return redirect('/login')


@auth_bp.route('/perfil')
@login_required
def perfil():
    """Página de perfil del usuario con opción de cambiar contraseña."""
    usuario = Auxiliar.query.get(session.get('usuario'))
    return render_template('perfil.html', usuario=usuario)


@auth_bp.route('/perfil/cambiar-contrasena', methods=['POST'])
@login_required
def cambiar_contrasena():
    """Permite al usuario autenticado cambiar su propia contraseña."""
    datos = request.json or {}

    contrasena_actual   = datos.get('contrasena_actual', '').strip()
    contrasena_nueva    = datos.get('contrasena_nueva', '').strip()
    contrasena_confirma = datos.get('contrasena_confirma', '').strip()

    # Validaciones básicas
    if not contrasena_actual or not contrasena_nueva or not contrasena_confirma:
        return jsonify({'success': False, 'message': 'Todos los campos son requeridos.'}), 400

    if contrasena_nueva != contrasena_confirma:
        return jsonify({'success': False, 'message': 'La nueva contraseña y la confirmación no coinciden.'}), 400

    pwd_valida, pwd_error = DataValidator.validate_password(contrasena_nueva)
    if not pwd_valida:
        return jsonify({'success': False, 'message': pwd_error}), 400

    usuario = Auxiliar.query.get(session.get('usuario'))
    if not usuario:
        return jsonify({'success': False, 'message': 'Usuario no encontrado.'}), 404

    if not check_password_hash(usuario.contraseña, contrasena_actual):
        return jsonify({'success': False, 'message': 'La contraseña actual es incorrecta.'}), 400

    try:
        usuario.contraseña = generate_password_hash(contrasena_nueva)
        registrar_auditoria(
            modulo='auth',
            entidad_tipo='Auxiliar',
            entidad_id=usuario.documento,
            accion='CAMBIAR_CONTRASENA',
            usuario_documento=usuario.documento,
            usuario_nombre=usuario.nombre_completo or '',
            descripcion='Cambio de contraseña desde perfil',
        )
        db.session.commit()
        return jsonify({'success': True, 'message': '¡Contraseña actualizada correctamente!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Error interno al actualizar la contraseña.'}), 500
