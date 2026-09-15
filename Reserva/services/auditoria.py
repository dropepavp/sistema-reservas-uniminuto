"""
Utilidades para Auditoría de Movimientos
========================================

Funciones helper para registrar cambios en los diferentes módulos
y mantener un registro de quién cambió qué y cuándo.
"""

from database import db, registrar_auditoria
from flask import session
import json

class AuditoriaHelper:
    """Helper para registrar auditorías fácilmente en los módulos"""
    
    @staticmethod
    def registrar_creacion(modulo, entidad_tipo, entidad_id, descripcion="", datos=None):
        """Registra la creación de una entidad"""
        try:
            usuario = session.get('usuario', 'sistema')
            usuario_nombre = session.get('nombre_completo', '')
            
            registrar_auditoria(
                modulo=modulo,
                entidad_tipo=entidad_tipo,
                entidad_id=str(entidad_id),
                accion='CREAR',
                descripcion=descripcion or f"Se creó {entidad_tipo} {entidad_id}",
                datos_antes=None,
                datos_despues=datos
            )
            db.session.commit()
        except Exception as e:
            print(f"Error al registrar auditoría de creación: {e}")
    
    @staticmethod
    def registrar_edicion(modulo, entidad_tipo, entidad_id, descripcion="", datos_antes=None, datos_despues=None):
        """Registra la edición de una entidad"""
        try:
            usuario = session.get('usuario', 'sistema')
            usuario_nombre = session.get('nombre_completo', '')
            
            registrar_auditoria(
                modulo=modulo,
                entidad_tipo=entidad_tipo,
                entidad_id=str(entidad_id),
                accion='EDITAR',
                descripcion=descripcion or f"Se editó {entidad_tipo} {entidad_id}",
                datos_antes=datos_antes,
                datos_despues=datos_despues
            )
            db.session.commit()
        except Exception as e:
            print(f"Error al registrar auditoría de edición: {e}")
    
    @staticmethod
    def registrar_eliminacion(modulo, entidad_tipo, entidad_id, descripcion="", datos=None):
        """Registra la eliminación de una entidad"""
        try:
            usuario = session.get('usuario', 'sistema')
            usuario_nombre = session.get('nombre_completo', '')
            
            registrar_auditoria(
                modulo=modulo,
                entidad_tipo=entidad_tipo,
                entidad_id=str(entidad_id),
                accion='ELIMINAR',
                descripcion=descripcion or f"Se eliminó {entidad_tipo} {entidad_id}",
                datos_antes=datos,
                datos_despues=None
            )
            db.session.commit()
        except Exception as e:
            print(f"Error al registrar auditoría de eliminación: {e}")
    
    @staticmethod
    def registrar_accion_personalizada(modulo, entidad_tipo, entidad_id, accion, 
                                      descripcion="", datos_antes=None, datos_despues=None):
        """Registra una acción personalizada (devolver, cancelar, etc)"""
        try:
            usuario = session.get('usuario', 'sistema')
            usuario_nombre = session.get('nombre_completo', '')
            
            registrar_auditoria(
                modulo=modulo,
                entidad_tipo=entidad_tipo,
                entidad_id=str(entidad_id),
                accion=accion.upper(),
                descripcion=descripcion or f"Se realizó {accion.lower()} en {entidad_tipo} {entidad_id}",
                datos_antes=datos_antes,
                datos_despues=datos_despues
            )
            db.session.commit()
        except Exception as e:
            print(f"Error al registrar auditoría personalizada: {e}")


def generar_resumen_cambios(datos_antes, datos_despues, campos_ignorar=None):
    """
    Genera un resumen de cambios entre dos dictionaries
    
    Args:
        datos_antes: Dict con datos anteriores
        datos_despues: Dict con datos nuevos
        campos_ignorar: Lista de campos a ignorar
    
    Returns:
        Dict con los cambios relevantes
    """
    if campos_ignorar is None:
        campos_ignorar = ['fecha_creacion', 'fecha_actualizacion', 'timestamp']
    
    cambios = {}
    
    if not datos_antes:
        return datos_despues
    
    if not datos_despues:
        return datos_antes
    
    # Detectar cambios
    todas_las_claves = set(datos_antes.keys()) | set(datos_despues.keys())
    
    for clave in todas_las_claves:
        if clave in campos_ignorar:
            continue
        
        valor_antes = datos_antes.get(clave, 'N/A')
        valor_despues = datos_despues.get(clave, 'N/A')
        
        if valor_antes != valor_despues:
            cambios[clave] = {
                'antes': valor_antes,
                'despues': valor_despues
            }
    
    return cambios


def diccionario_a_json(data):
    """Convierte un diccionario a JSON de forma segura"""
    try:
        if isinstance(data, str):
            return data
        return json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        return str(data)


# Ejemplo de uso en un blueprint:
"""
from utils.auditoria import AuditoriaHelper

# En una ruta que crea algo:
@blueprint.route('/crear', methods=['POST'])
def crear_prestamo():
    # ... hacer validaciones y crear ...
    prestamo = PrestamoEquipo(...)
    db.session.add(prestamo)
    db.session.commit()
    
    # Registrar auditoría
    AuditoriaHelper.registrar_creacion(
        modulo='prestamos',
        entidad_tipo='PrestamoEquipo',
        entidad_id=prestamo.id_prestamo,
        descripcion=f"Nuevo préstamo de {prestamo.equipo_prestado} a {prestamo.nombre_profesor}",
        datos={
            'profesor': prestamo.nombre_profesor,
            'equipo': prestamo.equipo_prestado,
            'fecha': str(prestamo.fecha_prestamo)
        }
    )

# En una ruta que edita:
@blueprint.route('/editar/<int:id>', methods=['POST'])
def editar_prestamo(id):
    prestamo = PrestamoEquipo.query.get_or_404(id)
    
    # Guardar estado anterior
    datos_antes = {
        'estado': prestamo.estado,
        'observaciones': prestamo.observaciones
    }
    
    # Actualizar
    prestamo.estado = request.form.get('estado')
    prestamo.observaciones = request.form.get('observaciones')
    db.session.commit()
    
    # Registrar auditoría
    AuditoriaHelper.registrar_edicion(
        modulo='prestamos',
        entidad_tipo='PrestamoEquipo',
        entidad_id=prestamo.id_prestamo,
        descripcion=f"Se editó el préstamo {prestamo.id_prestamo}",
        datos_antes=datos_antes,
        datos_despues={
            'estado': prestamo.estado,
            'observaciones': prestamo.observaciones
        }
    )

# Para acciones especiales:
@blueprint.route('/devolver/<int:id>', methods=['POST'])
def devolver_prestamo(id):
    prestamo = PrestamoEquipo.query.get_or_404(id)
    
    prestamo.estado = 'Devuelto'
    prestamo.fecha_devolucion = date.today()
    db.session.commit()
    
    AuditoriaHelper.registrar_accion_personalizada(
        modulo='prestamos',
        entidad_tipo='PrestamoEquipo',
        entidad_id=prestamo.id_prestamo,
        accion='DEVOLVER',
        descripcion=f"Se registró la devolución del équipo {prestamo.equipo_prestado}",
        datos_despues={'estado': prestamo.estado, 'fecha_devolucion': str(prestamo.fecha_devolucion)}
    )
"""
