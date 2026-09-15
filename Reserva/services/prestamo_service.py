"""
Servicio para la lógica de negocio relacionada con préstamos de equipos.
"""
from datetime import datetime, time, date
from typing import List, Tuple, Optional, Dict, Any
from database import db, PrestamoEquipo, Inventario, Profesor
from config import SystemConstants
from validators import DataValidator, BusinessValidator

def extraer_numero_corto(numero_inventario):
    """Extrae solo el número del inventario (ej: LAP01 → 01, ADA01 → 01)"""
    if not numero_inventario:
        return ''
    
    # Convertir a string y extraer solo los dígitos
    import re
    numeros = re.findall(r'\d+', str(numero_inventario))
    if numeros:
        # Si hay múltiples números, tomar el último (generalmente el consecutivo)
        return numeros[-1].zfill(2)  # Asegurar que tenga al menos 2 dígitos
    return str(numero_inventario)


def normalizar_identificador(item):
    """Normaliza el identificador para mostrar (quita prefijos comunes)"""
    if not item:
        return ''
    
    item_str = str(item).upper().strip()
    
    # Patrones comunes de prefijos
    prefijos = ['LAP', 'ADA', 'TEC', 'HDMI', 'CNT', 'CTRL']
    
    for prefijo in prefijos:
        if item_str.startswith(prefijo):
            # Extraer solo la parte numérica
            import re
            numeros = re.findall(r'\d+', item_str)
            if numeros:
                return numeros[-1].zfill(2)
    
    # Si no coincide con ningún prefijo, devolver el número si existe
    import re
    numeros = re.findall(r'\d+', item_str)
    if numeros:
        return numeros[-1].zfill(2)
    
    return item_str


class PrestamoService:
    """Servicio para gestionar la lógica de préstamos de equipos."""
    
    @staticmethod
    def calcular_jornada_desde_hora(hora_str: str) -> str:
        """Calcula la jornada (Mañana, Tarde, Noche) a partir de una hora."""
        if not hora_str or not isinstance(hora_str, str):
            return 'N/A'
        
        try:
            hora_dt = datetime.strptime(hora_str.strip()[:5], '%H:%M').time()
            
            if hora_dt <= SystemConstants.JORNADA_MANANA_FIN:
                return 'MAÑANA'
            elif hora_dt <= SystemConstants.JORNADA_TARDE_FIN:
                return 'TARDE'
            else:
                return 'NOCHE'
        except (ValueError, TypeError):
            return 'N/A'
    
    @staticmethod
    def calcular_horas_academicas(hora_inicio_str: str, hora_fin_str: str) -> float:
        """Calcula la diferencia en horas entre una hora de inicio y fin."""
        if not hora_inicio_str or not hora_fin_str:
            return 0
        
        try:
            inicio_dt = datetime.strptime(str(hora_inicio_str).strip()[:5], '%H:%M')
            fin_dt = datetime.strptime(str(hora_fin_str).strip()[:5], '%H:%M')
            duracion = fin_dt - inicio_dt
            return round(duracion.total_seconds() / 3600, 2)
        except (ValueError, TypeError):
            return 0
    
    @staticmethod
    def dividir_prestamo_por_jornadas(hora_inicio: time, hora_fin: time) -> List[Tuple[time, time]]:
        """
        Divide un préstamo en segmentos según las jornadas académicas.
        
        **Mejora:** Calcula automáticamente qué jornadas (MAÑANA/TARDE/NOCHE) cubre el préstamo
        y crea un registro separado por jornada para mejor análisis y estadísticas.
        
        Args:
            hora_inicio: Hora de inicio del préstamo (time object)
            hora_fin: Hora de finalización del préstamo (time object)
            
        Returns:
            Lista de tuplas (inicio, fin) para cada segmento de jornada cubierto
            Ejemplo: préstamo 11:00-15:00 retorna [(11:00, 13:44), (14:00, 15:00)]
                    para MAÑANA y TARDE
        """
        if not (isinstance(hora_inicio, time) and isinstance(hora_fin, time)):
            return [(hora_inicio, hora_fin)]  # Fallback si tipos incorrectos
            
        segmentos = []
        current_start = hora_inicio
        
        while current_start < hora_fin:
            jornada_fin = None
            next_jornada_start = None
            
            # Determinar los límites del segmento actual según configuración de jornadas
            if current_start <= SystemConstants.JORNADA_MANANA_FIN:
                jornada_fin = SystemConstants.JORNADA_MANANA_FIN
                next_jornada_start = SystemConstants.JORNADA_TARDE_INICIO
            elif current_start <= SystemConstants.JORNADA_TARDE_FIN:
                jornada_fin = SystemConstants.JORNADA_TARDE_FIN
                next_jornada_start = SystemConstants.JORNADA_NOCHE_INICIO
            else:
                jornada_fin = SystemConstants.JORNADA_NOCHE_FIN
                next_jornada_start = None
            
            # El segmento termina en el mínimo entre fin de jornada y fin del préstamo
            segmento_fin = min(hora_fin, jornada_fin)
            segmentos.append((current_start, segmento_fin))
            
            # Si hay más tiempo y otra jornada, continuar; si no, terminar
            if hora_fin > jornada_fin and next_jornada_start:
                current_start = next_jornada_start
            else:
                break
        
        return segmentos
    
    @staticmethod
    def crear_prestamo(datos: Dict[str, Any], auxiliar_entrega: str) -> Tuple[bool, str]:
        """
        Crea un nuevo préstamo de uno o varios equipos con validaciones completas.
        
        **CARACTERÍSTICA MEJORADA:** Divide automáticamente préstamos que cruzan 
        múltiples jornadas académicas (MAÑANA/TARDE/NOCHE). Un préstamo de 11:00 a 15:00
        genera 2 registros: uno para MAÑANA (11:00-13:44) y otro para TARDE (14:00-15:00).
        Esto mejora reportes y análisis estadísticos por jornada.
        
        Args:
            datos: Diccionario con los datos del préstamo:
                - cedula: Cédula del profesor
                - items: Lista de números de inventario a prestar
                - hora_inicio: Hora de inicio (HH:MM)
                - hora_fin: Hora de finalización (HH:MM)
                - ubicacion: Ubicación del préstamo (opcional)
                - observaciones: Observaciones (opcional)
            auxiliar_entrega: Nombre del auxiliar que entrega el equipo
            
        Returns:
            Tuple con (éxito: bool, mensaje: str)
            
        Example:
            >>> datos = {
            ...     'cedula': '1001234567',
            ...     'items': ['INV001', 'INV002'],
            ...     'hora_inicio': '11:00',
            ...     'hora_fin': '15:00',
            ...     'ubicacion': 'Laboratorio 1'
            ... }
            >>> success, msg = PrestamoService.crear_prestamo(datos, 'Juan Pérez')
            >>> # Si éxito, genera 2 registros (MAÑANA y TARDE) por cada equipo
        """
        try:
            # Obtener lista de items
            lista_inventario = datos.get('items', [])
            # Compatibilidad con versión anterior (un solo item)
            if not lista_inventario and datos.get('numero_inventario'):
                lista_inventario = [datos.get('numero_inventario')]
                
            if not lista_inventario:
                return False, 'Debe seleccionar al menos un equipo para el préstamo', None
            
            # Validar cédula del profesor
            cedula_valid, cedula_int, cedula_error = DataValidator.validate_cedula(datos.get('cedula'))
            if not cedula_valid:
                return False, cedula_error, None
            
            # Buscar profesor
            profesor = Profesor.query.get(cedula_int)
            if not profesor:
                return False, f'Profesor con cédula {cedula_int} no encontrado', None
            
            if not datos.get('hora_inicio'):
                datos['hora_inicio'] = datetime.now().strftime('%H:%M')
            
            # Validar horarios
            hora_inicio_valid, hora_inicio_obj, hora_inicio_error = DataValidator.validate_time(datos.get('hora_inicio'))
            if not hora_inicio_valid:
                return False, hora_inicio_error, None
            
            hora_fin_valid, hora_fin_obj, hora_fin_error = DataValidator.validate_time(datos.get('hora_fin'))
            if not hora_fin_valid:
                return False, hora_fin_error, None
            
            # Validar rango de tiempo
            range_valid, range_error = DataValidator.validate_time_range(hora_inicio_obj, hora_fin_obj)
            if not range_valid:
                return False, range_error, None
            
            # Dividir préstamo por jornadas
            segmentos = PrestamoService.dividir_prestamo_por_jornadas(hora_inicio_obj, hora_fin_obj)
            if not segmentos:
                return False, 'No se pudieron crear segmentos válidos para el préstamo', None
            
            fecha_prestamo = date.today()
            todos_prestamos = []
            primer_id_grupo = None
            sede_id = None

            # Mapa de cantidades solicitadas: { num_inventario: cantidad }
            # Puede venir como lista simple ['INV001'] o lista de dicts [{'numero': 'INV001', 'cantidad': 2}]
            cantidades_map = {}
            items_limpios = []
            for entry in lista_inventario:
                if isinstance(entry, dict):
                    num = str(entry.get('numero', '')).strip()
                    cant = int(entry.get('cantidad', 1))
                    estado_item = entry.get('estado_devolucion', SystemConstants.ESTADO_PRESTADO)
                else:
                    num = str(entry).strip()
                    cant = int(datos.get('cantidad', 1))
                    estado_item = SystemConstants.ESTADO_PRESTADO
                if num:
                    items_limpios.append(num)
                    cantidades_map[num] = {'cantidad': cant, 'estado': estado_item}

            for num_inv in items_limpios:
                map_item = cantidades_map.get(num_inv, {})
                cantidad_solicitada = map_item.get('cantidad', 1)
                estado_final = map_item.get('estado', SystemConstants.ESTADO_PRESTADO)

                # Buscar equipo en inventario
                identificador = str(num_inv).strip()
                item = Inventario.query.filter_by(numero_inventario=identificador).first()
                if not item:
                    # Fallback: permitir prestar por PLACA ACTIVO (activo_fijo)
                    item = Inventario.query.filter_by(activo_fijo=identificador).first()
                if not item:
                    # Fallback por número corto
                    item = Inventario.query.filter(
                        db.or_(
                            Inventario.numero_inventario.ilike(f'%{identificador}'),
                            Inventario.activo_fijo.ilike(f'%{identificador}')
                        )
                    ).first()
                if not item:
                    return False, f'Equipo "{identificador}" no encontrado en inventario', None

                # Siempre trabajamos con el numero_inventario real (FK)
                num_inv = item.numero_inventario
                if not num_inv:
                    return False, f'El equipo "{identificador}" no tiene número de inventario registrado', None
                
                # Validación según tipo de gestión
                if item.es_por_cantidad:
                    disponible = item.cantidad_disponible or 0
                    if disponible <= 0:
                        return False, f'No hay stock disponible de "{item.item}"', None
                    if cantidad_solicitada > disponible:
                        return False, f'Solo hay {disponible} unidades disponibles de "{item.item}" (solicitó {cantidad_solicitada})', None
                else:
                    if item.estado != 'Disponible':
                        return False, f'El equipo "{item.item}" ({num_inv}) ya se encuentra prestado o no está disponible', None
                
                # Sede del préstamo (usamos la del primer equipo)
                if not sede_id and item.bodega:
                    sede_id = item.bodega.sede_id

                # Validar conflictos de horarios en la misma fecha (Para equipos únicos)
                if not item.es_por_cantidad:
                    for inicio, fin in segmentos:
                        overlapping = PrestamoEquipo.query.filter(
                            PrestamoEquipo.numero_inventario_equipo == num_inv,
                            PrestamoEquipo.estado == SystemConstants.ESTADO_PRESTADO,
                            PrestamoEquipo.fecha_prestamo == fecha_prestamo,
                            PrestamoEquipo.hora_inicio < fin,
                            PrestamoEquipo.hora_fin > inicio
                        ).first()
                        if overlapping:
                            return False, f'El equipo "{item.item}" ya está prestado de {overlapping.hora_inicio.strftime("%H:%M")} a {overlapping.hora_fin.strftime("%H:%M")}', None


                # Crear descripción del equipo con validación de serial y número corto
                serial_valido = None
                if item.serial:
                    serial_str = str(item.serial).strip().lower()
                    # Excluir valores inválidos comunes
                    if serial_str not in ['nan', 'undefined', 'null', 'none', ''] and serial_str != 'nan':
                        serial_valido = item.serial
                
                # Usar número corto para el identificador
                numero_corto = extraer_numero_corto(item.numero_inventario)
                
                equipo_desc = f"{item.item} ({serial_valido or numero_corto})"
                if item.es_por_cantidad:
                    equipo_desc = f"{item.item} (x{cantidad_solicitada})"
                
                # Crear UN SOLO registro por equipo (sin dividir por jornadas)
                # Usar la hora original completa del préstamo
                p = PrestamoEquipo(
                    cedula_profesor=cedula_int,
                    nombre_profesor=profesor.nombre_completo,
                    equipo_prestado=equipo_desc,
                    numero_inventario_equipo=num_inv,
                    cantidad_prestada=map_item.get('cantidad', 1),
                    ubicacion_id=datos.get('ubicacion_id') if datos.get('ubicacion_id') else None,
                    recurso_id=datos.get('recurso_id') if datos.get('recurso_id') else None,
                    ubicacion=datos.get('ubicacion', '').strip(),
                    fecha_prestamo=fecha_prestamo,
                    jornada=PrestamoService.calcular_jornada_desde_hora(hora_inicio_obj.strftime('%H:%M')),
                    hora_inicio=hora_inicio_obj,
                    hora_fin=hora_fin_obj,
                    horas_academicas=PrestamoService.calcular_horas_academicas(
                        hora_inicio_obj.strftime('%H:%M'), hora_fin_obj.strftime('%H:%M')
                    ),
                    auxiliar_entrega=auxiliar_entrega,
                    observaciones=datos.get('observaciones', '').strip(),
                    estado=estado_final,
                    sede_id=int(datos.get('sede_id')) if datos.get('sede_id') else (item.bodega.sede_id if item.bodega else None)
                )
                
                if estado_final == SystemConstants.ESTADO_DEVUELTO:
                    # Normalizar campos de devolución: usar fecha_devolucion (Date) y hora_devolucion_real (Time)
                    p.fecha_devolucion = date.today()
                    p.hora_devolucion_real = datetime.now().time()
                    p.auxiliar_recibe = auxiliar_entrega

                if estado_final == SystemConstants.ESTADO_PRESTADO:
                    if item.es_por_cantidad:
                        item.cantidad_disponible = (item.cantidad_disponible or 0) - map_item.get('cantidad', 1)
                        if item.cantidad_disponible <= 0:
                            item.estado = 'En Préstamo'
                    else:
                        item.estado = 'En Préstamo'

                todos_prestamos.append(p)

            # Guardar todos los préstamos
            db.session.add_all(todos_prestamos)
            db.session.flush() # Para obtener IDs

            # Asignar el mismo ID de grupo a TODOS los registros de este préstamo múltiple
            id_grupo = todos_prestamos[0].id_prestamo
            for p in todos_prestamos:
                p.id_grupo_prestamo = id_grupo

            db.session.commit()
            
            # Emitir notificación de nuevo préstamo
            try:
                from services.notification_service import NotificationService
                for p in todos_prestamos:
                    NotificationService.notify_prestamo_creado(
                        prestamo_id=p.id_prestamo,
                        equipo=p.equipo_prestado,
                        profesor=p.nombre_profesor,
                        url=f'/prestamos/{p.id_prestamo}'
                    )
                    # Solo notificar el primero para no spam
                    break
            except Exception as e:
                print(f"Error al emitir notificación: {e}")
            
            return True, f'Préstamo registrado exitosamente ({len(items_limpios)} equipos, {len(todos_prestamos)} registros)', id_grupo

        except Exception as e:
            db.session.rollback()
            return False, f'Error al procesar préstamo: {str(e)}', None
    
    @staticmethod
    def devolver_prestamo(id_prestamo: int, auxiliar_recibe: str, items_a_devolver: Optional[List[str]] = None, observaciones_devolucion: str = '') -> Tuple[bool, str, Optional[Dict]]:
        """
        Marca un préstamo como devuelto. Soporta devoluciones parciales y registro de novedades.
        
        Args:
            id_prestamo: ID del préstamo a devolver (puede ser el id_grupo_prestamo)
            auxiliar_recibe: Nombre del auxiliar que recibe
            items_a_devolver: Lista opcional de numero_inventario_equipo a devolver. Si es None, devuelve todo el grupo.
            observaciones_devolucion: Novedades o comentarios de la devolución.
            
        Returns:
            Tuple con (éxito, mensaje, datos_devolucion)
        """
        try:
            prestamo = PrestamoEquipo.query.get(id_prestamo)

            # Determinar id_grupo_buscar: si existe el registro, usar su id_grupo_prestamo (o su propia PK si no tiene grupo);
            # en caso contrario, asumir que la entrada proporcionada puede ser un id_grupo
            if prestamo:
                id_grupo_buscar = getattr(prestamo, 'id_grupo_prestamo', None) or prestamo.id_prestamo
            else:
                id_grupo_buscar = id_prestamo

            # Buscar todos los préstamos del grupo (préstamos activos)
            prestamos_grupo = PrestamoEquipo.query.filter(
                db.or_(
                    PrestamoEquipo.id_grupo_prestamo == id_grupo_buscar,
                    PrestamoEquipo.id_prestamo == id_grupo_buscar
                ),
                PrestamoEquipo.estado == SystemConstants.ESTADO_PRESTADO
            ).all()

            # Elegir un representante para mensajes y datos de salida: preferir el registro encontrado por PK,
            # si no existe usar el primer préstamo activo del grupo (si hay)
            representante = prestamo if prestamo else (prestamos_grupo[0] if prestamos_grupo else None)
            
            if not prestamos_grupo:
                return False, 'Todos los equipos del préstamo ya fueron devueltos o no existe', None
                
            # Si se especificaron equipos, filtrar el grupo comparando como strings
            if items_a_devolver and len(items_a_devolver) > 0:
                items_str = [str(i).strip() for i in items_a_devolver]
                prestamos_grupo = [p for p in prestamos_grupo if str(p.numero_inventario_equipo).strip() in items_str]
                
            if not prestamos_grupo:
                return False, 'Ningún equipo seleccionado para devolver está activo en este préstamo', None
            
            # Marcar como devueltos
            now = datetime.now()
            hora_devolucion = now.time()
            fecha_devolucion = now.date()
            
            # Recopilar todos los números de inventario únicos devueltos para liberarlos
            numeros_inventario = set()
            # Mapa de cantidad total a devolver por numero_inventario
            cantidades_a_devolver = {}
            
            for p in prestamos_grupo:
                p.estado = SystemConstants.ESTADO_DEVUELTO
                p.hora_devolucion_real = hora_devolucion
                p.fecha_devolucion = fecha_devolucion
                p.auxiliar_recibe = auxiliar_recibe
                if observaciones_devolucion:
                    obs_actual = p.observaciones or ""
                    separador = "\n" if obs_actual else ""
                    p.observaciones = f"{obs_actual}{separador}Devolución: {observaciones_devolucion}"
                    
                if p.numero_inventario_equipo:
                    numeros_inventario.add(p.numero_inventario_equipo)
                    # Acumular cantidad a devolver (solo contamos 1 segmento por grupo para no duplicar)
                    if p.numero_inventario_equipo not in cantidades_a_devolver:
                        cantidades_a_devolver[p.numero_inventario_equipo] = p.cantidad_prestada or 1
            
            # Actualizar estado/stock de TODOS los equipos devueltos en inventario
            for num_inv in numeros_inventario:
                item = Inventario.query.filter_by(numero_inventario=num_inv).first()
                if not item:
                    continue
                if item.es_por_cantidad:
                    # Restituir la cantidad prestada
                    cantidad_devuelta = cantidades_a_devolver.get(num_inv, 1)
                    item.cantidad_disponible = min(
                        (item.cantidad_disponible or 0) + cantidad_devuelta,
                        item.cantidad_total or 9999
                    )
                    # Restaurar estado a Disponible si hay stock
                    if item.cantidad_disponible > 0:
                        item.estado = 'Disponible'
                else:
                    item.estado = 'Disponible'
            
            db.session.commit()
            
            # Emitir notificación de devolución de préstamo (usar representante seguro si existe)
            try:
                from services.notification_service import NotificationService
                notif_prestamo_id = representante.id_prestamo if representante else id_prestamo
                notif_equipo = getattr(representante, 'equipo_prestado', None) if representante else None
                NotificationService.notify_prestamo_devuelto(
                    prestamo_id=notif_prestamo_id,
                    equipo=notif_equipo,
                    url=f'/prestamos/{notif_prestamo_id}'
                )
            except Exception as e:
                # Registrar el error en salida estándar para depuración en desarrollo
                print(f"Error al emitir notificación: {e}")
            
            datos_devolucion = {
                'hora_devolucion': hora_devolucion.strftime('%H:%M'),
                'fecha_devolucion': fecha_devolucion.strftime('%Y-%m-%d'),
                'auxiliar_recibe': auxiliar_recibe,
                'equipo': (getattr(representante, 'equipo_prestado', None) if representante else None)
            }
            
            return True, 'Equipo(s) devuelto(s) exitosamente', datos_devolucion
            
        except Exception as e:
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return False, f'Error interno al devolver préstamo: {str(e)}', None

    @staticmethod
    def renovar_prestamo(id_grupo: int, horas_extra: int, auxiliar: str) -> Tuple[bool, str]:
        """
        Extiende el tiempo de un préstamo añadiendo horas a la hora_fin.
        Solo se aplica al último segmento de cada equipo.
        """
        try:
            # Buscar los préstamos activos del grupo
            prestamos = PrestamoEquipo.query.filter_by(
                id_grupo_prestamo=id_grupo,
                estado=SystemConstants.ESTADO_PRESTADO
            ).all()
            
            if not prestamos:
                return False, 'No se encontraron préstamos activos para renovar'
                
            from datetime import timedelta
            
            genero_cambio = False
            for p in prestamos:
                # Extender la hora de fin sumando timedelta
                hora_fin_dt = datetime.combine(date.today(), p.hora_fin)
                nueva_hora_fin = (hora_fin_dt + timedelta(hours=horas_extra)).time()
                p.hora_fin = nueva_hora_fin
                p.horas_academicas = PrestamoService.calcular_horas_academicas(
                    p.hora_inicio.strftime('%H:%M'), 
                    p.hora_fin.strftime('%H:%M')
                )
                
                obs_actual = p.observaciones or ""
                separador = "\n" if obs_actual else ""
                p.observaciones = f"{obs_actual}{separador}Renovado +{horas_extra}h por {auxiliar}"
                genero_cambio = True
                
            if genero_cambio:
                db.session.commit()
                return True, f'Préstamo renovado por {horas_extra} hora(s)'
            
            return False, 'No se pudo aplicar la renovación'
        except Exception as e:
            db.session.rollback()
            return False, f'Error al renovar préstamo: {str(e)}'
            
    @staticmethod
    def obtener_prestamos_vencidos(sede_id=None) -> List[Dict[str, Any]]:
        """Obtiene una lista de préstamos que están vencidos."""
        try:
            query = PrestamoEquipo.query.filter_by(
                estado=SystemConstants.ESTADO_PRESTADO
            )
            
            if sede_id:
                query = query.filter_by(sede_id=sede_id)
                
            prestamos_activos = query.all()
            
            prestamos_vencidos = []
            ahora = datetime.now()
            
            for prestamo in prestamos_activos:
                try:
                    # Combinar fecha y hora de devolución prevista
                    hora_devolucion_prevista = datetime.combine(
                        prestamo.fecha_prestamo, 
                        prestamo.hora_fin
                    )
                    
                    if ahora > hora_devolucion_prevista:
                        prestamos_vencidos.append({
                            'id_prestamo': prestamo.id_prestamo,
                            'nombre_profesor': prestamo.nombre_profesor,
                            'equipo_prestado': prestamo.equipo_prestado,
                            'hora_fin': prestamo.hora_fin.strftime('%H:%M'),
                            'fecha_prestamo': prestamo.fecha_prestamo.strftime('%Y-%m-%d'),
                            'horas_retraso': round(
                                (ahora - hora_devolucion_prevista).total_seconds() / 3600, 2
                            )
                        })
                except (ValueError, TypeError):
                    # Log el error pero continúa con el siguiente préstamo
                    continue
            
            return prestamos_vencidos
            
        except Exception as e:
            return []

    @staticmethod
    def verificar_estado_docente(cedula: str) -> Dict[str, Any]:
        """
        Verifica si un profesor tiene préstamos activos, pendientes o vencidos (mora).
        Retorna detalles para alertas inmediatas al operador.
        """
        if not cedula:
            return {'tiene_activos': False, 'tiene_mora': False, 'activos': [], 'vencidos': []}

        try:
            cedula_str = str(cedula).strip()
            # Buscar profesor
            profesor = Profesor.query.filter_by(cedula=cedula_str).first()
            if not profesor:
                # Intentar buscar por coincidencia en préstamos
                query = PrestamoEquipo.query.filter(
                    PrestamoEquipo.estado == SystemConstants.ESTADO_PRESTADO,
                    db.or_(
                        PrestamoEquipo.cedula_profesor == cedula_str,
                        PrestamoEquipo.nombre_profesor.ilike(f'%{cedula_str}%')
                    )
                )
            else:
                query = PrestamoEquipo.query.filter_by(
                    cedula_profesor=profesor.cedula,
                    estado=SystemConstants.ESTADO_PRESTADO
                )

            prestamos_activos = query.all()
            ahora = datetime.now()
            
            activos_list = []
            vencidos_list = []

            for p in prestamos_activos:
                hora_fin_str = p.hora_fin.strftime('%H:%M') if p.hora_fin else '--'
                fecha_str = p.fecha_prestamo.strftime('%Y-%m-%d') if p.fecha_prestamo else '--'
                
                # Check vencimiento
                es_vencido = False
                retraso_min = 0
                if p.fecha_prestamo and p.hora_fin:
                    try:
                        limite = datetime.combine(p.fecha_prestamo, p.hora_fin)
                        if ahora > limite:
                            es_vencido = True
                            retraso_min = int((ahora - limite).total_seconds() / 60)
                    except Exception:
                        pass

                item_info = {
                    'id_prestamo': p.id_prestamo,
                    'id_grupo': p.id_grupo_prestamo or p.id_prestamo,
                    'equipo': p.equipo_prestado,
                    'numero': p.numero_inventario_equipo,
                    'numero_corto': extraer_numero_corto(p.numero_inventario_equipo),
                    'ubicacion': p.ubicacion,
                    'fecha': fecha_str,
                    'hora_inicio': p.hora_inicio.strftime('%H:%M') if p.hora_inicio else '--',
                    'hora_fin': hora_fin_str,
                    'es_vencido': es_vencido,
                    'retraso_minutos': retraso_min
                }

                activos_list.append(item_info)
                if es_vencido:
                    vencidos_list.append(item_info)

            return {
                'success': True,
                'cedula': profesor.cedula if profesor else cedula_str,
                'nombre': profesor.nombre_completo if profesor else (activos_list[0]['equipo'] if activos_list else 'Docente'),
                'programa': profesor.programa if profesor else None,
                'correo': profesor.correo if profesor else None,
                'tiene_activos': len(activos_list) > 0,
                'tiene_mora': len(vencidos_list) > 0,
                'total_activos': len(activos_list),
                'total_vencidos': len(vencidos_list),
                'activos': activos_list,
                'vencidos': vencidos_list
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'tiene_activos': False,
                'tiene_mora': False,
                'activos': [],
                'vencidos': []
            }