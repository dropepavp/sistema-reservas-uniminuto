"""
Blueprint para gestión de reservas de salones y niñeras.
Incluye calendario, validación de disponibilidad y gestión de conflictos.
"""
from flask import Blueprint, render_template, request, redirect, flash, jsonify, send_file, url_for, session
import io
import pandas as pd
from datetime import datetime, date, timedelta
from database import db, Reserva, Profesor, Festivo, Sede, UserPermission, registrar_auditoria, Recurso, Ubicacion, AuxiliarSede
from utils.export_helpers import exportar_df_excel, exportar_df_csv
from extensions import socketio  # para notificaciones push
from services.notification_service import NotificationService

from config import SystemConstants
from validators import DataValidator, BusinessValidator
from sqlalchemy import func, or_, and_
from auth import login_required, permiso_requerido, sede_requerida
from services.prestamo_service import PrestamoService

reservas_bp = Blueprint('reservas', __name__, url_prefix='/reservas')


@reservas_bp.route('/')
@login_required
@permiso_requerido('reservas', 'ver')
@sede_requerida
def reservas_main():
    """Página principal de reservas con calendario y filtros de estado."""
    try:
        hoy = date.today()
        ahora = datetime.now()
        
        # Obtener sedes
        sedes = Sede.query.all()
        sede_actual_id = request.args.get('sede', '')
        
        if not sede_actual_id and session.get('rol') not in ('admin', 'superadmin') and session.get('sede_id'):
            sede_actual_id = str(session.get('sede_id'))
        
        # Obtener recursos dinámicamente de la DB
        recursos_query = Recurso.query.filter_by(activo=True)
        if sede_actual_id:
            recursos_query = recursos_query.join(Recurso.ubicacion).filter(Ubicacion.sede_id == int(sede_actual_id))
        
        recursos_db = recursos_query.all()
        recursos = {}
        for r in recursos_db:
            if r.tipo not in recursos:
                recursos[r.tipo] = []
            recursos[r.tipo].append(r.nombre)
        
        # Ordenar nombres
        for tipo in recursos:
            recursos[tipo].sort()

        if not recursos:
            recursos = {
                "Aula": getattr(SystemConstants, 'AULAS', SystemConstants.SALONES),
                "Niñera": SystemConstants.NINERAS
            }
        
        # Consultas base
        base_query = Reserva.query
        if sede_actual_id:
            base_query = base_query.filter_by(sede_id=int(sede_actual_id))

        # Todas las reservas relevantes (activas, cumplidas y canceladas)
        todas_reservas = base_query.order_by(Reserva.fecha.desc(), Reserva.hora_inicio.asc()).all()

        # Reservas activas y de hoy
        reservas_hoy = [r for r in todas_reservas if r.fecha == hoy and r.estado == SystemConstants.ESTADO_ACTIVA]
        reservas_activas = [r for r in todas_reservas if r.estado == SystemConstants.ESTADO_ACTIVA]

        # Estadísticas rápidas para pestañas
        total_hoy = len(reservas_hoy)
        total_activas = len(reservas_activas)
        total_cumplidas = base_query.filter(Reserva.estado == 'Completada').count()
        total_canceladas = base_query.filter(Reserva.estado == SystemConstants.ESTADO_CANCELADA).count()

        # Enriquecer reservas con banderas de proximidad y tiempo
        reservas_enriquecidas = []
        for r in todas_reservas:
            es_hoy = (r.fecha == hoy)
            minutos_para_inicio = None
            estado_tiempo = 'futura'

            if es_hoy and r.hora_inicio and r.hora_fin:
                dt_inicio = datetime.combine(hoy, r.hora_inicio)
                dt_fin = datetime.combine(hoy, r.hora_fin)
                diff_inicio = (dt_inicio - ahora).total_seconds() / 60
                diff_fin = (dt_fin - ahora).total_seconds() / 60

                minutos_para_inicio = round(diff_inicio)

                if diff_inicio > 30:
                    estado_tiempo = 'proxima'
                elif 0 <= diff_inicio <= 30:
                    estado_tiempo = 'por_iniciar'  # Semáforo amarillo (inicia en <30m)
                elif diff_inicio < 0 and diff_fin >= 0:
                    estado_tiempo = 'en_curso'     # Semáforo verde (en horario de clase)
                else:
                    estado_tiempo = 'vencida'      # Semáforo rojo (ya pasó la hora)

            reservas_enriquecidas.append({
                'id_reserva': r.id_reserva,
                'cedula_profesor': r.cedula_profesor,
                'nombre_profesor': r.nombre_profesor,
                'profesor_telefono': r.profesor.telefono if r.profesor else '--',
                'profesor_correo': r.profesor.correo if r.profesor else '--',
                'recurso_tipo': r.recurso_tipo,
                'recurso_nombre': r.recurso_nombre,
                'nrc': r.nrc or '',
                'fecha': r.fecha,
                'hora_inicio': r.hora_inicio,
                'hora_fin': r.hora_fin,
                'estado': r.estado,
                'observaciones': r.observaciones or '',
                'es_hoy': es_hoy,
                'estado_tiempo': estado_tiempo,
                'minutos_para_inicio': minutos_para_inicio
            })

        return render_template('reservas.html', 
                             recursos=recursos, 
                             reservas=todas_reservas,
                             reservas_enriquecidas=reservas_enriquecidas,
                             total_hoy=total_hoy,
                             total_activas=total_activas,
                             total_cumplidas=total_cumplidas,
                             total_canceladas=total_canceladas,
                             sedes=sedes,
                             salon_marcas=SystemConstants.SALON_MARCA,
                             salones_principal=SystemConstants.SALONES_PRINCIPAL,
                             salones_perdomo=SystemConstants.SALONES_PERDOMO,
                             sede_actual=sede_actual_id)
                             
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        flash('Error al cargar las reservas.', 'danger')
        return render_template('reservas.html', recursos={}, reservas=[], sedes=[])

@reservas_bp.route('/api/calendario')
@login_required
@permiso_requerido('reservas', 'ver')
def api_reservas_calendario():
    """API para obtener eventos del calendario."""
    try:
        # Filtro opcional por tipo de recurso y sede
        tipo_recurso_filtro = request.args.get('recurso_tipo', None)
        sede_id_filtro = request.args.get('sede_id', None)
        fecha_desde = request.args.get('start')
        fecha_hasta = request.args.get('end')

        query = Reserva.query.filter_by(estado=SystemConstants.ESTADO_ACTIVA)

        # Filtrar por tipo de recurso
        if tipo_recurso_filtro:
            query = query.filter_by(recurso_tipo=tipo_recurso_filtro)
        
        # Filtrar por sede
        if session.get('rol') not in ('admin', 'superadmin') and session.get('sede_id'):
            query = query.filter_by(sede_id=session.get('sede_id'))
        elif sede_id_filtro:
            query = query.filter_by(sede_id=int(sede_id_filtro))
        
        # Filtrar por rango de fechas (para el calendario)
        if fecha_desde and fecha_hasta:
            try:
                fecha_inicio = datetime.strptime(fecha_desde[:10], '%Y-%m-%d').date()
                fecha_fin = datetime.strptime(fecha_hasta[:10], '%Y-%m-%d').date()
                query = query.filter(Reserva.fecha.between(fecha_inicio, fecha_fin))
            except ValueError:
                pass  # Si las fechas no son válidas, ignorar filtro

        reservas = query.all()
        eventos = []
        
        for reserva in reservas:
            try:
                start_datetime = f"{reserva.fecha.strftime('%Y-%m-%d')}T{reserva.hora_inicio.strftime('%H:%M')}"
                end_datetime = f"{reserva.fecha.strftime('%Y-%m-%d')}T{reserva.hora_fin.strftime('%H:%M')}"
                
                # Colores por tipo de recurso
                color = '#3788d8'  # Azul para salones
                if reserva.recurso_tipo == 'Niñera':
                    color = '#198754'  # Verde para niñeras

                eventos.append({
                    'id': reserva.id_reserva,
                    'resourceId': reserva.recurso_nombre,
                    'title': f"{reserva.recurso_tipo} - {reserva.nombre_profesor or 'N/A'}",
                    'extendedProps': {
                        'recurso_tipo': reserva.recurso_tipo,
                        'recurso': reserva.recurso_nombre,
                        'nrc': reserva.nrc or 'N/A',
                        'profesor': reserva.nombre_profesor,
                        'cedula_profesor': reserva.cedula_profesor,
                        'observaciones': reserva.observaciones or ''
                    },
                    'start': start_datetime,
                    'end': end_datetime,
                    'color': color
                })
            except Exception as e:
                continue  # Saltar reservas con datos inválidos

        return jsonify(eventos)
        
    except Exception as e:
        return jsonify([]), 500

@reservas_bp.route('/api/festivos')
@login_required
@permiso_requerido('reservas', 'ver')
def api_festivos():
    """API para obtener días festivos para el calendario."""
    try:
        festivos = Festivo.query.all()
        eventos = []
        for f in festivos:
            eventos.append({
                'title': f.descripcion,
                'start': f.fecha.strftime('%Y-%m-%d'),
                'display': 'background',
                'color': '#ffc107',
                'allDay': True
            })
        return jsonify(eventos)
    except Exception as e:
        return jsonify([]), 500

@reservas_bp.route('/buscar')
@login_required
@permiso_requerido('reservas', 'ver')
def buscar_reservas_api():
    """API para búsqueda de reservas."""
    try:
        query_text = request.args.get('q', '')
        if not query_text:
            return jsonify({'success': True, 'results': []})
            
        search_term = f"%{query_text}%"
        reservas = Reserva.query.filter(
            or_(
                Reserva.nombre_profesor.ilike(search_term),
                Reserva.recurso_nombre.ilike(search_term),
                Reserva.nrc.ilike(search_term),
                Reserva.cedula_profesor.like(search_term)
            )
        ).limit(50).all()
        
        results = []
        for r in reservas:
            results.append({
                'id_reserva': r.id_reserva,
                'nombre_profesor': r.nombre_profesor,
                'recurso_nombre': r.recurso_nombre,
                'fecha': r.fecha.strftime('%Y-%m-%d'),
                'hora_inicio': r.hora_inicio.strftime('%H:%M'),
                'hora_fin': r.hora_fin.strftime('%H:%M'),
                'nrc': r.nrc or '',
                'estado': r.estado
            })
            
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# NUEVAS RUTAS API: CONFLICTOS, CONVERSIÓN A PRÉSTAMO Y ESTADOS
# ══════════════════════════════════════════════════════════════════

@reservas_bp.route('/api/verificar-disponibilidad')
@login_required
@permiso_requerido('reservas', 'ver')
def api_verificar_disponibilidad():
    """
    Verifica en tiempo real si un aula o recurso tiene colisiones con otra reserva o préstamo.
    Query params: recurso_nombre, fecha (YYYY-MM-DD), hora_inicio (HH:MM), hora_fin (HH:MM), excluir_id (opcional)
    """
    try:
        recurso = (request.args.get('recurso_nombre') or '').strip()
        fecha_str = (request.args.get('fecha') or '').strip()
        h_inicio_str = (request.args.get('hora_inicio') or '').strip()
        h_fin_str = (request.args.get('hora_fin') or '').strip()
        excluir_id = request.args.get('excluir_id')

        if not recurso or not fecha_str or not h_inicio_str or not h_fin_str:
            return jsonify({'disponible': True, 'mensaje': 'Parámetros incompletos para verificar'})

        fecha_valid, fecha_obj, _ = DataValidator.validate_date(fecha_str)
        inicio_valid, hora_inicio, _ = DataValidator.validate_time(h_inicio_str)
        fin_valid, hora_fin, _ = DataValidator.validate_time(h_fin_str)

        if not (fecha_valid and inicio_valid and fin_valid) or hora_inicio >= hora_fin:
            return jsonify({'disponible': True, 'mensaje': 'Horario en edición'})

        # 1. Verificar conflicto con otra reserva activa
        query_res = Reserva.query.filter(
            Reserva.recurso_nombre == recurso,
            Reserva.fecha == fecha_obj,
            Reserva.estado == SystemConstants.ESTADO_ACTIVA,
            Reserva.hora_inicio < hora_fin,
            Reserva.hora_fin > hora_inicio
        )
        if excluir_id:
            try:
                query_res = query_res.filter(Reserva.id_reserva != int(excluir_id))
            except (ValueError, TypeError):
                pass

        conflicto_res = query_res.first()
        if conflicto_res:
            return jsonify({
                'disponible': False,
                'tipo_conflicto': 'reserva',
                'mensaje': f'El espacio "{recurso}" ya está reservado por {conflicto_res.nombre_profesor} de {conflicto_res.hora_inicio.strftime("%H:%M")} a {conflicto_res.hora_fin.strftime("%H:%M")}',
                'conflicto': {
                    'profesor': conflicto_res.nombre_profesor,
                    'hora_inicio': conflicto_res.hora_inicio.strftime('%H:%M'),
                    'hora_fin': conflicto_res.hora_fin.strftime('%H:%M'),
                    'nrc': conflicto_res.nrc
                }
            })

        # 2. Verificar conflicto con préstamo activo en esa ubicación si la fecha es hoy
        if fecha_obj == date.today():
            from database import PrestamoEquipo
            conflicto_prest = PrestamoEquipo.query.filter(
                PrestamoEquipo.ubicacion == recurso,
                PrestamoEquipo.fecha_prestamo == fecha_obj,
                PrestamoEquipo.estado == SystemConstants.ESTADO_PRESTADO,
                PrestamoEquipo.hora_inicio < hora_fin,
                PrestamoEquipo.hora_fin > hora_inicio
            ).first()
            if conflicto_prest:
                return jsonify({
                    'disponible': False,
                    'tipo_conflicto': 'prestamo',
                    'mensaje': f'El espacio "{recurso}" tiene un préstamo activo de equipos asignado a {conflicto_prest.nombre_profesor} hasta las {conflicto_prest.hora_fin.strftime("%H:%M")}',
                    'conflicto': {
                        'profesor': conflicto_prest.nombre_profesor,
                        'hora_inicio': conflicto_prest.hora_inicio.strftime('%H:%M'),
                        'hora_fin': conflicto_prest.hora_fin.strftime('%H:%M')
                    }
                })

        return jsonify({
            'disponible': True,
            'mensaje': f'Espacio "{recurso}" disponible en el horario seleccionado'
        })

    except Exception as e:
        return jsonify({'disponible': True, 'error': str(e)})


@reservas_bp.route('/api/convertir-prestamo/<int:id_reserva>', methods=['POST'])
@login_required
@permiso_requerido('prestamos', 'crear')
def api_convertir_a_prestamo(id_reserva):
    """
    Convierte una reserva en préstamo activo.
    Retorna la URL de redirección a taquilla de préstamos con los datos precargados.
    """
    try:
        reserva = Reserva.query.get_or_404(id_reserva)

        # Validar si ya está cancelada
        if reserva.estado == SystemConstants.ESTADO_CANCELADA:
            return jsonify({'success': False, 'message': 'No se puede convertir una reserva cancelada'}), 400

        # Cambiar estado a 'Completada'
        reserva.estado = 'Completada'
        db.session.commit()

        # Registrar auditoría
        registrar_auditoria(
            modulo='reservas',
            entidad_tipo='Reserva',
            entidad_id=str(reserva.id_reserva),
            accion='EDITAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Reserva #{reserva.id_reserva} entregada y convertida a préstamo'
        )

        # Generar parámetros para autocompletar en préstamos
        params = {
            'cedula': reserva.cedula_profesor,
            'profesor': reserva.nombre_profesor,
            'ubicacion': reserva.recurso_nombre,
            'hora_inicio': reserva.hora_inicio.strftime('%H:%M'),
            'hora_fin': reserva.hora_fin.strftime('%H:%M'),
            'observaciones': f'Convertido desde Reserva #{reserva.id_reserva}' + (f' (NRC: {reserva.nrc})' if reserva.nrc else ''),
            'auto_borrador': '1'
        }
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        redirect_url = f"/prestamos/?{query_string}"

        return jsonify({
            'success': True,
            'message': f'Reserva convertida con éxito. Redirigiendo a taquilla de préstamos...',
            'redirect_url': redirect_url
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error al convertir reserva: {str(e)}'}), 500


@reservas_bp.route('/api/cambiar-estado/<int:id_reserva>', methods=['POST'])
@login_required
@permiso_requerido('reservas', 'editar')
def api_cambiar_estado_reserva(id_reserva):
    """Cambia el estado de una reserva (Activa, Cancelada, Cumplida)."""
    try:
        reserva = Reserva.query.get_or_404(id_reserva)
        data = request.json or {}
        nuevo_estado = data.get('estado')

        if not nuevo_estado:
            return jsonify({'success': False, 'message': 'Debe especificar el nuevo estado'}), 400

        estado_anterior = reserva.estado
        reserva.estado = nuevo_estado
        db.session.commit()

        registrar_auditoria(
            modulo='reservas',
            entidad_tipo='Reserva',
            entidad_id=str(reserva.id_reserva),
            accion='EDITAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Cambio de estado de reserva #{id_reserva}: {estado_anterior} -> {nuevo_estado}'
        )

        return jsonify({
            'success': True,
            'message': f'Estado actualizado a "{nuevo_estado}"'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@reservas_bp.route('/nueva', methods=['POST'])
@login_required
@permiso_requerido('reservas', 'crear')
def nueva_reserva():
    """Crea una nueva reserva."""
    try:
        datos = request.json
        
        # Validar cédula del profesor
        cedula_valid, cedula_int, cedula_error = DataValidator.validate_cedula(datos.get('cedula'))
        if not cedula_valid:
            return jsonify({'success': False, 'message': cedula_error}), 400

        # Buscar profesor
        profesor = Profesor.query.get(cedula_int)
        if not profesor:
            return jsonify({'success': False, 'message': f'Profesor con cédula {cedula_int} no encontrado'}), 404
        
        # Validar recurso
        recurso_nombre = datos.get('recurso_nombre')
        recurso_tipo = datos.get('recurso_tipo')

        # ── Resolución y verificación de sede ────────────────────────────────
        # Admins y superadmins pueden especificar cualquier sede_id desde el JSON.
        # Auxiliares solo pueden operar en las sedes que tienen asignadas; si
        # intentan enviar un sede_id distinto se rechaza la solicitud.
        rol = session.get('rol')
        if rol in ('admin', 'superadmin'):
            # Admin: acepta sede_id del JSON o cualquier valor de sesión
            sede_id = datos.get('sede_id') or session.get('sede_id')
        else:
            # Auxiliar: ignorar completamente el sede_id del JSON y usar el de sesión
            sede_id = session.get('sede_id')
            sede_id_solicitado = datos.get('sede_id')
            if sede_id_solicitado:
                try:
                    sede_id_solicitado = int(sede_id_solicitado)
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'message': 'sede_id inválido'}), 400

                # Construir el conjunto de sedes permitidas para este auxiliar
                usuario_doc = session.get('usuario')
                sedes_permitidas = set()
                if sede_id:
                    sedes_permitidas.add(int(sede_id))
                # Incluir sedes adicionales asignadas en la tabla auxiliar_sedes
                asignaciones = AuxiliarSede.query.filter_by(
                    usuario_documento=usuario_doc
                ).all()
                for asig in asignaciones:
                    sedes_permitidas.add(asig.sede_id)

                if sede_id_solicitado not in sedes_permitidas:
                    return jsonify({
                        'success': False,
                        'message': 'No tienes permiso para crear reservas en esa sede.'
                    }), 403

                # La solicitud es legítima: usar el sede_id solicitado
                sede_id = sede_id_solicitado

        if not sede_id:
            return jsonify({'success': False, 'message': 'No hay una sede activa en la sesión.'}), 400
        
        if not recurso_nombre or not recurso_tipo:
            return jsonify({'success': False, 'message': 'Debe seleccionar un recurso válido'}), 400
        
        # Validar que el recurso existe en la DB para la sede indicada
        recurso_db = Recurso.query.filter_by(nombre=recurso_nombre, tipo=recurso_tipo, activo=True).join(Recurso.ubicacion).filter(Ubicacion.sede_id == int(sede_id)).first()
        
        if not recurso_db:
             # Fallback a constantes si no hay recursos en DB aún (para evitar bloqueo inmediato)
             recursos_const = getattr(SystemConstants, 'AULAS', SystemConstants.SALONES) if recurso_tipo in ('Aula', 'Salón') else SystemConstants.NINERAS
             if recurso_nombre not in recursos_const:
                 return jsonify({'success': False, 'message': 'Recurso no encontrado en el sistema'}), 400

        # Validar fecha
        fecha_valid, fecha_obj, fecha_error = DataValidator.validate_date(datos.get('fecha'))
        if not fecha_valid:
            return jsonify({'success': False, 'message': fecha_error}), 400
        
        # Validar que la fecha sea futura o actual
        future_valid, future_error = BusinessValidator.validate_future_date(fecha_obj)
        if not future_valid:
            return jsonify({'success': False, 'message': future_error}), 400
        
        # Validar que no sea festivo o domingo
        if es_festivo(fecha_obj) or es_fin_semana(fecha_obj):
            return jsonify({'success': False, 'message': 'No se permiten reservas en festivos o domingos'}), 400

        # Validar horarios
        hora_inicio_valid, hora_inicio_obj, inicio_error = DataValidator.validate_time(datos.get('hora_inicio'))
        if not hora_inicio_valid:
            return jsonify({'success': False, 'message': inicio_error}), 400

        hora_fin_valid, hora_fin_obj, fin_error = DataValidator.validate_time(datos.get('hora_fin'))
        if not hora_fin_valid:
            return jsonify({'success': False, 'message': fin_error}), 400

        # Validar rango de tiempo
        range_valid, range_error = DataValidator.validate_time_range(hora_inicio_obj, hora_fin_obj)
        if not range_valid:
            return jsonify({'success': False, 'message': range_error}), 400

        # Validar horario laboral
        inicio_work_valid, inicio_work_error = BusinessValidator.validate_working_hours(hora_inicio_obj)
        if not inicio_work_valid:
            return jsonify({'success': False, 'message': inicio_work_error}), 400

        fin_work_valid, fin_work_error = BusinessValidator.validate_working_hours(hora_fin_obj)
        if not fin_work_valid:
            return jsonify({'success': False, 'message': fin_work_error}), 400

        # Validar disponibilidad del recurso
        if not validar_disponibilidad_recurso(recurso_nombre, fecha_obj, hora_inicio_obj, hora_fin_obj):
            return jsonify({'success': False, 'message': 'El recurso no está disponible en ese horario'}), 400

        # Validar campos opcionales
        nrc_valid, nrc_error = DataValidator.validate_string_field(
            datos.get('nrc', ''), 'NRC', required=False, max_length=20
        )
        if not nrc_valid:
            return jsonify({'success': False, 'message': nrc_error}), 400

        obs_valid, obs_error = DataValidator.validate_string_field(
            datos.get('observaciones', ''), 'Observaciones', required=False, max_length=500
        )
        if not obs_valid:
            return jsonify({'success': False, 'message': obs_error}), 400

        # Crear la reserva
        nueva_reserva = Reserva(
            cedula_profesor=cedula_int,
            nombre_profesor=profesor.nombre_completo,
            nrc=datos.get('nrc', '').strip(),
            recurso_tipo=recurso_tipo,
            recurso_nombre=recurso_nombre,
            recurso_id=recurso_db.id if recurso_db else None,
            fecha=fecha_obj,
            jornada=calcular_jornada_desde_hora(hora_inicio_obj.strftime('%H:%M')),
            hora_inicio=hora_inicio_obj,
            hora_fin=hora_fin_obj,
            sede_id=int(sede_id),
            tipo_reserva=datos.get('tipo_reserva', 'Por Horario'),
            estado=SystemConstants.ESTADO_ACTIVA,
            observaciones=datos.get('observaciones', '').strip()
        )

        db.session.add(nueva_reserva)
        db.session.commit()

        # Emitir notificación en tiempo real usando el servicio centralizado
        NotificationService.notify_nueva_reserva(
            reserva_id=nueva_reserva.id_reserva,
            recurso_nombre=recurso_nombre,
            profesor=profesor.nombre_completo,
            url=f'/reservas/{nueva_reserva.id_reserva}'
        )

        registrar_auditoria(
            modulo='reservas',
            entidad_tipo='Reserva',
            entidad_id=nueva_reserva.id_reserva,
            accion='CREAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Creación de reserva para {profesor.nombre_completo} en {recurso_nombre}',
            datos_antes=None,
            datos_despues={
                'fecha': datos.get('fecha'),
                'hora_inicio': datos.get('hora_inicio'),
                'hora_fin': datos.get('hora_fin'),
                'nrc': datos.get('nrc', ''),
                'recurso_tipo': recurso_tipo,
                'recurso_nombre': recurso_nombre,
            }
        )

        return jsonify({
            'success': True,
            'message': 'Reserva registrada exitosamente',
            'reserva': {
                'id': nueva_reserva.id_reserva,
                'profesor': profesor.nombre_completo,
                'recurso': recurso_nombre,
                'fecha': datos['fecha'],
                'hora_inicio': datos['hora_inicio'],
                'hora_fin': datos['hora_fin'],
                'nrc': datos.get('nrc', '')
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@reservas_bp.route('/<int:id_reserva>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@permiso_requerido('reservas', 'editar')
def gestionar_reserva(id_reserva):
    """Obtiene, actualiza o cancela una reserva específica."""
    reserva = Reserva.query.get_or_404(id_reserva)
    
    if request.method == 'GET':
        # Obtener datos de la reserva
        reserva_data = {
            'id_reserva': reserva.id_reserva,
            'cedula_profesor': reserva.cedula_profesor,
            'nombre_profesor': reserva.nombre_profesor,
            'nrc': reserva.nrc or '',
            'recurso_tipo': reserva.recurso_tipo,
            'recurso_nombre': reserva.recurso_nombre,
            'fecha': reserva.fecha.strftime('%Y-%m-%d'),
            'hora_inicio': reserva.hora_inicio.strftime('%H:%M'),
            'hora_fin': reserva.hora_fin.strftime('%H:%M'),
            'observaciones': reserva.observaciones or '',
            'estado': reserva.estado
        }
        return jsonify({'success': True, 'reserva': reserva_data})
    
    elif request.method == 'PUT':
        # Actualizar reserva
        try:
            if reserva.estado != SystemConstants.ESTADO_ACTIVA:
                return jsonify({'success': False, 'message': 'Solo se pueden editar reservas activas'}), 400

            datos = request.json

            datos_antes = {
                'fecha': reserva.fecha.strftime('%Y-%m-%d'),
                'hora_inicio': reserva.hora_inicio.strftime('%H:%M'),
                'hora_fin': reserva.hora_fin.strftime('%H:%M'),
                'nrc': reserva.nrc or '',
                'observaciones': reserva.observaciones or '',
                'estado': reserva.estado,
            }
            
            # Validar fecha
            fecha_valid, fecha_obj, fecha_error = DataValidator.validate_date(datos.get('fecha'))
            if not fecha_valid:
                return jsonify({'success': False, 'message': fecha_error}), 400
            
            # Validar que no sea festivo o domingo
            if es_festivo(fecha_obj) or es_fin_semana(fecha_obj):
                return jsonify({'success': False, 'message': 'No se permiten reservas en festivos o domingos'}), 400

            # Validar horarios
            hora_inicio_valid, hora_inicio_obj, inicio_error = DataValidator.validate_time(datos.get('hora_inicio'))
            if not hora_inicio_valid:
                return jsonify({'success': False, 'message': inicio_error}), 400

            hora_fin_valid, hora_fin_obj, fin_error = DataValidator.validate_time(datos.get('hora_fin'))
            if not hora_fin_valid:
                return jsonify({'success': False, 'message': fin_error}), 400

            # Validar disponibilidad (excluyendo la reserva actual)
            if not validar_disponibilidad_recurso(reserva.recurso_nombre, fecha_obj, 
                                                 hora_inicio_obj, hora_fin_obj, 
                                                 excluir_id=id_reserva):
                return jsonify({'success': False, 'message': 'El recurso no está disponible en el nuevo horario'}), 400

            # Actualizar campos
            reserva.fecha = fecha_obj
            reserva.hora_inicio = hora_inicio_obj
            reserva.hora_fin = hora_fin_obj
            reserva.nrc = datos.get('nrc', '').strip()
            reserva.observaciones = datos.get('observaciones', '').strip()
            reserva.jornada = calcular_jornada_desde_hora(hora_inicio_obj.strftime('%H:%M'))

            db.session.commit()

            datos_despues = {
                'fecha': reserva.fecha.strftime('%Y-%m-%d'),
                'hora_inicio': reserva.hora_inicio.strftime('%H:%M'),
                'hora_fin': reserva.hora_fin.strftime('%H:%M'),
                'nrc': reserva.nrc or '',
                'observaciones': reserva.observaciones or '',
                'estado': reserva.estado,
            }

            registrar_auditoria(
                modulo='reservas',
                entidad_tipo='Reserva',
                entidad_id=reserva.id_reserva,
                accion='EDITAR',
                usuario_documento=session.get('usuario', ''),
                usuario_nombre=session.get('nombre_completo', ''),
                descripcion=f'Edición de reserva {reserva.id_reserva}',
                datos_antes=datos_antes,
                datos_despues=datos_despues
            )

            return jsonify({'success': True, 'message': 'Reserva actualizada exitosamente'})

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500
    
    elif request.method == 'DELETE':
        # Cancelar reserva
        try:
            datos_antes = {
                'estado': reserva.estado,
                'fecha': reserva.fecha.strftime('%Y-%m-%d'),
                'hora_inicio': reserva.hora_inicio.strftime('%H:%M'),
                'hora_fin': reserva.hora_fin.strftime('%H:%M'),
            }

            reserva.estado = SystemConstants.ESTADO_CANCELADA
            db.session.commit()

            # Emitir notificación de reserva cancelada
            NotificationService.notify_reserva_cancelada(
                reserva_id=reserva.id_reserva,
                recurso_nombre=reserva.recurso_nombre,
                url=f'/reservas/{reserva.id_reserva}'
            )

            registrar_auditoria(
                modulo='reservas',
                entidad_tipo='Reserva',
                entidad_id=reserva.id_reserva,
                accion='CANCELAR',
                usuario_documento=session.get('usuario', ''),
                usuario_nombre=session.get('nombre_completo', ''),
                descripcion=f'Cancelación de reserva {reserva.id_reserva}',
                datos_antes=datos_antes,
                datos_despues={'estado': reserva.estado}
            )

            return jsonify({'success': True, 'message': 'Reserva cancelada exitosamente'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@reservas_bp.route('/disponibilidad/<tipo_recurso>')
@login_required
def consultar_disponibilidad(tipo_recurso):
    """Consulta la disponibilidad de un recurso en una fecha específica."""
    fecha = request.args.get('fecha')
    recurso = request.args.get('recurso')

    if not fecha or not recurso:
        return jsonify({'error': 'Los parámetros "fecha" y "recurso" son requeridos'}), 400

    try:
        fecha_valid, fecha_dt, fecha_error = DataValidator.validate_date(fecha)
        if not fecha_valid:
            return jsonify({'error': fecha_error}), 400

        horarios_ocupados = []
        reservas_activas = Reserva.query.filter_by(
            recurso_nombre=recurso,
            fecha=fecha_dt,
            estado=SystemConstants.ESTADO_ACTIVA
        ).all()

        for reserva in reservas_activas:
            horarios_ocupados.append({
                'inicio': reserva.hora_inicio.strftime('%H:%M'),
                'fin': reserva.hora_fin.strftime('%H:%M'),
                'profesor': reserva.nombre_profesor,
                'nrc': reserva.nrc or 'N/A'
            })

        return jsonify({'horarios_ocupados': horarios_ocupados})

    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@reservas_bp.route('/exportar/<formato>')
@login_required
@permiso_requerido('reservas', 'ver')
def exportar_reservas_activas(formato):
    """Exporta las reservas activas."""
    try:
        reservas_activas = Reserva.query.filter_by(estado=SystemConstants.ESTADO_ACTIVA).all()
        
        if not reservas_activas:
            flash('No hay reservas para exportar.', 'info')
            return redirect(url_for('reservas.reservas_main'))

        # Preparar datos
        data = []
        for r in reservas_activas:
            data.append({
                'ID Reserva': r.id_reserva,
                'Cédula Profesor': r.cedula_profesor,
                'Profesor': r.nombre_profesor,
                'NRC': r.nrc or '',
                'Tipo Recurso': r.recurso_tipo,
                'Recurso': r.recurso_nombre,
                'Fecha': r.fecha.strftime('%d-%m-%Y'),
                'Jornada': r.jornada or 'N/A',
                'Hora Inicio': r.hora_inicio.strftime('%H:%M'),
                'Hora Fin': r.hora_fin.strftime('%H:%M'),
                'Estado': r.estado,
                'Observaciones': r.observaciones or ''
            })

        export_df = pd.DataFrame(data)

        if formato.lower() == 'excel':
            return exportar_df_excel(export_df, sheet_name='Reservas_Activas', prefix='reservas_activas')
        elif formato.lower() == 'csv':
            return exportar_df_csv(export_df, prefix='reservas_activas')
        else:
            flash('Formato no válido.', 'error')
            return redirect(url_for('reservas.reservas_main'))

    except Exception as e:
        flash('Error al exportar reservas.', 'danger')
        return redirect(url_for('reservas.reservas_main'))

@reservas_bp.route('/historial')
@login_required
@permiso_requerido('reservas', 'ver')
def reservas_historial():
    """Muestra el historial de reservas."""
    try:
        hoy = date.today()
        historial = Reserva.query.filter(
            or_(
                Reserva.estado != SystemConstants.ESTADO_ACTIVA,
                Reserva.fecha < hoy
            )
        ).order_by(Reserva.fecha.desc()).all()

        return render_template('reservas_historial.html', historial=historial)
        
    except Exception as e:
        flash('Error al cargar el historial.', 'danger')
        return render_template('reservas_historial.html', historial=[])

# === FUNCIONES DE UTILIDAD ===
def es_festivo(fecha_obj):
    """Verifica si una fecha es festiva."""
    return Festivo.query.get(fecha_obj) is not None

def es_fin_semana(fecha_obj):
    """Verifica si es domingo."""
    return fecha_obj.weekday() == 6

def validar_disponibilidad_recurso(recurso_nombre, fecha, hora_inicio, hora_fin, excluir_id=None):
    """Valida si un recurso está disponible en un horario."""
    query = Reserva.query.filter(
        Reserva.recurso_nombre == recurso_nombre,
        Reserva.fecha == fecha,
        Reserva.estado == SystemConstants.ESTADO_ACTIVA,
        Reserva.hora_inicio < hora_fin,
        Reserva.hora_fin > hora_inicio
    )

    if excluir_id:
        query = query.filter(Reserva.id_reserva != excluir_id)

    return query.first() is None

def calcular_jornada_desde_hora(hora_str):
    """Calcula la jornada desde una hora."""
    if not hora_str:
        return 'N/A'
    try:
        return PrestamoService.calcular_jornada_desde_hora(hora_str)
    except Exception:
        return 'N/A'
@reservas_bp.route('/recursos/<int:sede_id>')
@login_required
def obtener_recursos_por_sede(sede_id):
    """Obtiene recursos agrupados por tipo y ubicación para una sede."""
    try:
        ubicaciones = Ubicacion.query.filter_by(sede_id=sede_id).all()
        res = []
        for u in ubicaciones:
            res_u = {
                'id': u.id,
                'nombre': u.nombre,
                'recursos': []
            }
            for r in u.recursos:
                if r.activo:
                    res_u['recursos'].append({
                        'id': r.id,
                        'nombre': r.nombre,
                        'tipo': r.tipo,
                        'marca': r.marca_tipo
                    })
            res.append(res_u)
        return jsonify({'success': True, 'ubicaciones': res})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
