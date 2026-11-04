"""
Blueprint para gestión completa del inventario de equipos y recursos.
Incluye CRUD, gestión de categorías, historial de movimientos y reportes.
"""
from flask import Blueprint, render_template, request, redirect, flash, jsonify, send_file, url_for, session, current_app
import io
import pandas as pd
from datetime import datetime, date
from database import db, Inventario, PrestamoEquipo, Sede, Bodega, CategoriaInventario, UserPermission, registrar_auditoria, MantenimientoInventario, AuditLog, InventarioCustodia
from extensions import socketio
from services.notification_service import NotificationService
from config import SystemConstants
from validators import DataValidator
from sqlalchemy import func, desc, asc
from auth import login_required, permiso_requerido, sede_requerida
from services.inventario_service import InventarioService
from services.acta_custodia_service import ActaCustodiaService
from utils.export_helpers import exportar_df_excel, exportar_df_csv
from blueprints.mantenimiento import _procesar_y_guardar_imagen
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

        sede_usuario = Sede.query.get(int(user_sede_id)) if user_sede_id and str(user_sede_id).isdigit() else None
        bodegas_usuario = Bodega.query.filter_by(sede_id=int(user_sede_id)).all() if user_sede_id and str(user_sede_id).isdigit() else []

        tab_activa = request.args.get('tab', 'inventario')
        custodias_list = InventarioService.obtener_custodias_filtradas(
            request.args, user_rol=user_rol, user_sede_id=user_sede_id
        )
        custodias_stats = InventarioService.calcular_estadisticas_custodia(custodias_list)

        # Opciones para filtros de la tabla de Custodia
        custodia_edificios = [r[0] for r in db.session.query(InventarioCustodia.edificio).filter(InventarioCustodia.edificio.isnot(None)).distinct().all() if r[0]]
        custodia_centros = [r[0] for r in db.session.query(InventarioCustodia.centro_costo).filter(InventarioCustodia.centro_costo.isnot(None)).distinct().all() if r[0]]
        custodia_estados = [r[0] for r in db.session.query(InventarioCustodia.estado).filter(InventarioCustodia.estado.isnot(None)).distinct().all() if r[0]]

        # === CATEGORÍAS FILTRADAS EXCLUSIVAMENTE POR LA SEDE EN SESIÓN ===
        user_sede_id_int = int(user_sede_id) if user_sede_id and str(user_sede_id).isdigit() else None
        
        # Bodegas pertenecientes a la sede en sesión
        bodegas_sede_activa = Bodega.query.filter_by(sede_id=user_sede_id_int).all() if user_sede_id_int else []
        bodega_ids_sede_activa = [b.id for b in bodegas_sede_activa]
        
        # Activos pertenecientes ÚNICAMENTE a la sede de la sesión
        if bodega_ids_sede_activa:
            items_sede_activa = Inventario.query.filter(Inventario.bodega_id.in_(bodega_ids_sede_activa)).order_by(Inventario.categoria, Inventario.item).all()
        else:
            items_sede_activa = []
        
        ICONOS_CATEGORIAS = {
            'Equipos Portátiles': ('bi-laptop', 'success'),
            'Proyectores (Video Beam)': ('bi-projector', 'primary'),
            'Adaptadores de corriente': ('bi-plug', 'warning'),
            'Periféricos (Teclados, Mouse)': ('bi-keyboard', 'info'),
            'Audio/Video (HDMI, Parlantes)': ('bi-speaker', 'secondary'),
            'Todo en Uno': ('bi-pc-display', 'primary'),
            'Pantallas Digitales Interactivas': ('bi-tv', 'danger'),
            'Controles TV': ('bi-remote', 'dark'),
            'Equipos de Medición y Laboratorio': ('bi-speedometer2', 'info'),
            'Material Deportivo y Lote': ('bi-trophy', 'warning'),
            'Otros / General': ('bi-box-seam', 'secondary'),
        }

        from collections import defaultdict
        cat_map = defaultdict(lambda: {
            'nombre': '',
            'total': 0,
            'disponibles': 0,
            'prestados': 0,
            'mantenimiento': 0,
            'baja': 0,
            'icono': 'bi-box-seam',
            'color': 'secondary',
            'items': []
        })

        for it in items_sede_activa:
            c_nom = (it.categoria or 'Otros / General').strip()
            entry = cat_map[c_nom]
            entry['nombre'] = c_nom
            entry['total'] += 1
            if it.estado == 'Disponible':
                entry['disponibles'] += 1
            elif it.estado == 'En Préstamo':
                entry['prestados'] += 1
            elif it.estado in ('En Mantenimiento', 'En Reparación'):
                entry['mantenimiento'] += 1
            elif it.estado == 'De Baja':
                entry['baja'] += 1
            
            ic_info = ICONOS_CATEGORIAS.get(c_nom, ('bi-box-seam', 'secondary'))
            entry['icono'] = ic_info[0]
            entry['color'] = ic_info[1]
            entry['items'].append(it)

        categorias_sede = sorted(cat_map.values(), key=lambda x: x['total'], reverse=True)

        stats_sede_activa = {
            'total': len(items_sede_activa),
            'disponibles': sum(c['disponibles'] for c in categorias_sede),
            'prestados': sum(c['prestados'] for c in categorias_sede),
            'mantenimiento': sum(c['mantenimiento'] for c in categorias_sede),
            'baja': sum(c['baja'] for c in categorias_sede)
        }

        return render_template('inventario.html', 
                             inventario=inventario_list,
                             custodias=custodias_list,
                             custodias_stats=custodias_stats,
                             custodia_edificios=custodia_edificios,
                             custodia_centros=custodia_centros,
                             custodia_estados=custodia_estados,
                             tab_activa=tab_activa,
                             categorias_sede=categorias_sede,
                             items_sede_activa=items_sede_activa,
                             stats_sede_activa=stats_sede_activa,
                             categorias=categorias,
                             estados=estados,
                             sedes=sedes,
                             bodegas=bodegas,
                             sede_usuario=sede_usuario,
                             bodegas_usuario=bodegas_usuario,
                             user_sede_id=user_sede_id,
                             stats=stats,
                             disponibles_count=calc_stats['disponibles_count'],
                             prestados_count=calc_stats['prestados_count'],
                             reparacion_count=calc_stats['mantenimiento_count'],
                             filtros={
                                 'categoria': categoria_filtro,
                                 'estado': estado_filtro,
                                 'busqueda': busqueda,
                                 'sede': sede_actual_id,
                                 'bodega': bodega_filtro,
                                 'edificio': request.args.get('edificio', ''),
                                 'centro_costo': request.args.get('centro_costo', ''),
                                 'cedula_custodio': request.args.get('cedula_custodio', ''),
                                 'tipo_inventario': request.args.get('tipo_inventario', '')
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
                             custodias=[],
                             custodias_stats={'total': 0, 'activos_fijos': 0, 'bodega_lote': 0, 'por_estado': {}, 'por_edificio': {}, 'por_centro_costo': {}},
                             custodia_edificios=[],
                             custodia_centros=[],
                             custodia_estados=[],
                             tab_activa='inventario',
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


def _propagar_foto_modelo_interno(origen, session_user=None, session_user_name=None):
    """
    Replica la foto del equipo origen a todos los equipos que tengan el mismo modelo o nombre de ítem.
    Retorna el número de equipos actualizados.
    """
    if not origen or not origen.foto_url:
        return 0

    modelo = (origen.marca_modelo or '').strip()
    nombre_item = (origen.item or '').strip()

    filtros = []
    if modelo and modelo.lower() not in ('nan', 'none', '--', 'no presenta', ''):
        filtros.append(func.lower(Inventario.marca_modelo) == modelo.lower())
    if nombre_item and nombre_item.lower() not in ('nan', 'none', '--', ''):
        filtros.append(func.lower(Inventario.item) == nombre_item.lower())

    if not filtros:
        return 0

    criterio = db.or_(*filtros)
    otros_equipos = Inventario.query.filter(Inventario.id != origen.id, criterio).all()

    actualizados = 0
    for target in otros_equipos:
        if target.foto_url != origen.foto_url:
            datos_antes = {'foto_url': target.foto_url}
            target.foto_url = origen.foto_url
            actualizados += 1
            if session_user:
                registrar_auditoria(
                    modulo='inventario',
                    entidad_tipo='Inventario',
                    entidad_id=target.id,
                    accion='REPLICAR_FOTO_MODELO',
                    usuario_documento=session_user,
                    usuario_nombre=session_user_name or '',
                    descripcion=f'Foto replicada desde equipo #{origen.id} ({modelo or nombre_item})',
                    datos_antes=datos_antes,
                    datos_despues={'foto_url': target.foto_url}
                )

    if actualizados > 0:
        db.session.commit()

    return actualizados

@inventario_bp.route('/agregar', methods=['POST'])
@login_required
@permiso_requerido('inventario', 'crear')
def agregar_item():
    """Agrega un nuevo item al inventario con ficha técnica y foto única estilo Hoja de Vida."""
    try:
        datos = request.get_json(silent=True) or request.form.to_dict()
        
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
        es_por_cantidad = bool(datos.get('es_por_cantidad') in (True, 'true', '1')) or accesorio
        
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
            
        # Sede: NO se le pide al usuario; se toma directamente de la sesión activa
        sede_id = session.get('sede_id') or (current_user.sede_id if hasattr(current_user, 'sede_id') else None)
        bodega_id = datos.get('bodega_id')
        if not bodega_id or str(bodega_id).strip() in ('', 'None', 'undefined'):
            if sede_id and str(sede_id).strip() not in ('', 'None', 'undefined'):
                try:
                    sede_id_int = int(sede_id)
                    bodega_existente = Bodega.query.filter_by(sede_id=sede_id_int).first()
                    if not bodega_existente:
                        sede_obj = Sede.query.get(sede_id_int)
                        nombre_sede = sede_obj.nombre if sede_obj else f"Sede {sede_id_int}"
                        bodega_existente = Bodega(nombre=f'Bodega Principal {nombre_sede}', sede_id=sede_id_int)
                        db.session.add(bodega_existente)
                        db.session.flush()
                    bodega_id = bodega_existente.id
                except Exception as e:
                    current_app.logger.warning(f"Error resolviendo bodega para sede {sede_id}: {e}")
                    bodega_id = None
            else:
                bodega_id = None
        else:
            try:
                bodega_id = int(bodega_id)
            except (ValueError, TypeError):
                bodega_id = None

        # Procesamiento de foto única del elemento (como en Hoja de Vida)
        foto_url = None
        if 'foto' in request.files and request.files['foto'].filename:
            foto_url = _procesar_y_guardar_imagen(request.files['foto'], subcarpeta='equipos')
        elif datos.get('foto_url'):
            foto_url = str(datos.get('foto_url')).strip() or None

        # Procesamiento de fechas de adquisición y garantía (Hoja de Vida)
        f_adq = datos.get('fecha_adquisicion')
        fecha_adq = None
        if f_adq and str(f_adq).strip():
            try:
                fecha_adq = datetime.strptime(str(f_adq).strip(), '%Y-%m-%d').date()
            except ValueError:
                pass

        f_gar = datos.get('garantia_vencimiento')
        fecha_gar = None
        if f_gar and str(f_gar).strip():
            try:
                fecha_gar = datetime.strptime(str(f_gar).strip(), '%Y-%m-%d').date()
            except ValueError:
                pass

        # Crear item con ficha técnica completa y única foto
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
            bodega_id=bodega_id,
            es_por_cantidad=es_por_cantidad,
            cantidad_total=cantidad_total,
            cantidad_disponible=cantidad_disponible,
            # Ficha técnica / Hoja de Vida
            foto_url=foto_url,
            hostname=(datos.get('hostname') or '').strip() or None,
            procesador=(datos.get('procesador') or '').strip() or None,
            ram_gb=(datos.get('ram_gb') or '').strip() or None,
            almacenamiento=(datos.get('almacenamiento') or '').strip() or None,
            sistema_operativo=(datos.get('sistema_operativo') or '').strip() or None,
            especificaciones_tecnicas=(datos.get('especificaciones_tecnicas') or '').strip() or None,
            proveedor=(datos.get('proveedor') or '').strip() or None,
            fecha_adquisicion=fecha_adq,
            garantia_vencimiento=fecha_gar
        )
        
        db.session.add(nuevo_item)
        db.session.commit()

        # Emitir notificación usando el servicio centralizado
                # Propagar foto al modelo si se solicitó
        if datos.get('propagar_foto_modelo') in (True, 'true', '1') and nuevo_item.foto_url:
            _propagar_foto_modelo_interno(nuevo_item, session.get('usuario', ''), session.get('nombre_completo', ''))
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
            descripcion=f'Creación de item de inventario "{nuevo_item.item}" con ficha técnica',
            datos_antes=None,
            datos_despues={
                'categoria': nuevo_item.categoria,
                'item': nuevo_item.item,
                'numero_inventario': nuevo_item.numero_inventario,
                'estado': nuevo_item.estado,
                'foto_url': nuevo_item.foto_url
            }
        )

        return jsonify({
            'success': True,
            'message': f'Item "{nuevo_item.item}" agregado exitosamente',
            'id': nuevo_item.id,
            'foto_url': nuevo_item.foto_url
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

@inventario_bp.route('/editar/<int:id>', methods=['PUT', 'POST', 'GET'])
@login_required
@permiso_requerido('inventario', 'editar')
def editar_item(id):
    """Obtiene o actualiza un item del inventario con su ficha técnica y foto única."""
    item = Inventario.query.get_or_404(id)
    
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'item': {
                'id': item.id,
                'categoria': item.categoria,
                'item': item.item,
                'marca_modelo': item.marca_modelo or '',
                'serial': item.serial or '',
                'activo_fijo': item.activo_fijo or '',
                'numero_inventario': item.numero_inventario or '',
                'ubicacion_permanente': item.ubicacion_permanente or '',
                'estado': item.estado,
                'observaciones': item.observaciones or '',
                'bodega_id': item.bodega_id,
                'bodega_nombre': item.bodega.nombre if item.bodega else '',
                'sede_id': item.bodega.sede_id if (item.bodega and item.bodega.sede_id) else None,
                'sede_nombre': item.bodega.sede.nombre if (item.bodega and item.bodega.sede) else '',
                'es_por_cantidad': item.es_por_cantidad,
                'cantidad_total': item.cantidad_total,
                'cantidad_disponible': item.cantidad_disponible,
                # Hoja de Vida / Ficha técnica
                'foto_url': item.foto_url or '',
                'hostname': item.hostname or '',
                'procesador': item.procesador or '',
                'ram_gb': item.ram_gb or '',
                'almacenamiento': item.almacenamiento or '',
                'sistema_operativo': item.sistema_operativo or '',
                'especificaciones_tecnicas': item.especificaciones_tecnicas or '',
                'proveedor': item.proveedor or '',
                'fecha_adquisicion': item.fecha_adquisicion.strftime('%Y-%m-%d') if item.fecha_adquisicion else '',
                'garantia_vencimiento': item.garantia_vencimiento.strftime('%Y-%m-%d') if item.garantia_vencimiento else ''
            }
        })
        
    try:
        datos = request.get_json(silent=True) or request.form.to_dict()
        
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
            'foto_url': item.foto_url
        }

        if datos.get('categoria'):
            item.categoria = datos.get('categoria')
        if datos.get('item'):
            item.item = datos.get('item')
        if 'marca_modelo' in datos:
            item.marca_modelo = datos.get('marca_modelo')
        if 'serial' in datos:
            item.serial = datos.get('serial')
        # Si el item es un accesorio (control/cable) permitimos dejar activo_fijo vacío
        nombre_item = (datos.get('item') or item.item or '')
        accesorio = 'control' in nombre_item.lower() or 'cable' in nombre_item.lower()
        if 'activo_fijo' in datos:
            item.activo_fijo = (datos.get('activo_fijo') or '').strip() if not accesorio else None
        # Mantener un número de inventario válido; si usuario lo vacía y es accesorio, no lo anulamos para no romper préstamos
        if num_inv:
            item.numero_inventario = num_inv
        if 'ubicacion_permanente' in datos:
            item.ubicacion_permanente = datos.get('ubicacion_permanente')
        if datos.get('estado'):
            item.estado = datos.get('estado')
        elif not item.estado:
            item.estado = 'Disponible'
        if 'observaciones' in datos:
            item.observaciones = datos.get('observaciones')
        
        # Bodega: si se especifica y cambia, actualizarla dentro de la sede
        bodega_val = datos.get('bodega_id')
        if bodega_val and str(bodega_val).strip() not in ('', 'None', 'undefined'):
            try:
                item.bodega_id = int(bodega_val)
            except (ValueError, TypeError):
                pass

        # Procesar foto única del elemento (subida o eliminación)
        if 'foto' in request.files and request.files['foto'].filename:
            foto_subida = _procesar_y_guardar_imagen(request.files['foto'], subcarpeta='equipos')
            if foto_subida:
                item.foto_url = foto_subida
        elif datos.get('eliminar_foto') in ('true', True, '1'):
            item.foto_url = None

        # Ficha técnica / Hoja de Vida
        if 'hostname' in datos:
            item.hostname = (datos.get('hostname') or '').strip() or None
        if 'procesador' in datos:
            item.procesador = (datos.get('procesador') or '').strip() or None
        if 'ram_gb' in datos:
            item.ram_gb = (datos.get('ram_gb') or '').strip() or None
        if 'almacenamiento' in datos:
            item.almacenamiento = (datos.get('almacenamiento') or '').strip() or None
        if 'sistema_operativo' in datos:
            item.sistema_operativo = (datos.get('sistema_operativo') or '').strip() or None
        if 'especificaciones_tecnicas' in datos:
            item.especificaciones_tecnicas = (datos.get('especificaciones_tecnicas') or '').strip() or None
        if 'proveedor' in datos:
            item.proveedor = (datos.get('proveedor') or '').strip() or None

        if 'fecha_adquisicion' in datos:
            f_adq = datos.get('fecha_adquisicion')
            if f_adq and str(f_adq).strip():
                try:
                    item.fecha_adquisicion = datetime.strptime(str(f_adq).strip(), '%Y-%m-%d').date()
                except ValueError:
                    pass
            else:
                item.fecha_adquisicion = None

        if 'garantia_vencimiento' in datos:
            f_gar = datos.get('garantia_vencimiento')
            if f_gar and str(f_gar).strip():
                try:
                    item.garantia_vencimiento = datetime.strptime(str(f_gar).strip(), '%Y-%m-%d').date()
                except ValueError:
                    pass
            else:
                item.garantia_vencimiento = None

        # Gestión por cantidad
        es_por_cantidad = bool(datos.get('es_por_cantidad') in (True, 'true', '1'))
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
                # Propagar foto al modelo si se solicitó
        if datos.get('propagar_foto_modelo') in (True, 'true', '1') and item.foto_url:
            _propagar_foto_modelo_interno(item, session.get('usuario', ''), session.get('nombre_completo', ''))
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
            'foto_url': item.foto_url
        }

        
        # Propagar todos los cambios (ficha técnica, garantía, foto) a todos los equipos del mismo modelo si se solicitó
        extra_modelo_count = 0
        if datos.get('propagar_todo_modelo') in (True, 'true', '1'):
            modelo = (item.marca_modelo or '').strip()
            nombre_item = (item.item or '').strip()
            filtros_mod = []
            if modelo and modelo.lower() not in ('nan', 'none', '--', 'no presenta', ''):
                filtros_mod.append(func.lower(Inventario.marca_modelo) == modelo.lower())
            if nombre_item and nombre_item.lower() not in ('nan', 'none', '--', ''):
                filtros_mod.append(func.lower(Inventario.item) == nombre_item.lower())

            if filtros_mod:
                criterio_mod = db.or_(*filtros_mod)
                otros_del_modelo = Inventario.query.filter(Inventario.id != item.id, criterio_mod).all()
                for target in otros_del_modelo:
                    target.procesador = item.procesador
                    target.ram_gb = item.ram_gb
                    target.almacenamiento = item.almacenamiento
                    target.sistema_operativo = item.sistema_operativo
                    target.especificaciones_tecnicas = item.especificaciones_tecnicas
                    target.proveedor = item.proveedor
                    target.fecha_adquisicion = item.fecha_adquisicion
                    target.garantia_vencimiento = item.garantia_vencimiento
                    if item.foto_url:
                        target.foto_url = item.foto_url
                    extra_modelo_count += 1
                if extra_modelo_count > 0:
                    db.session.commit()

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

        return jsonify({
            'success': True,
            'message': 'Item actualizado correctamente',
            'foto_url': item.foto_url
        })
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


@inventario_bp.route('/custodia')
@login_required
@permiso_requerido('inventario', 'ver')
@sede_requerida
def inventario_custodia_view():
    """Acceso directo a la pestaña de custodia y centros de costo."""
    args = dict(request.args)
    args['tab'] = 'custodia'
    return redirect(url_for('inventario.inventario_main', **args))


@inventario_bp.route('/exportar-custodia/<formato>')
@login_required
@permiso_requerido('inventario', 'ver')
def exportar_custodia(formato):
    """Exporta la tabla de custodia y centros de costo con las 8 columnas requeridas más detalles."""
    try:
        user_rol = session.get('rol')
        user_sede_id = session.get('sede_id')
        custodias = InventarioService.obtener_custodias_filtradas(
            request.args, user_rol=user_rol, user_sede_id=user_sede_id
        )
        if not custodias:
            flash('No hay registros de custodia para exportar.', 'info')
            return redirect(url_for('inventario.inventario_main', tab='custodia'))

        data = []
        for c in custodias:
            data.append({
                'ESTADO': c.estado,
                'NOMBRE DEL CENTRO DE COSTO': c.nombre_centro_costo or '',
                'CENTRO DE COSTO': c.centro_costo or '',
                'CARGO RESPONSABLE (CUSTODIA)': c.cargo_custodio or '',
                'RESPONSABLE (CUSTODIA)': c.responsable_custodia or '',
                'CEDULA': c.cedula_custodio or '',
                'EDIFICIO': c.edificio or '',
                'UBICACIÓN': c.ubicacion or '',
                'TIPO INVENTARIO': c.tipo_inventario,
                'PLACA': c.placa or '',
                'SERIE': c.serie or '',
                'DESCRIPCIÓN': c.descripcion,
                'MARCA': c.marca or '',
                'CANTIDAD': c.cantidad,
                'PROGRAMA / ÁREA': c.programa_area or '',
                'OBSERVACIONES': c.observaciones or ''
            })
        df = pd.DataFrame(data)
        if formato.lower() == 'excel':
            return exportar_df_excel(df, sheet_name='Custodia_Centros_Costo', prefix='custodia_perdomo')
        elif formato.lower() == 'csv':
            return exportar_df_csv(df, prefix='custodia_perdomo')
        else:
            flash('Formato no válido. Use excel o csv.', 'warning')
            return redirect(url_for('inventario.inventario_main', tab='custodia'))
    except Exception as e:
        current_app.logger.error(f"Error exportando custodia: {e}", exc_info=True)
        flash(f"Error al exportar custodia: {str(e)}", "danger")
        return redirect(url_for('inventario.inventario_main', tab='custodia'))


@inventario_bp.route('/api/custodia/<int:custodia_id>')
@login_required
def api_detalle_custodia(custodia_id):
    """Retorna información completa de un activo en custodia en formato JSON."""
    try:
        c = InventarioCustodia.query.get_or_404(custodia_id)
        return jsonify({
            'success': True,
            'data': {
                'id': c.id,
                'estado': c.estado,
                'nombre_centro_costo': c.nombre_centro_costo or 'Sin especificar',
                'centro_costo': c.centro_costo or 'N/A',
                'cargo_custodio': c.cargo_custodio or 'N/A',
                'responsable_custodia': c.responsable_custodia or 'Sin custodio asignado',
                'cedula_custodio': c.cedula_custodio or 'N/A',
                'edificio': c.edificio or 'PERDOMO',
                'ubicacion': c.ubicacion or 'Sin ubicación',
                'tipo_inventario': c.tipo_inventario,
                'placa': c.placa or 'Sin placa',
                'serie': c.serie or 'N/A',
                'descripcion': c.descripcion,
                'marca': c.marca or 'N/A',
                'cantidad': c.cantidad,
                'cantidad_anterior': c.cantidad_anterior or 'N/A',
                'programa_area': c.programa_area or 'N/A',
                'funcionario_inventario': c.funcionario_inventario or 'N/A',
                'fecha_inventario': c.fecha_inventario or 'N/A',
                'anio_llegada': c.anio_llegada or 'N/A',
                'es_investigacion': c.es_investigacion or 'No',
                'observaciones': c.observaciones or 'Sin observaciones adicionales'
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 404


@inventario_bp.route('/acta-custodia/pdf', methods=['GET', 'POST'])
@login_required
@permiso_requerido('inventario', 'ver')
def descargar_acta_custodia_pdf():
    """Genera y descarga el Acta Oficial de Custodia en PDF para los registros filtrados o seleccionados."""
    try:
        user_rol = session.get('rol')
        user_sede_id = session.get('sede_id')

        # Soporte para selección múltiple de ítems mediante ?ids=1,2,3 o JSON/form
        ids_param = request.args.get('ids')
        if not ids_param and request.is_json:
            ids_param = request.json.get('ids')
        elif not ids_param and request.form.get('ids'):
            ids_param = request.form.get('ids')

        es_seleccion_multiple = False
        if ids_param:
            if isinstance(ids_param, str):
                id_list = [int(x.strip()) for x in ids_param.split(',') if x.strip().isdigit()]
            elif isinstance(ids_param, list):
                id_list = [int(x) for x in ids_param if str(x).isdigit()]
            else:
                id_list = []

            if id_list:
                es_seleccion_multiple = True
                query = InventarioCustodia.query.filter(InventarioCustodia.id.in_(id_list))
                if user_rol not in ('admin', 'superadmin') and user_sede_id:
                    query = query.filter(InventarioCustodia.sede_id == user_sede_id)
                custodias = query.order_by(InventarioCustodia.id.asc()).all()
            else:
                custodias = []
        else:
            custodias = InventarioService.obtener_custodias_filtradas(
                request.args, user_rol=user_rol, user_sede_id=user_sede_id
            )

        if not custodias:
            flash('No se encontraron registros de custodia para generar el acta.', 'warning')
            return redirect(url_for('inventario.inventario_main', tab='custodia'))

        organizar_por = request.args.get('organizar_por', 'categoria')
        organizar_por_categoria = (organizar_por.lower() != 'ninguno')

        sede_nombre = "PERDOMO"
        if user_sede_id:
            s_obj = db.session.get(Sede, user_sede_id)
            if s_obj:
                sede_nombre = s_obj.nombre
        elif custodias and custodias[0].sede:
            sede_nombre = custodias[0].sede.nombre

        usuario_emisor = session.get('nombre_completo', session.get('usuario', 'Auxiliar de Inventario'))
        
        consecutivo = None
        if es_seleccion_multiple:
            consecutivo = f"ACTA-SEL-{len(custodias)}B-{datetime.now().strftime('%Y%m%d%H%M')}"

        pdf_buffer = ActaCustodiaService.generar_acta_pdf(
            custodias=custodias,
            consecutivo=consecutivo,
            usuario_emisor=usuario_emisor,
            sede_nombre=sede_nombre,
            organizar_por_categoria=organizar_por_categoria
        )

        tipo_sufijo = f"seleccion_{len(custodias)}bienes" if es_seleccion_multiple else sede_nombre.lower()
        nombre_archivo = f"acta_custodia_{tipo_sufijo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=False,
            download_name=nombre_archivo
        )
    except Exception as e:
        current_app.logger.error(f"Error generando acta de custodia PDF: {e}", exc_info=True)
        flash(f"Error al generar el acta de custodia en PDF: {str(e)}", "danger")
        return redirect(url_for('inventario.inventario_main', tab='custodia'))


@inventario_bp.route('/acta-custodia/<int:custodia_id>/pdf')
@login_required
@permiso_requerido('inventario', 'ver')
def descargar_acta_individual_pdf(custodia_id):
    """Genera y descarga el Acta Oficial de Custodia en PDF para un activo específico."""
    try:
        c = InventarioCustodia.query.get_or_404(custodia_id)
        sede_nombre = c.sede.nombre if c.sede else "PERDOMO"
        usuario_emisor = session.get('nombre_completo', session.get('usuario', 'Auxiliar de Inventario'))
        consecutivo = f"ACTA-IND-{c.placa or c.id}-{datetime.now().strftime('%Y%m%d')}"

        pdf_buffer = ActaCustodiaService.generar_acta_pdf(
            custodias=[c],
            consecutivo=consecutivo,
            usuario_emisor=usuario_emisor,
            sede_nombre=sede_nombre
        )

        placa_clean = re.sub(r'[^a-zA-Z0-9_-]', '_', c.placa or f"id_{c.id}")
        nombre_archivo = f"acta_custodia_{placa_clean}_{datetime.now().strftime('%Y%m%d')}.pdf"
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=False,
            download_name=nombre_archivo
        )
    except Exception as e:
        current_app.logger.error(f"Error generando acta individual PDF: {e}", exc_info=True)
        flash(f"Error al generar el acta individual en PDF: {str(e)}", "danger")
        return redirect(url_for('inventario.inventario_main', tab='custodia'))



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



@inventario_bp.route('/propagar_foto_modelo', methods=['POST'])
@login_required
@permiso_requerido('inventario', 'editar')
def propagar_foto_modelo():
    """Replica la foto de un item a todos los demás items que comparten el mismo modelo o nombre."""
    try:
        datos = request.get_json(silent=True) or request.form.to_dict()
        item_id = datos.get('item_id')
        if not item_id:
            return jsonify({'success': False, 'message': 'ID de item no proporcionado.'}), 400

        item = Inventario.query.get(int(item_id))
        if not item:
            return jsonify({'success': False, 'message': 'Equipo no encontrado.'}), 404

        if not item.foto_url:
            return jsonify({'success': False, 'message': 'Este equipo no cuenta con una foto asignada para replicar.'}), 400

        actualizados = _propagar_foto_modelo_interno(
            item, 
            session_user=session.get('usuario', ''),
            session_user_name=session.get('nombre_completo', '')
        )

        modelo_txt = item.marca_modelo or item.item
        return jsonify({
            'success': True,
            'message': f'Foto replicada exitosamente a {actualizados} equipos del modelo "{modelo_txt}".',
            'count': actualizados
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error en propagar_foto_modelo: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@inventario_bp.route('/bulk_edit_modelo', methods=['POST'])
@login_required
@permiso_requerido('inventario', 'editar')
def bulk_edit_modelo():
    """Edita campos comunes (ubicación, estado, ficha técnica, observaciones, foto) para múltiples items del mismo modelo."""
    try:
        if request.is_json:
            datos = request.json
        else:
            datos = request.form.to_dict()

        raw_ids = datos.get('item_ids', '')
        if isinstance(raw_ids, str):
            item_ids = [int(i.strip()) for i in raw_ids.split(',') if i.strip().isdigit()]
        elif isinstance(raw_ids, list):
            item_ids = [int(i) for i in raw_ids if str(i).isdigit()]
        else:
            item_ids = []

        if not item_ids:
            return jsonify({'success': False, 'message': 'No se seleccionaron equipos para edición masiva.'}), 400

        items = Inventario.query.filter(Inventario.id.in_(item_ids)).all()
        if not items:
            return jsonify({'success': False, 'message': 'No se encontraron los equipos seleccionados.'}), 404

        foto_subida = None
        if 'foto' in request.files and request.files['foto'].filename:
            foto_subida = _procesar_y_guardar_imagen(request.files['foto'], subcarpeta='equipos')
        elif datos.get('foto_url'):
            foto_subida = str(datos.get('foto_url')).strip() or None

        actualizados = 0
        usuario_doc = session.get('usuario', '')
        usuario_nom = session.get('nombre_completo', '')

        for item in items:
            datos_antes = {
                'categoria': item.categoria,
                'item': item.item,
                'marca_modelo': item.marca_modelo,
                'ubicacion_permanente': item.ubicacion_permanente,
                'estado': item.estado,
                'bodega_id': item.bodega_id,
                'procesador': item.procesador,
                'ram_gb': item.ram_gb,
                'almacenamiento': item.almacenamiento,
                'sistema_operativo': item.sistema_operativo,
                'especificaciones_tecnicas': item.especificaciones_tecnicas,
                'foto_url': item.foto_url
            }

            if 'categoria' in datos and datos['categoria'].strip():
                item.categoria = datos['categoria'].strip()
            if 'item' in datos and datos['item'].strip():
                item.item = datos['item'].strip()
            if 'marca_modelo' in datos and datos['marca_modelo'].strip():
                item.marca_modelo = datos['marca_modelo'].strip()
            if 'ubicacion_permanente' in datos and datos['ubicacion_permanente'].strip():
                item.ubicacion_permanente = datos['ubicacion_permanente'].strip()
            if 'estado' in datos and datos['estado'].strip():
                item.estado = datos['estado'].strip()
            if 'bodega_id' in datos and str(datos['bodega_id']).strip().isdigit():
                item.bodega_id = int(datos['bodega_id'])
            if 'observaciones' in datos and datos['observaciones'].strip():
                item.observaciones = datos['observaciones'].strip()

            if 'procesador' in datos and datos['procesador'].strip():
                item.procesador = datos['procesador'].strip()
            if 'ram_gb' in datos and datos['ram_gb'].strip():
                item.ram_gb = datos['ram_gb'].strip()
            if 'almacenamiento' in datos and datos['almacenamiento'].strip():
                item.almacenamiento = datos['almacenamiento'].strip()
            if 'sistema_operativo' in datos and datos['sistema_operativo'].strip():
                item.sistema_operativo = datos['sistema_operativo'].strip()
            if 'especificaciones_tecnicas' in datos and datos['especificaciones_tecnicas'].strip():
                item.especificaciones_tecnicas = datos['especificaciones_tecnicas'].strip()

            if 'proveedor' in datos and datos['proveedor'].strip():
                item.proveedor = datos['proveedor'].strip()
            if 'fecha_adquisicion' in datos and datos['fecha_adquisicion'].strip():
                try:
                    item.fecha_adquisicion = datetime.strptime(datos['fecha_adquisicion'].strip(), '%Y-%m-%d').date()
                except ValueError:
                    pass
            if 'garantia_vencimiento' in datos and datos['garantia_vencimiento'].strip():
                try:
                    item.garantia_vencimiento = datetime.strptime(datos['garantia_vencimiento'].strip(), '%Y-%m-%d').date()
                except ValueError:
                    pass

            if foto_subida:
                item.foto_url = foto_subida

            actualizados += 1

            registrar_auditoria(
                modulo='inventario',
                entidad_tipo='Inventario',
                entidad_id=item.id,
                accion='EDITAR_MASIVO_MODELO',
                usuario_documento=usuario_doc,
                usuario_nombre=usuario_nom,
                descripcion=f'Edición masiva de modelo para equipo "{item.item}" (#{item.numero_inventario})',
                datos_antes=datos_antes,
                datos_despues={
                    'categoria': item.categoria,
                    'item': item.item,
                    'marca_modelo': item.marca_modelo,
                    'estado': item.estado,
                    'foto_url': item.foto_url
                }
            )

        db.session.commit()

        propagar_todos = datos.get('propagar_todos_modelo') in (True, 'true', '1')
        extra_propagados = 0
        if propagar_todos and foto_subida and items:
            extra_propagados = _propagar_foto_modelo_interno(items[0], usuario_doc, usuario_nom)

        msg = f'Se actualizaron con éxito {actualizados} equipos seleccionados.'
        if extra_propagados > 0:
            msg += f' Además, la foto se replicó a {extra_propagados} equipos adicionales del mismo modelo.'

        return jsonify({
            'success': True,
            'message': msg,
            'count': actualizados,
            'extra_count': extra_propagados
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error en bulk_edit_modelo: {e}")
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

            hostname = str(row.get('hostname', '')).strip()
            if hostname.lower() == 'nan' or not hostname:
                hostname = None

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
                if hostname: item_existente.hostname = hostname
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
                    hostname=hostname,
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


