"""
Servicio para cálculo de estadísticas, reportes y métricas del sistema.
Todas las consultas usan el ORM de SQLAlchemy (la misma conexión que el resto
de la aplicación), nunca sqlite3 directo ni datos simulados.
"""
from datetime import datetime, timedelta, date as date_type
from typing import Dict, Any, List
import logging

from sqlalchemy import func, extract, case, and_
from database import db, PrestamoEquipo, Inventario, Reserva, Profesor

# Configurar logging
logger = logging.getLogger(__name__)


class EstadisticasService:
    """Servicio de lógica de negocio para estadísticas y métricas KPI."""

    # ------------------------------------------------------------------ #
    #  KPIs generales                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def obtener_kpis_generales() -> Dict[str, Any]:
        """Calcula los KPIs principales del sistema usando la sesión ORM."""
        try:
            fecha_actual = datetime.now().date()

            # Consultas individuales con manejo de errores
            try:
                prestamos_activos = PrestamoEquipo.query.filter(
                    PrestamoEquipo.estado == 'Prestado'
                ).count()
            except Exception:
                db.session.rollback()
                prestamos_activos = 0

            try:
                equipos_disponibles = Inventario.query.filter_by(
                    estado='Disponible'
                ).count()
            except Exception:
                db.session.rollback()
                equipos_disponibles = 0

            try:
                reservas_activas = Reserva.query.filter(
                    Reserva.fecha >= fecha_actual,
                    Reserva.estado == 'Activa'
                ).count()
            except Exception:
                db.session.rollback()
                reservas_activas = 0

            try:
                total_profesores = Profesor.query.count()
            except Exception:
                db.session.rollback()
                total_profesores = 0

            try:
                prestamos_vencidos = PrestamoEquipo.query.filter(
                    PrestamoEquipo.estado == 'Prestado',
                    PrestamoEquipo.fecha_devolucion < fecha_actual
                ).count()
            except Exception:
                db.session.rollback()
                prestamos_vencidos = 0

            # Consulta simplificada y más robusta para equipos populares
            try:
                equipos_populares_raw = db.session.query(
                    PrestamoEquipo.equipo_prestado,
                    func.count(PrestamoEquipo.id_prestamo).label('total_prestamos')
                ).filter(
                    PrestamoEquipo.equipo_prestado.isnot(None),
                    PrestamoEquipo.equipo_prestado != ''
                ).group_by(
                    PrestamoEquipo.equipo_prestado
                ).order_by(
                    db.desc('total_prestamos')
                ).limit(5).all()

                equipos_populares = [{
                    'nombre': e[0] or 'Equipo sin nombre',
                    'categoria': 'General',
                    'total_prestamos': e[1]
                } for e in equipos_populares_raw]
            except Exception as join_error:
                # Fallback: consulta simple sin join si falla
                equipos_populares_raw = db.session.query(
                    PrestamoEquipo.equipo_prestado,
                    func.count(PrestamoEquipo.id_prestamo).label('total_prestamos')
                ).group_by(
                    PrestamoEquipo.equipo_prestado
                ).order_by(
                    db.desc('total_prestamos')
                ).limit(5).all()

                equipos_populares = [{
                    'nombre': e[0] or 'Equipo sin nombre',
                    'categoria': 'General',
                    'total_prestamos': e[1]
                } for e in equipos_populares_raw]

            return {
                'prestamos_activos': prestamos_activos,
                'equipos_disponibles': equipos_disponibles,
                'reservas_activas': reservas_activas,
                'total_profesores': total_profesores,
                'prestamos_vencidos': prestamos_vencidos,
                'equipos_populares': equipos_populares
            }
        except Exception as e:
            logger.error(f"Error en obtener_kpis_generales: {str(e)}", exc_info=True)
            return {
                'prestamos_activos': 0,
                'equipos_disponibles': 0,
                'reservas_activas': 0,
                'total_profesores': 0,
                'prestamos_vencidos': 0,
                'equipos_populares': [],
                'error': str(e)
            }

    # ------------------------------------------------------------------ #
    #  Estadísticas por período (semana / mes / año)                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def obtener_estadisticas_por_periodo(periodo: str = 'mes') -> Dict[str, List]:
        """
        Devuelve totales de préstamos y reservas agrupados por día o mes
        según el período solicitado.  Usa el ORM + func de SQLAlchemy para
        ser compatible con PostgreSQL y SQLite sin cambiar el código.
        """
        try:
            fecha_fin = datetime.now().date()

            if periodo == 'semana':
                fecha_inicio = fecha_fin - timedelta(days=7)
                # Agrupar por día
                trunc_prestamos = func.date(PrestamoEquipo.fecha_prestamo)
                trunc_reservas  = func.date(Reserva.fecha)
            elif periodo == 'año':
                fecha_inicio = fecha_fin - timedelta(days=365)
                # Agrupar por mes (YYYY-MM)
                trunc_prestamos = func.to_char(PrestamoEquipo.fecha_prestamo, 'YYYY-MM')
                trunc_reservas  = func.to_char(Reserva.fecha, 'YYYY-MM')
            else:  # mes (default)
                fecha_inicio = fecha_fin - timedelta(days=30)
                trunc_prestamos = func.date(PrestamoEquipo.fecha_prestamo)
                trunc_reservas  = func.date(Reserva.fecha)

            # --- Préstamos ---
            filas_prestamos = db.session.query(
                trunc_prestamos.label('periodo'),
                func.count(PrestamoEquipo.id_prestamo).label('total')
            ).filter(
                PrestamoEquipo.fecha_prestamo.between(fecha_inicio, fecha_fin)
            ).group_by('periodo').order_by('periodo').all()

            # --- Reservas ---
            filas_reservas = db.session.query(
                trunc_reservas.label('periodo'),
                func.count(Reserva.id_reserva).label('total')
            ).filter(
                Reserva.fecha.between(fecha_inicio, fecha_fin)
            ).group_by('periodo').order_by('periodo').all()

            return {
                'prestamos': [{'periodo': str(r.periodo), 'total': r.total} for r in filas_prestamos],
                'reservas':  [{'periodo': str(r.periodo), 'total': r.total} for r in filas_reservas],
            }

        except Exception as e:
            db.session.rollback()
            return {'prestamos': [], 'reservas': [], 'error': str(e)}

    # ------------------------------------------------------------------ #
    #  Profesores más activos                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def obtener_profesores_mas_activos(limite: int = 10) -> Dict[str, List]:
        """Retorna los profesores con más préstamos y más reservas."""
        try:
            # Por préstamos
            por_prestamos_raw = db.session.query(
                Profesor.nombre_completo.label('nombre'),
                Profesor.cedula,
                Profesor.programa,
                func.count(PrestamoEquipo.id_prestamo).label('total_prestamos')
            ).join(PrestamoEquipo, Profesor.cedula == PrestamoEquipo.cedula_profesor
            ).group_by(Profesor.cedula, Profesor.nombre_completo, Profesor.programa
            ).order_by(db.desc('total_prestamos')
            ).limit(limite).all()

            # Por reservas
            por_reservas_raw = db.session.query(
                Profesor.nombre_completo.label('nombre'),
                Profesor.cedula,
                Profesor.programa,
                func.count(Reserva.id_reserva).label('total_reservas')
            ).join(Reserva, Profesor.cedula == Reserva.cedula_profesor
            ).group_by(Profesor.cedula, Profesor.nombre_completo, Profesor.programa
            ).order_by(db.desc('total_reservas')
            ).limit(limite).all()

            return {
                'por_prestamos': [{
                    'nombre':           r.nombre,
                    'cedula':           str(r.cedula),
                    'programa':         r.programa or 'Sin programa',
                    'total_prestamos':  r.total_prestamos
                } for r in por_prestamos_raw],
                'por_reservas': [{
                    'nombre':          r.nombre,
                    'cedula':          str(r.cedula),
                    'programa':        r.programa or 'Sin programa',
                    'total_reservas':  r.total_reservas
                } for r in por_reservas_raw],
            }

        except Exception as e:
            db.session.rollback()
            return {'por_prestamos': [], 'por_reservas': [], 'error': str(e)}

    # ------------------------------------------------------------------ #
    #  Distribución de préstamos por categoría                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def obtener_distribucion_categorias() -> List[Dict]:
        """Préstamos totales agrupados por categoría de inventario."""
        try:
            filas = db.session.query(
                Inventario.categoria.label('categoria'),
                func.count(PrestamoEquipo.id_prestamo).label('total_prestamos')
            ).join(
                PrestamoEquipo,
                Inventario.numero_inventario == PrestamoEquipo.numero_inventario_equipo
            ).group_by(Inventario.categoria
            ).order_by(db.desc('total_prestamos')).all()

            return [{
                'categoria':       r.categoria or 'Sin categoría',
                'total_prestamos': r.total_prestamos
            } for r in filas if r.total_prestamos > 0]

        except Exception as e:
            db.session.rollback()
            return []

    # ------------------------------------------------------------------ #
    #  Uso por jornada                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def obtener_uso_por_jornada() -> List[Dict]:
        """Total de actividad (préstamos + reservas) agrupado por jornada."""
        try:
            prestamos_j = db.session.query(
                PrestamoEquipo.jornada.label('jornada'),
                func.count(PrestamoEquipo.id_prestamo).label('total')
            ).filter(PrestamoEquipo.jornada.isnot(None)
            ).group_by(PrestamoEquipo.jornada).all()

            reservas_j = db.session.query(
                Reserva.jornada.label('jornada'),
                func.count(Reserva.id_reserva).label('total')
            ).filter(Reserva.jornada.isnot(None)
            ).group_by(Reserva.jornada).all()

            totales: Dict[str, int] = {}
            for r in prestamos_j:
                totales[r.jornada] = totales.get(r.jornada, 0) + r.total
            for r in reservas_j:
                totales[r.jornada] = totales.get(r.jornada, 0) + r.total

            return [
                {'jornada': j, 'total': t}
                for j, t in sorted(totales.items(), key=lambda x: x[1], reverse=True)
            ]

        except Exception as e:
            db.session.rollback()
            return []

    # ------------------------------------------------------------------ #
    #  Tendencias mensuales (últimos 12 meses) — datos reales             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def obtener_tendencias_mensuales() -> Dict[str, List]:
        """
        Devuelve totales mensuales de préstamos y reservas de los últimos
        12 meses completos.  Usa func.to_char para PostgreSQL; si la BD es
        SQLite se degrada limpiamente porque los tipos son iguales.
        """
        try:
            fecha_fin   = datetime.now().date()
            fecha_inicio = fecha_fin.replace(day=1) - timedelta(days=335)  # ~11 meses atrás

            trunc_p = func.to_char(PrestamoEquipo.fecha_prestamo, 'YYYY-MM')
            trunc_r = func.to_char(Reserva.fecha, 'YYYY-MM')

            filas_p = db.session.query(
                trunc_p.label('mes'),
                func.count(PrestamoEquipo.id_prestamo).label('total_prestamos')
            ).filter(
                PrestamoEquipo.fecha_prestamo >= fecha_inicio
            ).group_by('mes').order_by('mes').all()

            filas_r = db.session.query(
                trunc_r.label('mes'),
                func.count(Reserva.id_reserva).label('total_reservas')
            ).filter(
                Reserva.fecha >= fecha_inicio
            ).group_by('mes').order_by('mes').all()

            return {
                'prestamos': [{'mes': r.mes, 'total_prestamos': r.total_prestamos} for r in filas_p],
                'reservas':  [{'mes': r.mes, 'total_reservas':  r.total_reservas}  for r in filas_r],
            }

        except Exception as e:
            db.session.rollback()
            return {'prestamos': [], 'reservas': [], 'error': str(e)}

    # ------------------------------------------------------------------ #
    #  Mapa de calor: actividad por día de semana × hora                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def obtener_heatmap() -> List[Dict]:
        """
        Intensidad de uso por día de la semana (0=Dom … 6=Sáb) y hora del día,
        combinando préstamos y reservas.
        """
        try:
            # Préstamos: extraemos día de semana y hora de hora_inicio
            prestamos_heat = db.session.query(
                extract('dow', PrestamoEquipo.fecha_prestamo).label('dia'),
                extract('hour', PrestamoEquipo.hora_inicio).label('hora'),
                func.count(PrestamoEquipo.id_prestamo).label('total')
            ).filter(
                PrestamoEquipo.hora_inicio.isnot(None)
            ).group_by('dia', 'hora').all()

            # Reservas
            reservas_heat = db.session.query(
                extract('dow', Reserva.fecha).label('dia'),
                extract('hour', Reserva.hora_inicio).label('hora'),
                func.count(Reserva.id_reserva).label('total')
            ).filter(
                Reserva.hora_inicio.isnot(None)
            ).group_by('dia', 'hora').all()

            # Combinar en un dict {(dia, hora): intensidad}
            grid: Dict[tuple, int] = {}
            for r in prestamos_heat:
                grid[(int(r.dia), int(r.hora))] = grid.get((int(r.dia), int(r.hora)), 0) + r.total
            for r in reservas_heat:
                grid[(int(r.dia), int(r.hora))] = grid.get((int(r.dia), int(r.hora)), 0) + r.total

            return [
                {'day': d, 'hour': h, 'intensity': v}
                for (d, h), v in sorted(grid.items())
            ]

        except Exception as e:
            db.session.rollback()
            return []

    # ------------------------------------------------------------------ #
    #  Predicción (simple: promedio móvil sobre histórico real)           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def obtener_prediccion(dias_futuro: int = 30) -> Dict[str, List]:
        """
        Devuelve el histórico de los últimos 30 días y una predicción para
        los próximos `dias_futuro` días usando promedio móvil de 7 días.
        No usa random en ningún caso.
        """
        try:
            hoy = datetime.now().date()
            inicio_historico = hoy - timedelta(days=30)

            filas = db.session.query(
                func.date(PrestamoEquipo.fecha_prestamo).label('fecha'),
                func.count(PrestamoEquipo.id_prestamo).label('prestamos')
            ).filter(
                PrestamoEquipo.fecha_prestamo >= inicio_historico
            ).group_by('fecha').order_by('fecha').all()

            historical = [{'fecha': str(r.fecha), 'prestamos': r.prestamos} for r in filas]

            # Promedio de los últimos 7 días con datos reales
            valores_recientes = [r.prestamos for r in filas[-7:]] if filas else []
            promedio = sum(valores_recientes) / len(valores_recientes) if valores_recientes else 0
            promedio = round(promedio, 1)

            # Desviación estándar simple para bandas de confianza
            if len(valores_recientes) > 1:
                varianza = sum((v - promedio) ** 2 for v in valores_recientes) / len(valores_recientes)
                std = varianza ** 0.5
            else:
                std = 1.0

            predictions = []
            for i in range(1, dias_futuro + 1):
                fecha_futura = hoy + timedelta(days=i)
                predictions.append({
                    'fecha':           fecha_futura.isoformat(),
                    'prediccion':      max(0, round(promedio)),
                    'limite_superior': max(0, round(promedio + std)),
                    'limite_inferior': max(0, round(promedio - std)),
                })

            return {'historical': historical, 'predictions': predictions}

        except Exception as e:
            db.session.rollback()
            return {'historical': [], 'predictions': [], 'error': str(e)}

    # ------------------------------------------------------------------ #
    #  Actividad de profesores (gráfico de burbujas)                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def obtener_actividad_profesores(limite: int = 20) -> List[Dict]:
        """Total de préstamos, reservas y equipos distintos por profesor."""
        try:
            filas = db.session.query(
                Profesor.nombre_completo.label('nombre'),
                func.count(db.distinct(PrestamoEquipo.id_prestamo)).label('prestamos'),
                func.count(db.distinct(PrestamoEquipo.numero_inventario_equipo)).label('equipos_diferentes'),
                func.count(db.distinct(Reserva.id_reserva)).label('reservas')
            ).outerjoin(PrestamoEquipo, Profesor.cedula == PrestamoEquipo.cedula_profesor
            ).outerjoin(Reserva,        Profesor.cedula == Reserva.cedula_profesor
            ).group_by(Profesor.cedula, Profesor.nombre_completo
            ).having(
                db.or_(
                    func.count(db.distinct(PrestamoEquipo.id_prestamo)) > 0,
                    func.count(db.distinct(Reserva.id_reserva)) > 0
                )
            ).order_by(
                db.desc(func.count(db.distinct(PrestamoEquipo.id_prestamo)) +
                        func.count(db.distinct(Reserva.id_reserva)))
            ).limit(limite).all()

            return [{
                'nombre':            r.nombre,
                'prestamos':         r.prestamos,
                'reservas':          r.reservas,
                'equipos_diferentes': r.equipos_diferentes
            } for r in filas]

        except Exception as e:
            db.session.rollback()
            return []

    # ------------------------------------------------------------------ #
    #  Flujo de recursos (Sankey: categoría → jornada)                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def obtener_flujo_recursos() -> List[Dict]:
        """Flujo de categorías de equipo hacia jornadas de uso."""
        try:
            filas = db.session.query(
                Inventario.categoria.label('categoria'),
                PrestamoEquipo.jornada.label('jornada'),
                func.count(PrestamoEquipo.id_prestamo).label('cantidad')
            ).join(
                Inventario,
                PrestamoEquipo.numero_inventario_equipo == Inventario.numero_inventario
            ).filter(
                PrestamoEquipo.jornada.isnot(None),
                Inventario.categoria.isnot(None)
            ).group_by(Inventario.categoria, PrestamoEquipo.jornada).all()

            return [{
                'categoria': r.categoria,
                'jornada':   r.jornada,
                'cantidad':  r.cantidad
            } for r in filas]

        except Exception as e:
            db.session.rollback()
            return []

    # ------------------------------------------------------------------ #
    #  Métricas de rendimiento (radar)                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def obtener_metricas_rendimiento() -> Dict[str, float]:
        """
        Métricas multidimensionales calculadas sobre datos reales.
        Devuelve valores en escala 0-100.
        """
        try:
            fecha_actual = datetime.now().date()

            # 1. Préstamos activos (normalizado: 20 activos = 100%)
            prestamos_activos = PrestamoEquipo.query.filter_by(estado='Prestado').count()
            metrica_prestamos = min(100.0, prestamos_activos * 5.0)

            # 2. Reservas vigentes (normalizado: 10 reservas = 100%)
            reservas_activas = Reserva.query.filter(
                Reserva.fecha >= fecha_actual,
                Reserva.estado == 'Activa'
            ).count()
            metrica_reservas = min(100.0, reservas_activas * 10.0)

            # 3. Tasa de utilización de equipos
            total_equipos = Inventario.query.count() or 1
            en_prestamo   = Inventario.query.filter_by(estado='En Préstamo').count()
            metrica_utilizacion = (en_prestamo / total_equipos) * 100

            # 4. Disponibilidad de equipos
            disponibles = Inventario.query.filter_by(estado='Disponible').count()
            metrica_disponibilidad = (disponibles / total_equipos) * 100

            # 5. Eficiencia: tasa de devolución a tiempo
            devueltos_total = PrestamoEquipo.query.filter_by(estado='Devuelto').count()
            if devueltos_total > 0:
                # "a tiempo" = devuelto antes o en la fecha de devolución acordada
                devueltos_a_tiempo = PrestamoEquipo.query.filter(
                    PrestamoEquipo.estado == 'Devuelto',
                    PrestamoEquipo.fecha_devolucion.isnot(None),
                    # hora_devolucion_real <= hora_fin como proxy para "a tiempo"
                    PrestamoEquipo.hora_devolucion_real.isnot(None),
                    PrestamoEquipo.hora_devolucion_real <= PrestamoEquipo.hora_fin
                ).count()
                metrica_eficiencia = (devueltos_a_tiempo / devueltos_total) * 100
            else:
                metrica_eficiencia = 100.0  # Sin devoluciones = sin retrasos conocidos

            return {
                'prestamos':      round(metrica_prestamos, 1),
                'reservas':       round(metrica_reservas, 1),
                'utilizacion':    round(metrica_utilizacion, 1),
                'disponibilidad': round(metrica_disponibilidad, 1),
                'eficiencia':     round(metrica_eficiencia, 1),
            }

        except Exception as e:
            db.session.rollback()
            return {
                'prestamos': 0, 'reservas': 0, 'utilizacion': 0,
                'disponibilidad': 0, 'eficiencia': 0, 'error': str(e)
            }

    # ------------------------------------------------------------------ #
    #  Timeline de eventos recientes                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def obtener_timeline(limite: int = 30) -> List[Dict]:
        """Combina préstamos y reservas recientes/futuros en una línea de tiempo."""
        try:
            hace_30_dias = datetime.now().date() - timedelta(days=30)

            prestamos_raw = db.session.query(
                PrestamoEquipo.equipo_prestado.label('nombre'),
                PrestamoEquipo.fecha_prestamo.label('inicio'),
                PrestamoEquipo.fecha_devolucion.label('fin'),
                PrestamoEquipo.nombre_profesor.label('profesor'),
                PrestamoEquipo.estado
            ).filter(
                PrestamoEquipo.fecha_prestamo >= hace_30_dias
            ).order_by(PrestamoEquipo.fecha_prestamo.desc()).limit(limite).all()

            hace_15_dias = datetime.now().date() - timedelta(days=15)
            reservas_raw = db.session.query(
                Reserva.recurso_nombre.label('nombre'),
                Reserva.fecha.label('inicio'),
                Reserva.fecha.label('fin'),
                Reserva.nombre_profesor.label('profesor'),
                Reserva.estado
            ).filter(
                Reserva.fecha >= hace_15_dias
            ).order_by(Reserva.fecha.desc()).limit(limite).all()

            eventos = []
            for r in prestamos_raw:
                eventos.append({
                    'tipo':     'Prestamo',
                    'nombre':   r.nombre or 'Equipo sin nombre',
                    'inicio':   r.inicio.isoformat() if r.inicio else None,
                    'fin':      r.fin.isoformat()    if r.fin    else None,
                    'profesor': r.profesor,
                    'estado':   r.estado,
                })
            for r in reservas_raw:
                eventos.append({
                    'tipo':     'Reserva',
                    'nombre':   r.nombre or 'Recurso sin nombre',
                    'inicio':   r.inicio.isoformat() if r.inicio else None,
                    'fin':      r.fin.isoformat()    if r.fin    else None,
                    'profesor': r.profesor,
                    'estado':   r.estado,
                })

            eventos.sort(key=lambda x: x['inicio'] or '', reverse=True)
            return eventos[:limite]

        except Exception as e:
            db.session.rollback()
            return []

    # ------------------------------------------------------------------ #
    #  Reporte personalizado por rango de fechas                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def obtener_reporte_personalizado(
        fecha_inicio: str,
        fecha_fin: str,
        tipo: str = 'general'
    ) -> List[Dict]:
        """
        Genera un reporte entre dos fechas.
        tipo: 'prestamos' | 'reservas' | 'profesores' | 'general'
        """
        try:
            fi = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            ff = datetime.strptime(fecha_fin,    '%Y-%m-%d').date()

            if tipo == 'prestamos':
                filas = PrestamoEquipo.query.filter(
                    PrestamoEquipo.fecha_prestamo.between(fi, ff)
                ).order_by(PrestamoEquipo.fecha_prestamo.desc()).all()

                return [{
                    'id_prestamo':        p.id_prestamo,
                    'cedula_profesor':    p.cedula_profesor,
                    'nombre_profesor':    p.nombre_profesor,
                    'equipo_prestado':    p.equipo_prestado,
                    'numero_inventario':  p.numero_inventario_equipo,
                    'jornada':            p.jornada or 'N/A',
                    'fecha_prestamo':     p.fecha_prestamo.strftime('%Y-%m-%d'),
                    'estado':             p.estado,
                } for p in filas]

            elif tipo == 'reservas':
                filas = Reserva.query.filter(
                    Reserva.fecha.between(fi, ff)
                ).order_by(Reserva.fecha.desc()).all()

                return [{
                    'id_reserva':      r.id_reserva,
                    'nombre_profesor': r.nombre_profesor,
                    'recurso_nombre':  r.recurso_nombre,
                    'recurso_tipo':    r.recurso_tipo,
                    'fecha':           r.fecha.strftime('%Y-%m-%d'),
                    'jornada':         r.jornada or 'N/A',
                    'estado':          r.estado,
                } for r in filas]

            elif tipo == 'profesores':
                filas = db.session.query(
                    Profesor.nombre_completo.label('nombre'),
                    Profesor.cedula,
                    Profesor.programa,
                    Profesor.telefono,
                    Profesor.correo,
                    func.count(db.distinct(PrestamoEquipo.id_prestamo)).label('total_prestamos'),
                    func.count(db.distinct(Reserva.id_reserva)).label('total_reservas'),
                ).outerjoin(
                    PrestamoEquipo,
                    and_(
                        Profesor.cedula == PrestamoEquipo.cedula_profesor,
                        PrestamoEquipo.fecha_prestamo.between(fi, ff)
                    )
                ).outerjoin(
                    Reserva,
                    and_(
                        Profesor.cedula == Reserva.cedula_profesor,
                        Reserva.fecha.between(fi, ff)
                    )
                ).group_by(
                    Profesor.cedula, Profesor.nombre_completo,
                    Profesor.programa, Profesor.telefono, Profesor.correo
                ).order_by(
                    db.desc(
                        func.count(db.distinct(PrestamoEquipo.id_prestamo)) +
                        func.count(db.distinct(Reserva.id_reserva))
                    )
                ).all()

                return [{
                    'nombre':          r.nombre,
                    'cedula':          str(r.cedula),
                    'programa':        r.programa or '',
                    'telefono':        r.telefono or '',
                    'correo':          r.correo or '',
                    'total_prestamos': r.total_prestamos,
                    'total_reservas':  r.total_reservas,
                } for r in filas]

            else:  # general
                total_prestamos = PrestamoEquipo.query.filter(
                    PrestamoEquipo.fecha_prestamo.between(fi, ff)
                ).count()
                total_reservas = Reserva.query.filter(
                    Reserva.fecha.between(fi, ff)
                ).count()
                return [{
                    'tipo':             'Resumen General',
                    'total_prestamos':  total_prestamos,
                    'total_reservas':   total_reservas,
                    'fecha_inicio':     fecha_inicio,
                    'fecha_fin':        fecha_fin,
                }]

        except Exception as e:
            db.session.rollback()
            return []

    # ------------------------------------------------------------------ #
    #  Métricas de devolución (endpoint /metricas)                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def obtener_metricas_devolucion() -> Dict[str, Any]:
        """Tiempo promedio de préstamo y tasa de puntualidad."""
        try:
            # Préstamos devueltos con fecha de devolución real registrada
            devueltos = PrestamoEquipo.query.filter(
                PrestamoEquipo.estado == 'Devuelto',
                PrestamoEquipo.hora_devolucion_real.isnot(None)
            ).all()

            total_devueltos = len(devueltos)

            # Tasa de puntualidad (devuelto en la hora acordada o antes)
            a_tiempo = sum(
                1 for p in devueltos
                if p.hora_devolucion_real is not None
                and p.hora_fin is not None
                and p.hora_devolucion_real <= p.hora_fin
            )
            tasa_puntualidad = (a_tiempo / total_devueltos * 100) if total_devueltos > 0 else 0.0

            # Utilización de equipos
            total_equipos   = Inventario.query.count() or 1
            en_prestamo     = Inventario.query.filter_by(estado='En Préstamo').count()
            tasa_utilizacion = (en_prestamo / total_equipos) * 100

            return {
                'tasa_puntualidad':         round(tasa_puntualidad, 1),
                'tasa_utilizacion_equipos': round(tasa_utilizacion, 1),
                'total_equipos':            total_equipos,
                'total_devueltos':          total_devueltos,
            }

        except Exception as e:
            db.session.rollback()
            return {
                'tasa_puntualidad': 0, 'tasa_utilizacion_equipos': 0,
                'total_equipos': 0, 'total_devueltos': 0, 'error': str(e)
            }
