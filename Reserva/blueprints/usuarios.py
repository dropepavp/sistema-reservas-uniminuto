"""
Blueprint para el Directorio y Gestión Unificada de Usuarios UNIMINUTO.
Consolida en una sola página con pestañas:
1. Colaboradores (Personal operativo, horarios semanales, tareas y matriz de permisos).
2. Profesores (Cuerpo docente, datos académicos, historial de préstamos y reservas).
3. Estudiantes (Alumnos, códigos Banner, sedes, programas académicos y estados).
"""
from flask import (
    Blueprint, render_template, request, redirect, flash,
    url_for, session, jsonify, current_app
)
from sqlalchemy import or_, and_, func, desc, asc, cast, String

from extensions import db
from database import (
    Colaborador, HorarioColaborador, TareaColaborador, PermisoColaborador,
    Profesor, Estudiante, Sede, ProgramaAcademico, PrestamoEquipo, Reserva
)
from auth import login_required, permiso_requerido

usuarios_bp = Blueprint('usuarios', __name__, url_prefix='/usuarios')

DIAS_SEMANA = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado']
MODULOS_SISTEMA = [
    'prestamos', 'reservas', 'inventario', 'mantenimiento',
    'profesores', 'estadisticas', 'bitacora', 'salas_computo', 'colaboradores'
]


@usuarios_bp.route('/', methods=['GET'])
@login_required
def usuarios_dashboard():
    """Vista principal unificada de Usuarios con pestañas de Colaboradores, Profesores y Estudiantes."""
    try:
        tab_activa = request.args.get('tab', 'colaboradores').strip().lower()
        if tab_activa not in ('colaboradores', 'profesores', 'estudiantes'):
            tab_activa = 'colaboradores'

        busqueda = request.args.get('busqueda', '').strip()
        programa_filtro = request.args.get('programa', '').strip()

        # Tomar sede de la sesión activa si no viene en los parámetros GET
        sede_param = request.args.get('sede')
        if sede_param is None:
            sede_id_session = session.get('sede_id')
            sede_filtro = str(sede_id_session) if sede_id_session else ''
        else:
            sede_filtro = sede_param.strip()

        # Sedes y Programas para dropdowns
        sedes = Sede.query.order_by(Sede.nombre.asc()).all()
        programas = ProgramaAcademico.query.filter_by(activo=True).order_by(ProgramaAcademico.nombre.asc()).all()

        # ─────────────────────────────────────────────────────────────
        # 1. PESTAÑA: COLABORADORES
        # ─────────────────────────────────────────────────────────────
        query_colab = Colaborador.query
        if sede_filtro and sede_filtro.isdigit():
            query_colab = query_colab.filter(
                or_(Colaborador.sede_id == int(sede_filtro), Colaborador.sede_id.is_(None))
            )
        if busqueda and tab_activa == 'colaboradores':
            t_colab = f"%{busqueda}%"
            query_colab = query_colab.filter(
                or_(
                    Colaborador.nombre_completo.ilike(t_colab),
                    Colaborador.documento.ilike(t_colab),
                    Colaborador.cargo.ilike(t_colab),
                    Colaborador.correo.ilike(t_colab)
                )
            )
        colaboradores = query_colab.filter_by(activo=True).order_by(Colaborador.nombre_completo.asc()).all()

        total_colab = len(colaboradores)
        inactivos_colab = Colaborador.query.filter_by(activo=False).count()
        tareas_pendientes_colab = TareaColaborador.query.filter_by(estado='pendiente').count()
        cobertura_dias = {dia: 0 for dia in DIAS_SEMANA}
        total_horas_programadas = 0.0
        total_horas_meta = 0

        for c in colaboradores:
            total_horas_meta += (c.total_horas_semana or 42)
            total_horas_programadas += c.horas_programadas_total
            for h in c.horarios:
                if h.dia in cobertura_dias and (h.hora_entrada or h.hora_salida or h.horas_dia):
                    cobertura_dias[h.dia] += 1

        stats_colaboradores = {
            'total': total_colab,
            'inactivos': inactivos_colab,
            'tareas_pendientes': tareas_pendientes_colab,
            'cobertura_dias': cobertura_dias,
            'total_horas_programadas': round(total_horas_programadas, 1),
            'total_horas_meta': total_horas_meta,
            'cumplimiento_pct': round((total_horas_programadas / total_horas_meta * 100), 1) if total_horas_meta > 0 else 0,
        }

        # ─────────────────────────────────────────────────────────────
        # 2. PESTAÑA: PROFESORES
        # ─────────────────────────────────────────────────────────────
        query_prof = Profesor.query
        if programa_filtro:
            query_prof = query_prof.filter(Profesor.programa.ilike(f"%{programa_filtro}%"))
        if busqueda and tab_activa == 'profesores':
            t_prof = f"%{busqueda}%"
            query_prof = query_prof.filter(
                or_(
                    Profesor.nombre_completo.ilike(t_prof),
                    Profesor.correo.ilike(t_prof),
                    Profesor.telefono.ilike(t_prof),
                    cast(Profesor.cedula, String).like(t_prof)
                )
            )
        profesores = query_prof.order_by(Profesor.nombre_completo.asc()).all()

        total_prof = Profesor.query.count()
        con_prestamos_prof = db.session.query(func.count(func.distinct(PrestamoEquipo.cedula_profesor))).scalar() or 0
        programas_prof_unicos = [p[0] for p in db.session.query(Profesor.programa).filter(Profesor.programa.isnot(None)).distinct().all() if p[0]]
        programas_prof_unicos.sort()

        stats_profesores = {
            'total': total_prof,
            'con_prestamos': con_prestamos_prof,
            'programas': len(programas_prof_unicos)
        }

        # ─────────────────────────────────────────────────────────────
        # 3. PESTAÑA: ESTUDIANTES
        # ─────────────────────────────────────────────────────────────
        query_est = Estudiante.query
        if sede_filtro:
            if sede_filtro.isdigit():
                query_est = query_est.filter(Estudiante.sede_id == int(sede_filtro))
            else:
                query_est = query_est.filter(Estudiante.descripcion_sede.ilike(f"%{sede_filtro}%"))

        if programa_filtro:
            if programa_filtro.isdigit():
                query_est = query_est.filter(Estudiante.programa_id == int(programa_filtro))
            else:
                query_est = query_est.filter(
                    or_(
                        Estudiante.atributo_programa.ilike(f"%{programa_filtro}%"),
                        Estudiante.programa_rel.has(ProgramaAcademico.nombre.ilike(f"%{programa_filtro}%"))
                    )
                )

        if busqueda and tab_activa == 'estudiantes':
            t_est = f"%{busqueda}%"
            query_est = query_est.filter(
                or_(
                    Estudiante.nombre_completo.ilike(t_est),
                    Estudiante.codigo_banner.ilike(t_est),
                    Estudiante.documento.ilike(t_est),
                    Estudiante.correo.ilike(t_est)
                )
            )

        estudiantes = query_est.order_by(Estudiante.nombre_completo.asc()).limit(500).all()

        total_est = Estudiante.query.count()
        activos_est = Estudiante.query.filter_by(activo=True).count()
        engativa_est = Estudiante.query.filter(Estudiante.descripcion_sede.ilike('%ENGATIVA%')).count()
        cd_bolivar_est = Estudiante.query.filter(Estudiante.descripcion_sede.ilike('%BOLIVAR%')).count()

        kpis_estudiantes = {
            'total': total_est,
            'activos': activos_est,
            'engativa': engativa_est,
            'cd_bolivar': cd_bolivar_est
        }

        return render_template(
            'usuarios.html',
            tab_activa=tab_activa,
            # Colaboradores
            colaboradores=colaboradores,
            stats_colaboradores=stats_colaboradores,
            dias_semana=DIAS_SEMANA,
            modulos_sistema=MODULOS_SISTEMA,
            # Profesores
            profesores=profesores,
            stats_profesores=stats_profesores,
            programas_prof_unicos=programas_prof_unicos,
            # Estudiantes
            estudiantes=estudiantes,
            kpis_estudiantes=kpis_estudiantes,
            # Globales
            sedes=sedes,
            programas=programas,
            filtros={
                'busqueda': busqueda,
                'sede': sede_filtro,
                'programa': programa_filtro
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error en dashboard unificado de usuarios: {e}", exc_info=True)
        flash('Ocurrió un error al cargar la vista de usuarios.', 'danger')
        return render_template(
            'usuarios.html',
            tab_activa='colaboradores',
            colaboradores=[],
            stats_colaboradores={'total': 0, 'inactivos': 0, 'tareas_pendientes': 0, 'cumplimiento_pct': 0, 'total_horas_programadas': 0, 'total_horas_meta': 0, 'cobertura_dias': {}},
            dias_semana=DIAS_SEMANA,
            modulos_sistema=MODULOS_SISTEMA,
            profesores=[],
            stats_profesores={'total': 0, 'con_prestamos': 0, 'programas': 0},
            programas_prof_unicos=[],
            estudiantes=[],
            kpis_estudiantes={'total': 0, 'activos': 0, 'engativa': 0, 'cd_bolivar': 0},
            sedes=[],
            programas=[],
            filtros={}
        )
