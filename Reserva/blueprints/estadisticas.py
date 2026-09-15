"""
Blueprint de Estadísticas
=========================

Módulo para generar estadísticas, reportes y análisis de datos del sistema.
Incluye dashboard interactivo, gráficos y métricas de rendimiento.

Toda la lógica de consulta vive en EstadisticasService, que usa el ORM
SQLAlchemy de la aplicación.  Este blueprint NO abre conexiones directas a
la base de datos ni genera datos simulados.
"""

from datetime import datetime
from flask import (
    Blueprint, render_template, request, jsonify, send_file, current_app
)
import io
import pandas as pd

from auth import login_required, permiso_requerido
from services.estadisticas_service import EstadisticasService
from database import PrestamoEquipo, Reserva, db
from utils.export_helpers import exportar_df_excel, exportar_df_csv
from config import SystemConstants
from sqlalchemy import func

estadisticas_bp = Blueprint('estadisticas', __name__, url_prefix='/estadisticas')


# ============================================================================
#  PÁGINAS
# ============================================================================

@estadisticas_bp.route('/')
@login_required
@permiso_requerido('estadisticas', 'ver')
def dashboard():
    """Dashboard principal de estadísticas."""
    return render_template('estadisticas/dashboard.html')


@estadisticas_bp.route('/reportes')
@login_required
@permiso_requerido('estadisticas', 'ver')
def reportes():
    """Página de reportes personalizados."""
    return render_template('estadisticas/reportes.html')


@estadisticas_bp.route('/metricas')
@login_required
@permiso_requerido('estadisticas', 'ver')
def metricas():
    """Página de métricas avanzadas."""
    return render_template('estadisticas/metricas.html')


@estadisticas_bp.route('/visualizaciones')
@login_required
@permiso_requerido('estadisticas', 'ver')
def visualizaciones():
    """Página de visualizaciones avanzadas."""
    return render_template('estadisticas/visualizaciones.html')


@estadisticas_bp.route('/historial-prestamos')
@login_required
@permiso_requerido('estadisticas', 'ver')
def historial_prestamos():
    """Historial completo de préstamos con paginación y filtros."""
    try:
        page     = request.args.get('page', 1, type=int)
        per_page = 50
        estado   = request.args.get('estado', '')
        jornada  = request.args.get('jornada', '')

        query = PrestamoEquipo.query.order_by(PrestamoEquipo.fecha_prestamo.desc())

        if estado:
            query = query.filter_by(estado=estado)
        if jornada:
            query = query.filter_by(jornada=jornada)

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        total_prestamos      = PrestamoEquipo.query.count()
        prestamos_activos    = PrestamoEquipo.query.filter_by(estado=SystemConstants.ESTADO_PRESTADO).count()
        prestamos_devueltos  = PrestamoEquipo.query.filter_by(estado=SystemConstants.ESTADO_DEVUELTO).count()

        return render_template(
            'estadisticas/historial_prestamos.html',
            prestamos       = paginated.items,
            page            = page,
            pages           = paginated.pages,
            total           = total_prestamos,
            activos         = prestamos_activos,
            devueltos       = prestamos_devueltos,
            estado_filtro   = estado,
            jornada_filtro  = jornada,
        )
    except Exception as e:
        db.session.rollback()
        return render_template('error.html', error=f'Error al cargar historial: {str(e)}'), 500


# ============================================================================
#  API — KPIs y resumen general
# ============================================================================

@estadisticas_bp.route('/api/kpis')
@login_required
@permiso_requerido('estadisticas', 'ver')
def api_kpis():
    """KPIs principales del sistema."""
    try:
        kpis = EstadisticasService.obtener_kpis_generales()
        
        if 'error' in kpis:
            current_app.logger.error(f"Error en servicio de estadísticas: {kpis['error']}")
            return jsonify({'success': False, 'message': kpis['error']}), 500
        
        # Asegurar que todos los campos estén presentes
        default_kpis = {
            'prestamos_activos': 0,
            'equipos_disponibles': 0,
            'reservas_activas': 0,
            'total_profesores': 0,
            'prestamos_vencidos': 0,
            'equipos_populares': []
        }
        
        # Combinar con valores predeterminados
        for key, value in default_kpis.items():
            if key not in kpis or kpis[key] is None:
                kpis[key] = value
        
        current_app.logger.info(f"KPIs generados exitosamente: {kpis}")
        return jsonify({'success': True, 'data': kpis})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error crítico en api_kpis: {str(e)}", exc_info=True)
        return jsonify({
            'success': False, 
            'message': 'Error interno al obtener KPIs',
            'data': {
                'prestamos_activos': 0,
                'equipos_disponibles': 0,
                'reservas_activas': 0,
                'total_profesores': 0,
                'prestamos_vencidos': 0,
                'equipos_populares': []
            }
        }), 500


@estadisticas_bp.route('/api/estadisticas-totales')
@login_required
@permiso_requerido('estadisticas', 'ver')
def estadisticas_totales():
    """Totales generales del sistema para el panel de resumen."""
    try:
        total_prestamos          = PrestamoEquipo.query.count()
        total_prestamos_activos  = PrestamoEquipo.query.filter_by(estado=SystemConstants.ESTADO_PRESTADO).count()
        total_prestamos_devueltos= PrestamoEquipo.query.filter_by(estado=SystemConstants.ESTADO_DEVUELTO).count()

        total_reservas          = Reserva.query.count()
        total_reservas_activas  = Reserva.query.filter_by(estado=SystemConstants.ESTADO_ACTIVA).count()

        from database import Inventario, Profesor
        total_equipos       = Inventario.query.count()
        equipos_disponibles = Inventario.query.filter_by(estado='Disponible').count()
        equipos_prestados   = Inventario.query.filter_by(estado='En Préstamo').count()
        total_profesores    = Profesor.query.count()

        horas_totales = db.session.query(
            func.sum(PrestamoEquipo.horas_academicas)
        ).scalar() or 0

        equipo_top = db.session.query(
            PrestamoEquipo.equipo_prestado,
            func.count(PrestamoEquipo.id_prestamo).label('cnt')
        ).group_by(PrestamoEquipo.equipo_prestado).order_by(
            func.count(PrestamoEquipo.id_prestamo).desc()
        ).first()

        profesor_top = db.session.query(
            PrestamoEquipo.nombre_profesor,
            func.count(PrestamoEquipo.id_prestamo).label('cnt')
        ).group_by(PrestamoEquipo.nombre_profesor).order_by(
            func.count(PrestamoEquipo.id_prestamo).desc()
        ).first()

        return jsonify({
            'success': True,
            'prestamos': {
                'total':                    total_prestamos,
                'activos':                  total_prestamos_activos,
                'devueltos':                total_prestamos_devueltos,
                'horas_academicas_totales': float(horas_totales),
            },
            'reservas': {
                'total':   total_reservas,
                'activas': total_reservas_activas,
            },
            'inventario': {
                'total_equipos':  total_equipos,
                'disponibles':    equipos_disponibles,
                'en_prestamo':    equipos_prestados,
            },
            'profesores': {
                'total':              total_profesores,
                'mas_activo':         profesor_top[0] if profesor_top else 'N/A',
                'cantidad_prestamos': profesor_top[1] if profesor_top else 0,
            },
            'equipos': {
                'mas_usado':          equipo_top[0] if equipo_top else 'N/A',
                'cantidad_prestamos': equipo_top[1] if equipo_top else 0,
            },
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
#  API — Gráficos temporales
# ============================================================================

@estadisticas_bp.route('/api/periodo/<periodo>')
@login_required
@permiso_requerido('estadisticas', 'ver')
def api_periodo(periodo):
    """Estadísticas por período: semana | mes | año."""
    PERIODOS_VALIDOS = {'semana', 'mes', 'año'}
    if periodo not in PERIODOS_VALIDOS:
        return jsonify({
            'success': False,
            'message': f'Período no válido. Use: {", ".join(PERIODOS_VALIDOS)}'
        }), 400

    data = EstadisticasService.obtener_estadisticas_por_periodo(periodo)
    if 'error' in data:
        return jsonify({'success': False, 'message': data['error']}), 500
    return jsonify({'success': True, 'data': data})


@estadisticas_bp.route('/api/tendencias')
@login_required
@permiso_requerido('estadisticas', 'ver')
def api_tendencias():
    """Tendencias mensuales de los últimos 12 meses (datos reales)."""
    data = EstadisticasService.obtener_tendencias_mensuales()
    if 'error' in data:
        return jsonify({'success': False, 'message': data['error']}), 500
    return jsonify({'success': True, 'data': data})


# ============================================================================
#  API — Profesores y categorías
# ============================================================================

@estadisticas_bp.route('/api/profesores-activos')
@login_required
@permiso_requerido('estadisticas', 'ver')
def api_profesores_activos():
    """Profesores más activos por préstamos y reservas."""
    limite = request.args.get('limite', 10, type=int)
    limite = max(1, min(limite, 50))          # clamp 1-50
    data   = EstadisticasService.obtener_profesores_mas_activos(limite)
    if 'error' in data:
        return jsonify({'success': False, 'message': data['error']}), 500
    return jsonify({'success': True, 'data': data})


@estadisticas_bp.route('/api/categorias')
@login_required
@permiso_requerido('estadisticas', 'ver')
def api_categorias():
    """Distribución de préstamos por categoría de equipo."""
    data = EstadisticasService.obtener_distribucion_categorias()
    return jsonify({'success': True, 'data': data})


@estadisticas_bp.route('/api/jornadas')
@login_required
@permiso_requerido('estadisticas', 'ver')
def api_jornadas():
    """Uso por jornada (mañana, tarde, noche)."""
    data = EstadisticasService.obtener_uso_por_jornada()
    return jsonify({'success': True, 'data': data})


# ============================================================================
#  API — Visualizaciones avanzadas
# ============================================================================

@estadisticas_bp.route('/api/heatmap')
@login_required
@permiso_requerido('estadisticas', 'ver')
def api_heatmap():
    """Mapa de calor: actividad por día de semana × hora del día."""
    data = EstadisticasService.obtener_heatmap()
    return jsonify({'success': True, 'data': data})


@estadisticas_bp.route('/api/prediction')
@login_required
@permiso_requerido('estadisticas', 'ver')
def api_prediction():
    """Predicción de demanda basada en promedio móvil real (sin datos aleatorios)."""
    data = EstadisticasService.obtener_prediccion(dias_futuro=30)
    if 'error' in data:
        return jsonify({'success': False, 'error': data['error']}), 500
    return jsonify({'success': True, 'data': data})


@estadisticas_bp.route('/api/profesores-actividad')
@login_required
@permiso_requerido('estadisticas', 'ver')
def api_profesores_actividad():
    """Actividad de profesores (préstamos, reservas, equipos distintos) para gráfico de burbujas."""
    data = EstadisticasService.obtener_actividad_profesores(limite=20)
    return jsonify({'success': True, 'data': data})


@estadisticas_bp.route('/api/flujo-recursos')
@login_required
@permiso_requerido('estadisticas', 'ver')
def api_flujo_recursos():
    """Flujo de recursos: categoría → jornada (diagrama Sankey)."""
    data = EstadisticasService.obtener_flujo_recursos()
    return jsonify({'success': True, 'data': data})


@estadisticas_bp.route('/api/rendimiento')
@login_required
@permiso_requerido('estadisticas', 'ver')
def api_rendimiento():
    """Métricas de rendimiento multidimensionales para gráfico radar."""
    data = EstadisticasService.obtener_metricas_rendimiento()
    if 'error' in data:
        return jsonify({'success': False, 'error': data['error']}), 500
    return jsonify({'success': True, 'data': data})


@estadisticas_bp.route('/api/timeline')
@login_required
@permiso_requerido('estadisticas', 'ver')
def api_timeline():
    """Timeline interactivo de préstamos y reservas recientes."""
    data = EstadisticasService.obtener_timeline(limite=30)
    return jsonify({'success': True, 'data': data})


# ============================================================================
#  API — Métricas de devolución
# ============================================================================

@estadisticas_bp.route('/api/metricas/rendimiento')
@login_required
@permiso_requerido('estadisticas', 'ver')
def api_metricas_rendimiento():
    """Tiempo promedio de préstamo, tasa de puntualidad y utilización de equipos."""
    data = EstadisticasService.obtener_metricas_devolucion()
    if 'error' in data:
        return jsonify({'success': False, 'message': data['error']}), 500
    return jsonify({'success': True, 'data': data})


# ============================================================================
#  API — Reportes personalizados
# ============================================================================

@estadisticas_bp.route('/api/reporte/personalizado', methods=['POST'])
@login_required
@permiso_requerido('estadisticas', 'ver')
def api_reporte_personalizado():
    """Genera un reporte entre dos fechas para un tipo dado."""
    datos = request.get_json() or {}

    fecha_inicio = datos.get('fecha_inicio', '').strip()
    fecha_fin    = datos.get('fecha_fin', '').strip()
    tipo         = datos.get('tipo', 'general').strip()

    if not fecha_inicio or not fecha_fin:
        return jsonify({'success': False, 'message': 'Fechas de inicio y fin son requeridas.'}), 400

    TIPOS_VALIDOS = {'prestamos', 'reservas', 'profesores', 'general'}
    if tipo not in TIPOS_VALIDOS:
        return jsonify({'success': False, 'message': f'Tipo no válido. Use: {", ".join(TIPOS_VALIDOS)}'}), 400

    try:
        resultado = EstadisticasService.obtener_reporte_personalizado(fecha_inicio, fecha_fin, tipo)
        return jsonify({'success': True, 'data': resultado})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Error interno al generar el reporte.'}), 500


# ============================================================================
#  Exportación a Excel / CSV
# ============================================================================

@estadisticas_bp.route('/api/exportar-estadisticas/<formato>')
@login_required
@permiso_requerido('estadisticas', 'ver')
def exportar_estadisticas(formato):
    """Exporta el historial completo de préstamos en Excel o CSV."""
    FORMATOS_VALIDOS = {'excel', 'csv'}
    if formato.lower() not in FORMATOS_VALIDOS:
        return jsonify({'success': False, 'message': 'Formato no válido. Use: excel o csv'}), 400

    try:
        prestamos = PrestamoEquipo.query.order_by(PrestamoEquipo.fecha_prestamo.desc()).all()

        if not prestamos:
            return jsonify({'success': False, 'message': 'No hay datos para exportar.'}), 400

        data_prestamos = [{
            'ID Préstamo':       p.id_prestamo,
            'Cédula Profesor':   p.cedula_profesor,
            'Profesor':          p.nombre_profesor,
            'Equipo':            p.equipo_prestado,
            'N° Inventario':     p.numero_inventario_equipo,
            'Jornada':           p.jornada or 'N/A',
            'Fecha Préstamo':    p.fecha_prestamo.strftime('%Y-%m-%d') if p.fecha_prestamo else '',
            'Hora Inicio':       p.hora_inicio.strftime('%H:%M') if p.hora_inicio else '',
            'Hora Fin':          p.hora_fin.strftime('%H:%M') if p.hora_fin else '',
            'Horas Académicas':  p.horas_academicas or 0,
            'Estado':            p.estado,
            'Auxiliar Entrega':  p.auxiliar_entrega or '',
            'Auxiliar Recibe':   p.auxiliar_recibe or '',
            'Ubicación':         p.ubicacion or '',
            'Observaciones':     p.observaciones or '',
        } for p in prestamos]

        df = pd.DataFrame(data_prestamos)

        if formato.lower() == 'excel':
            resumen = pd.DataFrame({
                'Métrica': [
                    'Total de Préstamos',
                    'Préstamos Activos',
                    'Préstamos Devueltos',
                    'Equipos Únicos',
                    'Profesores Únicos',
                    'Horas Académicas Totales',
                ],
                'Cantidad': [
                    len(prestamos),
                    sum(1 for p in prestamos if p.estado == SystemConstants.ESTADO_PRESTADO),
                    sum(1 for p in prestamos if p.estado == SystemConstants.ESTADO_DEVUELTO),
                    len({p.numero_inventario_equipo for p in prestamos}),
                    len({p.cedula_profesor for p in prestamos}),
                    sum(p.horas_academicas or 0 for p in prestamos),
                ],
            })
            return exportar_df_excel(
                df,
                sheet_name='Préstamos',
                prefix='estadisticas_prestamos',
                extra_sheets=[(resumen, 'Resumen')],
            )
        else:  # csv
            return exportar_df_csv(df, prefix='estadisticas_prestamos')

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error al exportar: {str(e)}'}), 500
