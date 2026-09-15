"""
Servicio centralizado para emisión de notificaciones en tiempo real vía Socket.IO
Centraliza la lógica de notificaciones para mantener consistencia en todo el sistema
"""
from flask import request, session
from extensions import socketio
from datetime import datetime
import json


class NotificationService:
    """Servicio para gestionar notificaciones en tiempo real"""
    
    @staticmethod
    def emit_notification(evento, data, target_user=None, target_role=None, target_sede=None):
        """
        Emite una notificación vía Socket.IO
        
        Args:
            evento: Nombre del evento (ej: 'nueva_reserva', 'prestamo_vencido')
            data: Diccionario con los datos de la notificación
            target_user: Documento del usuario específico (opcional)
            target_role: Rol objetivo (admin, auxiliar, etc.) (opcional)
            target_sede: ID de sede objetivo (opcional)
        """
        try:
            # Agregar metadata a la notificación
            notification_data = {
                **data,
                'timestamp': datetime.now().isoformat(),
                'sender_user': session.get('usuario'),
                'sender_name': session.get('nombre_completo'),
                'sender_sede': session.get('sede_id')
            }
            
            # Si hay un objetivo específico, enviar solo a ese usuario
            if target_user:
                socketio.emit(evento, notification_data, room=f'user_{target_user}')
            # Si hay un rol objetivo, enviar a usuarios con ese rol
            elif target_role:
                socketio.emit(evento, notification_data, room=f'role_{target_role}')
            # Si hay una sede objetivo, enviar a usuarios de esa sede
            elif target_sede:
                socketio.emit(evento, notification_data, room=f'sede_{target_sede}')
            # Si no hay objetivo específico, broadcast a todos
            else:
                socketio.emit(evento, notification_data)
                
        except Exception as e:
            # No interrumpir la operación principal si falla la notificación
            print(f"Error al emitir notificación: {e}")
    
    @staticmethod
    def notify_nueva_reserva(reserva_id, recurso_nombre, profesor, url=None):
        """Notifica cuando se crea una nueva reserva"""
        NotificationService.emit_notification('nueva_reserva', {
            'reserva_id': reserva_id,
            'recurso_nombre': recurso_nombre,
            'profesor': profesor,
            'url': url
        })
    
    @staticmethod
    def notify_reserva_cancelada(reserva_id, recurso_nombre, url=None):
        """Notifica cuando se cancela una reserva"""
        NotificationService.emit_notification('reserva_cancelada', {
            'reserva_id': reserva_id,
            'recurso_nombre': recurso_nombre,
            'url': url
        })
    
    @staticmethod
    def notify_prestamo_creado(prestamo_id, equipo, profesor, url=None):
        """Notifica cuando se crea un nuevo préstamo"""
        NotificationService.emit_notification('prestamo_creado', {
            'prestamo_id': prestamo_id,
            'equipo': equipo,
            'profesor': profesor,
            'url': url
        })
    
    @staticmethod
    def notify_prestamo_devuelto(prestamo_id, equipo, url=None):
        """Notifica cuando se devuelve un equipo"""
        NotificationService.emit_notification('prestamo_devuelto', {
            'prestamo_id': prestamo_id,
            'equipo': equipo,
            'url': url
        })
    
    @staticmethod
    def notify_prestamo_vencido(prestamo_id, equipo, fecha_devolucion, url=None):
        """Notifica cuando un préstamo está vencido"""
        NotificationService.emit_notification('prestamo_vencido', {
            'prestamo_id': prestamo_id,
            'equipo': equipo,
            'fecha_devolucion': fecha_devolucion,
            'url': url
        })
    
    @staticmethod
    def notify_inventario_cambiado(accion, item_id, item_nombre, url=None):
        """Notifica cambios en el inventario"""
        NotificationService.emit_notification('inventario_cambiado', {
            'accion': accion,
            'item_id': item_id,
            'item_nombre': item_nombre,
            'url': url
        })
    
    @staticmethod
    def notify_alerta_sistema(mensaje, tipo='info'):
        """Notifica alertas generales del sistema"""
        NotificationService.emit_notification('alerta_sistema', {
            'message': mensaje,
            'type': tipo
        })
    
    @staticmethod
    def notify_estadisticas_actualizadas(periodo):
        """Notifica cuando se actualizan las estadísticas"""
        NotificationService.emit_notification('estadisticas_actualizadas', {
            'periodo': periodo
        })
    
    @staticmethod
    def notify_usuario_creado(usuario_documento, usuario_nombre, target_role='admin'):
        """Notifica a admins cuando se crea un nuevo usuario"""
        NotificationService.emit_notification('usuario_creado', {
            'usuario_documento': usuario_documento,
            'usuario_nombre': usuario_nombre
        }, target_role=target_role)
    
    @staticmethod
    def notify_backup_completado(tipo_backup, exitoso=True):
        """Notifica cuando se completa un backup"""
        NotificationService.emit_notification('backup_completado', {
            'tipo': tipo_backup,
            'exitoso': exitoso
        }, target_role='admin')
    
    @staticmethod
    def notify_error_critico(modulo, error_message, target_role='admin'):
        """Notifica errores críticos a administradores"""
        NotificationService.emit_notification('error_critico', {
            'modulo': modulo,
            'error': error_message,
            'timestamp': datetime.now().isoformat()
        }, target_role=target_role)