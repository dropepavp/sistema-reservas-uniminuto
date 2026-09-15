"""
Blueprint para rutas relacionadas con préstamos de equipos.
Versión consolidada: combina prestamos.py + prestamos_mejorado.py
"""
import re
import io
import pandas as pd
from datetime import datetime, date
from flask import Blueprint, request, jsonify, session, render_template, flash, redirect, url_for, send_file, current_app
from sqlalchemy import func
from database import db, PrestamoEquipo, Inventario, Profesor, Sede, Bodega, registrar_auditoria
from services.prestamo_service import PrestamoService
from services.notification_service import NotificationService
from config import SystemConstants
from utils.export_helpers import exportar_df_excel, exportar_df_csv
from validators import DataValidator
from auth import login_required, permiso_requerido, sede_requerida

prestamos_bp = Blueprint('prestamos', __name__, url_prefix='/prestamos')


def extraer_numero_corto(numero_inventario):
    """Extrae solo los dígitos finales del número de inventario para mostrar."""
    if not numero_inventario:
        return '--'
    if '-' in numero_inventario:
        return numero_inventario.split('-')[-1]
    match = re.search(r'(\d+)$', numero_inventario)
    if match:
        return match.group(1)
    return numero_inventario


def _contar_tipo(query_inv, filtros):
    """
    Retorna {'disponible': N, 'total': N} para un tipo de equipo.
    Soporta items individuales (por estado) y por cantidad (stock).
    """
    items = query_inv.filter(*filtros).all()
    disponible = 0
    total = 0
    for item in items:
        if item.es_por_cantidad:
            disponible += item.cantidad_disponible or 0
            total += item.cantidad_total or 0
        else:
            total += 1
            if item.estado == 'Disponible':
                disponible += 1
    return {'disponible': disponible, 'total': total}


def obtener_disponibles(query_inv):
    """
    Obtiene el conteo de equipos disponibles y totales por tipo.

    Returns:
        dict con {disponible, total} por tipo: portatiles, cargadores, hdmi, controles, teclados
    """
    try:
        _zero = {'disponible': 0, 'total': 0}
        return {
            'portatiles': _contar_tipo(query_inv, [db.or_(
                Inventario.item.ilike('%portátil%'),
                Inventario.item.ilike('%portatil%'),
                Inventario.item.ilike('%laptop%')
            )]),
            'cargadores': _contar_tipo(query_inv, [db.or_(
                Inventario.item.ilike('%cargador%'),
                Inventario.item.ilike('%adaptador%')
            )]),
            'hdmi': _contar_tipo(query_inv, [Inventario.item.ilike('%hdmi%')]),
            'controles': _contar_tipo(query_inv, [Inventario.item.ilike('%control%')]),
            'teclados': _contar_tipo(query_inv, [Inventario.item.ilike('%teclado%')]),
        }
    except Exception as e:
        current_app.logger.error("Error al contar equipos disponibles: %s", str(e))
        _zero = {'disponible': 0, 'total': 0}
        return {'portatiles': _zero, 'cargadores': _zero, 'hdmi': _zero, 'controles': _zero, 'teclados': _zero}


def agrupar_prestamos(prestamos_lista):
    """Agrupa préstamos por id_grupo_prestamo y consolida la información."""
    grupos = {}

    for prestamo in prestamos_lista:
        grupo_id = prestamo.id_grupo_prestamo or prestamo.id_prestamo

        if grupo_id not in grupos:
            grupos[grupo_id] = {
                'id_grupo': grupo_id,
                'nombre_profesor': prestamo.nombre_profesor,
                'telefono': prestamo.profesor.telefono if prestamo.profesor else '--',
                'ubicacion': prestamo.ubicacion,
                'fecha_prestamo': prestamo.fecha_prestamo,
                'hora_inicio': prestamo.hora_inicio,
                'hora_fin': prestamo.hora_fin,
                'fecha_devolucion': prestamo.fecha_devolucion,
                'hora_devolucion_real': prestamo.hora_devolucion_real,
                'auxiliar_entrega': prestamo.auxiliar_entrega,
                'auxiliar_recibe': prestamo.auxiliar_recibe,
                'observaciones': prestamo.observaciones,
                'estado': prestamo.estado,
                'equipos': {
                    'portatiles': [],
                    'cargadores': [],
                    'hdmi': [],
                    'controles': [],
                    'teclados': [],
                    'otros': []
                }
            }
        else:
            # Consolidar fecha/hora de devolución si algún registro posterior la tiene
            if prestamo.fecha_devolucion and not grupos[grupo_id]['fecha_devolucion']:
                grupos[grupo_id]['fecha_devolucion'] = prestamo.fecha_devolucion
            if prestamo.hora_devolucion_real and not grupos[grupo_id]['hora_devolucion_real']:
                grupos[grupo_id]['hora_devolucion_real'] = prestamo.hora_devolucion_real
            if prestamo.auxiliar_recibe and not grupos[grupo_id]['auxiliar_recibe']:
                grupos[grupo_id]['auxiliar_recibe'] = prestamo.auxiliar_recibe

        equipo_info = {
            'id_prestamo': prestamo.id_prestamo,  # requerido para edición individual
            'item': prestamo.equipo_prestado,
            'numero': prestamo.numero_inventario_equipo,
            'numero_corto': extraer_numero_corto(prestamo.numero_inventario_equipo)
        }

        item_lower = (prestamo.equipo_prestado or '').lower()

        if 'laptop' in item_lower or 'portátil' in item_lower or 'portatil' in item_lower:
            cat = 'portatiles'
        elif 'cargador' in item_lower or 'adaptador' in item_lower or 'fuente' in item_lower:
            cat = 'cargadores'
        elif 'teclado' in item_lower or 'keyboard' in item_lower:
            cat = 'teclados'
        elif 'hdmi' in item_lower or 'cable hdmi' in item_lower:
            cat = 'hdmi'
        elif 'control' in item_lower or 'remoto' in item_lower:
            cat = 'controles'
        else:
            cat = 'otros'

        if not any(e['numero'] == equipo_info['numero'] for e in grupos[grupo_id]['equipos'][cat]):
            grupos[grupo_id]['equipos'][cat].append(equipo_info)

    return list(grupos.values())


@prestamos_bp.route('/')
@login_required
@permiso_requerido('prestamos', 'ver')
@sede_requerida
def prestamos_equipos():
    """Página principal de préstamos de equipos con sub-pestañas."""
    try:
        query_inv = Inventario.query
        query_activos = PrestamoEquipo.query.filter_by(estado=SystemConstants.ESTADO_PRESTADO)
        query_devueltos = PrestamoEquipo.query.filter_by(estado=SystemConstants.ESTADO_DEVUELTO)
        query_todos = PrestamoEquipo.query

        rol = session.get('rol')
        sede_id_raw = session.get('sede_id') if rol not in ('admin', 'superadmin') else None

        # Normalizar sede_id a int cuando sea posible para evitar comparaciones tipo string/int
        sede_id = None
        if sede_id_raw is not None and sede_id_raw != '':
            try:
                sede_id = int(sede_id_raw)
            except (ValueError, TypeError):
                sede_id = None

        # Aplicar el filtro por sede sólo si hay una sede seleccionada en la sesión
        if sede_id is not None:
            query_inv = query_inv.join(Inventario.bodega).filter(Bodega.sede_id == sede_id)
            query_activos = query_activos.filter_by(sede_id=sede_id)
            query_devueltos = query_devueltos.filter_by(sede_id=sede_id)
            query_todos = query_todos.filter_by(sede_id=sede_id)

        # Loguear el filtro de sede usado para facilitar debugging si la tabla aparece vacía
        try:
            current_app.logger.info("Prestamos: filtro sede_id=%s", str(sede_id))
            # Conteos rápidos para ayudar a diagnóstico
            cnt_act = query_activos.with_entities(func.count(PrestamoEquipo.id_prestamo)).scalar() or 0
            current_app.logger.info("Prestamos activos (post-filter) = %s", cnt_act)
        except Exception:
            pass

        disponibles = obtener_disponibles(query_inv)

        # Préstamos del día actual
        from datetime import date, time
        hoy = date.today()
        prestamos_hoy = query_activos.filter(PrestamoEquipo.fecha_prestamo == hoy).all()
        prestamos_hoy_agrupados = agrupar_prestamos(prestamos_hoy)

        prestamos_activos_raw = query_activos.order_by(PrestamoEquipo.id_grupo_prestamo.desc()).all()
        prestamos_activos = agrupar_prestamos(prestamos_activos_raw)

        # Préstamos devueltos: ordenados por fecha y hora de devolución más recientes de primeras
        prestamos_devueltos_raw = query_devueltos.order_by(
            PrestamoEquipo.fecha_devolucion.desc().nullslast(),
            PrestamoEquipo.hora_devolucion_real.desc().nullslast(),
            PrestamoEquipo.fecha_prestamo.desc(),
            PrestamoEquipo.id_prestamo.desc()
        ).limit(300).all()
        prestamos_devueltos = agrupar_prestamos(prestamos_devueltos_raw)

        # Ordenar los grupos de devueltos de más reciente a más antiguo
        prestamos_devueltos.sort(
            key=lambda p: (
                p.get('fecha_devolucion') or p.get('fecha_prestamo') or date.min,
                p.get('hora_devolucion_real') or p.get('hora_fin') or time.min,
                p.get('id_grupo') or 0
            ),
            reverse=True
        )

        prestamos_vencidos = PrestamoService.obtener_prestamos_vencidos(sede_id=sede_id)

        # Agrupar vencidos por persona (nombre_profesor + hora_fin)
        _agrupados = {}
        for p in prestamos_vencidos:
            key = (p['nombre_profesor'], p['hora_fin'])
            if key not in _agrupados:
                _agrupados[key] = {'nombre': p['nombre_profesor'], 'hora_fin': p['hora_fin'], 'cantidad': 0}
            _agrupados[key]['cantidad'] += 1
        prestamos_vencidos_agrupados = list(_agrupados.values())

        group_key = func.coalesce(PrestamoEquipo.id_grupo_prestamo, PrestamoEquipo.id_prestamo)
        total_activos = query_activos.with_entities(func.count(func.distinct(group_key))).scalar() or 0
        total_devueltos = query_devueltos.with_entities(func.count(func.distinct(group_key))).scalar() or 0
        total_realizados = query_todos.with_entities(func.count(func.distinct(group_key))).scalar() or 0
        total_vencidos = len(prestamos_vencidos) if prestamos_vencidos else 0

        sedes = Sede.query.all()

        return render_template('prestamos_equipos_mejorado.html',
                               current_user=request.current_user if hasattr(request, 'current_user') else None,
                               prestamos_activos=prestamos_activos,
                               prestamos_hoy=prestamos_hoy_agrupados,
                               prestamos_devueltos=prestamos_devueltos,
                               prestamos_vencidos=prestamos_vencidos_agrupados,
                               disponibles=disponibles,
                               sedes=sedes,
                               total_activos=total_activos,
                               total_devueltos=total_devueltos,
                               total_realizados=total_realizados,
                               total_vencidos=total_vencidos)
    except Exception as e:
        current_app.logger.exception("Error cargando módulo de préstamos: %s", str(e))
        flash('No se pudieron cargar algunos datos de préstamos. Puedes recargar la página e intentar nuevamente.', 'warning')
        return render_template('prestamos_equipos_mejorado.html',
                               current_user=request.current_user if hasattr(request, 'current_user') else None,
                               prestamos_activos=[],
                               prestamos_devueltos=[],
                               prestamos_vencidos=[],
                               prestamos_vencidos_agrupados=[],
                               total_activos=0,
                               total_devueltos=0,
                               total_vencidos=0,
                               total_realizados=0,
                               disponibles={'portatiles': {'disponible': 0, 'total': 0}, 'cargadores': {'disponible': 0, 'total': 0}, 'hdmi': {'disponible': 0, 'total': 0}, 'controles': {'disponible': 0, 'total': 0}, 'teclados': {'disponible': 0, 'total': 0}},
                               sedes=[])


@prestamos_bp.route('/devueltos')
@login_required
@permiso_requerido('prestamos', 'ver')
@sede_requerida
def prestamos_devueltos():
    """Página de equipos devueltos con filtro por fecha."""
    try:
        fecha_filtro = request.args.get('fecha')
        query_devueltos = PrestamoEquipo.query.filter_by(estado=SystemConstants.ESTADO_DEVUELTO)
        rol = session.get('rol')
        sede_id_raw = session.get('sede_id') if rol not in ('admin', 'superadmin') else None
        sede_id = None
        if sede_id_raw is not None and sede_id_raw != '':
            try:
                sede_id = int(sede_id_raw)
            except (ValueError, TypeError):
                sede_id = None

        if sede_id is not None:
            query_devueltos = query_devueltos.filter_by(sede_id=sede_id)

        if fecha_filtro:
            try:
                fecha = datetime.strptime(fecha_filtro, '%Y-%m-%d').date()
                query_devueltos = query_devueltos.filter(PrestamoEquipo.fecha_devolucion >= fecha)
            except ValueError:
                pass

        prestamos_devueltos_raw = query_devueltos.order_by(PrestamoEquipo.fecha_devolucion.desc()).limit(200).all()
        prestamos_devueltos = agrupar_prestamos(prestamos_devueltos_raw)

        return render_template('prestamos_equipos.html',
                               prestamos_devueltos=prestamos_devueltos,
                               disponibles={'portatiles': 0, 'cargadores': 0, 'hdmi': 0, 'controles': 0},
                               sedes=Sede.query.all(),
                               solo_devueltos=True)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al cargar devoluciones: {str(e)}")
        return render_template('error.html', error=f'Error al cargar devoluciones: {str(e)}'), 500


@prestamos_bp.route('/nuevo', methods=['POST'])
@prestamos_bp.route('/crear', methods=['POST'])
@login_required
@permiso_requerido('prestamos', 'crear')
def nuevo_prestamo():
    """Crea un nuevo préstamo de equipo (soporta JSON y Form)."""
    try:
        if request.is_json:
            datos = request.json or {}
        else:
            datos = request.form.to_dict()
            if 'equipos' in request.form:
                datos['items'] = request.form.getlist('equipos')

        current_app.logger.info("📥 Datos recibidos para nuevo préstamo: %s", datos)

        is_ajax_or_json = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if not datos:
            if not is_ajax_or_json:
                flash('No se recibieron datos válidos', 'danger')
                return redirect(url_for('prestamos.prestamos_equipos'))
            return jsonify({'success': False, 'message': 'No se recibieron datos válidos'}), 400

        # Normalizar nombres de campos comunes
        if 'profesor_cedula' in datos and not datos.get('cedula'):
            datos['cedula'] = datos.get('profesor_cedula')
        if 'equipos' in datos and not datos.get('items'):
            datos['items'] = datos.get('equipos') if isinstance(datos.get('equipos'), list) else [datos.get('equipos')]

        if 'items' not in datos or not datos['items']:
            if not is_ajax_or_json:
                flash('No se especificaron equipos para prestar', 'warning')
                return redirect(url_for('prestamos.prestamos_equipos'))
            return jsonify({'success': False, 'message': 'No se especificaron equipos para prestar'}), 400
        if 'cedula' not in datos or not datos['cedula']:
            if not is_ajax_or_json:
                flash('No se especificó la cédula del profesor', 'warning')
                return redirect(url_for('prestamos.prestamos_equipos'))
            return jsonify({'success': False, 'message': 'No se especificó la cédula del profesor'}), 400

        # Asegurar que sede_id esté presente en los datos
        if not datos.get('sede_id'):
            datos['sede_id'] = session.get('sede_id')

        auxiliar_entrega = session.get('nombre_completo') or session.get('nombre') or 'Sistema'
        success, message, id_grupo = PrestamoService.crear_prestamo(datos, auxiliar_entrega)

        if success:
            registrar_auditoria(
                modulo='prestamos',
                entidad_tipo='PrestamoEquipo',
                entidad_id='*',
                accion='CREAR',
                usuario_documento=session.get('usuario', ''),
                usuario_nombre=session.get('nombre_completo', ''),
                descripcion='Registro de nuevo préstamo de equipos',
                datos_antes=None,
                datos_despues=datos
            )

        # Incluir id_grupo en la respuesta para que el frontend pueda redirigir o mostrar detalles inmediatamente
        response_payload = {'success': success, 'message': message}
        if success and id_grupo:
            response_payload['id_grupo'] = id_grupo

        if not request.is_json and not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if success:
                flash(message, 'success')
            else:
                flash(message, 'danger')
            return redirect(url_for('prestamos.prestamos_equipos'))

        return jsonify(response_payload), 200 if success else 400

    except Exception as e:
        current_app.logger.exception("Error al crear préstamo: %s", str(e))
        return jsonify({
            'success': False,
            'message': 'No se pudo registrar el préstamo en este momento. Verifica los datos e intenta nuevamente.'
        }), 500


@prestamos_bp.route('/devolver/<int:id_prestamo>', methods=['POST'])
@login_required
@permiso_requerido('prestamos', 'editar')
def devolver_prestamo(id_prestamo):
    """Marca un préstamo como devuelto."""
    try:
        auxiliar_recibe = session.get('nombre_completo') or session.get('nombre') or 'Sistema'
        datos = request.json or {}
        items_a_devolver = datos.get('items_devolver', None)
        observaciones_devolucion = datos.get('observaciones', '').strip()

        success, message, datos_devolucion = PrestamoService.devolver_prestamo(
            id_prestamo,
            auxiliar_recibe,
            items_a_devolver,
            observaciones_devolucion
        )

        if success:
            hora_dev = datos_devolucion.get('hora_devolucion')
            aux = datos_devolucion.get('auxiliar_recibe')
            registrar_auditoria(
                modulo='prestamos',
                entidad_tipo='PrestamoEquipo',
                entidad_id=id_prestamo,
                accion='DEVOLVER',
                usuario_documento=session.get('usuario', ''),
                usuario_nombre=session.get('nombre_completo', ''),
                descripcion=f"Devolución de préstamo {id_prestamo} por {aux} a las {hora_dev}",
                datos_antes=None,
                datos_despues=datos_devolucion
            )
            return jsonify({'success': True, 'message': message, **datos_devolucion})
        else:
            return jsonify({'success': False, 'message': message}), 400

    except Exception as e:
        current_app.logger.exception("Error al devolver préstamo %s: %s", id_prestamo, str(e))
        return jsonify({'success': False, 'message': 'No se pudo procesar la devolución. Intenta nuevamente.'}), 500


@prestamos_bp.route('/renovar/<int:id_grupo>', methods=['POST'])
@login_required
@permiso_requerido('prestamos', 'editar')
def renovar_prestamo(id_grupo):
    """Renueva un préstamo añadiendo tiempo a la hora_fin."""
    try:
        auxiliar = session.get('nombre_completo') or session.get('nombre') or 'Sistema'
        datos = request.json or {}
        horas_extra = int(datos.get('horas_extra', 1))

        success, message = PrestamoService.renovar_prestamo(id_grupo, horas_extra, auxiliar)

        if success:
            registrar_auditoria(
                modulo='prestamos',
                entidad_tipo='PrestamoEquipo',
                entidad_id=id_grupo,
                accion='RENOVAR',
                usuario_documento=session.get('usuario', ''),
                usuario_nombre=session.get('nombre_completo', ''),
                descripcion=f"Renovación de +{horas_extra}h en préstamo {id_grupo} por {auxiliar}",
                datos_antes=None,
                datos_despues={'horas_extra': horas_extra}
            )
            return jsonify({'success': True, 'message': message})

        return jsonify({'success': False, 'message': message}), 400

    except Exception as e:
        current_app.logger.exception("Error al renovar préstamo %s: %s", id_grupo, str(e))
        return jsonify({'success': False, 'message': 'No se pudo renovar el préstamo. Intenta nuevamente.'}), 500


@prestamos_bp.route('/detalles/<int:id_grupo>', methods=['GET'])
@login_required
@permiso_requerido('prestamos', 'ver')
def detalles_prestamo(id_grupo):
    """Obtiene los detalles completos de un préstamo por su ID de grupo."""
    try:
        prestamos_grupo = PrestamoEquipo.query.filter(
            db.or_(
                PrestamoEquipo.id_grupo_prestamo == id_grupo,
                PrestamoEquipo.id_prestamo == id_grupo
            )
        ).all()

        if not prestamos_grupo:
            return jsonify({'success': False, 'message': 'Préstamo no encontrado'}), 404

        equipos_agrupados = {'portatiles': [], 'cargadores': [], 'hdmi': [], 'controles': [], 'teclados': []}

        for prestamo in prestamos_grupo:
            item_lower = prestamo.equipo_prestado.lower() if prestamo.equipo_prestado else ''
            equipo_info = {
                'id_prestamo': prestamo.id_prestamo,
                'numero_inventario': prestamo.numero_inventario_equipo,
                'numero_corto': extraer_numero_corto(prestamo.numero_inventario_equipo),
                'equipo_prestado': prestamo.equipo_prestado,
                'hora_inicio': prestamo.hora_inicio.strftime('%H:%M') if prestamo.hora_inicio else None,
                'hora_fin': prestamo.hora_fin.strftime('%H:%M') if prestamo.hora_fin else None,
                'estado': prestamo.estado
            }

            if 'portátil' in item_lower or 'portatil' in item_lower or 'laptop' in item_lower:
                equipos_agrupados['portatiles'].append(equipo_info)
            elif 'cargador' in item_lower or 'adaptador' in item_lower or 'fuente' in item_lower:
                equipos_agrupados['cargadores'].append(equipo_info)
            elif 'hdmi' in item_lower:
                equipos_agrupados['hdmi'].append(equipo_info)
            elif 'control' in item_lower or 'remoto' in item_lower:
                equipos_agrupados['controles'].append(equipo_info)
            elif 'teclado' in item_lower or 'keyboard' in item_lower:
                equipos_agrupados['teclados'].append(equipo_info)

        primer_prestamo = prestamos_grupo[0]
        detalles = {
            'id_grupo': id_grupo,
            'cedula_profesor': primer_prestamo.cedula_profesor,
            'nombre_profesor': primer_prestamo.nombre_profesor,
            'telefono': primer_prestamo.telefono,
            'fecha_prestamo': primer_prestamo.fecha_prestamo.strftime('%Y-%m-%d') if primer_prestamo.fecha_prestamo else None,
            'hora_inicio': primer_prestamo.hora_inicio.strftime('%H:%M') if primer_prestamo.hora_inicio else None,
            'hora_fin': primer_prestamo.hora_fin.strftime('%H:%M') if primer_prestamo.hora_fin else None,
            'ubicacion': primer_prestamo.ubicacion,
            'estado': primer_prestamo.estado,
            'observaciones': primer_prestamo.observaciones,
            'equipos': equipos_agrupados,
            'total_equipos': len(prestamos_grupo)
        }

        return jsonify({'success': True, 'prestamo': detalles})

    except Exception as e:
        current_app.logger.error("Error al obtener detalles del préstamo %s: %s", id_grupo, str(e))
        return jsonify({'success': False, 'message': 'No se pudieron cargar los detalles del préstamo.'}), 500


@prestamos_bp.route('/editar/<int:id_prestamo>', methods=['GET', 'PUT'])
@login_required
@permiso_requerido('prestamos', 'editar')
def editar_prestamo(id_prestamo):
    """Obtiene o actualiza los datos de un préstamo."""
    prestamo_grupo = PrestamoEquipo.query.filter(
        db.or_(
            PrestamoEquipo.id_grupo_prestamo == id_prestamo,
            PrestamoEquipo.id_prestamo == id_prestamo
        )
    ).all()

    if not prestamo_grupo:
        return jsonify({'success': False, 'message': 'Préstamo no encontrado'}), 404

    prestamo = prestamo_grupo[0]

    if request.method == 'GET':
        equipos_agrupados = {
            'portatiles': [], 'cargadores': [], 'hdmi': [],
            'controles': [], 'teclados': [], 'cables': []
        }

        for p in prestamo_grupo:
            equipo_data = {
                'id_prestamo': p.id_prestamo,
                'numero_inventario': p.numero_inventario_equipo,
                'equipo': p.equipo_prestado,
                'item': p.equipo_prestado
            }
            item_lower = (p.equipo_prestado or '').lower()
            if 'laptop' in item_lower or 'portátil' in item_lower or 'portatil' in item_lower:
                equipos_agrupados['portatiles'].append(equipo_data)
            elif 'cargador' in item_lower or 'adaptador' in item_lower or 'fuente' in item_lower:
                equipos_agrupados['cargadores'].append(equipo_data)
            elif 'hdmi' in item_lower:
                equipos_agrupados['hdmi'].append(equipo_data)
            elif 'control' in item_lower:
                equipos_agrupados['controles'].append(equipo_data)
            elif 'teclado' in item_lower:
                equipos_agrupados['teclados'].append(equipo_data)
            elif 'cable' in item_lower:
                equipos_agrupados['cables'].append(equipo_data)

        prestamo_data = {
            'id_prestamo': prestamo.id_prestamo,
            'id_grupo': prestamo.id_grupo_prestamo or prestamo.id_prestamo,
            'nombre_profesor': prestamo.nombre_profesor,
            'ubicacion': prestamo.ubicacion,
            'hora_inicio': prestamo.hora_inicio.strftime('%H:%M'),
            'hora_fin': prestamo.hora_fin.strftime('%H:%M'),
            'observaciones': prestamo.observaciones,
            'fecha_prestamo': prestamo.fecha_prestamo.strftime('%Y-%m-%d'),
            'equipos': equipos_agrupados
        }
        return jsonify({'success': True, 'prestamo': prestamo_data})

    elif request.method == 'PUT':
        try:
            current_app.logger.info("✏️ PUT /prestamos/editar/%s - headers: %s", id_prestamo, dict(request.headers))
            if prestamo.estado != SystemConstants.ESTADO_PRESTADO:
                return jsonify({
                    'success': False,
                    'message': 'Solo se pueden editar préstamos activos (que no hayan sido devueltos)'
                }), 400

            datos = request.json
            current_app.logger.info("✏️ PUT datos recibidos: %s", datos)

            datos_antes = {
                'ubicacion': prestamo.ubicacion,
                'hora_inicio': prestamo.hora_inicio.strftime('%H:%M'),
                'hora_fin': prestamo.hora_fin.strftime('%H:%M'),
                'observaciones': prestamo.observaciones or '',
            }

            # Validar con DataValidator
            ubicacion_raw = datos.get('ubicacion', '') or ''
            observaciones_raw = datos.get('observaciones', '') or ''

            if len(ubicacion_raw.strip()) > 100:
                return jsonify({'success': False, 'message': 'Ubicación no puede tener más de 100 caracteres'}), 400
            if len(observaciones_raw.strip()) > 500:
                return jsonify({'success': False, 'message': 'Observaciones no puede tener más de 500 caracteres'}), 400

            hora_inicio_valid, hora_inicio_obj, hora_inicio_error = DataValidator.validate_time(
                datos.get('hora_inicio')
            )
            if not hora_inicio_valid:
                return jsonify({'success': False, 'message': hora_inicio_error}), 400

            hora_fin_valid, hora_fin_obj, hora_fin_error = DataValidator.validate_time(
                datos.get('hora_fin')
            )
            if not hora_fin_valid:
                return jsonify({'success': False, 'message': hora_fin_error}), 400

            range_valid, range_error = DataValidator.validate_time_range(hora_inicio_obj, hora_fin_obj)
            if not range_valid:
                return jsonify({'success': False, 'message': range_error}), 400

            ubicacion = ubicacion_raw.strip()
            observaciones = observaciones_raw.strip()

            # Actualizar todos los registros del grupo
            for p_reg in prestamo_grupo:
                p_reg.ubicacion = ubicacion
                p_reg.hora_inicio = hora_inicio_obj
                p_reg.hora_fin = hora_fin_obj
                p_reg.observaciones = observaciones
                p_reg.horas_academicas = PrestamoService.calcular_horas_academicas(
                    hora_inicio_obj.strftime('%H:%M'),
                    hora_fin_obj.strftime('%H:%M')
                )

            # Actualizar items individuales si se proporcionan
            items_edit = datos.get('items', [])
            current_app.logger.info("✏️ items_edit recibidos: %s", items_edit)
            for item_data in items_edit:
                p_id = item_data.get('id_prestamo')
                nuevo_num = item_data.get('numero_inventario', '').strip()
                current_app.logger.info("  → p_id=%s (type=%s) nuevo_num=%s", p_id, type(p_id).__name__, nuevo_num)
                if not p_id or not nuevo_num:
                    continue
                try:
                    p_id = int(p_id)
                except (ValueError, TypeError):
                    current_app.logger.warning("  → p_id inválido, saltando")
                    continue
                p_target = next((p for p in prestamo_grupo if p.id_prestamo == p_id), None)
                current_app.logger.info("  → p_target encontrado: %s", p_target is not None)
                if not p_target:
                    continue
                num_viejo = p_target.numero_inventario_equipo
                if num_viejo == nuevo_num:
                    continue  # Sin cambio

                # Verificar que el nuevo equipo existe y está disponible
                nuevo_item = Inventario.query.filter_by(numero_inventario=nuevo_num).first()
                if not nuevo_item:
                    return jsonify({'success': False, 'message': f'Equipo "{nuevo_num}" no encontrado en inventario'}), 400
                if nuevo_item.estado not in ('Disponible', 'En Préstamo') and nuevo_item.numero_inventario != num_viejo:
                    return jsonify({'success': False, 'message': f'El equipo "{nuevo_num}" no está disponible (estado: {nuevo_item.estado})'}), 400

                # Liberar equipo viejo
                if num_viejo:
                    item_viejo = Inventario.query.filter_by(numero_inventario=num_viejo).first()
                    if item_viejo and item_viejo.estado == 'En Préstamo':
                        # Solo liberar si no hay otros préstamos activos con ese equipo
                        otros = PrestamoEquipo.query.filter(
                            PrestamoEquipo.numero_inventario_equipo == num_viejo,
                            PrestamoEquipo.estado == SystemConstants.ESTADO_PRESTADO,
                            PrestamoEquipo.id_prestamo != p_id
                        ).count()
                        if otros == 0:
                            item_viejo.estado = 'Disponible'

                # Marcar nuevo equipo como prestado
                nuevo_item.estado = 'En Préstamo'
                p_target.numero_inventario_equipo = nuevo_num

            datos_despues = {
                'ubicacion': ubicacion,
                'hora_inicio': hora_inicio_obj.strftime('%H:%M'),
                'hora_fin': hora_fin_obj.strftime('%H:%M'),
                'observaciones': observaciones,
                'items_actualizados': len(items_edit)
            }

            db.session.commit()

            registrar_auditoria(
                modulo='prestamos',
                entidad_tipo='PrestamoEquipo',
                entidad_id=prestamo.id_grupo_prestamo or prestamo.id_prestamo,
                accion='EDITAR',
                usuario_documento=session.get('usuario', ''),
                usuario_nombre=session.get('nombre_completo', ''),
                descripcion=f"Edición de préstamo {prestamo.id_grupo_prestamo or prestamo.id_prestamo}",
                datos_antes=datos_antes,
                datos_despues=datos_despues
            )

            return jsonify({'success': True, 'message': 'Préstamo y equipos actualizados correctamente'})

        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Error al editar préstamo %s: %s", id_prestamo, str(e))
            return jsonify({
                'success': False,
                'message': 'No se pudieron guardar los cambios del préstamo. Revisa los datos e inténtalo nuevamente.'
            }), 500


@prestamos_bp.route('/buscar')
@login_required
@permiso_requerido('prestamos', 'ver')
def buscar_prestamos_api():
    """API para búsqueda de préstamos."""
    try:
        query_text = request.args.get('q', '').strip()
        if not query_text:
            return jsonify({'success': True, 'results': []})

        search_term = f"%{query_text}%"
        prestamos = PrestamoEquipo.query.filter(
            db.or_(
                PrestamoEquipo.nombre_profesor.ilike(search_term),
                PrestamoEquipo.equipo_prestado.ilike(search_term),
                PrestamoEquipo.numero_inventario_equipo.ilike(search_term),
                PrestamoEquipo.cedula_profesor.like(search_term)
            )
        ).limit(50).all()

        results = [{
            'id_prestamo': p.id_prestamo,
            'nombre_profesor': p.nombre_profesor,
            'equipo_prestado': p.equipo_prestado,
            'numero_inventario_equipo': p.numero_inventario_equipo,
            'fecha_prestamo': p.fecha_prestamo.strftime('%Y-%m-%d'),
            'estado': p.estado
        } for p in prestamos]

        return jsonify({'success': True, 'results': results})

    except Exception as e:
        current_app.logger.error("Error en búsqueda de préstamos: %s", str(e))
        return jsonify({'success': False, 'message': 'Error al buscar préstamos'}), 500


@prestamos_bp.route('/exportar/<formato>')
@login_required
@permiso_requerido('prestamos', 'ver')
def exportar_prestamos_activos(formato):
    """Exporta los préstamos activos en el formato especificado."""
    try:
        prestamos_activos = PrestamoEquipo.query.filter_by(
            estado=SystemConstants.ESTADO_PRESTADO
        ).all()

        if not prestamos_activos:
            flash('No hay préstamos activos para exportar.', 'info')
            return redirect(url_for('prestamos.prestamos_equipos'))

        data = [{
            'ID': p.id_prestamo,
            'Cédula Profesor': p.cedula_profesor,
            'Profesor': p.nombre_profesor,
            'N° Inventario': p.numero_inventario_equipo,
            'Equipo': p.equipo_prestado,
            'Fecha': p.fecha_prestamo.strftime('%d-%m-%Y') if p.fecha_prestamo else '',
            'Hora Inicio': p.hora_inicio.strftime('%H:%M') if p.hora_inicio else '',
            'Hora Fin': p.hora_fin.strftime('%H:%M') if p.hora_fin else '',
            'Ubicación': p.ubicacion or '',
            'Observaciones': p.observaciones or ''
        } for p in prestamos_activos]

        export_df = pd.DataFrame(data)

        if formato.lower() == 'excel':
            return exportar_df_excel(export_df, sheet_name='Prestamos_Activos', prefix='prestamos_activos')
        elif formato.lower() == 'csv':
            return exportar_df_csv(export_df, prefix='prestamos_activos')
        else:
            flash('Formato no válido. Usa Excel o CSV.', 'error')
            return redirect(url_for('prestamos.prestamos_equipos'))

    except Exception as e:
        current_app.logger.exception("Error al exportar préstamos: %s", str(e))
        flash('No se pudieron descargar los préstamos. Intenta nuevamente.', 'danger')
        return redirect(url_for('prestamos.prestamos_equipos'))


@prestamos_bp.route('/historial')
@login_required
@permiso_requerido('prestamos', 'ver')
def prestamos_historial():
    """Muestra el historial de préstamos."""
    try:
        historial_list = PrestamoEquipo.query.filter(
            PrestamoEquipo.estado != SystemConstants.ESTADO_PRESTADO
        ).order_by(PrestamoEquipo.fecha_prestamo.desc()).all()

        for prestamo in historial_list:
            if not prestamo.jornada:
                prestamo.jornada = PrestamoService.calcular_jornada_desde_hora(
                    prestamo.hora_inicio.strftime('%H:%M')
                )
            if not prestamo.horas_academicas:
                prestamo.horas_academicas = PrestamoService.calcular_horas_academicas(
                    prestamo.hora_inicio.strftime('%H:%M'),
                    prestamo.hora_fin.strftime('%H:%M')
                )

        return render_template('prestamos_historial.html', historial=historial_list)

    except Exception as e:
        current_app.logger.exception("Error al cargar historial de préstamos: %s", str(e))
        flash('No se pudo cargar el historial de préstamos. Intenta nuevamente.', 'danger')
        return render_template('prestamos_historial.html', historial=[])


@prestamos_bp.route('/historial/exportar')
@login_required
@permiso_requerido('prestamos', 'ver')
def exportar_historial_prestamos():
    """Exporta el historial de préstamos con filtros de fecha opcionales."""
    try:
        fecha_desde_str = request.args.get('fecha_desde')
        fecha_hasta_str = request.args.get('fecha_hasta')

        query = PrestamoEquipo.query.filter(
            PrestamoEquipo.estado != SystemConstants.ESTADO_PRESTADO
        )

        if fecha_desde_str:
            fecha_desde_valid, fecha_desde, _ = DataValidator.validate_date(fecha_desde_str)
            if fecha_desde_valid:
                query = query.filter(PrestamoEquipo.fecha_prestamo >= fecha_desde)

        if fecha_hasta_str:
            fecha_hasta_valid, fecha_hasta, _ = DataValidator.validate_date(fecha_hasta_str)
            if fecha_hasta_valid:
                query = query.filter(PrestamoEquipo.fecha_prestamo <= fecha_hasta)

        historial = query.all()

        if not historial:
            flash('No hay datos en el historial para exportar.', 'info')
            return redirect(url_for('prestamos.prestamos_historial'))

        data = []
        for p in historial:
            duracion = 0
            if p.fecha_devolucion and p.hora_devolucion_real:
                try:
                    inicio_dt = datetime.combine(p.fecha_prestamo, p.hora_inicio)
                    fin_dt = datetime.combine(p.fecha_devolucion, p.hora_devolucion_real)
                    duracion = round((fin_dt - inicio_dt).total_seconds() / 3600, 2)
                except Exception:
                    duracion = 0

            data.append({
                'ID Préstamo': p.id_prestamo,
                'Profesor': p.nombre_profesor,
                'Cédula Profesor': p.cedula_profesor,
                'Equipo': p.equipo_prestado,
                'Nº Inventario': p.numero_inventario_equipo,
                'Ubicación': p.ubicacion or '',
                'Jornada': p.jornada or 'N/A',
                'Horas Académicas': p.horas_academicas or 0,
                'Fecha Préstamo': p.fecha_prestamo.strftime('%d-%m-%Y'),
                'Hora Inicio': p.hora_inicio.strftime('%H:%M'),
                'Hora Fin Prevista': p.hora_fin.strftime('%H:%M'),
                'Fecha Devolución': p.fecha_devolucion.strftime('%d-%m-%Y') if p.fecha_devolucion else '',
                'Hora Devolución': p.hora_devolucion_real.strftime('%H:%M') if p.hora_devolucion_real else '',
                'Duración (Horas)': duracion,
                'Auxiliar Entrega': p.auxiliar_entrega or '',
                'Auxiliar Recibe': p.auxiliar_recibe or '',
                'Estado': p.estado,
                'Observaciones': p.observaciones or ''
            })

        export_df = pd.DataFrame(data)
        return exportar_df_excel(export_df, sheet_name='Historial_Prestamos', prefix='historial_prestamos')

    except Exception as e:
        current_app.logger.exception("Error al exportar historial: %s", str(e))
        flash('No se pudo descargar el historial. Intenta nuevamente.', 'danger')
        return redirect(url_for('prestamos.prestamos_historial'))


@prestamos_bp.route('/buscar-equipos', methods=['GET'])
@login_required
@permiso_requerido('prestamos', 'ver')
def buscar_equipos():
    """Busca equipos disponibles desde inventario según filtros."""
    try:
        tipo_equipo = request.args.get('tipo_equipo', '')
        marca = request.args.get('marca', '')
        salon = request.args.get('salon', '')
        numero_inventario = request.args.get('numero_inventario', '')

        current_app.logger.info("🔍 BUSCAR_EQUIPOS - tipo=%s marca=%s salon=%s num=%s",
                                tipo_equipo, marca, salon, numero_inventario)

        query = Inventario.query.filter(
            Inventario.estado.in_(['Disponible', 'En Préstamo'])
        )

        sede_id = session.get('sede_id') if session.get('rol') not in ('admin', 'superadmin') else None
        if sede_id:
            query = query.join(Inventario.bodega).filter(Bodega.sede_id == sede_id)

        if tipo_equipo:
            if tipo_equipo == 'PORTATIL':
                query = query.filter(db.or_(
                    Inventario.item.ilike('%portátil%'),
                    Inventario.item.ilike('%portatil%'),
                    Inventario.item.ilike('%laptop%')
                ))
            elif tipo_equipo == 'CARGADOR':
                query = query.filter(db.or_(
                    Inventario.item.ilike('%cargador%'),
                    Inventario.item.ilike('%adaptador%'),
                    Inventario.item.ilike('%fuente%')
                )).filter(
                    ~Inventario.item.ilike('%teclado%'),
                    ~Inventario.item.ilike('%keyboard%')
                )
            elif tipo_equipo == 'HDMI':
                query = query.filter(Inventario.item.ilike('%hdmi%'))
            elif tipo_equipo == 'CONTROL':
                query = query.filter(Inventario.item.ilike('%control%'))
            elif tipo_equipo == 'TECLADO':
                query = query.filter(Inventario.item.ilike('%teclado%'))

        if marca:
            query = query.filter(db.or_(
                Inventario.marca_modelo.ilike(f'%{marca}%'),
                Inventario.item.ilike(f'%{marca}%')
            ))

        if salon:
            query = query.filter(Inventario.item.ilike(f'%{salon}%'))

        if numero_inventario:
            query = query.filter(db.or_(
                Inventario.numero_inventario.ilike(f'%{numero_inventario}%'),
                Inventario.activo_fijo.ilike(f'%{numero_inventario}%')
            ))

        if numero_inventario:
            equipos = query.order_by(
                db.case(
                    (Inventario.numero_inventario == numero_inventario, 1),
                    (Inventario.activo_fijo == numero_inventario, 1),
                    else_=2
                ),
                db.func.length(Inventario.numero_inventario),
                Inventario.numero_inventario
            ).limit(50).all()
        else:
            equipos = query.limit(50).all()

        resultados = []
        for equipo in equipos:
            prestamo_activo = db.session.query(PrestamoEquipo).filter(
                PrestamoEquipo.numero_inventario_equipo == equipo.numero_inventario,
                PrestamoEquipo.estado == 'Prestado'
            ).first()

            if prestamo_activo:
                estado_equipo = 'prestado'
                mensaje_prestamo = f"Prestado a {prestamo_activo.nombre_profesor}"
            else:
                estado_equipo = 'disponible'
                mensaje_prestamo = None

            resultados.append({
                'id': equipo.id,
                'numero_inventario': equipo.numero_inventario,
                'numero_corto': extraer_numero_corto(equipo.numero_inventario),
                'activo_fijo': equipo.activo_fijo or '',
                'item': equipo.item,
                'marca': equipo.marca_modelo or '',
                'serial': equipo.serial or '',
                'bodega': equipo.bodega.nombre if equipo.bodega else '',
                'sede': equipo.bodega.sede.nombre if equipo.bodega and equipo.bodega.sede else '',
                'estado_equipo': estado_equipo,
                'mensaje_prestamo': mensaje_prestamo,
                'disponible': estado_equipo == 'disponible'
            })

        return jsonify({'success': True, 'equipos': resultados, 'total': len(resultados)})

    except Exception as e:
        current_app.logger.exception("Error al buscar equipos: %s", str(e))
        return jsonify({'success': False, 'message': 'Error al buscar equipos', 'equipos': [], 'total': 0}), 500


@prestamos_bp.route('/api/docente-estado/<cedula>', methods=['GET'])
@login_required
@permiso_requerido('prestamos', 'ver')
def api_docente_estado(cedula):
    """Verifica préstamos activos, pendientes y estado de mora de un docente."""
    try:
        resultado = PrestamoService.verificar_estado_docente(cedula)
        return jsonify(resultado)
    except Exception as e:
        current_app.logger.exception("Error verificando estado docente: %s", str(e))
        return jsonify({'success': False, 'error': str(e), 'tiene_activos': False, 'tiene_mora': False}), 500


@prestamos_bp.route('/api/escanear-equipo', methods=['GET'])
@login_required
@permiso_requerido('prestamos', 'ver')
def api_escanear_equipo():
    """Búsqueda directa y unificada por código de barras, activo fijo o número de inventario."""
    try:
        codigo = (request.args.get('codigo') or '').strip()
        if not codigo:
            return jsonify({'success': False, 'message': 'Código no proporcionado'}), 400

        sede_id = session.get('sede_id') if session.get('rol') not in ('admin', 'superadmin') else None

        query = Inventario.query
        if sede_id:
            query = query.join(Inventario.bodega).filter(Bodega.sede_id == sede_id)

        equipo = query.filter(
            db.or_(
                Inventario.activo_fijo == codigo,
                Inventario.numero_inventario == codigo,
                Inventario.serial == codigo,
                Inventario.activo_fijo.ilike(f'%{codigo}%'),
                Inventario.numero_inventario.ilike(f'%{codigo}%')
            )
        ).first()

        if not equipo:
            return jsonify({'success': False, 'message': f'Equipo no encontrado con código: {codigo}'}), 404

        # Verificar si está prestado
        prestamo_activo = PrestamoEquipo.query.filter_by(
            numero_inventario_equipo=equipo.numero_inventario,
            estado='Prestado'
        ).first()

        identificador = (equipo.activo_fijo and equipo.activo_fijo.strip()) or equipo.numero_inventario
        numero_corto = extraer_numero_corto(equipo.numero_inventario)

        # Determinar tipo
        item_lower = (equipo.item or '').lower()
        if 'laptop' in item_lower or 'portátil' in item_lower or 'portatil' in item_lower:
            tipo = 'portatil'
        elif 'cargador' in item_lower or 'adaptador' in item_lower or 'fuente' in item_lower:
            tipo = 'cargador'
        elif 'teclado' in item_lower or 'keyboard' in item_lower:
            tipo = 'teclado'
        elif 'hdmi' in item_lower:
            tipo = 'hdmi'
        elif 'control' in item_lower:
            tipo = 'control'
        else:
            tipo = 'otro'

        return jsonify({
            'success': True,
            'equipo': {
                'id': equipo.id,
                'identificador': identificador,
                'numero_inventario': equipo.numero_inventario,
                'numero_corto': numero_corto,
                'activo_fijo': equipo.activo_fijo or '',
                'item': equipo.item,
                'marca': equipo.marca_modelo or '',
                'serial': equipo.serial or '',
                'tipo': tipo,
                'bodega': equipo.bodega.nombre if equipo.bodega else '',
                'disponible': prestamo_activo is None,
                'prestado_a': prestamo_activo.nombre_profesor if prestamo_activo else None,
                'prestamo_id_grupo': (prestamo_activo.id_grupo_prestamo or prestamo_activo.id_prestamo) if prestamo_activo else None
            }
        })
    except Exception as e:
        current_app.logger.exception("Error al escanear equipo: %s", str(e))
        return jsonify({'success': False, 'message': 'Error al escanear equipo'}), 500

