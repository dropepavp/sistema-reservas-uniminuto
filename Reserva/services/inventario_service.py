"""
Servicio para la gestión y consultas complejas del inventario.
"""
from collections import Counter, defaultdict
from typing import Dict, Any, List, Tuple
from sqlalchemy import func, desc, asc
from database import db, Inventario, Bodega


class InventarioService:
    """Servicio de lógica de negocio para la gestión de inventario."""

    @staticmethod
    def obtener_inventario_filtrado(params: Dict[str, Any], user_rol: str = None, user_sede_id: int = None) -> List[Inventario]:
        """
        Aplica filtros de búsqueda, categoría, estado, ubicación, sede y bodega a la consulta de inventario.
        """
        categoria_filtro = params.get('categoria', '')
        estado_filtro = params.get('estado', '')
        ubicacion_filtro = params.get('ubicacion', '')
        busqueda = params.get('busqueda', '')

        query = Inventario.query

        if categoria_filtro:
            query = query.filter(Inventario.categoria == categoria_filtro)

        if estado_filtro:
            query = query.filter(Inventario.estado == estado_filtro)

        if ubicacion_filtro:
            query = query.filter(Inventario.ubicacion_permanente == ubicacion_filtro)

        if busqueda:
            search_term = f"%{busqueda}%"
            query = query.filter(
                db.or_(
                    Inventario.item.ilike(search_term),
                    Inventario.marca_modelo.ilike(search_term),
                    Inventario.serial.ilike(search_term),
                    Inventario.numero_inventario.ilike(search_term)
                )
            )

        # Filtro por sede de usuario (auxiliares)
        if user_sede_id and user_rol not in ('admin', 'superadmin'):
            query = query.outerjoin(Inventario.bodega).filter(
                db.or_(Bodega.sede_id == user_sede_id, Inventario.bodega_id.is_(None))
            )

        # Ordenar resultados
        ordenar_por = params.get('ordenar', 'id')
        orden = params.get('orden', 'desc')

        if ordenar_por == 'item':
            query = query.order_by(desc(Inventario.item) if orden == 'desc' else asc(Inventario.item))
        elif ordenar_por == 'categoria':
            query = query.order_by(desc(Inventario.categoria) if orden == 'desc' else asc(Inventario.categoria))
        elif ordenar_por == 'estado':
            query = query.order_by(desc(Inventario.estado) if orden == 'desc' else asc(Inventario.estado))
        else:
            query = query.order_by(desc(Inventario.id) if orden == 'desc' else asc(Inventario.id))

        # Filtro de Sede / Bodega desde URL
        sede_actual_id = params.get('sede', '')
        if sede_actual_id:
            bodegas = Bodega.query.filter_by(sede_id=int(sede_actual_id)).all()
            bodega_ids = [b.id for b in bodegas]
            if bodega_ids:
                query = query.filter(Inventario.bodega_id.in_(bodega_ids))
            else:
                query = query.filter(db.false())

        bodega_filtro = params.get('bodega', '')
        if bodega_filtro:
            query = query.filter(Inventario.bodega_id == int(bodega_filtro))

        return query.all()

    @staticmethod
    def calcular_estadisticas_inventario(inventario_list: List[Inventario]) -> Dict[str, Any]:
        """
        Calcula contadores, métricas y agregados sobre una lista de inventario.
        """
        categorias_count = defaultdict(int)
        for item in inventario_list:
            if item.categoria:
                if item.es_por_cantidad:
                    categorias_count[item.categoria] += item.cantidad_total or 0
                else:
                    categorias_count[item.categoria] += 1

        estados_count = Counter(item.estado for item in inventario_list if item.estado)
        total_items = len(inventario_list)

        disponibles_count = 0
        prestados_count = 0
        for item in inventario_list:
            if item.es_por_cantidad:
                disp = item.cantidad_disponible or 0
                tot = item.cantidad_total or 0
                disponibles_count += disp
                prestados_count += max(0, tot - disp)
            else:
                if item.estado == 'Disponible':
                    disponibles_count += 1
                elif item.estado == 'En Préstamo':
                    prestados_count += 1

        mantenimiento_count = estados_count.get('En Mantenimiento', 0) + estados_count.get('En Reparación', 0)
        baja_count = estados_count.get('De Baja', 0)

        # Top 5 items más prestados
        items_con_prestamos = [(item, item.veces_prestado) for item in inventario_list if item.veces_prestado > 0]
        items_con_prestamos.sort(key=lambda x: x[1], reverse=True)
        items_mas_prestados = [item for item, _ in items_con_prestamos[:5]]

        # Stock por tipo
        items_stock = [item for item in inventario_list if item.es_por_cantidad]
        stock_info = []
        for item in items_stock:
            stock_info.append({
                'item': item.item,
                'marca': item.marca_modelo or 'Sin marca',
                'total': item.cantidad_total or 0,
                'disponible': item.cantidad_disponible or 0,
                'en_uso': (item.cantidad_total or 0) - (item.cantidad_disponible or 0),
                'numero_inventario': item.numero_inventario
            })

        stock_por_tipo = defaultdict(lambda: {'total': 0, 'disponible': 0, 'detalles': []})
        for info in stock_info:
            nombre = info['item']
            stock_por_tipo[nombre]['total'] += info['total']
            stock_por_tipo[nombre]['disponible'] += info['disponible']
            stock_por_tipo[nombre]['detalles'].append(info)

        return {
            'total_items': total_items,
            'categorias_count': dict(categorias_count),
            'estados_count': dict(estados_count),
            'disponibles_count': disponibles_count,
            'prestados_count': prestados_count,
            'mantenimiento_count': mantenimiento_count,
            'baja_count': baja_count,
            'items_mas_prestados': items_mas_prestados,
            'stock_info': stock_info,
            'stock_por_tipo': dict(stock_por_tipo)
        }
