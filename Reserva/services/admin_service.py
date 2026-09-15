"""
Servicio para funciones administrativas, auditoría y gestión de usuarios auxiliares.
"""
from typing import Dict, Any, List, Optional
from sqlalchemy import desc, asc, or_
from database import db, Auxiliar, AuxiliarSede, UserPermission, AuditLog


class AdminService:
    """Servicio de lógica de negocio para administración del sistema."""

    @staticmethod
    def obtener_usuarios_filtrados(params: Dict[str, Any]) -> List[Auxiliar]:
        """Obtiene la lista de usuarios auxiliares/administradores filtrada y ordenada."""
        rol_filtro = params.get('rol', '')
        busqueda = params.get('busqueda', '')
        sede_filtro = params.get('sede_id', '')
        estado_filtro = params.get('estado', '')
        ordenar_por = params.get('ordenar', 'nombre_completo')
        orden = params.get('orden', 'asc')

        query = Auxiliar.query

        if rol_filtro:
            query = query.filter(Auxiliar.rol == rol_filtro)

        if sede_filtro:
            query = query.filter(Auxiliar.sede_id == int(sede_filtro))

        if estado_filtro == 'activo':
            query = query.filter(Auxiliar.activo == True)
        elif estado_filtro == 'inactivo':
            query = query.filter(Auxiliar.activo == False)

        if busqueda:
            search_term = f"%{busqueda}%"
            query = query.filter(
                or_(
                    Auxiliar.nombre_completo.ilike(search_term),
                    Auxiliar.documento.ilike(search_term),
                    Auxiliar.correo.ilike(search_term)
                )
            )

        if ordenar_por == 'documento':
            query = query.order_by(desc(Auxiliar.documento) if orden == 'desc' else asc(Auxiliar.documento))
        elif ordenar_por == 'correo':
            query = query.order_by(desc(Auxiliar.correo) if orden == 'desc' else asc(Auxiliar.correo))
        elif ordenar_por == 'rol':
            query = query.order_by(desc(Auxiliar.rol) if orden == 'desc' else asc(Auxiliar.rol))
        else:
            query = query.order_by(desc(Auxiliar.nombre_completo) if orden == 'desc' else asc(Auxiliar.nombre_completo))

        return query.all()

    @staticmethod
    def obtener_auditoria_filtrada(params: Dict[str, Any], limit: int = 100) -> List[AuditLog]:
        """Obtiene registros de auditoría filtrados."""
        modulo = params.get('modulo', '')
        usuario = params.get('usuario', '')

        query = AuditLog.query

        if modulo:
            query = query.filter(AuditLog.modulo == modulo)

        if usuario:
            query = query.filter(AuditLog.usuario.ilike(f"%{usuario}%"))

        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
