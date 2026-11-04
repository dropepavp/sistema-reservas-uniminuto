"""
Servicio para la gestión y consultas complejas del inventario.
"""
from collections import Counter, defaultdict
from typing import Dict, Any, List, Tuple
from sqlalchemy import func, desc, asc
from database import db, Inventario, Bodega, InventarioCustodia


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
                    Inventario.numero_inventario.ilike(search_term),
                    Inventario.hostname.ilike(search_term)
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

    @staticmethod
    def obtener_custodias_filtradas(params: Dict[str, Any], user_rol: str = None, user_sede_id: int = None) -> List[InventarioCustodia]:
        """
        Aplica filtros a la tabla de custodia y centros de costo.
        Columnas: ESTADO, NOMBRE DEL CENTRO DE COSTO, CENTRO DE COSTO, CARGO RESPONSABLE, RESPONSABLE, CEDULA, EDIFICIO, UBICACIÓN.
        """
        query = InventarioCustodia.query

        estado_filtro = params.get('estado', '').strip()
        if estado_filtro:
            query = query.filter(InventarioCustodia.estado == estado_filtro)

        edificio_filtro = params.get('edificio', '').strip()
        if edificio_filtro:
            query = query.filter(InventarioCustodia.edificio == edificio_filtro)

        centro_costo_filtro = params.get('centro_costo', '').strip()
        if centro_costo_filtro:
            query = query.filter(InventarioCustodia.centro_costo == centro_costo_filtro)

        nombre_cc_filtro = params.get('nombre_centro_costo', '').strip()
        if nombre_cc_filtro:
            query = query.filter(InventarioCustodia.nombre_centro_costo.ilike(f"%{nombre_cc_filtro}%"))

        cargo_filtro = params.get('cargo_custodio', '').strip()
        if cargo_filtro:
            query = query.filter(InventarioCustodia.cargo_custodio.ilike(f"%{cargo_filtro}%"))

        responsable_filtro = params.get('responsable_custodia', '').strip()
        if responsable_filtro:
            query = query.filter(InventarioCustodia.responsable_custodia.ilike(f"%{responsable_filtro}%"))

        cedula_filtro = params.get('cedula_custodio', '').strip()
        if cedula_filtro:
            query = query.filter(InventarioCustodia.cedula_custodio.ilike(f"%{cedula_filtro}%"))

        ubicacion_filtro = params.get('ubicacion', '').strip()
        if ubicacion_filtro:
            query = query.filter(InventarioCustodia.ubicacion == ubicacion_filtro)

        tipo_filtro = params.get('tipo_inventario', '').strip()
        if tipo_filtro:
            query = query.filter(InventarioCustodia.tipo_inventario == tipo_filtro)

        sede_param = params.get('sede', '').strip()
        if sede_param and str(sede_param).isdigit():
            query = query.filter(InventarioCustodia.sede_id == int(sede_param))
        elif user_sede_id and user_rol not in ('admin', 'superadmin'):
            query = query.filter(InventarioCustodia.sede_id == user_sede_id)

        busqueda = params.get('busqueda', '').strip()
        if busqueda:
            term = f"%{busqueda}%"
            query = query.filter(
                db.or_(
                    InventarioCustodia.descripcion.ilike(term),
                    InventarioCustodia.placa.ilike(term),
                    InventarioCustodia.serie.ilike(term),
                    InventarioCustodia.marca.ilike(term),
                    InventarioCustodia.responsable_custodia.ilike(term),
                    InventarioCustodia.cedula_custodio.ilike(term),
                    InventarioCustodia.cargo_custodio.ilike(term),
                    InventarioCustodia.nombre_centro_costo.ilike(term),
                    InventarioCustodia.centro_costo.ilike(term),
                    InventarioCustodia.edificio.ilike(term),
                    InventarioCustodia.ubicacion.ilike(term)
                )
            )

        return query.order_by(InventarioCustodia.id.asc()).all()

    @staticmethod
    def calcular_estadisticas_custodia(custodias: List[InventarioCustodia]) -> Dict[str, Any]:
        """Calcula estadísticas y agrupaciones para la vista de Custodia."""
        total = len(custodias)
        por_estado = defaultdict(int)
        por_edificio = defaultdict(int)
        por_centro_costo = defaultdict(int)
        activos_fijos = 0
        bodega_lote = 0

        for c in custodias:
            por_estado[c.estado or 'Sin Estado'] += 1
            if c.edificio:
                por_edificio[c.edificio] += 1
            if c.centro_costo:
                lbl = f"{c.centro_costo} - {c.nombre_centro_costo or ''}".strip(' -')
                por_centro_costo[lbl] += 1
            if c.tipo_inventario == 'BODEGA_LOTE':
                bodega_lote += 1
            else:
                activos_fijos += 1

        return {
            'total': total,
            'activos_fijos': activos_fijos,
            'bodega_lote': bodega_lote,
            'por_estado': dict(por_estado),
            'por_edificio': dict(por_edificio),
            'por_centro_costo': dict(por_centro_costo)
        }

