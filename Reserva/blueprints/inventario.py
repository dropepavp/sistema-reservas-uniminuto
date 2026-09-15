"""
Blueprint para gestión completa del inventario de equipos y recursos.
Incluye CRUD, gestión de categorías, historial de movimientos y reportes.
"""
from flask import Blueprint, render_template, request, redirect, flash, jsonify, send_file, url_for, session, current_app
import io
import pandas as pd
from datetime import datetime, date
from database import db, Inventario, PrestamoEquipo, Sede, Bodega, CategoriaInventario, UserPermission, registrar_auditoria, MantenimientoInventario, AuditLog
from extensions import socketio
from services.notification_service import NotificationService
from config import SystemConstants
from validators import DataValidator
from sqlalchemy import func, desc, asc
from auth import login_required, permiso_requerido, sede_requerida
from services.inventario_service import InventarioService
from utils.export_helpers import exportar_df_excel, exportar_df_csv
import re

inventario_bp = Blueprint('inventario', __name__, url_prefix='/inventario')


@inventario_bp.route('/')
@login_required
@permiso_requerido('inventario', 'ver')
@sede_requerida
def inventario_main():
    """Página principal del inventario con filtros y estadísticas."""
    try:
        categoria_filtro = request.args.get('categoria', '')
        estado_filtro = request.args.get('estado', '')
        busqueda = request.args.get('busqueda', '')
        sede_actual_id = request.args.get('sede', '')
        bodega_filtro = request.args.get('bodega', '')

        user_rol = session.get('rol')
        user_sede_id = session.get('sede_id')

        inventario_list = InventarioService.obtener_inventario_filtrado(
            request.args, user_rol=user_rol, user_sede_id=user_sede_id
        )

        calc_stats = InventarioService.calcular_estadisticas_inventario(inventario_list)

        db.session.rollback()

        stats = {
            'total': calc_stats['total_items'],
            'disponibles': calc_stats['disponibles_count'],
            'prestados': calc_stats['prestados_count'],
            'mantenimiento': calc_stats['mantenimiento_count'],
            'baja': calc_stats['baja_count'],
            'por_categoria': calc_stats['categorias_count'],
            'por_estado': calc_stats['estados_count'],
            'mas_prestados': calc_stats['items_mas_prestados'],
            'stock_items': calc_stats['stock_info'],
            'stock_por_tipo': calc_stats['stock_por_tipo']
        }

        # Datos para los filtros - cargar desde nueva sesión limpia
        categorias_db = CategoriaInventario.query.all()
        if not categorias_db:
            # Seed inicial si está vacía
            for cat_name in SystemConstants.CATEGORIAS_INVENTARIO:
                if not CategoriaInventario.query.filter_by(nombre=cat_name).first():
                    db.session.add(CategoriaInventario(nombre=cat_name))
            db.session.commit()
            categorias_db = CategoriaInventario.query.all()

        categorias = [c.nombre for c in categorias_db]
        estados = ['Disponible', 'En Préstamo', 'En Mantenimiento', 'En Reparación', 'De Baja']
        sedes = Sede.query.all()
        bodegas = Bodega.query.filter_by(sede_id=int(sede_actual_id)).all() if sede_actual_id else []

        return render_template('inventario.html', 
                             inventario=inventario_list,
                             categorias=categorias,
                             estados=estados,
                             sedes=sedes,
                             bodegas=bodegas,
                             stats=stats,
                             disponibles_count=calc_stats['disponibles_count'],
                             prestados_count=calc_stats['prestados_count'],
                             reparacion_count=calc_stats['mantenimiento_count'],
                             filtros={
                                 'categoria': categoria_filtro,
                                 'estado': estado_filtro,
                                 'busqueda': busqueda,
                                 'sede': sede_actual_id,
                                 'bodega': bodega_filtro
                             })

    except Exception as e:
        current_app.logger.error(f'Error al cargar el inventario: {str(e)}', exc_info=True)
        flash('Error al cargar el inventario.', 'danger')
        return render_template('inventario.html', 
                             inventario=[], 
                             categorias=[], 
                             estados=[], 
                             sedes=[],
                             bodegas=[],
                             stats={
                                 'total': 0,
                                 'disponibles': 0,
                                 'prestados': 0,
                                 'mantenimiento': 0,
                                 'baja': 0,
                                 'por_categoria': {},
                                 'por_estado': {},
                                 'mas_prestados': [],
                                 'stock_items': [],
                                 'stock_por_tipo': {}
                             },
                             disponibles_count=0,
                             prestados_count=0,
                             reparacion_count=0,
                             filtros={})

@inventario_bp.route('/corregir_estados')
@login_required
def corregir_estados():
    """Corrige estados del inventario según préstamos activos. Solo admin."""
    try:
        if session.get('rol') not in ('admin', 'superadmin'):
            flash('Acción permitida solo para administradores.', 'danger')
            return redirect(url_for('inventario.inventario_main'))
        
        corregidos = 0
        activos = db.session.query(PrestamoEquipo.numero_inventario_equipo)\
            .filter_by(estado=SystemConstants.ESTADO_PRESTADO).distinct().all()
        numeros_prestados = [p[0] for p in activos if p[0]]
        
        if numeros_prestados:
            items_prestados = Inventario.query.filter(Inventario.numero_inventario.in_(numeros_prestados)).all()
            for item in items_prestados:
                if item.estado != 'En Préstamo':
                    item.estado = 'En Préstamo'
                    corregidos += 1
        
        items_mal_marcados = Inventario.query.filter(
            Inventario.estado == 'En Préstamo',
            ~Inventario.numero_inventario.in_(numeros_prestados)
        ).all()
        for item in items_mal_marcados:
            item.estado = 'Disponible'
            corregidos += 1
        
        db.session.commit()
        flash(f'Estados del inventario corregidos. Se actualizaron {corregidos} registros.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ocurrió un error al corregir los estados del inventario.', 'danger')
    return redirect(url_for('inventario.inventario_main'))

@inventario_bp.route('/agregar', methods=['POST'])
@login_required
@permiso_requerido('inventario', 'crear')
def agregar_item():
    """Agrega un nuevo item al inventario."""
    try:
        datos = request.json
        
        def es_accesorio_cable_control(nombre: str) -> bool:
            if not nombre:
                return False
            n = nombre.lower()
            keywords = ['control', 'cable', 'hdmi', 'vga', 'displayport', 'dp', 'usb', 'aux', 'audio', 'parlante', 'adaptador', 'convertidor']
            return any(k in n for k in keywords)

        def generar_num_inventario_stock(nombre: str) -> str:
            base = re.sub(r'[^A-Za-z0-9]+', '-', (nombre or 'ITEM').upper()).strip('-')
            candidato = f"STOCK-{base}"
            sufijo = 1
            # Asegurar unicidad si ya existe
            while Inventario.query.filter_by(numero_inventario=candidato).first():
                sufijo += 1
                candidato = f"STOCK-{base}-{sufijo}"
            return candidato
        
        # Validaciones
        categoria_valid, categoria_error = DataValidator.validate_string_field(
            datos.get('categoria'), 'Categoría', max_length=100
        )
        if not categoria_valid:
            return jsonify({'success': False, 'message': categoria_error}), 400
        
        # Validar que la categoría sea válida en la DB
        cate_db = CategoriaInventario.query.filter_by(nombre=datos.get('categoria')).first()
        if not cate_db:
            return jsonify({'success': False, 'message': 'Categoría no válida'}), 400
        
        # Validar item (nombre)
        item_valid, item_error = DataValidator.validate_string_field(
            datos.get('item'), 'Nombre del Item', max_length=150
        )
        if not item_valid:
            return jsonify({'success': False, 'message': item_error}), 400
        
        # Determinar si es accesorio tipo control/cable para NO exigir número de inventario ni activo fijo
        item_nombre = datos.get('item', '')
        accesorio = es_accesorio_cable_control(item_nombre)
        
        # Gestión por cantidad (forzamos para accesorios tipo control/cable)
        es_por_cantidad = bool(datos.get('es_por_cantidad', False)) or accesorio
        
        # Número de inventario: opcional para accesorios; si viene vacío y es accesorio, generamos un ID estable
        num_inv = (datos.get('numero_inventario') or '').strip()
        if not num_inv:
            if not accesorio:
                return jsonify({'success': False, 'message': 'El número de inventario es requerido'}), 400
            else:
                num_inv = generar_num_inventario_stock(item_nombre)
        
        if Inventario.query.filter_by(numero_inventario=num_inv).first():
            return jsonify({'success': False, 'message': f'Ya existe un equipo con el número de inventario {num_inv}'}), 400
        
        cantidad_total = None
        cantidad_disponible = None
        if es_por_cantidad:
            try:
                cantidad_total = int(datos.get('cantidad_total', 1))
                if cantidad_total <= 0:
                    return jsonify({'success': False, 'message': 'La cantidad total debe ser mayor a 0'}), 400
                cantidad_disponible = cantidad_total  # Al crear, todo está disponible
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'La cantidad total debe ser un número válido'}), 400
            
        # Crear item
        nuevo_item = Inventario(
            categoria=datos.get('categoria'),
            item=datos.get('item'),
            marca_modelo=datos.get('marca_modelo'),
            serial=datos.get('serial'),
            activo_fijo=None if accesorio else datos.get('activo_fijo'),
            numero_inventario=num_inv,
            ubicacion_permanente=datos.get('ubicacion_permanente'),
            estado=datos.get('estado', 'Disponible'),
            observaciones=datos.get('observaciones'),
            bodega_id=datos.get('bodega_id'),
            es_por_cantidad=es_por_cantidad,
            cantidad_total=cantidad_total,
            cantidad_disponible=cantidad_disponible
        )
        
        db.session.add(nuevo_item)
        db.session.commit()

        # Emitir notificación usando el servicio centralizado
        NotificationService.notify_inventario_cambiado(
            accion='crear',
            item_id=nuevo_item.id,
            item_nombre=nuevo_item.item,
            url=f'/inventario/{nuevo_item.id}'
        )

        registrar_auditoria(
            modulo='inventario',
            entidad_tipo='Inventario',
            entidad_id=nuevo_item.id,
            accion='CREAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Creación de item de inventario "{nuevo_item.item}"',
            datos_antes=None,
            datos_despues={
                'categoria': nuevo_item.categoria,
                'item': nuevo_item.item,
                'numero_inventario': nuevo_item.numero_inventario,
                'estado': nuevo_item.estado,
            }
        )

        return jsonify({
            'success': True,
            'message': f'Item "{nuevo_item.item}" agregado exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@inventario_bp.route('/bulk_delete', methods=['POST'])
@login_required
@permiso_requerido('inventario', 'eliminar')
def bulk_delete():
    """Elimina múltiples items del inventario (solo superadmin)."""
    try:
        if session.get('rol') != 'superadmin':
            return jsonify({'success': False, 'message': 'Acceso denegado. Se requiere rol superadmin.'}), 403

        datos = request.json or {}
        item_ids = [int(i) for i in (datos.get('item_ids') or [])]
        if not item_ids:
            return jsonify({'success': False, 'message': 'No se seleccionaron items.'}), 400

        items = Inventario.query.filter(Inventario.id.in_(item_ids)).all()
        items_by_id = {i.id: i for i in items}

        eliminados = 0
        no_encontrados = []
        for item_id in item_ids:
            item = items_by_id.get(item_id)
            if not item:
                no_encontrados.append(item_id)
                continue

            datos_antes = {
                'categoria': item.categoria,
                'item': item.item,
                'numero_inventario': item.numero_inventario,
                'estado': item.estado,
            }

            if item.numero_inventario:
                PrestamoEquipo.query.filter_by(
                    numero_inventario_equipo=item.numero_inventario
                ).delete(synchronize_session=False)

            db.session.delete(item)
            eliminados += 1

            registrar_auditoria(
                modulo='inventario',
                entidad_tipo='Inventario',
                entidad_id=item_id,
                accion='ELIMINAR_MASIVO',
                usuario_documento=session.get('usuario', ''),
                usuario_nombre=session.get('nombre_completo', ''),
                descripcion=f'Eliminación masiva (forzada) de item de inventario "{item.item}"',
                datos_antes=datos_antes,
                datos_despues=None
            )

        db.session.commit()

        msg = f'Se eliminaron {eliminados} items.'
        if no_encontrados:
            msg += f' No encontrados: {len(no_encontrados)}'

        return jsonify({'success': True, 'message': msg, 'eliminados': eliminados, 'no_encontrados': no_encontrados})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error en bulk_delete inventario: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@inventario_bp.route('/editar/<int:id>', methods=['PUT', 'GET'])
@login_required
@permiso_requerido('inventario', 'editar')
def editar_item(id):
    """Obtiene o actualiza un item del inventario."""
    item = Inventario.query.get_or_404(id)
    
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'item': {
                'id': item.id,
                'categoria': item.categoria,
                'item': item.item,
                'marca_modelo': item.marca_modelo,
                'serial': item.serial,
                'activo_fijo': item.activo_fijo,
                'numero_inventario': item.numero_inventario,
                'ubicacion_permanente': item.ubicacion_permanente,
                'estado': item.estado,
                'observaciones': item.observaciones,
                'bodega_id': item.bodega_id,
                'es_por_cantidad': item.es_por_cantidad,
                'cantidad_total': item.cantidad_total,
                'cantidad_disponible': item.cantidad_disponible
            }
        })
        
    try:
        datos = request.json
        
        # Validar categoría
        cate_db = CategoriaInventario.query.filter_by(nombre=datos.get('categoria')).first()
        if not cate_db:
             return jsonify({'success': False, 'message': 'Categoría no válida'}), 400

        # Validar número de inventario (si cambia)
        num_inv = (datos.get('numero_inventario') or '').strip()
        if num_inv != item.numero_inventario:
            if num_inv and Inventario.query.filter_by(numero_inventario=num_inv).first():
                return jsonify({'success': False, 'message': 'Este número de inventario ya está en uso'}), 400
        
        datos_antes = {
            'categoria': item.categoria,
            'item': item.item,
            'marca_modelo': item.marca_modelo,
            'serial': item.serial,
            'activo_fijo': item.activo_fijo,
            'numero_inventario': item.numero_inventario,
            'estado': item.estado,
            'cantidad_total': item.cantidad_total,
            'cantidad_disponible': item.cantidad_disponible,
        }

        item.categoria = datos.get('categoria')
        item.item = datos.get('item')
        item.marca_modelo = datos.get('marca_modelo')
        item.serial = datos.get('serial')
        # Si el item es un accesorio (control/cable) permitimos dejar activo_fijo vacío
        nombre_item = (datos.get('item') or '')
        accesorio = 'control' in nombre_item.lower() or 'cable' in nombre_item.lower()
        item.activo_fijo = (datos.get('activo_fijo') or '').strip() if not accesorio else None
        # Mantener un número de inventario válido; si usuario lo vacía y es accesorio, no lo anulamos para no romper préstamos
        if num_inv:
            item.numero_inventario = num_inv
        item.ubicacion_permanente = datos.get('ubicacion_permanente')
        item.estado = datos.get('estado')
        item.observaciones = datos.get('observaciones')
        item.bodega_id = datos.get('bodega_id')

        # Gestión por cantidad
        es_por_cantidad = bool(datos.get('es_por_cantidad', False))
        item.es_por_cantidad = es_por_cantidad
        if es_por_cantidad:
            try:
                nueva_cantidad_total = int(datos.get('cantidad_total', item.cantidad_total or 1))
                if nueva_cantidad_total <= 0:
                    return jsonify({'success': False, 'message': 'La cantidad total debe ser mayor a 0'}), 400
                # Ajustar cantidad_disponible proporcionalmente si cambió el total
                if item.cantidad_total and item.cantidad_total != nueva_cantidad_total:
                    diferencia = nueva_cantidad_total - item.cantidad_total
                    item.cantidad_disponible = max(0, (item.cantidad_disponible or 0) + diferencia)
                elif not item.cantidad_total:
                    item.cantidad_disponible = nueva_cantidad_total
                item.cantidad_total = nueva_cantidad_total
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'La cantidad total debe ser un número válido'}), 400
        else:
            item.cantidad_total = None
            item.cantidad_disponible = None
        
        db.session.commit()

        # Emitir notificación de edición de inventario
        NotificationService.notify_inventario_cambiado(
            accion='editar',
            item_id=item.id,
            item_nombre=item.item,
            url=f'/inventario/{item.id}'
        )

        datos_despues = {
            'categoria': item.categoria,
            'item': item.item,
            'marca_modelo': item.marca_modelo,
            'serial': item.serial,
            'activo_fijo': item.activo_fijo,
            'numero_inventario': item.numero_inventario,
            'estado': item.estado,
            'cantidad_total': item.cantidad_total,
            'cantidad_disponible': item.cantidad_disponible,
        }

        registrar_auditoria(
            modulo='inventario',
            entidad_tipo='Inventario',
            entidad_id=item.id,
            accion='EDITAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Edición de item de inventario "{item.item}"',
            datos_antes=datos_antes,
            datos_despues=datos_despues
        )

        return jsonify({'success': True, 'message': 'Item actualizado correctamente'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@inventario_bp.route('/eliminar/<int:id>', methods=['DELETE'])
@login_required
@permiso_requerido('inventario', 'eliminar')
def eliminar_item(id):
    """Elimina un item del inventario."""
    try:
        item = Inventario.query.get_or_404(id)

        def es_accesorio_cable_control(nombre: str) -> bool:
            if not nombre:
                return False
            n = nombre.lower()
            keywords = ['control', 'cable', 'hdmi', 'vga', 'displayport', 'dp', 'usb', 'aux', 'audio', 'parlante', 'adaptador', 'convertidor']
            return any(k in n for k in keywords)

        # Si no es admin, solo permitir eliminar accesorios (controles/cables) y dentro de su sede
        if session.get('rol') not in ('admin', 'superadmin'):
            if not es_accesorio_cable_control(item.item or '') and not es_accesorio_cable_control(item.categoria or ''):
                return jsonify({'success': False, 'message': 'Solo puedes eliminar accesorios (controles, cables, adaptadores).'}), 403
            sede_id = session.get('sede_id')
            if sede_id and item.bodega and item.bodega.sede_id != sede_id:
                return jsonify({'success': False, 'message': 'No puedes eliminar items fuera de tu sede.'}), 403

        # Verificar si tiene préstamos activos
        prestamos_activos = PrestamoEquipo.query.filter_by(
            numero_inventario_equipo=item.numero_inventario,
            estado=SystemConstants.ESTADO_PRESTADO
        ).count()
        
        if prestamos_activos > 0:
            return jsonify({
                'success': False, 
                'message': 'No se puede eliminar un equipo que tiene préstamos pendientes de devolución'
            }), 400

        # Verificar si tiene historial de préstamos (devueltos o activos). Si se elimina, el FK
        # intentará quedar en NULL y la BD lo prohíbe (NOT NULL).
        prestamos_historicos = PrestamoEquipo.query.filter_by(
            numero_inventario_equipo=item.numero_inventario
        ).count()

        if prestamos_historicos > 0:
            force = str(request.args.get('force', '')).strip() in ('1', 'true', 'True', 'yes', 'YES')
            superadmins = current_app.config.get('SUPERADMIN_DOCUMENTS')
            if session.get('rol') == 'superadmin':
                is_superadmin = True
            elif isinstance(superadmins, set):
                is_superadmin = session.get('rol') == 'admin' and str(session.get('usuario', '')).strip() in superadmins
            else:
                is_superadmin = False

            if not (force and is_superadmin):
                return jsonify({
                    'success': False,
                    'message': 'No se puede eliminar este item porque tiene historial de préstamos. En su lugar, cámbielo a estado "De Baja".'
                }), 400

            PrestamoEquipo.query.filter_by(numero_inventario_equipo=item.numero_inventario).delete(synchronize_session=False)
            
        nombre_item = item.item

        datos_antes = {
            'categoria': item.categoria,
            'item': item.item,
            'numero_inventario': item.numero_inventario,
            'estado': item.estado,
        }

        db.session.delete(item)
        db.session.commit()

        # Emitir notificación de eliminación de inventario
        NotificationService.notify_inventario_cambiado(
            accion='eliminar',
            item_id=id,
            item_nombre=nombre_item,
            url='/inventario'
        )

        registrar_auditoria(
            modulo='inventario',
            entidad_tipo='Inventario',
            entidad_id=id,
            accion='ELIMINAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Eliminación de item de inventario "{nombre_item}"',
            datos_antes=datos_antes,
            datos_despues=None
        )

        return jsonify({
            'success': True,
            'message': f'Item "{nombre_item}" eliminado del inventario'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@inventario_bp.route('/api/items/disponibles')
@login_required
def api_items_disponibles():
    """Devuelve items disponibles para autocompletes/selección (filtrado por sede para auxiliares)."""
    try:
        query = Inventario.query.filter_by(estado='Disponible')

        if session.get('rol') not in ('admin', 'superadmin') and session.get('sede_id'):
            from sqlalchemy import or_
            query = query.outerjoin(Inventario.bodega).filter(
                or_(Bodega.sede_id == session.get('sede_id'), Inventario.bodega_id.is_(None))
            )

        items = query.order_by(Inventario.item.asc()).limit(500).all()
        return jsonify([
            {
                'id': i.id,
                'item': i.item,
                'marca_modelo': i.marca_modelo,
                'numero_inventario': i.numero_inventario,
                'serial': i.serial
            } for i in items
        ])
    except Exception as e:
        current_app.logger.error('Error api_items_disponibles: %s', e, exc_info=True)
        return jsonify([]), 500

@inventario_bp.route('/importar', methods=['POST'])
@login_required
def importar_inventario():
    """Importa inventario desde un archivo Excel."""
    if 'archivo' not in request.files:
        flash('No se seleccionó ningún archivo', 'warning')
        return redirect(url_for('inventario.inventario_main'))
        
    archivo = request.files['archivo']
    if archivo.filename == '':
        flash('Nombre de archivo vacío', 'warning')
        return redirect(url_for('inventario.inventario_main'))
        
    try:
        # Leer Excel
        df = pd.read_excel(archivo)
        
        # Mapeo de columnas esperado
        # 'CATEGORIA', 'ITEM', 'MARCA/MODELO', 'SERIAL', 'ACTIVO FIJO', 'ID', 'UBICACION PERMANENTE', 'ESTADO', 'BODEGA'
        
        exitos = 0
        errores = 0
        consecutivos_generados = 0
        
        def generar_consecutivo_por_categoria(categoria, item_nombre):
            """Genera un número de inventario consecutivo único basado en las 3 primeras letras del item."""
            # Priorizar el nombre del item sobre la categoría
            if item_nombre and item_nombre.strip():
                # Limpiar el nombre del item (quitar espacios, caracteres especiales)
                nombre_limpio = re.sub(r'[^A-Za-z0-9]+', '', item_nombre.upper())
                # Tomar solo las 3 primeras letras
                base = nombre_limpio[:3] if len(nombre_limpio) >= 3 else nombre_limpio.ljust(3, 'X')
            elif categoria and categoria.strip():
                nombre_limpio = re.sub(r'[^A-Za-z0-9]+', '', categoria.upper())
                base = nombre_limpio[:3] if len(nombre_limpio) >= 3 else nombre_limpio.ljust(3, 'X')
            else:
                base = 'ITM'
            
            # Buscar el último consecutivo para esta base
            patron = f"{base}%"
            ultimos = db.session.query(Inventario.numero_inventario)\
                .filter(Inventario.numero_inventario.like(patron))\
                .all()
            
            # Extraer números y encontrar el máximo
            max_num = 0
            for (num_inv,) in ultimos:
                # Extraer solo los dígitos al final
                match = re.search(r'(\d+)$', num_inv)
                if match:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
            
            nuevo_num = max_num + 1
            
            # Generar el nuevo número con formato de 2 dígitos (01, 02, 03...)
            return f"{base}{nuevo_num:02d}"
        
        for idx, row in df.iterrows():
            try:
                # Obtener categoría e item
                categoria_nombre = str(row.get('CATEGORIA', 'General')).strip()
                item_nombre = str(row.get('ITEM', '')).strip()
                
                if not item_nombre:
                    errores += 1
                    continue
                
                # Validar categoría
                if not CategoriaInventario.query.filter_by(nombre=categoria_nombre).first():
                    db.session.add(CategoriaInventario(nombre=categoria_nombre))
                    db.session.commit()
                
                # Generar número de inventario consecutivo automáticamente
                num_inv = generar_consecutivo_por_categoria(categoria_nombre, item_nombre)
                consecutivos_generados += 1
                
                # Obtener bodega por nombre
                bodega_nombre = str(row.get('BODEGA', '')).strip()
                bodega_id = None
                if bodega_nombre and bodega_nombre != 'nan':
                    bodega = Bodega.query.filter(Bodega.nombre.ilike(bodega_nombre)).first()
                    if bodega:
                        bodega_id = bodega.id
                
                # Obtener valores opcionales
                marca_modelo = str(row.get('MARCA/MODELO', ''))
                if marca_modelo == 'nan':
                    marca_modelo = ''
                    
                serial = str(row.get('SERIAL', ''))
                if serial == 'nan':
                    serial = ''
                    
                activo_fijo = str(row.get('ACTIVO FIJO', ''))
                if activo_fijo == 'nan':
                    activo_fijo = ''
                    
                ubicacion = str(row.get('UBICACION PERMANENTE', ''))
                if ubicacion == 'nan':
                    ubicacion = ''
                    
                estado = str(row.get('ESTADO', 'Disponible'))
                if estado == 'nan':
                    estado = 'Disponible'
                
                # Crear nuevo item con consecutivo generado
                nuevo_item = Inventario(
                    categoria=categoria_nombre,
                    item=item_nombre,
                    marca_modelo=marca_modelo,
                    serial=serial,
                    activo_fijo=activo_fijo,
                    numero_inventario=num_inv,
                    ubicacion_permanente=ubicacion,
                    estado=estado,
                    bodega_id=bodega_id
                )
                db.session.add(nuevo_item)
                
                exitos += 1
                
                # Commit cada 50 registros para evitar problemas de memoria
                if exitos % 50 == 0:
                    db.session.commit()
                    
            except Exception as e:
                errores += 1
                current_app.logger.error(f'Error en fila {idx + 2}: {str(e)}')
                continue
        
        db.session.commit()
        
        mensaje = f'Importación completada: {exitos} registros procesados con {consecutivos_generados} números de inventario generados automáticamente'
        if errores > 0:
            mensaje += f', {errores} errores'
        
        flash(mensaje, 'success' if errores == 0 else 'warning')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al procesar el archivo: {str(e)}', 'danger')
        current_app.logger.error(f'Error en importación: {str(e)}', exc_info=True)
        
    return redirect(url_for('inventario.inventario_main'))

@inventario_bp.route('/reporte/existencias')
@login_required
def reporte_existencias():
    """Genera reporte de existencias en Excel."""
    try:
        items = Inventario.query.all()
        
        data = []
        for i in items:
            data.append({
                'ID': i.numero_inventario,
                'Item': i.item,
                'Categoría': i.categoria,
                'Marca/Modelo': i.marca_modelo,
                'Serial': i.serial,
                'Activo Fijo': i.activo_fijo,
                'Estado': i.estado,
                'Ubicación': i.ubicacion_permanente,
                'Bodega': i.bodega.nombre if i.bodega else 'N/A',
                'Veces Prestado': i.veces_prestado
            })
            
        df = pd.DataFrame(data)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Inventario')
            
        output.seek(0)
        
        filename = f"reporte_inventario_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            download_name=filename,
            as_attachment=True
        )
    except Exception as e:
        flash('Error al generar el reporte.', 'danger')
        return redirect(url_for('inventario.inventario_main'))

def calcular_estadisticas_inventario():
    """Calcula estadísticas rápidas para el dashboard de inventario."""
    try:
        total_items = Inventario.query.count()
        disponibles = Inventario.query.filter_by(estado='Disponible').count()
        prestados = Inventario.query.filter_by(estado='En Préstamo').count()
        mantenimiento = Inventario.query.filter_by(estado='En Mantenimiento').count()
        reparacion = Inventario.query.filter_by(estado='En Reparación').count()
        
        # Categoría más prestada (simulado por ahora o basado en historial)
        categorias_count = db.session.query(
            Inventario.categoria, func.count(Inventario.id)
        ).group_by(Inventario.categoria).all()
        
        return {
            'total': total_items,
            'disponibles': disponibles,
            'prestados': prestados,
            'mantenimiento': mantenimiento,
            'reparacion': reparacion,
            'por_categoria': dict(categorias_count)
        }
    except:
        return {}


@inventario_bp.route('/exportar/<formato>')
@login_required
@permiso_requerido('inventario', 'ver')
def exportar_inventario(formato):
    """Exporta el inventario visible (con los mismos filtros activos) en Excel o CSV."""
    try:
        # Reutilizar los mismos filtros que usa la vista principal
        categoria_filtro  = request.args.get('categoria', '')
        estado_filtro     = request.args.get('estado', '')
        busqueda          = request.args.get('busqueda', '')
        sede_actual_id    = request.args.get('sede', '')
        bodega_filtro     = request.args.get('bodega', '')

        query = Inventario.query

        if categoria_filtro:
            query = query.filter(Inventario.categoria == categoria_filtro)
        if estado_filtro:
            query = query.filter(Inventario.estado == estado_filtro)
        if busqueda:
            t = f"%{busqueda}%"
            query = query.filter(
                db.or_(
                    Inventario.item.ilike(t),
                    Inventario.marca_modelo.ilike(t),
                    Inventario.serial.ilike(t),
                    Inventario.numero_inventario.ilike(t),
                )
            )

        # Seguridad por sede para auxiliares
        sede_id_sesion = session.get('sede_id') if session.get('rol') not in ('admin', 'superadmin') else None
        if sede_id_sesion:
            query = query.outerjoin(Inventario.bodega).filter(
                db.or_(Bodega.sede_id == sede_id_sesion, Inventario.bodega_id.is_(None))
            )
        elif sede_actual_id:
            bodegas = Bodega.query.filter_by(sede_id=int(sede_actual_id)).all()
            ids = [b.id for b in bodegas]
            query = query.filter(Inventario.bodega_id.in_(ids)) if ids else query.filter(db.false())

        if bodega_filtro:
            query = query.filter(Inventario.bodega_id == int(bodega_filtro))

        items = query.order_by(Inventario.id).all()

        if not items:
            flash('No hay ítems que coincidan con los filtros para exportar.', 'info')
            return redirect(url_for('inventario.inventario_main'))

        data = []
        for i in items:
            data.append({
                'N° Inventario':       i.numero_inventario or '',
                'Categoría':           i.categoria or '',
                'Equipo/Item':         i.item or '',
                'Marca/Modelo':        i.marca_modelo or '',
                'Serial':              i.serial or '',
                'Activo Fijo':         i.activo_fijo or '',
                'Estado':              i.estado or '',
                'Ubicación':           i.ubicacion_permanente or '',
                'Bodega':              i.bodega.nombre if i.bodega else '',
                'Gestión por Cantidad':  'Sí' if i.es_por_cantidad else 'No',
                'Cantidad Total':      i.cantidad_total if i.es_por_cantidad else '',
                'Cantidad Disponible': i.cantidad_disponible if i.es_por_cantidad else '',
                'Veces Prestado':      i.veces_prestado,
                'Observaciones':       i.observaciones or '',
            })

        df = pd.DataFrame(data)

        if formato.lower() == 'excel':
            return exportar_df_excel(df, sheet_name='Inventario', prefix='inventario')
        elif formato.lower() == 'csv':
            return exportar_df_csv(df, prefix='inventario')
        else:
            flash('Formato no válido. Use excel o csv.', 'warning')
            return redirect(url_for('inventario.inventario_main'))

    except Exception as e:
        current_app.logger.error('Error al exportar inventario: %s', e, exc_info=True)
        flash('Error al exportar el inventario.', 'danger')
        return redirect(url_for('inventario.inventario_main'))


@inventario_bp.route('/bulk_update', methods=['POST'])
@login_required
@permiso_requerido('inventario', 'editar')
def bulk_update():
    """Actualiza sede y bodega de múltiples items del inventario."""
    try:
        datos = request.json
        item_ids = [int(i) for i in datos.get('item_ids', [])]
        sede_id = datos.get('sede_id')
        bodega_id = datos.get('bodega_id')

        if not item_ids:
            return jsonify({'success': False, 'message': 'No se seleccionaron items.'}), 400
        
        if not sede_id or not bodega_id:
            return jsonify({'success': False, 'message': 'Sede y Bodega son requeridas.'}), 400

        items = Inventario.query.filter(Inventario.id.in_(item_ids)).all()
        
        actualizados = 0
        for item in items:
            # Auditoría antes del cambio
            datos_antes = {
                'sede_id': item.bodega.sede_id if item.bodega else None,
                'bodega_id': item.bodega_id
            }

            item.bodega_id = int(bodega_id)
            actualizados += 1

            registrar_auditoria(
                modulo='inventario',
                entidad_tipo='Inventario',
                entidad_id=item.id,
                accion='EDITAR_MASIVO',
                usuario_documento=session.get('usuario', ''),
                usuario_nombre=session.get('nombre_completo', ''),
                descripcion=f'Cambio masivo de ubicación para "{item.item}"',
                datos_antes=datos_antes,
                datos_despues={'sede_id': int(sede_id), 'bodega_id': int(bodega_id)}
            )

        db.session.commit()
        return jsonify({
            'success': True, 
            'message': f'Se actualizaron {actualizados} items correctamente.'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error en bulk_update inventario: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# =========================================================================
# RUTAS DE TRAZABILIDAD, MANTENIMIENTO, BAJAS, ETIQUETAS Y PLANTILLA EXCEL
# =========================================================================




@inventario_bp.route('/<int:id>/trazabilidad')
@login_required
@permiso_requerido('inventario', 'ver')
def trazabilidad_item(id):
    """Retorna la ficha técnica, historial de préstamos y mantenimientos del equipo."""
    try:
        item = Inventario.query.get_or_404(id)

        # 1. Historial de préstamos
        prestamos_raw = PrestamoEquipo.query.filter_by(
            numero_inventario_equipo=item.numero_inventario
        ).order_by(PrestamoEquipo.fecha_prestamo.desc(), PrestamoEquipo.hora_inicio.desc()).limit(50).all()

        prestamos_historial = []
        for p in prestamos_raw:
            prestamos_historial.append({
                'id_prestamo': p.id_prestamo,
                'profesor': p.nombre_profesor or (p.profesor.nombre_completo if p.profesor else 'Docente'),
                'fecha': p.fecha_prestamo.strftime('%d/%m/%Y'),
                'horario': f"{p.hora_inicio.strftime('%H:%M')} - {p.hora_fin.strftime('%H:%M')}",
                'auxiliar_entrega': p.auxiliar_entrega,
                'auxiliar_recibe': p.auxiliar_recibe or '--',
                'estado': p.estado,
                'fecha_devolucion': p.fecha_devolucion.strftime('%d/%m/%Y') if p.fecha_devolucion else '--',
                'observaciones': p.observaciones or ''
            })

        # 2. Historial de mantenimientos
        mantenimientos_raw = MantenimientoInventario.query.filter_by(
            inventario_id=item.id
        ).order_by(MantenimientoInventario.fecha_envio.desc()).all()

        mantenimientos_historial = []
        for m in mantenimientos_raw:
            mantenimientos_historial.append({
                'id': m.id,
                'tipo': m.tipo,
                'motivo': m.motivo,
                'proveedor': m.proveedor_tecnico or 'Técnico Interno',
                'fecha_envio': m.fecha_envio.strftime('%d/%m/%Y'),
                'fecha_retorno': m.fecha_retorno_real.strftime('%d/%m/%Y') if m.fecha_retorno_real else (f"Est: {m.fecha_estimada_retorno.strftime('%d/%m/%Y')}" if m.fecha_estimada_retorno else '--'),
                'estado': m.estado,
                'diagnostico': m.diagnostico_solucion or '--',
                'auxiliar': m.auxiliar_responsable
            })

        # 3. Auditoría de cambios
        auditorias_raw = AuditLog.query.filter(
            AuditLog.modulo == 'inventario',
            AuditLog.entidad_id == str(item.id)
        ).order_by(AuditLog.fecha.desc(), AuditLog.hora.desc()).limit(20).all()

        auditorias = []
        for a in auditorias_raw:
            auditorias.append({
                'accion': a.accion,
                'usuario': a.usuario_nombre or a.usuario_documento,
                'fecha': f"{a.fecha.strftime('%d/%m/%Y')} {a.hora.strftime('%H:%M')}",
                'descripcion': a.descripcion
            })

        return jsonify({
            'success': True,
            'item': {
                'id': item.id,
                'item': item.item,
                'categoria': item.categoria,
                'marca_modelo': item.marca_modelo or '--',
                'serial': item.serial or '--',
                'activo_fijo': item.activo_fijo or '--',
                'numero_inventario': item.numero_inventario or '--',
                'ubicacion': item.ubicacion_permanente or '--',
                'estado': item.estado,
                'sede': item.bodega.sede.nombre if item.bodega and item.bodega.sede else 'Sin Sede',
                'bodega': item.bodega.nombre if item.bodega else 'Sin Bodega',
                'veces_prestado': item.veces_prestado,
                'es_por_cantidad': item.es_por_cantidad,
                'cantidad_total': item.cantidad_total,
                'cantidad_disponible': item.cantidad_disponible,
                'observaciones': item.observaciones or ''
            },
            'prestamos': prestamos_historial,
            'mantenimientos': mantenimientos_historial,
            'auditorias': auditorias
        })
    except Exception as e:
        current_app.logger.error(f"Error obteniendo trazabilidad: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@inventario_bp.route('/<int:id>/mantenimiento', methods=['POST'])
@login_required
@permiso_requerido('inventario', 'editar')
def registrar_mantenimiento(id):
    """Envía un equipo a mantenimiento correctivo/preventivo."""
    try:
        item = Inventario.query.get_or_404(id)
        datos = request.form

        tipo = datos.get('tipo', 'Correctivo').strip()
        motivo = datos.get('motivo', '').strip()
        proveedor = datos.get('proveedor_tecnico', '').strip()
        fecha_retorno_str = datos.get('fecha_estimada_retorno', '')
        fecha_retorno = datetime.strptime(fecha_retorno_str, '%Y-%m-%d').date() if fecha_retorno_str else None

        if not motivo:
            flash('El motivo del mantenimiento es obligatorio.', 'warning')
            return redirect(url_for('inventario.inventario_main'))

        ahora = datetime.now()
        auxiliar_nombre = session.get('nombre_completo', session.get('usuario', 'Auxiliar'))

        nuevo_mant = MantenimientoInventario(
            inventario_id=item.id,
            tipo=tipo,
            motivo=motivo,
            proveedor_tecnico=proveedor,
            fecha_envio=ahora.date(),
            fecha_estimada_retorno=fecha_retorno,
            estado='En Proceso',
            auxiliar_responsable=auxiliar_nombre
        )
        db.session.add(nuevo_mant)

        estado_ant = item.estado
        item.estado = 'En Mantenimiento'

        db.session.commit()

        registrar_auditoria(
            modulo='inventario',
            entidad_tipo='Inventario',
            entidad_id=item.id,
            accion='ENVIAR_MANTENIMIENTO',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=auxiliar_nombre,
            descripcion=f'Equipo "{item.item}" enviado a mantenimiento ({tipo}): {motivo[:60]}',
            datos_antes={'estado': estado_ant},
            datos_despues={'estado': 'En Mantenimiento'}
        )

        flash(f'Equipo "{item.item}" enviado a mantenimiento exitosamente.', 'success')
        return redirect(url_for('inventario.inventario_main'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error registrando mantenimiento: {e}")
        flash(f'Error al registrar mantenimiento: {str(e)}', 'danger')
        return redirect(url_for('inventario.inventario_main'))


@inventario_bp.route('/<int:id>/retornar_mantenimiento', methods=['POST'])
@login_required
@permiso_requerido('inventario', 'editar')
def retornar_mantenimiento(id):
    """Registra el retorno exitoso de un equipo de mantenimiento a Disponible."""
    try:
        item = Inventario.query.get_or_404(id)
        diagnostico = request.form.get('diagnostico_solucion', '').strip()
        ahora = datetime.now()
        auxiliar_nombre = session.get('nombre_completo', session.get('usuario', 'Auxiliar'))

        ultimo_mant = MantenimientoInventario.query.filter_by(
            inventario_id=item.id, estado='En Proceso'
        ).order_by(MantenimientoInventario.fecha_envio.desc()).first()

        if ultimo_mant:
            ultimo_mant.estado = 'Finalizado'
            ultimo_mant.fecha_retorno_real = ahora.date()
            ultimo_mant.diagnostico_solucion = diagnostico

        item.estado = 'Disponible'
        db.session.commit()

        registrar_auditoria(
            modulo='inventario',
            entidad_tipo='Inventario',
            entidad_id=item.id,
            accion='RETORNO_MANTENIMIENTO',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=auxiliar_nombre,
            descripcion=f'Equipo "{item.item}" retornó de mantenimiento a Disponible: {diagnostico[:60]}',
            datos_antes={'estado': 'En Mantenimiento'},
            datos_despues={'estado': 'Disponible'}
        )

        flash(f'Equipo "{item.item}" reincorporado a inventario Disponible.', 'success')
        return redirect(url_for('inventario.inventario_main'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error retornando de mantenimiento: {e}")
        flash(f'Error al retornar de mantenimiento: {str(e)}', 'danger')
        return redirect(url_for('inventario.inventario_main'))


@inventario_bp.route('/<int:id>/baja', methods=['POST'])
@login_required
@permiso_requerido('inventario', 'eliminar')
def dar_de_baja_item(id):
    """Da de baja un equipo del inventario de forma oficial con justificación."""
    try:
        item = Inventario.query.get_or_404(id)
        motivo = request.form.get('motivo_baja', '').strip()
        soporte = request.form.get('soporte_resolucion', '').strip()

        if not motivo:
            flash('El motivo de baja es obligatorio.', 'warning')
            return redirect(url_for('inventario.inventario_main'))

        ahora = datetime.now()
        auxiliar_nombre = session.get('nombre_completo', session.get('usuario', 'Auxiliar'))

        estado_ant = item.estado
        item.estado = 'De Baja'
        item.observaciones = f"[DADO DE BAJA {ahora.strftime('%d/%m/%Y')} por {auxiliar_nombre}]: {motivo}. Soporte: {soporte or 'N/A'}"

        db.session.commit()

        registrar_auditoria(
            modulo='inventario',
            entidad_tipo='Inventario',
            entidad_id=item.id,
            accion='DAR_DE_BAJA',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=auxiliar_nombre,
            descripcion=f'Equipo "{item.item}" ({item.numero_inventario}) dado de baja: {motivo[:60]}',
            datos_antes={'estado': estado_ant},
            datos_despues={'estado': 'De Baja'}
        )

        flash(f'Equipo "{item.item}" marcado como De Baja.', 'success')
        return redirect(url_for('inventario.inventario_main'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error dando de baja: {e}")
        flash(f'Error al dar de baja el item: {str(e)}', 'danger')
        return redirect(url_for('inventario.inventario_main'))


@inventario_bp.route('/api/etiquetas', methods=['POST'])
@login_required
def api_generar_etiquetas():
    """Genera datos de etiquetas con código de barras y QR para los items seleccionados."""
    try:
        datos = request.get_json(silent=True) or request.form
        item_ids = datos.get('item_ids', [])
        if not item_ids:
            return jsonify({'success': False, 'message': 'No se seleccionaron items.'}), 400

        items = Inventario.query.filter(Inventario.id.in_([int(i) for i in item_ids])).all()

        etiquetas = []
        for i in items:
            etiquetas.append({
                'id': i.id,
                'numero_inventario': i.numero_inventario or f"ID-{i.id}",
                'item': i.item,
                'categoria': i.categoria,
                'marca_modelo': i.marca_modelo or '',
                'serial': i.serial or '',
                'activo_fijo': i.activo_fijo or '',
                'sede': i.bodega.sede.nombre if i.bodega and i.bodega.sede else 'UNIMINUTO',
                'bodega': i.bodega.nombre if i.bodega else ''
            })

        return jsonify({'success': True, 'etiquetas': etiquetas})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@inventario_bp.route('/plantilla_excel', methods=['GET'])
@login_required
def descargar_plantilla_excel():
    """Genera y descarga la plantilla oficial de Excel para carga masiva de inventario."""
    try:
        data = {
            'numero_inventario': ['INV-PC-001', 'INV-CAB-002'],
            'categoria': ['Computadores', 'Cables y Adaptadores'],
            'item': ['Portátil HP ProBook 450 G8', 'Cable HDMI 2.0 (1.8m)'],
            'marca_modelo': ['HP ProBook 450', 'UGREEN High Speed'],
            'serial': ['5CD1234XYZ', 'N/A'],
            'activo_fijo': ['AF-987654', 'AF-987655'],
            'ubicacion_permanente': ['Estante A-3', 'Caja 12 - Bodega Principal'],
            'sede': ['Sede Principal', 'Sede Principal'],
            'bodega': ['Bodega Principal', 'Bodega Principal'],
            'es_por_cantidad': ['NO', 'SI'],
            'cantidad_total': [1, 20],
            'observaciones': ['Equipo asignado a préstamos docentes', 'Stock de cables para aulas']
        }
        df = pd.DataFrame(data)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Inventario', index=False)
            ws = writer.sheets['Inventario']
            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = col[0].column_letter
                ws.column_dimensions[col_letter].width = max(max_len + 4, 15)
                
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name='Plantilla_Carga_Inventario_UNIMINUTO.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        current_app.logger.error(f"Error generando plantilla excel: {e}")
        flash('Error al generar la plantilla de Excel.', 'danger')
        return redirect(url_for('inventario.inventario_main'))


@inventario_bp.route('/importar_excel', methods=['POST'])
@login_required
@permiso_requerido('inventario', 'crear')
def importar_excel():
    """Importa registros de inventario de forma masiva desde un archivo Excel/CSV."""
    try:
        archivo = request.files.get('archivo_excel')
        if not archivo or not archivo.filename:
            flash('Debe seleccionar un archivo Excel (.xlsx, .xls) o CSV.', 'warning')
            return redirect(url_for('inventario.inventario_main'))

        filename = archivo.filename.lower()
        if filename.endswith('.csv'):
            df = pd.read_csv(archivo)
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(archivo)
        else:
            flash('Formato no soportado. Suba un archivo .xlsx, .xls o .csv.', 'danger')
            return redirect(url_for('inventario.inventario_main'))

        df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]

        creados = 0
        actualizados = 0

        sedes_map = {s.nombre.lower(): s.id for s in Sede.query.all()}
        bodegas_all = Bodega.query.all()
        bodegas_map = {(b.sede_id, b.nombre.lower()): b.id for b in bodegas_all}

        default_sede = Sede.query.first()
        default_bodega = Bodega.query.first() if default_sede else None

        for idx, row in df.iterrows():
            item_nombre = str(row.get('item', '')).strip()
            if not item_nombre or item_nombre.lower() == 'nan':
                continue

            categoria = str(row.get('categoria', 'Otros')).strip()
            if not categoria or categoria.lower() == 'nan':
                categoria = 'Otros'

            sede_nombre = str(row.get('sede', '')).strip().lower()
            bodega_nombre = str(row.get('bodega', '')).strip().lower()

            sede_id = sedes_map.get(sede_nombre) or (default_sede.id if default_sede else None)
            bodega_id = bodegas_map.get((sede_id, bodega_nombre)) or (default_bodega.id if default_bodega else None)

            if not bodega_id and sede_id and bodega_nombre and bodega_nombre != 'nan':
                nueva_bod = Bodega(nombre=row.get('bodega').strip(), sede_id=sede_id)
                db.session.add(nueva_bod)
                db.session.flush()
                bodegas_map[(sede_id, bodega_nombre)] = nueva_bod.id
                bodega_id = nueva_bod.id

            es_por_cant_raw = str(row.get('es_por_cantidad', 'NO')).strip().upper()
            es_por_cantidad = es_por_cant_raw in ['SI', 'YES', 'TRUE', '1', 'S']

            try:
                cant_total = int(row.get('cantidad_total', 1))
            except (ValueError, TypeError):
                cant_total = 1

            num_inv = str(row.get('numero_inventario', '')).strip()
            if num_inv.lower() == 'nan' or not num_inv:
                num_inv = None

            serial = str(row.get('serial', '')).strip()
            if serial.lower() == 'nan':
                serial = None

            activo_fijo = str(row.get('activo_fijo', '')).strip()
            if activo_fijo.lower() == 'nan':
                activo_fijo = None

            marca_mod = str(row.get('marca_modelo', '')).strip()
            if marca_mod.lower() == 'nan':
                marca_mod = None

            ubicacion = str(row.get('ubicacion_permanente', '')).strip()
            if ubicacion.lower() == 'nan':
                ubicacion = None

            obs = str(row.get('observaciones', '')).strip()
            if obs.lower() == 'nan':
                obs = ''

            item_existente = None
            if num_inv:
                item_existente = Inventario.query.filter_by(numero_inventario=num_inv).first()

            if item_existente:
                item_existente.item = item_nombre
                item_existente.categoria = categoria
                item_existente.marca_modelo = marca_mod
                item_existente.serial = serial
                item_existente.activo_fijo = activo_fijo
                item_existente.bodega_id = bodega_id
                item_existente.ubicacion_permanente = ubicacion
                if es_por_cantidad:
                    item_existente.es_por_cantidad = True
                    item_existente.cantidad_total = cant_total
                    item_existente.cantidad_disponible = cant_total
                if obs:
                    item_existente.observaciones = obs
                actualizados += 1
            else:
                nuevo_item = Inventario(
                    categoria=categoria,
                    item=item_nombre,
                    marca_modelo=marca_mod,
                    serial=serial,
                    activo_fijo=activo_fijo,
                    numero_inventario=num_inv,
                    bodega_id=bodega_id,
                    ubicacion_permanente=ubicacion,
                    estado='Disponible',
                    es_por_cantidad=es_por_cantidad,
                    cantidad_total=cant_total if es_por_cantidad else 1,
                    cantidad_disponible=cant_total if es_por_cantidad else 1,
                    observaciones=obs
                )
                db.session.add(nuevo_item)
                creados += 1

        db.session.commit()

        auxiliar_nombre = session.get('nombre_completo', session.get('usuario', 'Auxiliar'))
        registrar_auditoria(
            modulo='inventario',
            entidad_tipo='Inventario',
            accion='IMPORTACION_MASIVA_EXCEL',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=auxiliar_nombre,
            descripcion=f'Importación masiva completada: {creados} creados, {actualizados} actualizados.'
        )

        flash(f'Importación exitosa: {creados} items creados y {actualizados} actualizados.', 'success')
        return redirect(url_for('inventario.inventario_main'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error importando archivo excel: {e}")
        flash(f'Error al procesar el archivo: {str(e)}', 'danger')
        return redirect(url_for('inventario.inventario_main'))


