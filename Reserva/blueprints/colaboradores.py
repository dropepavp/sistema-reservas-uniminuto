"""
Blueprint para gestión de colaboradores.
Permite administrar horarios semanales, tareas y permisos de módulos.
"""
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
from extensions import db
from database import Colaborador, HorarioColaborador, TareaColaborador, PermisoColaborador, Sede
from decorators import login_required

colaboradores_bp = Blueprint('colaboradores', __name__, url_prefix='/colaboradores')

DIAS_SEMANA = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']
MODULOS_SISTEMA = ['prestamos', 'reservas', 'inventario', 'profesores',
                   'estadisticas', 'bitacora', 'salas_computo', 'colaboradores']


def _admin_required():
    return session.get('rol') in ('admin', 'superadmin')


# ─── PÁGINA PRINCIPAL ───────────────────────────────────────────────────────

@colaboradores_bp.route('/')
@login_required
def colaboradores_main():
    """Página principal de colaboradores con lista y vista de horarios."""
    colaboradores = Colaborador.query.filter_by(activo=True).order_by(Colaborador.nombre_completo).all()
    sedes = Sede.query.order_by(Sede.nombre).all()

    # Stats
    total = Colaborador.query.filter_by(activo=True).count()
    inactivos = Colaborador.query.filter_by(activo=False).count()
    total_tareas_pendientes = TareaColaborador.query.filter_by(estado='pendiente').count()

    # Cobertura de colaboradores con turno programado por día
    cobertura_dias = {dia: 0 for dia in DIAS_SEMANA}
    total_horas_programadas = 0.0
    total_horas_meta = 0

    for c in colaboradores:
        total_horas_meta += (c.total_horas_semana or 42)
        total_horas_programadas += c.horas_programadas_total
        for h in c.horarios:
            if h.dia in cobertura_dias and (h.hora_entrada or h.hora_salida or h.horas_dia):
                cobertura_dias[h.dia] += 1

    stats = {
        'total': total,
        'inactivos': inactivos,
        'tareas_pendientes': total_tareas_pendientes,
        'cobertura_dias': cobertura_dias,
        'total_horas_programadas': round(total_horas_programadas, 1),
        'total_horas_meta': total_horas_meta,
        'cumplimiento_pct': round((total_horas_programadas / total_horas_meta * 100), 1) if total_horas_meta > 0 else 0,
    }

    return render_template('colaboradores.html',
                           colaboradores=colaboradores,
                           sedes=sedes,
                           stats=stats,
                           dias_semana=DIAS_SEMANA,
                           modulos_sistema=MODULOS_SISTEMA)


# ─── API COLABORADORES ───────────────────────────────────────────────────────

@colaboradores_bp.route('/api/colaboradores', methods=['GET'])
@login_required
def api_listar():
    """Retorna lista de colaboradores en JSON."""
    solo_activos = request.args.get('activos', '1') == '1'
    q = Colaborador.query
    if solo_activos:
        q = q.filter_by(activo=True)
    colaboradores = q.order_by(Colaborador.nombre_completo).all()
    return jsonify({'success': True, 'colaboradores': [_collab_to_dict(c) for c in colaboradores]})


@colaboradores_bp.route('/api/colaboradores', methods=['POST'])
@login_required
def api_crear():
    """Crea un nuevo colaborador."""
    if not _admin_required():
        return jsonify({'success': False, 'message': 'Sin permisos'}), 403

    data = request.get_json() or {}
    nombre = (data.get('nombre_completo') or '').strip()
    if not nombre:
        return jsonify({'success': False, 'message': 'El nombre es requerido'}), 400

    # Documento único si se provee
    doc = (data.get('documento') or '').strip() or None
    if doc and Colaborador.query.filter_by(documento=doc).first():
        return jsonify({'success': False, 'message': 'Ya existe un colaborador con ese documento'}), 400

    colab = Colaborador(
        nombre_completo=nombre,
        cargo=(data.get('cargo') or '').strip() or None,
        documento=doc,
        correo=(data.get('correo') or '').strip() or None,
        telefono=(data.get('telefono') or '').strip() or None,
        sede_id=int(data['sede_id']) if data.get('sede_id') else None,
        total_horas_semana=int(data.get('total_horas_semana') or 42),
        fecha_inicio_horario=(data.get('fecha_inicio_horario') or '').strip() or None,
        horario_texto=(data.get('horario_texto') or '').strip() or None,
        observaciones=(data.get('observaciones') or '').strip() or None,
    )
    db.session.add(colab)
    db.session.flush()

    # Crear horarios vacíos para todos los días
    for dia in DIAS_SEMANA:
        db.session.add(HorarioColaborador(colaborador_id=colab.id, dia=dia))

    db.session.commit()
    return jsonify({'success': True, 'message': 'Colaborador creado', 'colaborador': _collab_to_dict(colab)}), 201


@colaboradores_bp.route('/api/colaboradores/<int:cid>', methods=['GET'])
@login_required
def api_obtener(cid):
    colab = Colaborador.query.get_or_404(cid)
    return jsonify({'success': True, 'colaborador': _collab_to_dict(colab, detalle=True)})


@colaboradores_bp.route('/api/colaboradores/<int:cid>', methods=['PUT'])
@login_required
def api_editar(cid):
    if not _admin_required():
        return jsonify({'success': False, 'message': 'Sin permisos'}), 403

    colab = Colaborador.query.get_or_404(cid)
    data = request.get_json() or {}

    nombre = (data.get('nombre_completo') or '').strip()
    if not nombre:
        return jsonify({'success': False, 'message': 'El nombre es requerido'}), 400

    colab.nombre_completo = nombre
    colab.cargo = (data.get('cargo') or '').strip() or None
    colab.correo = (data.get('correo') or '').strip() or None
    colab.telefono = (data.get('telefono') or '').strip() or None
    colab.sede_id = int(data['sede_id']) if data.get('sede_id') else None
    colab.total_horas_semana = int(data.get('total_horas_semana') or 42)
    colab.fecha_inicio_horario = (data.get('fecha_inicio_horario') or '').strip() or None
    colab.horario_texto = (data.get('horario_texto') or '').strip() or None
    colab.observaciones = (data.get('observaciones') or '').strip() or None
    colab.activo = bool(data.get('activo', True))

    db.session.commit()
    return jsonify({'success': True, 'message': 'Colaborador actualizado', 'colaborador': _collab_to_dict(colab)})


@colaboradores_bp.route('/api/colaboradores/<int:cid>', methods=['DELETE'])
@login_required
def api_eliminar(cid):
    if not _admin_required():
        return jsonify({'success': False, 'message': 'Sin permisos'}), 403
    colab = Colaborador.query.get_or_404(cid)
    colab.activo = False
    db.session.commit()
    return jsonify({'success': True, 'message': 'Colaborador desactivado'})


# ─── API HORARIOS ────────────────────────────────────────────────────────────

@colaboradores_bp.route('/api/horarios-todos', methods=['GET'])
@login_required
def api_todos_horarios():
    """Retorna todos los colaboradores con sus horarios completos."""
    colaboradores = Colaborador.query.filter_by(activo=True).order_by(Colaborador.nombre_completo).all()
    return jsonify({
        'success': True,
        'colaboradores': [_collab_to_dict(c, detalle=True) for c in colaboradores]
    })


@colaboradores_bp.route('/api/colaboradores/<int:cid>/horarios', methods=['GET'])
@login_required
def api_horarios(cid):
    Colaborador.query.get_or_404(cid)
    horarios = HorarioColaborador.query.filter_by(colaborador_id=cid).all()
    return jsonify({'success': True, 'horarios': [_horario_to_dict(h) for h in horarios]})


@colaboradores_bp.route('/api/colaboradores/<int:cid>/horarios', methods=['PUT'])
@login_required
def api_guardar_horarios(cid):
    """Guarda/actualiza todos los horarios diarios de un colaborador con validación."""
    if not _admin_required():
        return jsonify({'success': False, 'message': 'Sin permisos'}), 403

    colab = Colaborador.query.get_or_404(cid)
    data = request.get_json() or {}
    horarios_data = data.get('horarios', [])  # lista de {dia, hora_entrada, hora_salida, horas_dia, jornada, ...}

    total_calculado = 0.0

    for h_data in horarios_data:
        dia = (h_data.get('dia') or '').strip()
        if not dia:
            continue
        horario = HorarioColaborador.query.filter_by(colaborador_id=cid, dia=dia).first()
        if not horario:
            horario = HorarioColaborador(colaborador_id=cid, dia=dia)
            db.session.add(horario)
            
        h_ent = (h_data.get('hora_entrada') or '').strip() or None
        h_sal = (h_data.get('hora_salida') or '').strip() or None

        # Validación básica de horas si ambas están presentes
        if h_ent and h_sal and h_ent >= h_sal:
            return jsonify({
                'success': False,
                'message': f'En el día {dia}, la hora de salida ({h_sal}) debe ser posterior a la de entrada ({h_ent})'
            }), 400

        horario.jornada = (h_data.get('jornada') or '').strip() or None
        horario.hora_entrada = h_ent
        horario.hora_salida = h_sal
        horario.piso_laboratorio = (h_data.get('piso_laboratorio') or '').strip() or None
        horario.recurso_movil = (h_data.get('recurso_movil') or '').strip() or None
        
        val = h_data.get('horas_dia')
        if val not in (None, ''):
            try:
                horas_dia_val = round(float(val), 2)
                horario.horas_dia = horas_dia_val
                total_calculado += horas_dia_val
            except (ValueError, TypeError):
                horario.horas_dia = None
        else:
            horario.horas_dia = None

    # Actualizar total_horas_semana en colaborador
    total_enviado = data.get('total_horas_semana')
    if total_enviado is not None:
        try:
            colab.total_horas_semana = int(total_enviado)
        except (ValueError, TypeError):
            colab.total_horas_semana = round(total_calculado)

    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Horarios guardados exitosamente',
        'total_horas_calculado': round(total_calculado, 2)
    })


# ─── API TAREAS ──────────────────────────────────────────────────────────────

@colaboradores_bp.route('/api/colaboradores/<int:cid>/tareas', methods=['GET'])
@login_required
def api_tareas(cid):
    Colaborador.query.get_or_404(cid)
    tareas = TareaColaborador.query.filter_by(colaborador_id=cid).order_by(TareaColaborador.id.desc()).all()
    return jsonify({'success': True, 'tareas': [_tarea_to_dict(t) for t in tareas]})


@colaboradores_bp.route('/api/colaboradores/<int:cid>/tareas', methods=['POST'])
@login_required
def api_crear_tarea(cid):
    if not _admin_required():
        return jsonify({'success': False, 'message': 'Sin permisos'}), 403
    Colaborador.query.get_or_404(cid)
    data = request.get_json() or {}
    titulo = (data.get('titulo') or '').strip()
    if not titulo:
        return jsonify({'success': False, 'message': 'El título es requerido'}), 400

    tarea = TareaColaborador(
        colaborador_id=cid,
        titulo=titulo,
        descripcion=(data.get('descripcion') or '').strip() or None,
        estado=data.get('estado', 'pendiente'),
        prioridad=data.get('prioridad', 'normal'),
        fecha_asignacion=data.get('fecha_asignacion') or datetime.now().strftime('%Y-%m-%d'),
        fecha_vencimiento=data.get('fecha_vencimiento') or None,
    )
    db.session.add(tarea)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Tarea creada', 'tarea': _tarea_to_dict(tarea)}), 201


@colaboradores_bp.route('/api/tareas/<int:tid>', methods=['PUT'])
@login_required
def api_editar_tarea(tid):
    if not _admin_required():
        return jsonify({'success': False, 'message': 'Sin permisos'}), 403
    tarea = TareaColaborador.query.get_or_404(tid)
    data = request.get_json() or {}
    titulo = (data.get('titulo') or '').strip()
    if titulo:
        tarea.titulo = titulo
    tarea.descripcion = (data.get('descripcion') or '').strip() or tarea.descripcion
    tarea.estado = data.get('estado', tarea.estado)
    tarea.prioridad = data.get('prioridad', tarea.prioridad)
    tarea.fecha_vencimiento = data.get('fecha_vencimiento') or tarea.fecha_vencimiento
    db.session.commit()
    return jsonify({'success': True, 'message': 'Tarea actualizada', 'tarea': _tarea_to_dict(tarea)})


@colaboradores_bp.route('/api/tareas/<int:tid>', methods=['DELETE'])
@login_required
def api_eliminar_tarea(tid):
    if not _admin_required():
        return jsonify({'success': False, 'message': 'Sin permisos'}), 403
    tarea = TareaColaborador.query.get_or_404(tid)
    db.session.delete(tarea)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Tarea eliminada'})


# ─── API PERMISOS ────────────────────────────────────────────────────────────

@colaboradores_bp.route('/api/colaboradores/<int:cid>/permisos', methods=['GET'])
@login_required
def api_permisos(cid):
    Colaborador.query.get_or_404(cid)
    permisos = PermisoColaborador.query.filter_by(colaborador_id=cid).all()
    return jsonify({'success': True, 'permisos': [_permiso_to_dict(p) for p in permisos]})


@colaboradores_bp.route('/api/colaboradores/<int:cid>/permisos', methods=['PUT'])
@login_required
def api_guardar_permisos(cid):
    if not _admin_required():
        return jsonify({'success': False, 'message': 'Sin permisos'}), 403
    Colaborador.query.get_or_404(cid)
    data = request.get_json() or {}
    permisos_data = data.get('permisos', [])  # lista de {modulo, puede_ver, puede_crear, puede_editar, puede_eliminar}

    for p_data in permisos_data:
        modulo = (p_data.get('modulo') or '').strip()
        if not modulo:
            continue
        permiso = PermisoColaborador.query.filter_by(colaborador_id=cid, modulo=modulo).first()
        if not permiso:
            permiso = PermisoColaborador(colaborador_id=cid, modulo=modulo)
            db.session.add(permiso)
        permiso.puede_ver = bool(p_data.get('puede_ver', False))
        permiso.puede_crear = bool(p_data.get('puede_crear', False))
        permiso.puede_editar = bool(p_data.get('puede_editar', False))
        permiso.puede_eliminar = bool(p_data.get('puede_eliminar', False))

    db.session.commit()
    return jsonify({'success': True, 'message': 'Permisos guardados'})


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _collab_to_dict(c: Colaborador, detalle=False):
    d = {
        'id': c.id,
        'nombre_completo': c.nombre_completo,
        'cargo': c.cargo,
        'documento': c.documento,
        'correo': c.correo,
        'telefono': c.telefono,
        'sede_id': c.sede_id,
        'sede': c.sede.nombre if c.sede else None,
        'total_horas_semana': c.total_horas_semana,
        'horas_programadas': round(c.horas_programadas_total, 2),
        'fecha_inicio_horario': c.fecha_inicio_horario,
        'horario_texto': c.horario_texto,
        'activo': c.activo,
        'observaciones': c.observaciones,
    }
    if detalle:
        d['horarios'] = [_horario_to_dict(h) for h in c.horarios]
        d['tareas'] = [_tarea_to_dict(t) for t in c.tareas]
        d['permisos'] = [_permiso_to_dict(p) for p in c.permisos]
    return d


def _horario_to_dict(h):
    return {
        'id': h.id,
        'dia': h.dia,
        'jornada': h.jornada,
        'hora_entrada': h.hora_entrada,
        'hora_salida': h.hora_salida,
        'piso_laboratorio': h.piso_laboratorio,
        'recurso_movil': h.recurso_movil,
        'horas_dia': h.horas_dia,
        'activo': h.activo,
    }


def _tarea_to_dict(t: TareaColaborador):
    return {
        'id': t.id,
        'titulo': t.titulo,
        'descripcion': t.descripcion,
        'estado': t.estado,
        'prioridad': t.prioridad,
        'fecha_asignacion': t.fecha_asignacion,
        'fecha_vencimiento': t.fecha_vencimiento,
    }


def _permiso_to_dict(p: PermisoColaborador):
    return {
        'id': p.id,
        'modulo': p.modulo,
        'puede_ver': p.puede_ver,
        'puede_crear': p.puede_crear,
        'puede_editar': p.puede_editar,
        'puede_eliminar': p.puede_eliminar,
    }
