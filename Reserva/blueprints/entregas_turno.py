"""
Blueprint para el Sistema de Entregas de Turno y Mensajería Interna UNIMINUTO.
Permite el traspaso formal de novedades operativas entre las jornadas de trabajo
(Jornada de la Mañana y Jornada de la Tarde/Noche) mediante una interfaz tipo correo interno:
- Bandeja de Entrada (Entregas recibidas para mi sede / usuario)
- Enviados (Entregas emitidas por el operador saliente)
- Redactar Entrega de Turno (con checklist de actividades, equipos pendientes, novedades de salas y tareas)
- Autocarga inteligente de préstamos activos y novedades del día
- Acuse de Recibo con conformidad y observaciones
- Hilo de correspondencia y seguimiento de novedades
- Acta oficial imprimible
"""
import os
import uuid
from datetime import datetime, date, time
from flask import (
    Blueprint, render_template, request, redirect, flash,
    url_for, session, jsonify, current_app, send_file
)
from sqlalchemy import or_, and_, func, desc, asc
from werkzeug.utils import secure_filename

from extensions import db
from database import (
    EntregaTurno, ComentarioEntregaTurno, Auxiliar, Sede,
    PrestamoEquipo, NovedadTecnicaSala, Recurso, Ubicacion, registrar_auditoria
)
from auth import login_required, permiso_requerido

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

entregas_turno_bp = Blueprint('entregas_turno', __name__, url_prefix='/entregas-turno')

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


def _allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def _procesar_evidencia(file_storage) -> str | None:
    """Guarda y comprime la foto o soporte de la entrega de turno."""
    if not file_storage or not file_storage.filename or not _allowed_file(file_storage.filename):
        return None
    try:
        base_dir = current_app.static_folder
        carpeta = os.path.join(base_dir, 'uploads', 'turnos')
        os.makedirs(carpeta, exist_ok=True)

        nombre = f"turno_{uuid.uuid4().hex[:10]}_{int(datetime.now().timestamp())}.jpg"
        ruta = os.path.join(carpeta, nombre)

        if HAS_PIL and Image is not None:
            try:
                img = Image.open(file_storage.stream)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                img.save(ruta, format='JPEG', quality=85, optimize=True)
            except Exception:
                file_storage.seek(0)
                file_storage.save(ruta)
        else:
            file_storage.save(ruta)

        return f"/static/uploads/turnos/{nombre}"
    except Exception as e:
        current_app.logger.warning(f"Error al guardar evidencia de entrega de turno: {e}")
        return None


def _generar_consecutivo(fecha_turno: date) -> str:
    """Genera un consecutivo único secuencial ej: ET-20261021-001."""
    prefijo = f"ET-{fecha_turno.strftime('%Y%m%d')}"
    conteo = EntregaTurno.query.filter(EntregaTurno.consecutivo.like(f"{prefijo}-%")).count()
    return f"{prefijo}-{conteo + 1:03d}"


def _determinar_jornada_sugerida() -> str:
    """Determina si por la hora actual se sugiere entregar turno de Mañana o de Tarde."""
    hora_actual = datetime.now().time()
    # Mañana: 06:00 a 13:59 -> entrega Mañana; 14:00 en adelante -> entrega Tarde
    if time(6, 0) <= hora_actual < time(14, 0):
        return 'Mañana'
    return 'Tarde'


# ─────────────────────────────────────────────────────────────────────────────
# 1. BANDEJA PRINCIPAL (BUZÓN DE ENTREGAS DE TURNO)
# ─────────────────────────────────────────────────────────────────────────────

@entregas_turno_bp.route('/', methods=['GET'])
@login_required
def dashboard_entregas():
    """Bandeja principal estilo correo interno: Entrada, Enviados, Historial y Filtros."""
    try:
        usuario_doc = str(session.get('usuario', '')).strip()
        usuario_rol = session.get('rol', 'auxiliar')
        sede_id_session = session.get('sede_id')

        # Parámetros de pestaña y filtros
        tab = request.args.get('tab', 'recibidos').strip().lower()
        if tab not in ('recibidos', 'enviados', 'todas', 'manana', 'tarde', 'pendientes'):
            tab = 'recibidos'

        sede_filtro = request.args.get('sede', '').strip()
        jornada_filtro = request.args.get('jornada', '').strip()
        prioridad_filtro = request.args.get('prioridad', '').strip()
        estado_filtro = request.args.get('estado', '').strip()
        fecha_filtro = request.args.get('fecha', '').strip()
        busqueda = request.args.get('busqueda', '').strip()

        query = EntregaTurno.query

        # Filtrado según pestaña (Carpeta de Correo)
        if tab == 'recibidos':
            # Entregas dirigidas a la sede del usuario o donde es el receptor específico
            condiciones = []
            if sede_id_session and usuario_rol not in ('admin', 'superadmin'):
                condiciones.append(and_(EntregaTurno.sede_id == int(sede_id_session), EntregaTurno.para_toda_sede == True))
            else:
                condiciones.append(EntregaTurno.para_toda_sede == True)

            if usuario_doc:
                condiciones.append(EntregaTurno.usuario_receptor_doc == usuario_doc)

            query = query.filter(or_(*condiciones))
        elif tab == 'enviados':
            query = query.filter(EntregaTurno.usuario_emisor_doc == usuario_doc)
        elif tab == 'manana':
            query = query.filter(EntregaTurno.jornada == 'Mañana')
        elif tab == 'tarde':
            query = query.filter(EntregaTurno.jornada == 'Tarde')
        elif tab == 'pendientes':
            query = query.filter(EntregaTurno.estado == 'Pendiente')

        # Filtros adicionales
        if sede_filtro and sede_filtro.isdigit():
            query = query.filter(EntregaTurno.sede_id == int(sede_filtro))
        elif sede_id_session and usuario_rol not in ('admin', 'superadmin') and tab != 'recibidos':
            query = query.filter(EntregaTurno.sede_id == int(sede_id_session))

        if jornada_filtro in ('Mañana', 'Tarde'):
            query = query.filter(EntregaTurno.jornada == jornada_filtro)

        if prioridad_filtro in ('Normal', 'Importante', 'Urgente'):
            query = query.filter(EntregaTurno.prioridad == prioridad_filtro)

        if estado_filtro in ('Pendiente', 'Recibido Conforme', 'Con Observaciones'):
            query = query.filter(EntregaTurno.estado == estado_filtro)

        if fecha_filtro:
            try:
                f_obj = datetime.strptime(fecha_filtro, '%Y-%m-%d').date()
                query = query.filter(EntregaTurno.fecha == f_obj)
            except ValueError:
                pass

        if busqueda:
            term = f"%{busqueda}%"
            query = query.filter(
                or_(
                    EntregaTurno.consecutivo.ilike(term),
                    EntregaTurno.asunto.ilike(term),
                    EntregaTurno.actividades_realizadas.ilike(term),
                    EntregaTurno.equipos_pendientes.ilike(term),
                    EntregaTurno.pendientes_siguiente_turno.ilike(term)
                )
            )

        entregas = query.order_by(EntregaTurno.fecha.desc(), EntregaTurno.hora.desc()).limit(150).all()

        # KPIs del buzón
        hoy = date.today()
        primer_dia_mes = hoy.replace(day=1)

        total_mes = EntregaTurno.query.filter(EntregaTurno.fecha >= primer_dia_mes).count()
        manana_count = EntregaTurno.query.filter(EntregaTurno.fecha >= primer_dia_mes, EntregaTurno.jornada == 'Mañana').count()
        tarde_count = EntregaTurno.query.filter(EntregaTurno.fecha >= primer_dia_mes, EntregaTurno.jornada == 'Tarde').count()
        pendientes_count = EntregaTurno.query.filter(EntregaTurno.estado == 'Pendiente').count()

        # No leídos dirigidos al usuario actual
        no_leidos_count = EntregaTurno.query.filter(
            EntregaTurno.leido == False,
            or_(
                EntregaTurno.usuario_receptor_doc == usuario_doc,
                and_(EntregaTurno.para_toda_sede == True, EntregaTurno.usuario_emisor_doc != usuario_doc)
            )
        ).count()

        sedes = Sede.query.order_by(Sede.nombre.asc()).all()
        auxiliares = Auxiliar.query.filter_by(activo=True).order_by(Auxiliar.nombre_completo.asc()).all()

        return render_template(
            'entregas_turno/buzon.html',
            entregas=entregas,
            tab=tab,
            stats={
                'total_mes': total_mes,
                'manana_count': manana_count,
                'tarde_count': tarde_count,
                'pendientes_count': pendientes_count,
                'no_leidos_count': no_leidos_count
            },
            sedes=sedes,
            auxiliares=auxiliares,
            jornada_sugerida=_determinar_jornada_sugerida(),
            filtros={
                'sede': sede_filtro,
                'jornada': jornada_filtro,
                'prioridad': prioridad_filtro,
                'estado': estado_filtro,
                'fecha': fecha_filtro,
                'busqueda': busqueda
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error en dashboard de entregas de turno: {e}", exc_info=True)
        flash('Ocurrió un error al cargar el buzón de entregas de turno.', 'danger')
        return render_template(
            'entregas_turno/buzon.html',
            entregas=[],
            tab='recibidos',
            stats={'total_mes': 0, 'manana_count': 0, 'tarde_count': 0, 'pendientes_count': 0, 'no_leidos_count': 0},
            sedes=[],
            auxiliares=[],
            jornada_sugerida='Mañana',
            filtros={}
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. REDACTAR NUEVA ENTREGA DE TURNO
# ─────────────────────────────────────────────────────────────────────────────

@entregas_turno_bp.route('/redactar', methods=['GET', 'POST'])
@login_required
def redactar_entrega():
    """Formulario para redactar y enviar una entrega formal de turno."""
    if request.method == 'POST':
        is_json = request.is_json
        data = request.get_json() if is_json else request.form

        try:
            usuario_doc = str(session.get('usuario', '')).strip()
            if not usuario_doc:
                raise ValueError("No se detectó un usuario autenticado para emitir la entrega.")

            jornada = data.get('jornada', '').strip()
            if jornada not in ('Mañana', 'Tarde'):
                jornada = _determinar_jornada_sugerida()

            fecha_str = data.get('fecha', '').strip()
            if fecha_str:
                fecha_turno = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            else:
                fecha_turno = date.today()

            hora_str = data.get('hora', '').strip()
            if hora_str:
                hora_turno = datetime.strptime(hora_str, '%H:%M').time()
            else:
                hora_turno = datetime.now().time()

            sede_id_val = data.get('sede_id')
            if not sede_id_val or not str(sede_id_val).isdigit():
                # Si no viene, tomar sede de la sesión
                sede_id_val = session.get('sede_id')
                if not sede_id_val:
                    primera_sede = Sede.query.first()
                    sede_id_val = primera_sede.id if primera_sede else None

            if not sede_id_val:
                raise ValueError("Debe especificar una sede para la entrega de turno.")

            sede_obj = Sede.query.get(int(sede_id_val))
            if not sede_obj:
                raise ValueError("La sede especificada no existe.")

            usuario_receptor = data.get('usuario_receptor_doc', '').strip() or None
            para_toda_sede = (data.get('para_toda_sede') in ('true', '1', 'on', True)) or (usuario_receptor is None)

            asunto = data.get('asunto', '').strip()
            if not asunto:
                asunto = f"Entrega Turno {jornada} — {sede_obj.nombre} ({fecha_turno.strftime('%d/%m/%Y')})"

            prioridad = data.get('prioridad', 'Normal').strip()
            if prioridad not in ('Normal', 'Importante', 'Urgente'):
                prioridad = 'Normal'

            actividades = data.get('actividades_realizadas', '').strip()
            if not actividades:
                raise ValueError("Debe ingresar el detalle de actividades realizadas en el turno.")

            equipos_pendientes = data.get('equipos_pendientes', '').strip() or None
            novedades_salas = data.get('novedades_salas', '').strip() or None
            pendientes_sig = data.get('pendientes_siguiente_turno', '').strip() or None
            observaciones = data.get('observaciones', '').strip() or None

            # Manejo de evidencia fotográfica si viene archivo
            evidencia_url = None
            if 'evidencia' in request.files:
                evidencia_url = _procesar_evidencia(request.files['evidencia'])

            consecutivo = _generar_consecutivo(fecha_turno)

            nueva_entrega = EntregaTurno(
                consecutivo=consecutivo,
                sede_id=int(sede_id_val),
                jornada=jornada,
                fecha=fecha_turno,
                hora=hora_turno,
                usuario_emisor_doc=usuario_doc,
                usuario_receptor_doc=usuario_receptor,
                para_toda_sede=para_toda_sede,
                asunto=asunto,
                prioridad=prioridad,
                actividades_realizadas=actividades,
                equipos_pendientes=equipos_pendientes,
                novedades_salas=novedades_salas,
                pendientes_siguiente_turno=pendientes_sig,
                observaciones=observaciones,
                evidencia_url=evidencia_url,
                estado='Pendiente',
                leido=False
            )

            db.session.add(nueva_entrega)
            db.session.commit()

            registrar_auditoria(
                modulo='turnos',
                entidad_tipo='EntregaTurno',
                entidad_id=str(nueva_entrega.id),
                accion='EMITIR_ENTREGA_TURNO',
                usuario_documento=usuario_doc,
                usuario_nombre=session.get('nombre_completo', ''),
                descripcion=f"Emitida entrega de turno {consecutivo} ({jornada}) en {sede_obj.nombre}",
                datos_despues={'consecutivo': consecutivo, 'jornada': jornada, 'sede': sede_obj.nombre}
            )

            msg = f"Entrega de Turno {consecutivo} enviada exitosamente para la jornada {jornada}."
            if is_json:
                return jsonify({
                    'success': True,
                    'message': msg,
                    'id': nueva_entrega.id,
                    'consecutivo': consecutivo
                })

            flash(msg, 'success')
            return redirect(url_for('entregas_turno.ver_entrega', entrega_id=nueva_entrega.id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al redactar entrega de turno: {e}", exc_info=True)
            msg_error = f"Error al enviar la entrega de turno: {str(e)}"
            if is_json:
                return jsonify({'success': False, 'message': msg_error}), 400
            flash(msg_error, 'danger')
            return redirect(url_for('entregas_turno.dashboard_entregas'))

    # GET: renderizar vista completa de redacción
    sedes = Sede.query.order_by(Sede.nombre.asc()).all()
    auxiliares = Auxiliar.query.filter_by(activo=True).order_by(Auxiliar.nombre_completo.asc()).all()
    jornada_sug = _determinar_jornada_sugerida()
    hoy_str = date.today().strftime('%Y-%m-%d')
    hora_str = datetime.now().strftime('%H:%M')

    return render_template(
        'entregas_turno/redactar.html',
        sedes=sedes,
        auxiliares=auxiliares,
        jornada_sugerida=jornada_sug,
        hoy_str=hoy_str,
        hora_str=hora_str,
        sede_actual_id=session.get('sede_id')
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. LECTURA Y DETALLE DE LA ENTREGA DE TURNO (CORREO INTERNO)
# ─────────────────────────────────────────────────────────────────────────────

@entregas_turno_bp.route('/<int:entrega_id>', methods=['GET'])
@login_required
def ver_entrega(entrega_id: int):
    """Muestra el detalle del correo/acta de entrega de turno y lo marca como leído."""
    try:
        entrega = EntregaTurno.query.get_or_404(entrega_id)
        usuario_actual = str(session.get('usuario', '')).strip()

        # Marcar como leído si no es el emisor y aún estaba no leído
        if not entrega.leido and usuario_actual != entrega.usuario_emisor_doc:
            entrega.leido = True
            entrega.fecha_lectura = datetime.now()
            db.session.commit()

        return render_template(
            'entregas_turno/detalle.html',
            entrega=entrega,
            usuario_actual=usuario_actual
        )

    except Exception as e:
        current_app.logger.error(f"Error al ver entrega de turno {entrega_id}: {e}", exc_info=True)
        flash('No se pudo cargar la entrega de turno solicitada.', 'warning')
        return redirect(url_for('entregas_turno.dashboard_entregas'))


# ─────────────────────────────────────────────────────────────────────────────
# 4. ACUSE DE RECIBO DE LA ENTREGA (CONFIRMACIÓN DEL TURNO ENTRANTE)
# ─────────────────────────────────────────────────────────────────────────────

@entregas_turno_bp.route('/<int:entrega_id>/acuse', methods=['POST'])
@login_required
def confirmar_acuse(entrega_id: int):
    """Registra la recepción formal del turno por parte del compañero entrante."""
    is_json = request.is_json
    data = request.get_json() if is_json else request.form

    try:
        entrega = EntregaTurno.query.get_or_404(entrega_id)
        usuario_actual = str(session.get('usuario', '')).strip()
        nombre_actual = session.get('nombre_completo', 'Operador Entrante')

        tipo_acuse = data.get('tipo_acuse', 'Recibido Conforme').strip()
        if tipo_acuse not in ('Recibido Conforme', 'Con Observaciones'):
            tipo_acuse = 'Recibido Conforme'

        observaciones = data.get('observaciones_acuse', '').strip() or None

        entrega.estado = tipo_acuse
        entrega.usuario_acuse_doc = usuario_actual
        entrega.fecha_acuse = datetime.now()
        entrega.observaciones_acuse = observaciones

        # Crear comentario automático en el hilo
        texto_comentario = f"📋 Acuse de recibo registrado: {tipo_acuse}."
        if observaciones:
            texto_comentario += f" Observaciones: {observaciones}"

        comentario_auto = ComentarioEntregaTurno(
            entrega_id=entrega.id,
            usuario_doc=usuario_actual,
            usuario_nombre=nombre_actual,
            mensaje=texto_comentario
        )
        db.session.add(comentario_auto)
        db.session.commit()

        registrar_auditoria(
            modulo='turnos',
            entidad_tipo='EntregaTurno',
            entidad_id=str(entrega.id),
            accion='CONFIRMAR_ACUSE_TURNO',
            usuario_documento=usuario_actual,
            usuario_nombre=nombre_actual,
            descripcion=f"Acuse de recibo {tipo_acuse} para entrega {entrega.consecutivo}",
            datos_despues={'estado': tipo_acuse, 'observaciones': observaciones}
        )

        msg = f"Recepción del turno confirmada exitosamente ({tipo_acuse})."
        if is_json:
            return jsonify({'success': True, 'message': msg, 'estado': tipo_acuse})

        flash(msg, 'success')
        return redirect(url_for('entregas_turno.ver_entrega', entrega_id=entrega.id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al registrar acuse de recibo en turno {entrega_id}: {e}", exc_info=True)
        msg_err = f"Error al registrar acuse de recibo: {str(e)}"
        if is_json:
            return jsonify({'success': False, 'message': msg_err}), 400
        flash(msg_err, 'danger')
        return redirect(url_for('entregas_turno.ver_entrega', entrega_id=entrega_id))


# ─────────────────────────────────────────────────────────────────────────────
# 5. COMENTARIOS Y SEGUIMIENTO EN EL HILO DE CORREO
# ─────────────────────────────────────────────────────────────────────────────

@entregas_turno_bp.route('/<int:entrega_id>/comentario', methods=['POST'])
@login_required
def agregar_comentario(entrega_id: int):
    """Agrega una nota o respuesta al hilo de la entrega de turno."""
    is_json = request.is_json
    data = request.get_json() if is_json else request.form

    try:
        entrega = EntregaTurno.query.get_or_404(entrega_id)
        usuario_actual = str(session.get('usuario', '')).strip()
        nombre_actual = session.get('nombre_completo', 'Colaborador')

        mensaje = data.get('mensaje', '').strip()
        if not mensaje:
            raise ValueError("El mensaje no puede estar vacío.")

        comentario = ComentarioEntregaTurno(
            entrega_id=entrega.id,
            usuario_doc=usuario_actual,
            usuario_nombre=nombre_actual,
            mensaje=mensaje
        )
        db.session.add(comentario)
        db.session.commit()

        if is_json:
            return jsonify({
                'success': True,
                'message': 'Respuesta agregada al hilo.',
                'comentario': {
                    'id': comentario.id,
                    'autor': nombre_actual,
                    'mensaje': mensaje,
                    'fecha': comentario.created_at.strftime('%d/%m/%Y %H:%M')
                }
            })

        flash('Respuesta registrada en el hilo de la entrega.', 'success')
        return redirect(url_for('entregas_turno.ver_entrega', entrega_id=entrega.id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al agregar comentario a entrega {entrega_id}: {e}", exc_info=True)
        msg_err = f"Error al responder: {str(e)}"
        if is_json:
            return jsonify({'success': False, 'message': msg_err}), 400
        flash(msg_err, 'danger')
        return redirect(url_for('entregas_turno.ver_entrega', entrega_id=entrega_id))


# ─────────────────────────────────────────────────────────────────────────────
# 6. AUTO-CARGA INTELIGENTE DE NOVEDADES DEL DÍA
# ─────────────────────────────────────────────────────────────────────────────

@entregas_turno_bp.route('/api/resumen-automatico', methods=['GET'])
@login_required
def api_resumen_automatico():
    """
    Consulta en tiempo real préstamos de equipos activos sin devolver y novedades de salas
    reportadas hoy para autocompletar la redacción de la entrega con 1 clic.
    """
    try:
        sede_id = request.args.get('sede_id', type=int) or session.get('sede_id')
        hoy = date.today()

        # 1. Préstamos activos (sin devolver) de hoy en la sede
        q_prestamos = PrestamoEquipo.query.filter(
            PrestamoEquipo.fecha_prestamo == hoy,
            PrestamoEquipo.estado == 'Prestado'
        )
        if sede_id:
            q_prestamos = q_prestamos.filter(PrestamoEquipo.sede_id == sede_id)

        prestamos_activos = q_prestamos.order_by(PrestamoEquipo.hora_inicio.asc()).all()

        lineas_prestamos = []
        for p in prestamos_activos:
            prof_nom = p.nombre_profesor or 'Docente'
            ubica_txt = f" ({p.ubicacion})" if p.ubicacion else ""
            hora_txt = p.hora_inicio.strftime('%H:%M') if p.hora_inicio else 'N/A'
            lineas_prestamos.append(
                f"• {p.equipo_prestado} [{p.numero_inventario_equipo or 'S/N'}] prestado a {prof_nom}{ubica_txt} a las {hora_txt} — Pendiente devolución."
            )

        texto_equipos = "\n".join(lineas_prestamos) if lineas_prestamos else "Sin equipos pendientes al cierre del turno. Todos devueltos y verificados."

        # 2. Novedades técnicas de salas de hoy
        q_novedades = NovedadTecnicaSala.query.filter(NovedadTecnicaSala.fecha_reporte == hoy)
        if sede_id:
            q_novedades = q_novedades.join(Recurso).join(Ubicacion).filter(Ubicacion.sede_id == sede_id)

        novedades_hoy = q_novedades.all()
        lineas_salas = []
        for n in novedades_hoy:
            lineas_salas.append(
                f"• Sala/Recurso: {n.recurso.nombre if n.recurso else 'Sala'} - Tipo: {n.tipo_falla} ({n.prioridad}): {n.descripcion} [Estado: {n.estado}]"
            )

        texto_salas = "\n".join(lineas_salas) if lineas_salas else "Salas de cómputo y laboratorios operando con normalidad. Sin fallas reportadas."

        return jsonify({
            'success': True,
            'equipos_pendientes_sugerido': texto_equipos,
            'novedades_salas_sugerido': texto_salas,
            'total_prestamos_pendientes': len(prestamos_activos),
            'total_novedades_salas': len(novedades_hoy)
        })

    except Exception as e:
        current_app.logger.error(f"Error al generar resumen automático de turno: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# 7. ACTA OFICIAL IMPRIMIBLE / EXPORTACIÓN
# ─────────────────────────────────────────────────────────────────────────────

@entregas_turno_bp.route('/<int:entrega_id>/imprimir', methods=['GET'])
@login_required
def imprimir_acta(entrega_id: int):
    """Genera la vista limpia e imprimible del Acta Formal de Entrega de Turno."""
    entrega = EntregaTurno.query.get_or_404(entrega_id)
    return render_template('entregas_turno/imprimir_acta.html', entrega=entrega)
