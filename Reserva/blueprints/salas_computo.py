from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app, session, send_file
from datetime import datetime, date, time, timedelta
from sqlalchemy import desc, asc, or_, and_, func
import io
import pandas as pd
from database import (
    db, Profesor, registrar_auditoria, ClaseSalaComputo, Sede, 
    Recurso, Ubicacion, PuestoComputo, SoftwareSala, SoftwareAsignadoSala, NovedadTecnicaSala,
    PracticaLibre, Estudiante, Reserva
)
from auth import login_required, permiso_requerido
from config import SystemConstants

salas_computo_bp = Blueprint('salas_computo', __name__, url_prefix='/salas-computo')


# =========================================================================
# 1. DASHBOARD PRINCIPAL DE SALAS DE CÓMPUTO
# =========================================================================

@salas_computo_bp.route('/')
@login_required
@permiso_requerido('salas_computo', 'ver')
def dashboard_salas():
    """Dashboard principal con gestión de clases, puestos, software y novedades técnicas."""
    try:
        hoy = date.today()
        hoy_str = hoy.strftime('%Y-%m-%d')
        ahora = datetime.now()

        # Paginación y Filtros de Clases
        page = request.args.get('page', 1, type=int)
        tab_activa = request.args.get('tab', 'clases')
        per_page = request.args.get('per_page', 50, type=int) if tab_activa == 'clases' else 15
        
        fecha_filtro = request.args.get('fecha', '')
        salon_filtro = request.args.get('salon', '')
        jornada_filtro = request.args.get('jornada', '').strip()
        busqueda = request.args.get('busqueda', '')
        sede_filtro_id = request.args.get('sede', '')
        
        # Filtro de Sede de Usuario
        if not sede_filtro_id and session.get('rol') not in ('admin', 'superadmin') and session.get('sede_id'):
            sede_filtro_id = str(session.get('sede_id'))

        # -------------------------------------------------------------
        # 1.1 Consultas de Clases Programadas
        # -------------------------------------------------------------
        query_clases = ClaseSalaComputo.query
        
        if fecha_filtro:
            query_clases = query_clases.filter(ClaseSalaComputo.fecha == datetime.strptime(fecha_filtro, '%Y-%m-%d').date())
        
        if salon_filtro:
            query_clases = query_clases.filter(ClaseSalaComputo.salon.ilike(f"%{salon_filtro}%"))
            
        if jornada_filtro:
            query_clases = query_clases.filter(ClaseSalaComputo.jornada.ilike(f"%{jornada_filtro}%"))

        if busqueda:
            term = f"%{busqueda}%"
            query_clases = query_clases.filter(
                or_(
                    ClaseSalaComputo.nombre_profesor.ilike(term),
                    ClaseSalaComputo.materia.ilike(term),
                    ClaseSalaComputo.programa.ilike(term)
                )
            )
            
        if sede_filtro_id:
            query_clases = query_clases.filter(ClaseSalaComputo.sede_id == int(sede_filtro_id))

        query_clases = query_clases.order_by(
            ClaseSalaComputo.fecha.desc(),
            ClaseSalaComputo.hora_inicio.desc()
        )
        
        pagination_clases = query_clases.paginate(page=page, per_page=per_page, error_out=False)
        clases = pagination_clases.items

        # Agrupar clases por Piso y Salón para la vista de Ronda Rápida
        clases_agrupadas = {}
        total_asistieron = sum(1 for c in clases if c.asistencia == 'Sí')
        total_no_asistieron = sum(1 for c in clases if c.asistencia != 'Sí')

        clases_ordenadas_ronda = sorted(clases, key=lambda x: (x.salon or '', x.hora_inicio))
        for c in clases_ordenadas_ronda:
            sal = (c.salon or 'General').strip()
            if sal.startswith('7'):
                grupo = 'Piso 7'
            elif sal.startswith('8'):
                grupo = 'Piso 8'
            elif sal.startswith('A'):
                grupo = 'Edificio A'
            elif sal.startswith('B'):
                grupo = 'Edificio B'
            elif sal.startswith('C'):
                grupo = 'Edificio C'
            elif sal.startswith('D'):
                grupo = 'Edificio D'
            else:
                grupo = 'Salas Generales'
                
            if grupo not in clases_agrupadas:
                clases_agrupadas[grupo] = {}
            if sal not in clases_agrupadas[grupo]:
                clases_agrupadas[grupo][sal] = []
            clases_agrupadas[grupo][sal].append(c)

        # -------------------------------------------------------------
        # 1.2 Consultas de Salas de Cómputo y Puestos (Salas específicas por sede)
        # -------------------------------------------------------------
        query_salas = Recurso.query.join(Ubicacion).filter(Recurso.activo.is_(True))
        if sede_filtro_id:
            s_id = int(sede_filtro_id)
            if s_id == 1:
                query_salas = query_salas.filter(
                    Ubicacion.sede_id == 1,
                    Recurso.nombre.in_(SystemConstants.SALONES_PERDOMO_COMPUTO)
                )
            elif s_id == 2:
                query_salas = query_salas.filter(
                    Ubicacion.sede_id == 2,
                    db.or_(
                        Recurso.nombre.ilike('%LS%'),
                        Recurso.nombre.in_(SystemConstants.SALONES_PRINCIPAL_COMPUTO)
                    )
                )
            else:
                query_salas = query_salas.filter(
                    Ubicacion.sede_id == s_id,
                    Recurso.nombre.ilike('%LS%')
                )
        else:
            query_salas = query_salas.filter(
                db.or_(
                    db.and_(
                        Ubicacion.sede_id == 1,
                        Recurso.nombre.in_(SystemConstants.SALONES_PERDOMO_COMPUTO)
                    ),
                    db.and_(
                        Ubicacion.sede_id == 2,
                        db.or_(
                            Recurso.nombre.ilike('%LS%'),
                            Recurso.nombre.in_(SystemConstants.SALONES_PRINCIPAL_COMPUTO)
                        )
                    ),
                    db.and_(
                        ~Ubicacion.sede_id.in_([1, 2]),
                        Recurso.nombre.ilike('%LS%')
                    )
                )
            )
            
        salas_db = query_salas.order_by(Recurso.nombre.asc()).all()

        salas_metricas = []
        total_puestos_global = 0
        total_puestos_operativos = 0
        total_puestos_fallas = 0

        for sala in salas_db:
            puestos = PuestoComputo.query.filter_by(recurso_id=sala.id).order_by(PuestoComputo.numero_puesto.asc()).all()
            cant_total = len(puestos)
            cant_operativos = sum(1 for p in puestos if p.estado == 'Operativo')
            cant_fallas = sum(1 for p in puestos if p.estado != 'Operativo')
            
            total_puestos_global += cant_total
            total_puestos_operativos += cant_operativos
            total_puestos_fallas += cant_fallas
            
            porcentaje_operatividad = round((cant_operativos / cant_total * 100)) if cant_total > 0 else 100
            
            # Software instalado en esta sala
            software_asignado = SoftwareAsignadoSala.query.filter_by(recurso_id=sala.id).all()
            novedades_pendientes_count = NovedadTecnicaSala.query.filter_by(recurso_id=sala.id, estado='Pendiente').count()
            
            salas_metricas.append({
                'sala': sala,
                'puestos': puestos,
                'total_puestos': cant_total,
                'operativos': cant_operativos,
                'fallas': cant_fallas,
                'porcentaje': porcentaje_operatividad,
                'software_instalado': [sa.software for sa in software_asignado if sa.software],
                'novedades_pendientes': novedades_pendientes_count,
                'sede_nombre': sala.ubicacion.sede.nombre if sala.ubicacion and sala.ubicacion.sede else 'Principal'
            })

        # -------------------------------------------------------------
        # 1.3 Catálogo de Software
        # -------------------------------------------------------------
        software_catalogo_raw = SoftwareSala.query.filter_by(activo=True).order_by(SoftwareSala.categoria.asc(), SoftwareSala.nombre.asc()).all()
        software_catalogo = []
        for s in software_catalogo_raw:
            asignaciones = SoftwareAsignadoSala.query.filter_by(software_id=s.id).all()
            salas_nombres = [a.recurso.nombre for a in asignaciones if a.recurso]
            software_catalogo.append({
                'item': s,
                'total_salas': len(salas_nombres),
                'salas_nombres': salas_nombres
            })

        # -------------------------------------------------------------
        # 1.4 Novedades Técnicas e Incidencias
        # -------------------------------------------------------------
        query_novedades = NovedadTecnicaSala.query
        if sede_filtro_id:
            query_novedades = query_novedades.join(Recurso).join(Ubicacion).filter(Ubicacion.sede_id == int(sede_filtro_id))
            
        novedades_todas = query_novedades.order_by(
            NovedadTecnicaSala.estado.asc(),  # Pendientes primero
            NovedadTecnicaSala.fecha_reporte.desc(),
            NovedadTecnicaSala.hora_reporte.desc()
        ).limit(150).all()

        total_novedades_pendientes = sum(1 for n in novedades_todas if n.estado == 'Pendiente')
        total_novedades_revision = sum(1 for n in novedades_todas if n.estado == 'En Revisión')
        total_novedades_solucionadas = sum(1 for n in novedades_todas if n.estado == 'Solucionada')

        # Clases de hoy
        total_clases_hoy = ClaseSalaComputo.query.filter_by(fecha=hoy).count()

        # -------------------------------------------------------------
        # 1.5 Práctica Libre Estudiantil
        # -------------------------------------------------------------
        practica_busqueda = request.args.get('practica_busqueda', '').strip()
        practica_fecha = request.args.get('practica_fecha', '').strip()
        practica_salon = request.args.get('practica_salon', '').strip()
        practica_estado = request.args.get('practica_estado', '').strip()

        # Prácticas Activas (En Curso)
        query_practicas_activas = PracticaLibre.query.filter_by(estado='En Curso')
        if sede_filtro_id:
            query_practicas_activas = query_practicas_activas.filter_by(sede_id=int(sede_filtro_id))
        practicas_activas = query_practicas_activas.order_by(PracticaLibre.hora_inicio.desc()).all()

        # Historial de Prácticas
        query_practicas_hist = PracticaLibre.query
        if sede_filtro_id:
            query_practicas_hist = query_practicas_hist.filter_by(sede_id=int(sede_filtro_id))
        if practica_fecha:
            try:
                query_practicas_hist = query_practicas_hist.filter(PracticaLibre.fecha == datetime.strptime(practica_fecha, '%Y-%m-%d').date())
            except ValueError:
                pass
        if practica_salon:
            query_practicas_hist = query_practicas_hist.filter(PracticaLibre.salon.ilike(f"%{practica_salon}%"))
        if practica_estado:
            query_practicas_hist = query_practicas_hist.filter_by(estado=practica_estado)
        if practica_busqueda:
            term_p = f"%{practica_busqueda}%"
            query_practicas_hist = query_practicas_hist.filter(
                or_(
                    PracticaLibre.codigo_banner.ilike(term_p),
                    PracticaLibre.nombre_estudiante.ilike(term_p),
                    PracticaLibre.programa_estudiante.ilike(term_p)
                )
            )
        practicas_historial = query_practicas_hist.order_by(
            PracticaLibre.fecha.desc(),
            PracticaLibre.hora_inicio.desc()
        ).limit(150).all()

        total_practicas_activas = len(practicas_activas)
        total_practicas_hoy = PracticaLibre.query.filter_by(fecha=hoy).count()

        # Docentes y Sedes para listas desplegables
        profesores = Profesor.query.order_by(Profesor.nombre_completo.asc()).all()
        sedes = Sede.query.all()
        
        return render_template(
            'salas_computo.html',
            tab_activa=tab_activa,
            clases=clases,
            pagination=pagination_clases,
            profesores=profesores,
            sedes=sedes,
            hoy_str=hoy_str,
            salas_metricas=salas_metricas,
            software_catalogo=software_catalogo,
            novedades=novedades_todas,
            clases_agrupadas=clases_agrupadas,
            total_asistieron=total_asistieron,
            total_no_asistieron=total_no_asistieron,
            total_clases_hoy=total_clases_hoy,
            total_puestos_global=total_puestos_global,
            total_puestos_operativos=total_puestos_operativos,
            total_puestos_fallas=total_puestos_fallas,
            total_novedades_pendientes=total_novedades_pendientes,
            total_novedades_revision=total_novedades_revision,
            total_novedades_solucionadas=total_novedades_solucionadas,
            total_software=len(software_catalogo),
            practicas_activas=practicas_activas,
            practicas_historial=practicas_historial,
            total_practicas_activas=total_practicas_activas,
            total_practicas_hoy=total_practicas_hoy,
            filtros={
                'fecha': fecha_filtro,
                'salon': salon_filtro,
                'jornada': jornada_filtro,
                'busqueda': busqueda,
                'sede': sede_filtro_id,
                'practica_busqueda': practica_busqueda,
                'practica_fecha': practica_fecha,
                'practica_salon': practica_salon,
                'practica_estado': practica_estado
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error cargando salas de cómputo: {e}")
        import traceback
        print(traceback.format_exc())
        flash('Error al cargar la información de salas de cómputo.', 'danger')
        return render_template('salas_computo.html', clases=[], salas_metricas=[], software_catalogo=[], novedades=[], practicas_activas=[], practicas_historial=[], filtros={})


# =========================================================================
# 2. GESTIÓN Y API DE PUESTOS DE CÓMPUTO
# =========================================================================

@salas_computo_bp.route('/api/sala/<int:recurso_id>/puestos', methods=['GET'])
@login_required
def api_puestos_sala(recurso_id):
    """Retorna JSON con la lista de puestos y estado de una sala específica."""
    try:
        sala = Recurso.query.get_or_404(recurso_id)
        puestos = PuestoComputo.query.filter_by(recurso_id=recurso_id).order_by(PuestoComputo.numero_puesto.asc()).all()
        software_asig = SoftwareAsignadoSala.query.filter_by(recurso_id=recurso_id).all()

        puestos_data = []
        for p in puestos:
            novedad_activa = NovedadTecnicaSala.query.filter_by(puesto_id=p.id, estado='Pendiente').order_by(NovedadTecnicaSala.fecha_reporte.desc()).first()
            puestos_data.append({
                'id': p.id,
                'numero_puesto': p.numero_puesto,
                'nombre_equipo': p.nombre_equipo or f"PC-{sala.nombre}-{str(p.numero_puesto).zfill(2)}",
                'serial_activo': p.serial_activo or '',
                'estado': p.estado,
                'observaciones': p.observaciones or '',
                'novedad_activa': {
                    'id': novedad_activa.id,
                    'tipo_falla': novedad_activa.tipo_falla,
                    'descripcion': novedad_activa.descripcion,
                    'fecha': novedad_activa.fecha_reporte.strftime('%Y-%m-%d')
                } if novedad_activa else None
            })

        return jsonify({
            'success': True,
            'sala_nombre': sala.nombre,
            'recurso_id': sala.id,
            'total_puestos': len(puestos),
            'operativos': sum(1 for p in puestos if p.estado == 'Operativo'),
            'puestos': puestos_data,
            'software': [{'id': sa.software.id, 'nombre': sa.software.nombre, 'version': sa.software.version, 'categoria': sa.software.categoria} for sa in software_asig if sa.software]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@salas_computo_bp.route('/puestos/<int:puesto_id>/estado', methods=['POST'])
@login_required
@permiso_requerido('salas_computo', 'editar')
def actualizar_estado_puesto(puesto_id):
    """Actualiza el estado de un puesto de cómputo en 1 clic."""
    try:
        puesto = PuestoComputo.query.get_or_404(puesto_id)
        data = request.get_json(silent=True) or request.form
        nuevo_estado = data.get('estado', 'Operativo')
        observaciones = data.get('observaciones', '')

        if nuevo_estado not in ['Operativo', 'Falla Leve', 'Fuera de Servicio', 'Mantenimiento']:
            return jsonify({'success': False, 'message': 'Estado no válido'}), 400

        estado_anterior = puesto.estado
        puesto.estado = nuevo_estado
        if observaciones:
            puesto.observaciones = observaciones

        db.session.commit()

        registrar_auditoria(
            modulo='salas_computo',
            entidad_tipo='PuestoComputo',
            entidad_id=str(puesto.id),
            accion='CAMBIO_ESTADO',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Puesto #{puesto.numero_puesto} de {puesto.recurso.nombre}: {estado_anterior} -> {nuevo_estado}'
        )

        if request.is_json:
            return jsonify({'success': True, 'puesto_id': puesto.id, 'nuevo_estado': nuevo_estado})
        
        flash(f'Puesto #{puesto.numero_puesto} actualizado a {nuevo_estado}.', 'success')
        return redirect(url_for('salas_computo.dashboard_salas', tab='puestos'))
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'success': False, 'message': str(e)}), 500
        flash(f'Error al actualizar el puesto: {str(e)}', 'danger')
        return redirect(url_for('salas_computo.dashboard_salas', tab='puestos'))


@salas_computo_bp.route('/puestos/generar', methods=['POST'])
@login_required
@permiso_requerido('salas_computo', 'crear')
def generar_puestos_sala():
    """Genera o ajusta la cantidad total de puestos para una sala."""
    try:
        recurso_id = int(request.form.get('recurso_id'))
        cantidad = int(request.form.get('cantidad_puestos', 25))
        sala = Recurso.query.get_or_404(recurso_id)

        if cantidad < 1 or cantidad > 100:
            flash('La cantidad de puestos debe estar entre 1 y 100.', 'warning')
            return redirect(url_for('salas_computo.dashboard_salas', tab='puestos'))

        puestos_existentes = PuestoComputo.query.filter_by(recurso_id=recurso_id).all()
        existentes_dict = {p.numero_puesto: p for p in puestos_existentes}

        # Crear los puestos que falten
        for i in range(1, cantidad + 1):
            if i not in existentes_dict:
                nuevo = PuestoComputo(
                    recurso_id=recurso_id,
                    numero_puesto=i,
                    nombre_equipo=f"PC-{sala.nombre}-{str(i).zfill(2)}",
                    estado='Operativo'
                )
                db.session.add(nuevo)

        # Si se reduce la cantidad, eliminar los sobrantes si no tienen novedades pendientes
        for i, p in existentes_dict.items():
            if i > cantidad:
                db.session.delete(p)

        db.session.commit()

        registrar_auditoria(
            modulo='salas_computo',
            entidad_tipo='PuestoComputo',
            entidad_id=str(recurso_id),
            accion='GENERAR_PUESTOS',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Generados {cantidad} puestos para la sala {sala.nombre}'
        )

        flash(f'Se configuraron {cantidad} puestos para la sala {sala.nombre}.', 'success')
        return redirect(url_for('salas_computo.dashboard_salas', tab='puestos'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error generando puestos: {e}")
        flash(f'Error al generar puestos: {str(e)}', 'danger')
        return redirect(url_for('salas_computo.dashboard_salas', tab='puestos'))


# =========================================================================
# 3. GESTIÓN DE NOVEDADES TÉCNICAS E INCIDENCIAS
# =========================================================================

@salas_computo_bp.route('/novedades/nueva', methods=['POST'])
@login_required
@permiso_requerido('salas_computo', 'crear')
def nueva_novedad():
    """Registra una nueva falla o novedad técnica en una sala / puesto."""
    try:
        datos = request.form
        recurso_id = int(datos.get('recurso_id'))
        puesto_id = int(datos.get('puesto_id')) if datos.get('puesto_id') else None
        
        tipo_falla = datos.get('tipo_falla', 'Hardware').strip()
        prioridad = datos.get('prioridad', 'Media').strip()
        descripcion = datos.get('descripcion', '').strip()
        
        ahora = datetime.now()
        auxiliar_nombre = session.get('nombre_completo', session.get('usuario', 'Auxiliar'))

        nueva = NovedadTecnicaSala(
            recurso_id=recurso_id,
            puesto_id=puesto_id,
            tipo_falla=tipo_falla,
            prioridad=prioridad,
            descripcion=descripcion,
            estado='Pendiente',
            auxiliar_reporta=auxiliar_nombre,
            fecha_reporte=ahora.date(),
            hora_reporte=ahora.time()
        )
        db.session.add(nueva)

        # Si se asoció a un puesto, actualizar el estado del puesto automáticamente
        if puesto_id:
            puesto = PuestoComputo.query.get(puesto_id)
            if puesto:
                if prioridad in ('Alta', 'Crítica'):
                    puesto.estado = 'Fuera de Servicio'
                else:
                    puesto.estado = 'Falla Leve'
                puesto.observaciones = f"Novedad #{tipo_falla}: {descripcion[:60]}..."

        db.session.commit()

        sala = Recurso.query.get(recurso_id)
        registrar_auditoria(
            modulo='salas_computo',
            entidad_tipo='NovedadTecnicaSala',
            entidad_id=str(nueva.id),
            accion='CREAR_NOVEDAD',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=auxiliar_nombre,
            descripcion=f'Novedad reportada en {sala.nombre if sala else "Sala"}: {tipo_falla} - {descripcion[:50]}'
        )

        flash('Novedad técnica registrada exitosamente.', 'success')
        return redirect(url_for('salas_computo.dashboard_salas', tab='novedades'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error registrando novedad: {e}")
        flash(f'Error al registrar la novedad: {str(e)}', 'danger')
        return redirect(url_for('salas_computo.dashboard_salas', tab='novedades'))


@salas_computo_bp.route('/novedades/<int:novedad_id>/resolver', methods=['POST'])
@login_required
@permiso_requerido('salas_computo', 'editar')
def resolver_novedad(novedad_id):
    """Marca una novedad como solucionada y reestablece el estado del equipo si aplica."""
    try:
        novedad = NovedadTecnicaSala.query.get_or_404(novedad_id)
        solucion = request.form.get('solucion_aplicada', '').strip()
        ahora = datetime.now()
        auxiliar_nombre = session.get('nombre_completo', session.get('usuario', 'Auxiliar'))

        novedad.estado = 'Solucionada'
        novedad.solucion_aplicada = solucion
        novedad.auxiliar_soluciona = auxiliar_nombre
        novedad.fecha_solucion = ahora.date()
        novedad.hora_solucion = ahora.time()

        # Si la novedad era de un puesto, verificar si no quedan otras novedades pendientes para dejarlo Operativo
        if novedad.puesto_id:
            puesto = PuestoComputo.query.get(novedad.puesto_id)
            if puesto:
                otras_pendientes = NovedadTecnicaSala.query.filter(
                    NovedadTecnicaSala.puesto_id == puesto.id,
                    NovedadTecnicaSala.id != novedad.id,
                    NovedadTecnicaSala.estado == 'Pendiente'
                ).count()
                if otras_pendientes == 0:
                    puesto.estado = 'Operativo'
                    puesto.observaciones = 'Operativo (Novedad resuelta)'

        db.session.commit()

        registrar_auditoria(
            modulo='salas_computo',
            entidad_tipo='NovedadTecnicaSala',
            entidad_id=str(novedad.id),
            accion='RESOLVER_NOVEDAD',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=auxiliar_nombre,
            descripcion=f'Novedad #{novedad.id} resuelta: {solucion[:50]}'
        )

        flash('Novedad técnica marcada como solucionada.', 'success')
        return redirect(url_for('salas_computo.dashboard_salas', tab='novedades'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resolviendo novedad: {e}")
        flash(f'Error al resolver la novedad: {str(e)}', 'danger')
        return redirect(url_for('salas_computo.dashboard_salas', tab='novedades'))


# =========================================================================
# 4. GESTIÓN Y CATÁLOGO DE SOFTWARE POR SALA
# =========================================================================

@salas_computo_bp.route('/software/nuevo', methods=['POST'])
@login_required
@permiso_requerido('salas_computo', 'crear')
def nuevo_software():
    """Agrega un nuevo programa al catálogo de software."""
    try:
        datos = request.form
        nombre = datos.get('nombre', '').strip()
        version = datos.get('version', '').strip()
        categoria = datos.get('categoria', 'General').strip()
        licencia = datos.get('licencia', 'Institucional').strip()
        descripcion = datos.get('descripcion', '').strip()
        icono = datos.get('icono', 'bi-app-indicator').strip()

        if not nombre:
            flash('El nombre del software es obligatorio.', 'warning')
            return redirect(url_for('salas_computo.dashboard_salas', tab='software'))

        nuevo = SoftwareSala(
            nombre=nombre,
            version=version,
            categoria=categoria,
            licencia=licencia,
            descripcion=descripcion,
            icono=icono,
            activo=True
        )
        db.session.add(nuevo)
        db.session.commit()

        # Si se seleccionaron salas en el formulario, asignarlas
        salas_ids = request.form.getlist('salas_asignadas')
        for s_id in salas_ids:
            if s_id.isdigit():
                db.session.add(SoftwareAsignadoSala(software_id=nuevo.id, recurso_id=int(s_id)))
        db.session.commit()

        registrar_auditoria(
            modulo='salas_computo',
            entidad_tipo='SoftwareSala',
            entidad_id=str(nuevo.id),
            accion='CREAR_SOFTWARE',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Software creado: {nombre} v{version}'
        )

        flash(f'Software "{nombre}" agregado al catálogo correctamente.', 'success')
        return redirect(url_for('salas_computo.dashboard_salas', tab='software'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creando software: {e}")
        flash(f'Error al crear software: {str(e)}', 'danger')
        return redirect(url_for('salas_computo.dashboard_salas', tab='software'))


@salas_computo_bp.route('/software/asignar', methods=['POST'])
@login_required
@permiso_requerido('salas_computo', 'editar')
def asignar_software_salas():
    """Asigna o actualiza las salas donde está instalado un software."""
    try:
        software_id = int(request.form.get('software_id'))
        salas_ids = request.form.getlist('salas_ids')  # lista de IDs
        
        software = SoftwareSala.query.get_or_404(software_id)

        # Borrar asignaciones previas y reasignar
        SoftwareAsignadoSala.query.filter_by(software_id=software_id).delete()

        for s_id in salas_ids:
            if s_id.isdigit():
                db.session.add(SoftwareAsignadoSala(software_id=software_id, recurso_id=int(s_id)))

        db.session.commit()

        registrar_auditoria(
            modulo='salas_computo',
            entidad_tipo='SoftwareSala',
            entidad_id=str(software_id),
            accion='ASIGNAR_SALAS',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Asignación de {software.nombre} actualizada a {len(salas_ids)} salas.'
        )

        flash(f'Instalación de "{software.nombre}" actualizada correctamente en las salas.', 'success')
        return redirect(url_for('salas_computo.dashboard_salas', tab='software'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error asignando software: {e}")
        flash(f'Error al asignar software: {str(e)}', 'danger')
        return redirect(url_for('salas_computo.dashboard_salas', tab='software'))


# =========================================================================
# 5. GESTIÓN DE CLASES Y ASISTENCIA ACADÉMICA
# =========================================================================

@salas_computo_bp.route('/nueva', methods=['POST'])
@login_required
@permiso_requerido('salas_computo', 'crear')
def nueva_clase():
    try:
        datos = request.form
        
        fecha = datetime.strptime(datos.get('fecha'), '%Y-%m-%d').date()
        hora_inicio = datetime.strptime(datos.get('hora_inicio'), '%H:%M').time()
        hora_fin = datetime.strptime(datos.get('hora_fin'), '%H:%M').time()
        
        salon = datos.get('salon', '').strip()
        nombre_profesor = datos.get('nombre_profesor', '').strip()
        materia = datos.get('materia', '').strip()
        
        asistencia = datos.get('asistencia', 'No')
        horas_academicas = datos.get('horas_academicas')
        horas_academicas = float(horas_academicas) if horas_academicas else None
        
        jornada = datos.get('jornada', '').strip()
        num_estudiantes = datos.get('num_estudiantes')
        num_estudiantes = int(num_estudiantes) if num_estudiantes else None
        
        programa = datos.get('programa', '').strip()
        modalidad = datos.get('modalidad', '').strip()
        observaciones = datos.get('observaciones', '').strip()
        
        if hora_inicio >= hora_fin:
            flash('La hora de inicio debe ser anterior a la hora de fin.', 'warning')
            return redirect(url_for('salas_computo.dashboard_salas', tab='clases'))

        nueva_clase = ClaseSalaComputo(
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            salon=salon,
            nombre_profesor=nombre_profesor,
            materia=materia,
            asistencia=asistencia,
            horas_academicas=horas_academicas,
            jornada=jornada,
            num_estudiantes=num_estudiantes,
            programa=programa,
            modalidad=modalidad,
            sede_id=int(datos.get('sede_id')) if datos.get('sede_id') else None,
            recurso_id=int(datos.get('recurso_id')) if datos.get('recurso_id') else None,
            observaciones=observaciones,
            estado='Programada'
        )
        
        db.session.add(nueva_clase)
        db.session.commit()
        
        registrar_auditoria(
            modulo='salas_computo',
            entidad_tipo='ClaseSalaComputo',
            entidad_id=str(nueva_clase.id_clase),
            accion='CREAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Clase creada: {materia} ({salon})'
        )
        
        flash('Clase registrada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creando clase: {e}")
        flash(f'Error al registrar la clase: {str(e)}', 'danger')
        
    return redirect(url_for('salas_computo.dashboard_salas', tab='clases'))


@salas_computo_bp.route('/clase/<int:id_clase>', methods=['POST'])
@login_required
def editar_clase(id_clase):
    try:
        _method = request.form.get('_method', '').upper()
        clase = ClaseSalaComputo.query.get_or_404(id_clase)
        
        if _method == 'DELETE':
            db.session.delete(clase)
            db.session.commit()
            flash('Clase eliminada exitosamente.', 'success')
            return redirect(url_for('salas_computo.dashboard_salas', tab='clases'))

        datos = request.form
        clase.fecha = datetime.strptime(datos.get('fecha'), '%Y-%m-%d').date()
        clase.hora_inicio = datetime.strptime(datos.get('hora_inicio'), '%H:%M').time()
        clase.hora_fin = datetime.strptime(datos.get('hora_fin'), '%H:%M').time()
        
        clase.salon = datos.get('salon', '').strip()
        clase.nombre_profesor = datos.get('nombre_profesor', '').strip()
        clase.materia = datos.get('materia', '').strip()
        clase.asistencia = datos.get('asistencia', 'No')
        
        ha = datos.get('horas_academicas')
        clase.horas_academicas = float(ha) if ha else None
        clase.jornada = datos.get('jornada', '').strip()
        
        ne = datos.get('num_estudiantes')
        clase.num_estudiantes = int(ne) if ne else None
        clase.programa = datos.get('programa', '').strip()
        clase.modalidad = datos.get('modalidad', '').strip()
        clase.observaciones = datos.get('observaciones', '').strip()
        
        if clase.hora_inicio >= clase.hora_fin:
            flash('La hora de inicio debe ser anterior a la hora de fin.', 'warning')
            return redirect(url_for('salas_computo.dashboard_salas', tab='clases'))
            
        db.session.commit()
        
        registrar_auditoria(
            modulo='salas_computo',
            entidad_tipo='ClaseSalaComputo',
            entidad_id=str(clase.id_clase),
            accion='EDITAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Clase editada: {clase.materia} ({clase.salon})'
        )
        
        flash('Clase actualizada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error actualizando clase: {e}")
        flash(f'Error al actualizar la clase: {str(e)}', 'danger')
        
    return redirect(url_for('salas_computo.dashboard_salas', tab='clases'))


@salas_computo_bp.route('/clase/<int:id_clase>/asistencia', methods=['POST'])
@login_required
@permiso_requerido('salas_computo', 'editar')
def actualizar_asistencia(id_clase):
    try:
        clase = ClaseSalaComputo.query.get_or_404(id_clase)
        datos = request.get_json(silent=True) if request.is_json else request.form
        
        asistencia = datos.get('asistencia', 'No')
        observaciones = datos.get('observaciones')
        
        clase.asistencia = asistencia
        if observaciones is not None:
            clase.observaciones = observaciones.strip()
        
        db.session.commit()
        
        registrar_auditoria(
            modulo='salas_computo',
            entidad_tipo='ClaseSalaComputo',
            entidad_id=str(clase.id_clase),
            accion='EDITAR_ASISTENCIA',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Asistencia actualizada a {asistencia}: {clase.materia} ({clase.salon})'
        )
        
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'id_clase': clase.id_clase,
                'asistencia': clase.asistencia,
                'observaciones': clase.observaciones or '',
                'salon': clase.salon,
                'profesor': clase.nombre_profesor,
                'message': f'Asistencia de {clase.nombre_profesor} en {clase.salon} guardada como {asistencia}.'
            })

        flash('Asistencia actualizada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error actualizando asistencia: {e}")
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        flash(f'Error al actualizar la asistencia: {str(e)}', 'danger')
        
    return redirect(url_for('salas_computo.dashboard_salas', tab='clases'))


@salas_computo_bp.route('/clases/marcar-asistencia-masiva', methods=['POST'])
@login_required
@permiso_requerido('salas_computo', 'editar')
def marcar_asistencia_masiva():
    """Permite marcar asistencia masiva a clases (por salón, piso o todas las visibles)."""
    try:
        data = request.get_json(silent=True) if request.is_json else request.form
        asistencia_val = data.get('asistencia', 'Sí')
        
        ids_raw = data.getlist('clase_ids') if hasattr(data, 'getlist') else data.get('clase_ids', [])
        if isinstance(ids_raw, str):
            ids = [int(i.strip()) for i in ids_raw.split(',') if i.strip().isdigit()]
        elif isinstance(ids_raw, list):
            ids = [int(i) for i in ids_raw if str(i).isdigit()]
        else:
            ids = []
            
        if not ids:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'No se seleccionaron clases para actualizar.'}), 400
            flash('No seleccionaste clases para actualizar.', 'warning')
            return redirect(url_for('salas_computo.dashboard_salas', tab='clases'))
            
        clases = ClaseSalaComputo.query.filter(ClaseSalaComputo.id_clase.in_(ids)).all()
        for c in clases:
            c.asistencia = asistencia_val
            
        db.session.commit()
        
        registrar_auditoria(
            modulo='salas_computo',
            entidad_tipo='ClaseSalaComputo',
            entidad_id=','.join(str(i) for i in ids[:10]),
            accion='EDITAR_ASISTENCIA_MASIVA',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Asistencia ({asistencia_val}) asignada masivamente a {len(clases)} clases'
        )
        
        msg = f'Asistencia ({asistencia_val}) registrada para {len(clases)} clases.'
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'count': len(clases), 'asistencia': asistencia_val, 'message': msg})
            
        flash(msg, 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error en asistencia masiva: {e}")
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        flash(f'Error al registrar asistencia masiva: {str(e)}', 'danger')
        
    return redirect(url_for('salas_computo.dashboard_salas', tab='clases'))


@salas_computo_bp.route('/clases/sincronizar-reservas', methods=['POST'])
@login_required
@permiso_requerido('salas_computo', 'crear')
def sincronizar_reservas_a_clases():
    """Sincroniza reservas existentes hacia clases_salas_computo para seguimiento y asistencia docente."""
    try:
        user_rol = session.get('rol')
        user_sede_id = session.get('sede_id')
        sede_param = request.form.get('sede_id') or request.args.get('sede')
        
        sede_filtro = None
        if user_rol not in ('admin', 'superadmin'):
            sede_filtro = user_sede_id
        elif sede_param and str(sede_param).isdigit():
            sede_filtro = int(sede_param)

        alias_map = {
            'LS1': '704LS1',
            'LS2': '803LS2',
            'LS3': '804LS3',
            'LS4': '801LS4',
            'LS5': '703LS5'
        }
        
        recursos = Recurso.query.join(Ubicacion).all()
        rec_map = {}
        for r in recursos:
            s_id = r.ubicacion.sede_id if r.ubicacion else None
            rec_map[(r.nombre.upper(), s_id)] = r
            if (r.nombre.upper(), None) not in rec_map:
                rec_map[(r.nombre.upper(), None)] = r

        query_res = Reserva.query
        if sede_filtro:
            query_res = query_res.filter(
                or_(
                    Reserva.sede_id == sede_filtro,
                    Reserva.recurso.has(Recurso.ubicacion.has(Ubicacion.sede_id == sede_filtro))
                )
            )
            
        reservas = query_res.order_by(Reserva.fecha.asc(), Reserva.hora_inicio.asc()).all()
        creados = 0
        actualizados = 0

        for r in reservas:
            nombre_salon = (r.recurso_nombre or 'Salón').strip()
            if nombre_salon in alias_map:
                nombre_salon = alias_map[nombre_salon]

            s_id = r.sede_id
            if not s_id:
                if nombre_salon in ['704LS1', '803LS2', '804LS3', '801LS4', '703LS5']:
                    s_id = 1
                elif nombre_salon.startswith(('A', 'B', 'C', 'D')) or 'Niñera' in nombre_salon:
                    s_id = 2
                else:
                    s_id = 1

            rec_id = r.recurso_id
            if not rec_id or not db.session.get(Recurso, rec_id):
                match_rec = rec_map.get((nombre_salon.upper(), s_id)) or rec_map.get((nombre_salon.upper(), None))
                if match_rec:
                    rec_id = match_rec.id

            obs = (r.observaciones or '').strip()
            if obs and not obs.lower().startswith('reserva generada') and obs.lower() not in ['prueba automática', 'ok', 'prueba']:
                materia = obs
            elif r.nrc:
                materia = f"Clase NRC {r.nrc}"
            else:
                materia = r.programa or "Clase Académica"

            if r.hora_inicio and r.hora_fin:
                dt_ini = datetime.combine(date.min, r.hora_inicio)
                dt_fin = datetime.combine(date.min, r.hora_fin)
                duracion_seg = (dt_fin - dt_ini).total_seconds()
                horas_acad = round(duracion_seg / 3600.0, 2)
            else:
                horas_acad = 1.5

            jornada = r.jornada
            if not jornada and r.hora_inicio:
                if r.hora_inicio < time(13, 45):
                    jornada = 'MAÑANA'
                elif r.hora_inicio < time(18, 15):
                    jornada = 'TARDE'
                else:
                    jornada = 'NOCHE'
            elif jornada:
                jornada = jornada.upper()

            asistencia = 'Sí' if r.estado == 'Completada' else 'No'
            estado = 'Cancelada' if r.estado == 'Cancelada' else ('Realizada' if r.estado == 'Completada' else 'Programada')
            obs_final = f"NRC: {r.nrc} | {r.observaciones or ''}".strip(' |')

            clase_existente = ClaseSalaComputo.query.filter(
                ClaseSalaComputo.fecha == r.fecha,
                ClaseSalaComputo.salon == nombre_salon,
                ClaseSalaComputo.hora_inicio == r.hora_inicio
            ).first()

            if clase_existente:
                clase_existente.sede_id = s_id
                clase_existente.recurso_id = rec_id
                clase_existente.cedula_profesor = r.cedula_profesor
                clase_existente.nombre_profesor = r.nombre_profesor
                clase_existente.materia = materia
                clase_existente.horas_academicas = horas_acad
                clase_existente.jornada = jornada
                clase_existente.programa = r.programa
                clase_existente.programa_id = r.programa_id
                if not clase_existente.observaciones:
                    clase_existente.observaciones = obs_final
                actualizados += 1
            else:
                nueva = ClaseSalaComputo(
                    fecha=r.fecha,
                    hora_inicio=r.hora_inicio,
                    hora_fin=r.hora_fin,
                    sede_id=s_id,
                    recurso_id=rec_id,
                    salon=nombre_salon,
                    cedula_profesor=r.cedula_profesor,
                    nombre_profesor=r.nombre_profesor,
                    materia=materia,
                    asistencia=asistencia,
                    horas_academicas=horas_acad,
                    jornada=jornada,
                    num_estudiantes=None,
                    programa=r.programa,
                    programa_id=r.programa_id,
                    modalidad='Presencial',
                    estado=estado,
                    observaciones=obs_final
                )
                db.session.add(nueva)
                creados += 1

        db.session.commit()
        flash(f'Sincronización completada: {creados} nuevas clases creadas y {actualizados} actualizadas desde la lista de reservas.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error sincronizando reservas a clases: {e}")
        flash(f'Error al sincronizar reservas a clases: {str(e)}', 'danger')

    return redirect(url_for('salas_computo.dashboard_salas', tab='clases'))


# =========================================================================
# 6. GESTIÓN DE PRÁCTICA LIBRE ESTUDIANTIL
# =========================================================================

def verificar_disponibilidad_salon(salon, fecha, hora_inicio, hora_fin=None, recurso_id=None):
    """
    Verifica si un salón/laboratorio está libre para práctica estudiantil
    o si tiene una clase programada o reserva activa en ese horario.
    Retorna: (disponible: bool, mensaje: str, objeto_conflicto, tipo_conflicto: str)
    """
    if not salon and not recurso_id:
        return False, "Salón no especificado", None, None

    # Normalizar fechas y horas
    if isinstance(fecha, str):
        try:
            fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
        except ValueError:
            fecha = date.today()
            
    if isinstance(hora_inicio, str):
        try:
            hora_inicio = datetime.strptime(hora_inicio, '%H:%M').time()
        except ValueError:
            hora_inicio = datetime.now().time()

    if isinstance(hora_fin, str) and hora_fin:
        try:
            hora_fin = datetime.strptime(hora_fin, '%H:%M').time()
        except ValueError:
            hora_fin = None

    # 1. Verificar Clases Programadas (ClaseSalaComputo)
    query_clase = ClaseSalaComputo.query.filter(
        ClaseSalaComputo.fecha == fecha,
        ClaseSalaComputo.estado != 'Cancelada'
    )
    if recurso_id:
        query_clase = query_clase.filter(or_(ClaseSalaComputo.recurso_id == recurso_id, ClaseSalaComputo.salon.ilike(salon.strip())))
    else:
        query_clase = query_clase.filter(ClaseSalaComputo.salon.ilike(salon.strip()))

    if hora_fin:
        query_clase = query_clase.filter(
            ClaseSalaComputo.hora_inicio < hora_fin,
            ClaseSalaComputo.hora_fin > hora_inicio
        )
    else:
        query_clase = query_clase.filter(
            ClaseSalaComputo.hora_inicio <= hora_inicio,
            ClaseSalaComputo.hora_fin > hora_inicio
        )
    
    clase_conflicto = query_clase.first()
    if clase_conflicto:
        h_ini = clase_conflicto.hora_inicio.strftime('%H:%M')
        h_fin = clase_conflicto.hora_fin.strftime('%H:%M')
        msg = f"OCUPADO: Salón en clase de '{clase_conflicto.materia}' con el docente {clase_conflicto.nombre_profesor} ({h_ini} a {h_fin})."
        return False, msg, clase_conflicto, 'clase'

    # 2. Verificar Reservas Activas (Reserva)
    query_reserva = Reserva.query.filter(
        Reserva.fecha == fecha,
        Reserva.estado == 'Activa'
    )
    if recurso_id:
        query_reserva = query_reserva.filter(or_(Reserva.recurso_id == recurso_id, Reserva.recurso_nombre.ilike(salon.strip())))
    else:
        query_reserva = query_reserva.filter(Reserva.recurso_nombre.ilike(salon.strip()))

    if hora_fin:
        query_reserva = query_reserva.filter(
            Reserva.hora_inicio < hora_fin,
            Reserva.hora_fin > hora_inicio
        )
    else:
        query_reserva = query_reserva.filter(
            Reserva.hora_inicio <= hora_inicio,
            Reserva.hora_fin > hora_inicio
        )

    reserva_conflicto = query_reserva.first()
    if reserva_conflicto:
        h_ini = reserva_conflicto.hora_inicio.strftime('%H:%M')
        h_fin = reserva_conflicto.hora_fin.strftime('%H:%M')
        msg = f"OCUPADO: Salón reservado para {reserva_conflicto.nombre_profesor} ({reserva_conflicto.tipo_reserva or 'Reserva'}) de {h_ini} a {h_fin}."
        return False, msg, reserva_conflicto, 'reserva'

    # Salón completamente disponible
    return True, "Salón libre y disponible para práctica estudiantil.", None, None


@salas_computo_bp.route('/api/buscar-estudiante', methods=['GET'])
@login_required
def api_buscar_estudiante():
    """Búsqueda rápida de estudiantes por ID Banner, Cédula o Nombre para asignar práctica libre."""
    try:
        q = request.args.get('q', '').strip()
        if not q or len(q) < 2:
            return jsonify({'success': True, 'estudiantes': []})

        term = f"%{q}%"
        estudiantes = Estudiante.query.filter(
            or_(
                Estudiante.codigo_banner.ilike(term),
                Estudiante.documento.ilike(term),
                Estudiante.nombre_completo.ilike(term)
            )
        ).limit(10).all()

        resultados = []
        for e in estudiantes:
            prog_nombre = e.programa_rel.nombre if e.programa_rel else (e.atributo_programa or 'No registrado')
            sede_nom = e.sede.nombre if e.sede else (e.descripcion_sede or 'No asignada')
            resultados.append({
                'id': e.id,
                'codigo_banner': e.codigo_banner,
                'documento': e.documento or '',
                'nombre_completo': e.nombre_completo,
                'programa': prog_nombre,
                'sede_id': e.sede_id or (session.get('sede_id') or 1),
                'sede_nombre': sede_nom,
                'activo': e.activo
            })

        return jsonify({'success': True, 'estudiantes': resultados})
    except Exception as e:
        current_app.logger.error(f"Error buscando estudiante: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@salas_computo_bp.route('/api/verificar-disponibilidad', methods=['GET'])
@login_required
def api_verificar_disponibilidad():
    """Verificación en tiempo real de si un salón está libre o en clase."""
    try:
        salon = request.args.get('salon', '').strip()
        recurso_id = request.args.get('recurso_id', type=int)
        fecha_str = request.args.get('fecha', '').strip() or date.today().strftime('%Y-%m-%d')
        hora_inicio_str = request.args.get('hora_inicio', '').strip() or datetime.now().strftime('%H:%M')
        hora_fin_str = request.args.get('hora_fin', '').strip()

        # Si viene recurso_id pero no salón, buscar el nombre del salón
        if recurso_id and not salon:
            rec = Recurso.query.get(recurso_id)
            if rec:
                salon = rec.nombre

        disponible, mensaje, conflicto, tipo_conflicto = verificar_disponibilidad_salon(
            salon=salon,
            fecha=fecha_str,
            hora_inicio=hora_inicio_str,
            hora_fin=hora_fin_str,
            recurso_id=recurso_id
        )

        # Contar cuántos estudiantes están actualmente practicando en ese salón
        practicas_en_curso = 0
        if salon:
            practicas_en_curso = PracticaLibre.query.filter(
                PracticaLibre.salon.ilike(salon.strip()),
                PracticaLibre.fecha == datetime.strptime(fecha_str, '%Y-%m-%d').date(),
                PracticaLibre.estado == 'En Curso'
            ).count()

        return jsonify({
            'success': True,
            'disponible': disponible,
            'mensaje': mensaje,
            'tipo_conflicto': tipo_conflicto,
            'practicas_en_curso': practicas_en_curso,
            'salon': salon
        })
    except Exception as e:
        current_app.logger.error(f"Error verificando disponibilidad: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@salas_computo_bp.route('/practica-libre/registrar', methods=['POST'])
@login_required
@permiso_requerido('salas_computo', 'crear')
def registrar_practica_libre():
    """Registra el ingreso de un estudiante a práctica libre en un salón disponible."""
    try:
        datos = request.form
        
        codigo_banner = datos.get('codigo_banner', '').strip()
        nombre_estudiante = datos.get('nombre_estudiante', '').strip()
        programa_estudiante = datos.get('programa_estudiante', '').strip()
        estudiante_id = datos.get('estudiante_id', type=int)
        
        salon = datos.get('salon', '').strip()
        recurso_id = datos.get('recurso_id', type=int)
        sede_id = datos.get('sede_id', type=int) or session.get('sede_id') or 1
        numero_puesto = datos.get('numero_puesto', type=int)
        
        fecha_str = datos.get('fecha', '').strip()
        hora_inicio_str = datos.get('hora_inicio', '').strip()
        hora_fin_estimada_str = datos.get('hora_fin_estimada', '').strip()
        observaciones = datos.get('observaciones', '').strip()

        if not codigo_banner or not nombre_estudiante:
            flash('Debe ingresar el ID Banner y Nombre del estudiante.', 'warning')
            return redirect(url_for('salas_computo.dashboard_salas', tab='practica'))

        if not salon and not recurso_id:
            flash('Debe seleccionar el salón o laboratorio de cómputo.', 'warning')
            return redirect(url_for('salas_computo.dashboard_salas', tab='practica'))

        if recurso_id and not salon:
            rec = Recurso.query.get(recurso_id)
            if rec:
                salon = rec.nombre

        # Fecha y Hora
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else date.today()
        hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M').time() if hora_inicio_str else datetime.now().time()
        hora_fin_estimada = datetime.strptime(hora_fin_estimada_str, '%H:%M').time() if hora_fin_estimada_str else None

        # Si no se pasó estudiante_id pero existe en la base de datos por banner, asociarlo
        if not estudiante_id and codigo_banner:
            est_db = Estudiante.query.filter_by(codigo_banner=codigo_banner).first()
            if est_db:
                estudiante_id = est_db.id
                if not programa_estudiante and est_db.programa_rel:
                    programa_estudiante = est_db.programa_rel.nombre

        # VALIDACIÓN ESTRICTA: ¿El salón está libre o en clase?
        disponible, mensaje, conflicto, tipo = verificar_disponibilidad_salon(
            salon=salon,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin_estimada,
            recurso_id=recurso_id
        )

        if not disponible:
            flash(f'No se puede asignar práctica libre. {mensaje}', 'danger')
            return redirect(url_for('salas_computo.dashboard_salas', tab='practica'))

        # Obtener nombre de la sede
        sede_obj = Sede.query.get(sede_id) if sede_id else None
        sede_nombre = sede_obj.nombre if sede_obj else 'Principal'

        # Crear registro de práctica libre
        nueva_practica = PracticaLibre(
            estudiante_id=estudiante_id,
            codigo_banner=codigo_banner,
            nombre_estudiante=nombre_estudiante,
            programa_estudiante=programa_estudiante or 'No especificado',
            sede_id=sede_id,
            sede_nombre=sede_nombre,
            recurso_id=recurso_id,
            salon=salon,
            numero_puesto=numero_puesto,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin_estimada=hora_fin_estimada,
            estado='En Curso',
            auxiliar_registro=session.get('nombre_completo') or session.get('usuario') or 'Auxiliar',
            observaciones=observaciones
        )
        
        db.session.add(nueva_practica)
        db.session.commit()

        registrar_auditoria(
            modulo='salas_computo',
            entidad_tipo='PracticaLibre',
            entidad_id=str(nueva_practica.id),
            accion='CREAR_PRACTICA_LIBRE',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Práctica Libre asignada a {nombre_estudiante} (ID: {codigo_banner}) en {salon}' + (f' Puesto #{numero_puesto}' if numero_puesto else '')
        )

        flash(f'¡Práctica libre registrada con éxito para el estudiante {nombre_estudiante} en {salon}!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error registrando práctica libre: {e}")
        flash(f'Error al registrar la práctica libre: {str(e)}', 'danger')

    return redirect(url_for('salas_computo.dashboard_salas', tab='practica'))


@salas_computo_bp.route('/practica-libre/<int:id_practica>/finalizar', methods=['POST'])
@login_required
@permiso_requerido('salas_computo', 'editar')
def finalizar_practica_libre(id_practica):
    """Marca la finalización (salida) de una práctica libre registrando la hora exacta."""
    try:
        practica = PracticaLibre.query.get_or_404(id_practica)
        practica.hora_salida_real = datetime.now().time()
        practica.estado = 'Finalizada'
        
        obs = request.form.get('observaciones_salida', '').strip()
        if obs:
            practica.observaciones = (practica.observaciones or '') + f" [Salida: {obs}]"

        db.session.commit()

        registrar_auditoria(
            modulo='salas_computo',
            entidad_tipo='PracticaLibre',
            entidad_id=str(practica.id),
            accion='FINALIZAR_PRACTICA_LIBRE',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Práctica Libre finalizada: {practica.nombre_estudiante} en {practica.salon}'
        )

        flash(f'Práctica de {practica.nombre_estudiante} en {practica.salon} finalizada exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error finalizando práctica libre: {e}")
        flash(f'Error al finalizar la práctica: {str(e)}', 'danger')

    return redirect(url_for('salas_computo.dashboard_salas', tab='practica'))


@salas_computo_bp.route('/practica-libre/<int:id_practica>/cancelar', methods=['POST'])
@login_required
@permiso_requerido('salas_computo', 'editar')
def cancelar_practica_libre(id_practica):
    """Cancela un registro de práctica libre."""
    try:
        practica = PracticaLibre.query.get_or_404(id_practica)
        practica.estado = 'Cancelada'
        
        db.session.commit()

        registrar_auditoria(
            modulo='salas_computo',
            entidad_tipo='PracticaLibre',
            entidad_id=str(practica.id),
            accion='CANCELAR_PRACTICA_LIBRE',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Práctica Libre cancelada: {practica.nombre_estudiante} en {practica.salon}'
        )

        flash(f'Práctica de {practica.nombre_estudiante} cancelada.', 'info')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error cancelando práctica libre: {e}")
        flash(f'Error al cancelar la práctica: {str(e)}', 'danger')

    return redirect(url_for('salas_computo.dashboard_salas', tab='practica'))


@salas_computo_bp.route('/practica-libre/exportar', methods=['GET'])
@login_required
@permiso_requerido('salas_computo', 'ver')
def exportar_practicas_libres():
    """Exporta el reporte de prácticas libres a formato Excel."""
    try:
        fecha_filtro = request.args.get('practica_fecha', '').strip()
        salon_filtro = request.args.get('practica_salon', '').strip()
        estado_filtro = request.args.get('practica_estado', '').strip()
        busqueda = request.args.get('practica_busqueda', '').strip()
        sede_id = request.args.get('sede', '').strip()

        query = PracticaLibre.query
        if sede_id:
            query = query.filter_by(sede_id=int(sede_id))
        if fecha_filtro:
            query = query.filter(PracticaLibre.fecha == datetime.strptime(fecha_filtro, '%Y-%m-%d').date())
        if salon_filtro:
            query = query.filter(PracticaLibre.salon.ilike(f"%{salon_filtro}%"))
        if estado_filtro:
            query = query.filter_by(estado=estado_filtro)
        if busqueda:
            term = f"%{busqueda}%"
            query = query.filter(
                or_(
                    PracticaLibre.codigo_banner.ilike(term),
                    PracticaLibre.nombre_estudiante.ilike(term),
                    PracticaLibre.programa_estudiante.ilike(term)
                )
            )

        practicas = query.order_by(PracticaLibre.fecha.desc(), PracticaLibre.hora_inicio.desc()).all()

        data = []
        for p in practicas:
            duracion_min = ''
            if p.hora_inicio and p.hora_salida_real:
                t1 = datetime.combine(date.today(), p.hora_inicio)
                t2 = datetime.combine(date.today(), p.hora_salida_real)
                diff = (t2 - t1).total_seconds() / 60
                duracion_min = f"{int(diff)} min" if diff >= 0 else ''

            data.append({
                'ID': p.id,
                'Fecha': p.fecha.strftime('%Y-%m-%d') if p.fecha else '',
                'ID Banner / Código': p.codigo_banner,
                'Estudiante': p.nombre_estudiante,
                'Programa Académico': p.programa_estudiante or '',
                'Sede': p.sede_nombre or '',
                'Salón / Laboratorio': p.salon,
                'Puesto #': p.numero_puesto or 'General',
                'Hora Ingreso': p.hora_inicio.strftime('%H:%M') if p.hora_inicio else '',
                'Hora Estimada Fin': p.hora_fin_estimada.strftime('%H:%M') if p.hora_fin_estimada else '',
                'Hora Salida Real': p.hora_salida_real.strftime('%H:%M') if p.hora_salida_real else '',
                'Duración': duracion_min,
                'Estado': p.estado,
                'Auxiliar Responsable': p.auxiliar_registro,
                'Observaciones': p.observaciones or ''
            })

        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Prácticas Libres')
        output.seek(0)

        filename = f"Practicas_Libres_UNIMINUTO_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            output,
            download_name=filename,
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        current_app.logger.error(f"Error exportando prácticas libres: {e}")
        flash(f'Error al exportar prácticas libres: {str(e)}', 'danger')
        return redirect(url_for('salas_computo.dashboard_salas', tab='practica'))
