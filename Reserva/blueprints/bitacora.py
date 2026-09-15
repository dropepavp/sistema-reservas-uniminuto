"""
Blueprint de Bitácora de Movimientos
====================================

Módulo para visualizar y audit el registro detallado de todas las modificaciones
realizadas en el sistema por cada auxiliar/usuario.

Funcionalidades:
- Visualización de logs de auditoría filtrados
- Detalles de cambios (antes/después)
- Búsqueda avanzada por módulo, usuario, fecha, acción
- Exportación de reportes de auditoría
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash, send_file
from datetime import datetime, timedelta, date
from database import db, AuditLog, Auxiliar
import json
import io
import pandas as pd
from utils.export_helpers import exportar_df_excel, exportar_df_csv
from auth import login_required, admin_required

# Crear blueprint
bitacora_bp = Blueprint('bitacora', __name__, url_prefix='/bitacora')


@bitacora_bp.route('/')
@login_required
@admin_required
def dashboard_bitacora():
    """Dashboard principal de bitácora"""
    
    # Parámetros de búsqueda/filtro
    modulo = request.args.get('modulo', '')
    usuario = request.args.get('usuario', '')
    accion = request.args.get('accion', '')
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin = request.args.get('fecha_fin', '')
    pagina = request.args.get('page', 1, type=int)
    
    # Construir query base
    query = AuditLog.query
    
    # Aplicar filtros
    if modulo:
        query = query.filter_by(modulo=modulo)
    
    if usuario:
        query = query.filter_by(usuario_documento=usuario)
    
    if accion:
        query = query.filter_by(accion=accion)
    
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            query = query.filter(AuditLog.fecha >= fecha_inicio_obj)
        except ValueError:
            pass
    
    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            query = query.filter(AuditLog.fecha <= fecha_fin_obj)
        except ValueError:
            pass
    
    # Ordenar por fecha descendente
    query = query.order_by(AuditLog.fecha.desc(), AuditLog.hora.desc())
    
    # Paginación
    logs_paginados = query.paginate(page=pagina, per_page=50)
    logs = logs_paginados.items
    
    # Obtener lista de módulos, usuarios y acciones únicas para los filtros
    modulos_unicos = db.session.query(AuditLog.modulo).distinct().all()
    modulos_list = [m[0] for m in modulos_unicos if m[0]]
    
    usuarios_unicos = db.session.query(AuditLog.usuario_documento, AuditLog.usuario_nombre).distinct().all()
    usuarios_list = [(u[0], u[1] or u[0]) for u in usuarios_unicos]
    
    acciones_unicas = db.session.query(AuditLog.accion).distinct().all()
    acciones_list = [a[0] for a in acciones_unicas if a[0]]
    
    return render_template(
        'bitacora/dashboard.html',
        logs=logs,
        logs_paginados=logs_paginados,
        modulos_list=modulos_list,
        usuarios_list=usuarios_list,
        acciones_list=acciones_list,
        filtro_modulo=modulo,
        filtro_usuario=usuario,
        filtro_accion=accion,
        filtro_fecha_inicio=fecha_inicio,
        filtro_fecha_fin=fecha_fin,
        page=pagina,
        total_logs=query.count()
    )


@bitacora_bp.route('/detalles/<int:log_id>')
@login_required
@admin_required
def detalles_log(log_id):
    """Ver detalles completos de un log específico"""
    log = AuditLog.query.get_or_404(log_id)
    
    # Parsear JSON si existen
    datos_antes = None
    datos_despues = None
    
    try:
        if log.datos_antes:
            datos_antes = json.loads(log.datos_antes)
    except (json.JSONDecodeError, TypeError):
        datos_antes = log.datos_antes
    
    try:
        if log.datos_despues:
            datos_despues = json.loads(log.datos_despues)
    except (json.JSONDecodeError, TypeError):
        datos_despues = log.datos_despues
    
    return render_template(
        'bitacora/detalles.html',
        log=log,
        datos_antes=datos_antes,
        datos_despues=datos_despues
    )


@bitacora_bp.route('/usuario/<usuario_documento>')
@login_required
@admin_required
def movimientos_usuario(usuario_documento):
    """Ver todos los movimientos de un usuario específico"""
    usuario = Auxiliar.query.get_or_404(usuario_documento)
    
    pagina = request.args.get('page', 1, type=int)
    
    # Query de todos los logs del usuario
    query = AuditLog.query.filter_by(usuario_documento=usuario_documento)
    query = query.order_by(AuditLog.fecha.desc(), AuditLog.hora.desc())
    
    logs_paginados = query.paginate(page=pagina, per_page=50)
    logs = logs_paginados.items
    
    # Estadísticas del usuario
    total_acciones = query.count()
    acciones_por_modulo = db.session.query(
        AuditLog.modulo,
        db.func.count(AuditLog.id).label('cantidad')
    ).filter_by(usuario_documento=usuario_documento).group_by(AuditLog.modulo).all()
    
    acciones_por_tipo = db.session.query(
        AuditLog.accion,
        db.func.count(AuditLog.id).label('cantidad')
    ).filter_by(usuario_documento=usuario_documento).group_by(AuditLog.accion).all()
    
    return render_template(
        'bitacora/movimientos_usuario.html',
        usuario=usuario,
        logs=logs,
        logs_paginados=logs_paginados,
        total_acciones=total_acciones,
        acciones_por_modulo=acciones_por_modulo,
        acciones_por_tipo=acciones_por_tipo,
        page=pagina
    )


@bitacora_bp.route('/modulo/<modulo>')
@login_required
@admin_required
def movimientos_modulo(modulo):
    """Ver todos los movimientos de un módulo específico"""
    
    modulos_validos = ['prestamos', 'reservas', 'inventario', 'profesores', 'admin', 'estadisticas']
    if modulo not in modulos_validos:
        flash('Módulo no válido', 'danger')
        return redirect(url_for('bitacora.dashboard_bitacora'))
    
    pagina = request.args.get('page', 1, type=int)
    
    # Query de todos los logs del módulo
    query = AuditLog.query.filter_by(modulo=modulo)
    query = query.order_by(AuditLog.fecha.desc(), AuditLog.hora.desc())
    
    logs_paginados = query.paginate(page=pagina, per_page=50)
    logs = logs_paginados.items
    
    # Estadísticas del módulo
    total_acciones = query.count()
    acciones_por_usuario = db.session.query(
        AuditLog.usuario_documento,
        AuditLog.usuario_nombre,
        db.func.count(AuditLog.id).label('cantidad')
    ).filter_by(modulo=modulo).group_by(AuditLog.usuario_documento, AuditLog.usuario_nombre).all()
    
    acciones_por_tipo = db.session.query(
        AuditLog.accion,
        db.func.count(AuditLog.id).label('cantidad')
    ).filter_by(modulo=modulo).group_by(AuditLog.accion).all()
    
    return render_template(
        'bitacora/movimientos_modulo.html',
        modulo=modulo,
        logs=logs,
        logs_paginados=logs_paginados,
        total_acciones=total_acciones,
        acciones_por_usuario=acciones_por_usuario,
        acciones_por_tipo=acciones_por_tipo,
        page=pagina
    )


# --- export helpers -------------------------------------------------

def generar_pdf_tabla(df, titulo, nombre_archivo, columnas_mostrar=None):
    """Genera un PDF a partir de un DataFrame (copia simplificada de app.py)."""
    try:
        buffer = io.BytesIO()
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=18)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1
        )
        elements = []
        elements.append(Paragraph(titulo, title_style))
        elements.append(Spacer(1, 12))
        if columnas_mostrar:
            df_export = df[columnas_mostrar] if all(col in df.columns for col in columnas_mostrar) else df
        else:
            df_export = df
        data = [df_export.columns.tolist()]
        for _, row in df_export.iterrows():
            data.append([str(val) if pd.notna(val) else '' for val in row])
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return buffer
    except Exception:
        return None


@bitacora_bp.route('/export/<formato>')
@login_required
@admin_required
def export_bitacora(formato):
    """Exporta registros de bitácora filtrados en el formato especificado."""
    # extraer mismos filtros que el dashboard
    modulo = request.args.get('modulo', '')
    usuario = request.args.get('usuario', '')
    accion = request.args.get('accion', '')
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin = request.args.get('fecha_fin', '')
    query = AuditLog.query
    if modulo:
        query = query.filter_by(modulo=modulo)
    if usuario:
        query = query.filter_by(usuario_documento=usuario)
    if accion:
        query = query.filter_by(accion=accion)
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            query = query.filter(AuditLog.fecha >= fecha_inicio_obj)
        except ValueError:
            pass
    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            query = query.filter(AuditLog.fecha <= fecha_fin_obj)
        except ValueError:
            pass
    records = query.order_by(AuditLog.fecha.desc(), AuditLog.hora.desc()).all()
    if not records:
        flash('No hay registros para exportar con los filtros actuales.', 'info')
        return redirect(url_for('bitacora.dashboard_bitacora'))
    data = []
    for log in records:
        data.append({
            'Fecha': log.fecha.strftime('%Y-%m-%d') if log.fecha else '',
            'Hora': log.hora.strftime('%H:%M:%S') if log.hora else '',
            'Módulo': log.modulo,
            'Acción': log.accion,
            'Usuario Documento': log.usuario_documento,
            'Usuario Nombre': log.usuario_nombre,
            'Descripción': log.descripcion,
            'Entidad Tipo': log.entidad_tipo,
            'Entidad ID': log.entidad_id
        })
    df = pd.DataFrame(data)
    if formato.lower() == 'excel':
        return exportar_df_excel(df, sheet_name='Bitacora', prefix='bitacora')
    elif formato.lower() == 'csv':
        return exportar_df_csv(df, prefix='bitacora')
    elif formato.lower() == 'pdf':
        pdf_buffer = generar_pdf_tabla(df, 'Bitácora de Movimientos', 'bitacora.pdf')
        if pdf_buffer:
            return send_file(pdf_buffer,
                             mimetype='application/pdf',
                             download_name='bitacora.pdf',
                             as_attachment=True)
        else:
            flash('Error al generar el PDF.', 'danger')
            return redirect(url_for('bitacora.dashboard_bitacora'))
    else:
        flash('Formato de exportación no válido.', 'danger')
        return redirect(url_for('bitacora.dashboard_bitacora'))


@bitacora_bp.route('/api/estadisticas')
@login_required
@admin_required
def api_estadisticas():
    """API para obtener estadísticas generales de auditoría"""
    
    try:
        # Total de registros
        total_registros = AuditLog.query.count()

        
        # últimos 30 días
        fecha_hace_30 = date.today() - timedelta(days=30)
        registros_30_dias = AuditLog.query.filter(AuditLog.fecha >= fecha_hace_30).count()
        
        # Distribución por módulo
        distribucion_modulo = db.session.query(
            AuditLog.modulo,
            db.func.count(AuditLog.id).label('cantidad')
        ).group_by(AuditLog.modulo).all()
        
        # Distribución por acción
        distribucion_accion = db.session.query(
            AuditLog.accion,
            db.func.count(AuditLog.id).label('cantidad')
        ).group_by(AuditLog.accion).all()
        
        # Top 10 usuarios más activos
        top_usuarios = db.session.query(
            AuditLog.usuario_documento,
            AuditLog.usuario_nombre,
            db.func.count(AuditLog.id).label('cantidad')
        ).group_by(AuditLog.usuario_documento, AuditLog.usuario_nombre)\
            .order_by(db.func.count(AuditLog.id).desc())\
            .limit(10).all()
        
        # Últimos 7 días de movimientos
        fecha_hace_7 = date.today() - timedelta(days=7)
        movimientos_7_dias = db.session.query(
            AuditLog.fecha,
            db.func.count(AuditLog.id).label('cantidad')
        ).filter(AuditLog.fecha >= fecha_hace_7)\
            .group_by(AuditLog.fecha)\
            .order_by(AuditLog.fecha).all()
        
        return jsonify({
            'success': True,
            'total_registros': total_registros,
            'registros_30_dias': registros_30_dias,
            'distribucion_modulo': [
                {'modulo': m[0], 'cantidad': m[1]} for m in distribucion_modulo
            ],
            'distribucion_accion': [
                {'accion': a[0], 'cantidad': a[1]} for a in distribucion_accion
            ],
            'top_usuarios': [
                {
                    'usuario': u[0],
                    'nombre': u[1] or u[0],
                    'cantidad': u[2]
                } for u in top_usuarios
            ],
            'movimientos_7_dias': [
                {'fecha': str(m[0]), 'cantidad': m[1]} for m in movimientos_7_dias
            ]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
