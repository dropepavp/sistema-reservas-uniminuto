"""
Blueprint para gestión de profesores y datos académicos.
Incluye CRUD completo, importación/exportación y historial académico.
"""
from flask import Blueprint, render_template, request, redirect, flash, jsonify, send_file, url_for, session, current_app
import io
import pandas as pd
from datetime import datetime, date
from utils.export_helpers import exportar_df_excel, exportar_df_csv
from database import db, Profesor, PrestamoEquipo, Reserva, UserPermission, registrar_auditoria
from validators import DataValidator
from sqlalchemy import func, desc, asc, or_, cast, String
from auth import login_required, permiso_requerido

profesores_bp = Blueprint('profesores', __name__, url_prefix='/profesores')


@profesores_bp.route('/buscar')
@login_required
def api_buscar_profesores():
    """API para búsqueda de profesores con autocompletado."""
    try:
        query = request.args.get('q', '').strip()
        current_app.logger.info(f"Buscando profesores con query: '{query}'")
        
        if not query or len(query) < 2:
            current_app.logger.info("Query muy corto, retornando vacío")
            return jsonify({'success': False, 'results': []})
        
        # Buscar por cédula o nombre
        search_term = f"%{query}%"
        current_app.logger.info(f"Search term: '{search_term}'")
        
        profesores = Profesor.query.filter(
            or_(
                Profesor.nombre_completo.like(search_term),
                cast(Profesor.cedula, String).like(search_term)
            )
        ).limit(10).all()
        
        current_app.logger.info(f"Profesores encontrados: {len(profesores)}")
        
        results = [{
            'cedula': prof.cedula,
            'nombre_completo': prof.nombre_completo,
            'correo': prof.correo,
            'telefono': prof.telefono,
            'programa': prof.programa
        } for prof in profesores]
        
        current_app.logger.info(f"Resultados: {len(results)} profesores")
        return jsonify({
            'success': True,
            'results': results,
            'profesores': results
        })

    except Exception as e:
        current_app.logger.error(f"Error al buscar profesores: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'results': [], 'profesores': [], 'error': str(e)}), 500


@profesores_bp.route('/')
@login_required
@permiso_requerido('profesores', 'ver')
def profesores_main():
    """Página principal de gestión de profesores."""
    try:
        # Filtros y búsqueda
        programa_filtro = request.args.get('programa', '')
        busqueda = request.args.get('busqueda', '')
        ordenar_por = request.args.get('ordenar', 'nombre_completo')
        orden = request.args.get('orden', 'asc')
        
        # Query base
        query = Profesor.query
        
        # Aplicar filtros
        if programa_filtro:
            query = query.filter(Profesor.programa.ilike(f"%{programa_filtro}%"))

        if busqueda:
            search_term = f"%{busqueda}%"
            query = query.filter(
                or_(
                    Profesor.nombre_completo.ilike(search_term),
                    Profesor.correo.ilike(search_term),
                    Profesor.telefono.ilike(search_term),
                    cast(Profesor.cedula, String).like(search_term)
                )
            )
        
        # Ordenamiento
        if ordenar_por == 'cedula':
            query = query.order_by(desc(Profesor.cedula) if orden == 'desc' else asc(Profesor.cedula))
        elif ordenar_por == 'programa':
            query = query.order_by(desc(Profesor.programa) if orden == 'desc' else asc(Profesor.programa))
        else:  # nombre_completo por defecto
            query = query.order_by(desc(Profesor.nombre_completo) if orden == 'desc' else asc(Profesor.nombre_completo))
        
        profesores = query.all()
        
        # Estadísticas
        stats = calcular_estadisticas_profesores()
        
        # Programas únicos para el filtro
        programas = list(set([p.programa for p in Profesor.query.all() if p.programa]))
        programas.sort()
        
        return render_template('profesores.html',
                             profesores=profesores,
                             programas=programas,
                             stats=stats,
                             filtros={
                                 'programa': programa_filtro,
                                 'busqueda': busqueda,
                                 'ordenar': ordenar_por,
                                 'orden': orden
                             })
                             
    except Exception as e:
        flash('Error al cargar los profesores.', 'danger')
        return render_template('profesores.html', profesores=[], programas=[], stats={}, filtros={})

@profesores_bp.route('/agregar', methods=['POST'])
@login_required
@permiso_requerido('profesores', 'crear')
def agregar_profesor():
    """Agrega un nuevo profesor."""
    try:
        datos = request.json
        
        # Validar cédula
        cedula_valid, cedula_int, cedula_error = DataValidator.validate_cedula(datos.get('cedula'))
        if not cedula_valid:
            return jsonify({'success': False, 'message': cedula_error}), 400
        
        # Verificar que no exista
        if Profesor.query.get(cedula_int):
            return jsonify({'success': False, 'message': 'Ya existe un profesor con esa cédula'}), 409
        
        # Validar nombre completo
        nombre_valid, nombre_error = DataValidator.validate_string_field(
            datos.get('nombre_completo'), 'Nombre completo', min_length=3, max_length=150
        )
        if not nombre_valid:
            return jsonify({'success': False, 'message': nombre_error}), 400
        
        # Validar email (opcional)
        correo = datos.get('correo', '').strip()
        if correo:
            email_valid, email_error = DataValidator.validate_email(correo)
            if not email_valid:
                return jsonify({'success': False, 'message': email_error}), 400
            
            # Verificar que el email no esté en uso
            if Profesor.query.filter_by(correo=correo.lower()).first():
                return jsonify({'success': False, 'message': 'El correo ya está registrado'}), 409
        
        # Validar teléfono (opcional)
        telefono = datos.get('telefono', '').strip()
        if telefono:
            phone_valid, phone_error = DataValidator.validate_phone(telefono)
            if not phone_valid:
                return jsonify({'success': False, 'message': phone_error}), 400
        
        # Validar programa (opcional)
        programa_valid, programa_error = DataValidator.validate_string_field(
            datos.get('programa', ''), 'Programa', required=False, max_length=100
        )
        if not programa_valid:
            return jsonify({'success': False, 'message': programa_error}), 400
        
        # Crear el profesor
        nuevo_profesor = Profesor(
            cedula=cedula_int,
            nombre_completo=datos.get('nombre_completo').strip(),
            correo=correo.lower() if correo else None,
            telefono=telefono or None,
            programa=datos.get('programa', '').strip() or None
        )
        
        db.session.add(nuevo_profesor)
        db.session.commit()

        registrar_auditoria(
            modulo='profesores',
            entidad_tipo='Profesor',
            entidad_id=nuevo_profesor.cedula,
            accion='CREAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Creación de profesor {nuevo_profesor.nombre_completo}',
            datos_antes=None,
            datos_despues={
                'cedula': nuevo_profesor.cedula,
                'nombre_completo': nuevo_profesor.nombre_completo,
                'correo': nuevo_profesor.correo,
                'telefono': nuevo_profesor.telefono,
                'programa': nuevo_profesor.programa,
            }
        )

        return jsonify({
            'success': True,
            'message': 'Profesor agregado exitosamente',
            'profesor_id': nuevo_profesor.cedula
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@profesores_bp.route('/<int:cedula>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@permiso_requerido('profesores', 'editar')
def gestionar_profesor(cedula):
    """Obtiene, actualiza o elimina un profesor."""
    profesor = Profesor.query.get_or_404(cedula)
    
    if request.method == 'GET':
        # Calcular estadísticas con queries de agregación directas
        # (evita N+1 del lazy-load de profesor.prestamos y profesor.reservas)
        total_prestamos = PrestamoEquipo.query.filter_by(
            cedula_profesor=cedula
        ).count()
        prestamos_activos = PrestamoEquipo.query.filter_by(
            cedula_profesor=cedula, estado='Prestado'
        ).count()
        total_reservas = Reserva.query.filter_by(
            cedula_profesor=cedula
        ).count()
        reservas_activas = Reserva.query.filter_by(
            cedula_profesor=cedula, estado='Activa'
        ).count()

        profesor_data = {
            'cedula': profesor.cedula,
            'nombre_completo': profesor.nombre_completo,
            'correo': profesor.correo or '',
            'telefono': profesor.telefono or '',
            'programa': profesor.programa or '',
            'stats': {
                'total_prestamos':   total_prestamos,
                'total_reservas':    total_reservas,
                'prestamos_activos': prestamos_activos,
                'reservas_activas':  reservas_activas,
            }
        }
        return jsonify({'success': True, 'profesor': profesor_data})
    
    elif request.method == 'PUT':
        # Actualizar profesor
        try:
            datos = request.json
            
            # Validar nombre completo
            nombre_valid, nombre_error = DataValidator.validate_string_field(
                datos.get('nombre_completo'), 'Nombre completo', min_length=3, max_length=150
            )
            if not nombre_valid:
                return jsonify({'success': False, 'message': nombre_error}), 400
            
            # Validar email si se proporciona
            correo = datos.get('correo', '').strip()
            if correo:
                email_valid, email_error = DataValidator.validate_email(correo)
                if not email_valid:
                    return jsonify({'success': False, 'message': email_error}), 400
                
                # Verificar que el email no esté en uso por otro profesor
                otro_profesor = Profesor.query.filter(
                    Profesor.correo == correo.lower(),
                    Profesor.cedula != cedula
                ).first()
                if otro_profesor:
                    return jsonify({'success': False, 'message': 'El correo ya está registrado'}), 409
            
            # Validar teléfono si se proporciona
            telefono = datos.get('telefono', '').strip()
            if telefono:
                phone_valid, phone_error = DataValidator.validate_phone(telefono)
                if not phone_valid:
                    return jsonify({'success': False, 'message': phone_error}), 400
            
            # Validar programa
            programa_valid, programa_error = DataValidator.validate_string_field(
                datos.get('programa', ''), 'Programa', required=False, max_length=100
            )
            if not programa_valid:
                return jsonify({'success': False, 'message': programa_error}), 400
            
            datos_antes = {
                'nombre_completo': profesor.nombre_completo,
                'correo': profesor.correo,
                'telefono': profesor.telefono,
                'programa': profesor.programa,
            }

            # Actualizar campos
            profesor.nombre_completo = datos.get('nombre_completo').strip()
            profesor.correo = correo.lower() if correo else None
            profesor.telefono = telefono or None
            profesor.programa = datos.get('programa', '').strip() or None

            db.session.commit()

            datos_despues = {
                'nombre_completo': profesor.nombre_completo,
                'correo': profesor.correo,
                'telefono': profesor.telefono,
                'programa': profesor.programa,
            }

            registrar_auditoria(
                modulo='profesores',
                entidad_tipo='Profesor',
                entidad_id=profesor.cedula,
                accion='EDITAR',
                usuario_documento=session.get('usuario', ''),
                usuario_nombre=session.get('nombre_completo', ''),
                descripcion=f'Edición de profesor {profesor.nombre_completo}',
                datos_antes=datos_antes,
                datos_despues=datos_despues
            )

            return jsonify({'success': True, 'message': 'Profesor actualizado exitosamente'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500
    
    elif request.method == 'DELETE':
        # Eliminar profesor
        try:
            # Verificar si tiene préstamos activos
            prestamos_activos = PrestamoEquipo.query.filter_by(
                cedula_profesor=cedula,
                estado='Prestado'
            ).count()
            
            if prestamos_activos > 0:
                return jsonify({
                    'success': False,
                    'message': f'No se puede eliminar el profesor porque tiene {prestamos_activos} préstamo(s) activo(s)'
                }), 400
            
            # Verificar si tiene reservas activas
            reservas_activas = Reserva.query.filter_by(
                cedula_profesor=cedula,
                estado='Activa'
            ).count()
            
            if reservas_activas > 0:
                return jsonify({
                    'success': False,
                    'message': f'No se puede eliminar el profesor porque tiene {reservas_activas} reserva(s) activa(s)'
                }), 400
            
            # Verificar si tiene historial
            tiene_historial = (PrestamoEquipo.query.filter_by(cedula_profesor=cedula).first() is not None or
                              Reserva.query.filter_by(cedula_profesor=cedula).first() is not None)
            
            if tiene_historial:
                return jsonify({
                    'success': False,
                    'message': 'No se puede eliminar el profesor porque tiene historial de préstamos o reservas. Use la función de desactivar.'
                }), 400
            
            # Si no tiene historial, eliminar
            datos_antes = {
                'cedula': profesor.cedula,
                'nombre_completo': profesor.nombre_completo,
                'correo': profesor.correo,
                'telefono': profesor.telefono,
                'programa': profesor.programa,
            }

            db.session.delete(profesor)
            db.session.commit()

            registrar_auditoria(
                modulo='profesores',
                entidad_tipo='Profesor',
                entidad_id=cedula,
                accion='ELIMINAR',
                usuario_documento=session.get('usuario', ''),
                usuario_nombre=session.get('nombre_completo', ''),
                descripcion=f'Eliminación de profesor {datos_antes["nombre_completo"]}',
                datos_antes=datos_antes,
                datos_despues=None
            )

            return jsonify({'success': True, 'message': 'Profesor eliminado exitosamente'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@profesores_bp.route('/buscar')
@login_required
def buscar_profesor():
    """API para búsqueda rápida de profesores."""
    try:
        q = request.args.get('q', '').strip()
        if not q:
            return jsonify({'success': True, 'profesores': []})

        current_app.logger.info(f"Buscando profesor: {q}")
        
        # Búsqueda súper flexible
        term = f"%{q}%"
        profesores = Profesor.query.filter(
            or_(
                Profesor.nombre_completo.ilike(term),
                cast(Profesor.cedula, String).ilike(term)
            )
        ).limit(10).all()

        results = []
        for p in profesores:
            results.append({
                'cedula': p.cedula,
                'nombre_completo': p.nombre_completo,
                'correo': p.correo or '',
                'programa': p.programa or ''
            })

        return jsonify({
            'success': True,
            'profesores': results,
            'count': len(results)
        })
    except Exception as e:
        # Usar logging estándar si current_app falla por alguna razón
        import logging
        logging.error(f"Error búsqueda: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@profesores_bp.route('/historial/<int:cedula>')
@login_required
def historial_profesor(cedula):
    """Obtiene el historial completo de un profesor."""
    try:
        profesor = Profesor.query.get_or_404(cedula)
        
        # Obtener préstamos ordenados por fecha
        prestamos = PrestamoEquipo.query.filter_by(
            cedula_profesor=cedula
        ).order_by(PrestamoEquipo.fecha_prestamo.desc()).all()
        
        # Obtener reservas ordenadas por fecha
        reservas = Reserva.query.filter_by(
            cedula_profesor=cedula
        ).order_by(Reserva.fecha.desc()).all()
        
        # Estadísticas del profesor
        stats = {
            'total_prestamos': len(prestamos),
            'total_reservas': len(reservas),
            'prestamos_por_estado': {},
            'reservas_por_estado': {},
            'equipos_mas_utilizados': {},
            'recursos_mas_utilizados': {}
        }
        
        # Contar préstamos por estado
        for prestamo in prestamos:
            estado = prestamo.estado
            stats['prestamos_por_estado'][estado] = stats['prestamos_por_estado'].get(estado, 0) + 1
            
            # Contar equipos más utilizados
            equipo = prestamo.equipo_prestado
            stats['equipos_mas_utilizados'][equipo] = stats['equipos_mas_utilizados'].get(equipo, 0) + 1
        
        # Contar reservas por estado
        for reserva in reservas:
            estado = reserva.estado
            stats['reservas_por_estado'][estado] = stats['reservas_por_estado'].get(estado, 0) + 1
            
            # Contar recursos más utilizados
            recurso = f"{reserva.recurso_tipo} - {reserva.recurso_nombre}"
            stats['recursos_mas_utilizados'][recurso] = stats['recursos_mas_utilizados'].get(recurso, 0) + 1
        
        return render_template('profesor_historial.html',
                             profesor=profesor,
                             prestamos=prestamos,
                             reservas=reservas,
                             stats=stats)
                             
    except Exception as e:
        flash('Error al cargar el historial del profesor.', 'danger')
        return redirect(url_for('profesores.profesores_main'))

@profesores_bp.route('/exportar/<formato>')
@login_required
def exportar_profesores(formato):
    """Exporta la lista de profesores."""
    try:
        # Aplicar filtros si existen
        programa_filtro = request.args.get('programa')
        busqueda = request.args.get('busqueda')
        
        query = Profesor.query
        
        if programa_filtro:
            query = query.filter(Profesor.programa.ilike(f"%{programa_filtro}%"))
        
        if busqueda:
            search_term = f"%{busqueda}%"
            query = query.filter(
                or_(
                    Profesor.nombre_completo.ilike(search_term),
                    Profesor.correo.ilike(search_term),
                    Profesor.telefono.ilike(search_term)
                )
            )
        
        profesores = query.all()

        if not profesores:
            flash('No hay profesores para exportar.', 'info')
            return redirect(url_for('profesores.profesores_main'))

        # ── Conteos en 2 queries de agregación (evita N+1) ───────────────────
        cedulas = [p.cedula for p in profesores]

        prestamos_counts = dict(
            db.session.query(
                PrestamoEquipo.cedula_profesor,
                func.count(PrestamoEquipo.id_prestamo)
            ).filter(PrestamoEquipo.cedula_profesor.in_(cedulas))
             .group_by(PrestamoEquipo.cedula_profesor).all()
        )
        prestamos_activos_counts = dict(
            db.session.query(
                PrestamoEquipo.cedula_profesor,
                func.count(PrestamoEquipo.id_prestamo)
            ).filter(
                PrestamoEquipo.cedula_profesor.in_(cedulas),
                PrestamoEquipo.estado == 'Prestado'
            ).group_by(PrestamoEquipo.cedula_profesor).all()
        )
        reservas_counts = dict(
            db.session.query(
                Reserva.cedula_profesor,
                func.count(Reserva.id_reserva)
            ).filter(Reserva.cedula_profesor.in_(cedulas))
             .group_by(Reserva.cedula_profesor).all()
        )
        reservas_activas_counts = dict(
            db.session.query(
                Reserva.cedula_profesor,
                func.count(Reserva.id_reserva)
            ).filter(
                Reserva.cedula_profesor.in_(cedulas),
                Reserva.estado == 'Activa'
            ).group_by(Reserva.cedula_profesor).all()
        )

        # ── Construir filas del DataFrame ─────────────────────────────────────
        data = [{
            'Cédula':             p.cedula,
            'Nombre Completo':    p.nombre_completo,
            'Correo':             p.correo or '',
            'Teléfono':           p.telefono or '',
            'Programa':           p.programa or '',
            'Total Préstamos':    prestamos_counts.get(p.cedula, 0),
            'Total Reservas':     reservas_counts.get(p.cedula, 0),
            'Préstamos Activos':  prestamos_activos_counts.get(p.cedula, 0),
            'Reservas Activas':   reservas_activas_counts.get(p.cedula, 0),
        } for p in profesores]
        
        export_df = pd.DataFrame(data)

        if formato.lower() == 'excel':
            return exportar_df_excel(export_df, sheet_name='Profesores', prefix='profesores')
        elif formato.lower() == 'csv':
            return exportar_df_csv(export_df, prefix='profesores')
        else:
            flash('Formato no válido.', 'error')
            return redirect(url_for('profesores.profesores_main'))
    
    except Exception as e:
        flash('Error al exportar profesores.', 'danger')
        return redirect(url_for('profesores.profesores_main'))

def calcular_estadisticas_profesores():
    """Calcula estadísticas generales de profesores."""
    try:
        stats = {}
        
        # Total de profesores
        stats['total'] = Profesor.query.count()
        
        # Profesores por programa
        stats['por_programa'] = {}
        programas_query = db.session.query(
            Profesor.programa, func.count(Profesor.cedula)
        ).filter(Profesor.programa.isnot(None)).group_by(Profesor.programa).all()
        
        for programa, cantidad in programas_query:
            stats['por_programa'][programa] = cantidad
        
        # Profesores más activos (con más préstamos)
        stats['mas_activos'] = []
        activos_query = db.session.query(
            Profesor.nombre_completo, Profesor.cedula, func.count(PrestamoEquipo.id_prestamo).label('prestamos')
        ).join(PrestamoEquipo).group_by(
            Profesor.cedula, Profesor.nombre_completo
        ).order_by(func.count(PrestamoEquipo.id_prestamo).desc()).limit(10).all()
        
        for nombre, cedula, prestamos in activos_query:
            stats['mas_activos'].append({
                'nombre': nombre,
                'cedula': cedula,
                'prestamos': prestamos
            })
        
        return stats
        
    except Exception as e:
        return {}


