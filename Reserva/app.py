from dotenv import load_dotenv
load_dotenv(encoding='utf-8', override=True)

import os
import calendar
from datetime import datetime, date, timedelta

from flask import Flask, render_template, request, redirect, flash, url_for, session
from sqlalchemy import func, or_, and_

from extensions import db, csrf, limiter, socketio, migrate, swagger
from swagger_config import SWAGGER_CONFIG, SWAGGER_TEMPLATE
from database import init_db, Auxiliar, Profesor, Inventario, PrestamoEquipo, Reserva, Festivo
from config import config, SystemConstants, AdminConfig
from validators import DataValidator, BusinessValidator, ValidationError
from services.prestamo_service import PrestamoService
from services.auth_service import registrar_auxiliar

# Blueprints
from blueprints.auth import auth_bp
from blueprints.estadisticas import estadisticas_bp
from blueprints.api import api_bp
from blueprints.prestamos import prestamos_bp
from blueprints.reservas import reservas_bp
from blueprints.inventario import inventario_bp
from blueprints.admin import admin_bp
from blueprints.profesores import profesores_bp
from blueprints.bitacora import bitacora_bp
from blueprints.salas_computo import salas_computo_bp
from blueprints.sedes import sedes_bp
from blueprints.colaboradores import colaboradores_bp
from blueprints.programas import programas_bp
from blueprints.estudiantes import estudiantes_bp


def create_app(config_name=None):
    """Factory function para crear la aplicación Flask."""
    app = Flask(__name__)

    if config_name is None:
        config_name = os.getenv('FLASK_CONFIG', 'default')
    app.config.from_object(config[config_name])

    # Inicializar extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    socketio.init_app(app)
    app.config['SWAGGER'] = {**SWAGGER_CONFIG, 'template': SWAGGER_TEMPLATE}
    swagger.init_app(app)

    # Registrar blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(estadisticas_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(prestamos_bp)
    app.register_blueprint(reservas_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(profesores_bp)
    app.register_blueprint(bitacora_bp)
    app.register_blueprint(salas_computo_bp, name='salas_computo')
    app.register_blueprint(sedes_bp)
    app.register_blueprint(colaboradores_bp)
    app.register_blueprint(programas_bp)
    app.register_blueprint(estudiantes_bp)

    # ── Context processor ──────────────────────────────────────────────────────
    @app.context_processor
    def inject_module_access():
        """
        Expone permisos de módulo a todas las plantillas.

        Para auxiliares, los permisos se cachean en la sesión con la clave
        'mod_access_cache' para evitar una query a UserPermission en cada
        request que renderice una plantilla.  El cache se invalida automáticamente
        cuando un admin actualiza los permisos del usuario (ver admin.py →
        gestionar_permisos_usuario).
        """
        try:
            rol     = session.get('rol')
            usuario = session.get('usuario')
            modulos = ['prestamos', 'reservas', 'inventario', 'profesores',
                       'estadisticas', 'bitacora', 'salas_computo', 'colaboradores']

            # Admins y superadmins tienen acceso total — sin query ni cache
            if rol in ('admin', 'superadmin'):
                return {'mod_access': {m: True for m in modulos}}

            # Usuario no autenticado
            if not usuario:
                return {'mod_access': {m: False for m in modulos}}

            # Leer del cache de sesión si está disponible
            cached = session.get('mod_access_cache')
            if cached is not None:
                return {'mod_access': cached}

            # Cache vacío: calcular desde BD y guardar en sesión
            from database import UserPermission
            perms  = UserPermission.query.filter_by(usuario_documento=usuario).all()
            access = {m: False for m in modulos}
            for p in perms:
                if p.modulo in access:
                    access[p.modulo] = True

            session['mod_access_cache'] = access   # guardar para requests siguientes
            return {'mod_access': access}

        except Exception:
            app.logger.warning('Error en inject_module_access', exc_info=True)
            modulos = ['prestamos', 'reservas', 'inventario', 'profesores',
                       'estadisticas', 'bitacora', 'salas_computo', 'colaboradores']
            return {'mod_access': {m: False for m in modulos}}

    # ── Manejadores de error ───────────────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return render_template('errors/400.html'), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    @app.route('/favicon.ico')
    def favicon():
        """Redirige las solicitudes de favicon tradicionales al icono estático."""
        return redirect(url_for('static', filename='favicon.svg'))
    # ── Ruta principal ─────────────────────────────────────────────────────────
    from auth import login_required

    @app.route('/')
    @login_required
    def index():
        """Página principal con dashboard."""
        try:
            periodo = request.args.get('periodo', 'dia')
            hoy = date.today()

            if periodo == 'dia':
                fecha_inicio = fecha_fin = hoy
                titulo_periodo = 'de Hoy'
            elif periodo == 'semana':
                fecha_inicio = hoy - timedelta(days=hoy.weekday())
                fecha_fin = fecha_inicio + timedelta(days=6)
                titulo_periodo = 'de la Semana'
            else:
                fecha_inicio = hoy.replace(day=1)
                _, num_days = calendar.monthrange(hoy.year, hoy.month)
                fecha_fin = hoy.replace(day=num_days)
                titulo_periodo = 'del Mes'

            sede_id = session.get('sede_id') if session.get('rol') not in ('admin', 'superadmin') else None

            # Estadísticas de préstamos
            query_prestamos = db.session.query(
                func.count(func.distinct(PrestamoEquipo.id_grupo_prestamo))
            ).filter(
                PrestamoEquipo.fecha_prestamo.between(fecha_inicio, fecha_fin),
                PrestamoEquipo.estado == SystemConstants.ESTADO_PRESTADO
            )
            if sede_id:
                query_prestamos = query_prestamos.filter(PrestamoEquipo.sede_id == sede_id)
            prestamos_total = query_prestamos.scalar() or 0

            # Estadísticas de reservas
            query_reservas_base = db.session.query(func.count(Reserva.id_reserva)).filter(
                Reserva.fecha.between(fecha_inicio, fecha_fin),
                Reserva.estado == SystemConstants.ESTADO_ACTIVA
            )
            if sede_id:
                query_reservas_base = query_reservas_base.filter(Reserva.sede_id == sede_id)

            reservas_salon = query_reservas_base.filter(Reserva.recurso_tipo == 'Salón').scalar() or 0
            reservas_ninera = query_reservas_base.filter(Reserva.recurso_tipo == 'Niñera').scalar() or 0

            # Top equipo y profesor
            top_equipo = {'nombre': 'N/A', 'cantidad': 0}
            top_profesor = {'nombre': 'N/A', 'cantidad': 0}

            q_top_eq = db.session.query(
                PrestamoEquipo.equipo_prestado,
                func.count(func.distinct(PrestamoEquipo.id_grupo_prestamo))
            ).group_by(PrestamoEquipo.equipo_prestado)
            if sede_id:
                q_top_eq = q_top_eq.filter(PrestamoEquipo.sede_id == sede_id)
            top_eq = q_top_eq.order_by(
                func.count(func.distinct(PrestamoEquipo.id_grupo_prestamo)).desc()
            ).first()
            if top_eq:
                top_equipo = {'nombre': top_eq[0], 'cantidad': top_eq[1]}

            q_top_prof = db.session.query(
                PrestamoEquipo.nombre_profesor,
                func.count(func.distinct(PrestamoEquipo.id_grupo_prestamo))
            ).group_by(PrestamoEquipo.nombre_profesor)
            if sede_id:
                q_top_prof = q_top_prof.filter(PrestamoEquipo.sede_id == sede_id)
            top_prof = q_top_prof.order_by(
                func.count(func.distinct(PrestamoEquipo.id_grupo_prestamo)).desc()
            ).first()
            if top_prof:
                top_profesor = {'nombre': top_prof[0], 'cantidad': top_prof[1]}

            # Préstamos vencidos
            vencidos_count = len(PrestamoService.obtener_prestamos_vencidos(sede_id=sede_id))

            stats = {
                'periodo_actual': periodo,
                'titulo_periodo': titulo_periodo,
                'prestamos_total': prestamos_total,
                'reservas_salon': reservas_salon,
                'reservas_ninera': reservas_ninera,
                'prestamos_vencidos': vencidos_count
            }

            # Alertas (no interrumpen el dashboard si fallan)
            try:
                from services.alert_service import AlertService
                overdue = AlertService.check_overdue_prestamos(sede_id=sede_id)
                if overdue:
                    flash(f'ATENCIÓN: {len(overdue)} préstamos vencidos.', 'warning')
                upcoming = AlertService.check_upcoming_reservas(days=2, sede_id=sede_id)
                if upcoming:
                    flash(f'Próximas reservas ({len(upcoming)}) en los próximos 2 días.', 'info')
            except Exception:
                app.logger.warning('Error al procesar alertas', exc_info=True)

            return render_template('index.html', stats=stats,
                                   top_equipo=top_equipo, top_profesor=top_profesor)

        except Exception as e:
            app.logger.error("Error al generar estadísticas para el index: %s", str(e), exc_info=True)
            flash('No se pudieron cargar las estadísticas del sistema.', 'warning')
            return render_template('index.html', stats=None, top_equipo=None, top_profesor=None)

    # ── Inicialización de DB y admin por defecto ───────────────────────────────
    if not app.config.get('TESTING') and not os.environ.get('FLASK_SKIP_INIT_DB'):
        try:
            with app.app_context():
                init_db(app)
                admin_doc = AdminConfig.DEFAULT_ADMIN_USER
                if not Auxiliar.query.filter_by(documento=admin_doc).first():
                    success, message = registrar_auxiliar(
                        AdminConfig.DEFAULT_ADMIN_USER,
                        'Administrador del Sistema',
                        AdminConfig.DEFAULT_ADMIN_EMAIL,
                        AdminConfig.DEFAULT_ADMIN_PASSWORD,
                        rol='admin'
                    )
                    if success:
                        app.logger.warning(
                            "Usuario administrador creado. Cambie las credenciales por defecto inmediatamente."
                        )
                    else:
                        app.logger.error("Error al crear administrador: %s", message)
        except Exception as e:
            app.logger.error("Aviso al inicializar base de datos en el arranque: %s", str(e))

    return app


if __name__ == '__main__':
    app = create_app()
    print("Sistema Integrado Iniciado")
    print("Módulos: Préstamos + Salones + Niñeras")
    print("Accede: http://127.0.0.1:5000")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
