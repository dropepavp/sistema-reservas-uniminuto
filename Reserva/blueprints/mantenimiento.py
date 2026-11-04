"""
Blueprint para el Módulo de Mantenimiento y Hojas de Vida de Equipos.
Permite registrar y controlar:
- Actualizaciones de equipos (hardware / SO / BIOS)
- Instalaciones y licencias de software
- Cambio de partes, repuestos y ampliaciones de memoria/disco
- Arreglos, diagnósticos y mantenimientos preventivos/correctivos
- Hojas de Vida integrales de cada equipo con espacio para foto, especificaciones y trazabilidad completa
"""
import os
import uuid
import io
from datetime import datetime, date
import pandas as pd
try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    Image = None
    HAS_PIL = False
from werkzeug.utils import secure_filename
from flask import (
    Blueprint, render_template, request, redirect, flash,
    url_for, session, jsonify, send_file, current_app
)
from sqlalchemy import or_, and_, func

from extensions import db
from database import (
    Inventario, MantenimientoInventario, Sede, Bodega,
    CategoriaInventario, PrestamoEquipo, registrar_auditoria
)
from auth import login_required, permiso_requerido, sede_requerida
from config import SystemConstants

mantenimiento_bp = Blueprint('mantenimiento', __name__, url_prefix='/mantenimiento')

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def _procesar_y_guardar_imagen(file_storage, subcarpeta='equipos', max_dim=(1200, 1200)):
    """
    Guarda y optimiza una imagen subida por el usuario.
    Retorna la ruta relativa para ser servida desde static (ej: '/static/uploads/equipos/nombre.jpg').
    """
    if not file_storage or not file_storage.filename or not _allowed_file(file_storage.filename):
        return None

    try:
        base_dir = current_app.static_folder
        carpeta_destino = os.path.join(base_dir, 'uploads', subcarpeta)
        os.makedirs(carpeta_destino, exist_ok=True)

        nombre_unico = f"{subcarpeta}_{uuid.uuid4().hex[:10]}_{int(datetime.now().timestamp())}.jpg"
        ruta_archivo = os.path.join(carpeta_destino, nombre_unico)

        if HAS_PIL and Image is not None:
            try:
                # Procesar con Pillow para estandarizar y comprimir
                img = Image.open(file_storage.stream)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.thumbnail(max_dim, Image.Resampling.LANCZOS)
                img.save(ruta_archivo, format='JPEG', quality=85, optimize=True)
            except Exception as e_pil:
                current_app.logger.warning(f"Fallo al procesar con PIL, guardando directo: {e_pil}")
                file_storage.stream.seek(0)
                file_storage.save(ruta_archivo)
        else:
            file_storage.stream.seek(0)
            file_storage.save(ruta_archivo)

        return f"/static/uploads/{subcarpeta}/{nombre_unico}"
    except Exception as e:
        current_app.logger.error(f"Error guardando imagen en {subcarpeta}: {e}")
        return None


# =========================================================================
# 1. DASHBOARD PRINCIPAL DE MANTENIMIENTO
# =========================================================================

@mantenimiento_bp.route('/')
@login_required
@permiso_requerido('mantenimiento', 'ver')
def dashboard_mantenimiento():
    """Panel principal de Mantenimiento y Hojas de Vida."""
    try:
        tab_activa = request.args.get('tab', 'intervenciones')  # 'intervenciones' o 'hojas_vida'
        busqueda = request.args.get('busqueda', '').strip()
        tipo_filtro = request.args.get('tipo', '').strip()
        estado_filtro = request.args.get('estado', '').strip()
        fecha_desde = request.args.get('fecha_desde', '').strip()
        fecha_hasta = request.args.get('fecha_hasta', '').strip()
        sede_filtro = request.args.get('sede', '').strip()
        categoria_filtro = request.args.get('categoria', '').strip()

        # Control de sede para auxiliares
        user_rol = session.get('rol')
        user_sede_id = session.get('sede_id')
        if user_rol not in ('admin', 'superadmin'):
            sede_filtro = str(user_sede_id) if user_sede_id else ''

        # -----------------------------------------------------------------
        # Consulta de Mantenimientos / Intervenciones
        # -----------------------------------------------------------------
        query_m = MantenimientoInventario.query.join(Inventario)

        if sede_filtro and sede_filtro.isdigit():
            query_m = query_m.outerjoin(Bodega, Inventario.bodega_id == Bodega.id).filter(
                or_(
                    MantenimientoInventario.sede_id == int(sede_filtro),
                    Bodega.sede_id == int(sede_filtro)
                )
            )

        if tipo_filtro:
            query_m = query_m.filter(MantenimientoInventario.tipo == tipo_filtro)

        if estado_filtro:
            query_m = query_m.filter(MantenimientoInventario.estado == estado_filtro)

        if fecha_desde:
            try:
                f_d = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                query_m = query_m.filter(MantenimientoInventario.fecha_envio >= f_d)
            except ValueError:
                pass

        if fecha_hasta:
            try:
                f_h = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                query_m = query_m.filter(MantenimientoInventario.fecha_envio <= f_h)
            except ValueError:
                pass

        if busqueda:
            termino = f"%{busqueda}%"
            query_m = query_m.filter(
                or_(
                    Inventario.numero_inventario.ilike(termino),
                    Inventario.item.ilike(termino),
                    Inventario.serial.ilike(termino),
                    Inventario.activo_fijo.ilike(termino),
                    MantenimientoInventario.titulo.ilike(termino),
                    MantenimientoInventario.motivo.ilike(termino),
                    MantenimientoInventario.software_instalado.ilike(termino),
                    MantenimientoInventario.partes_cambiadas.ilike(termino),
                    MantenimientoInventario.auxiliar_responsable.ilike(termino),
                    MantenimientoInventario.proveedor_tecnico.ilike(termino)
                )
            )

        mantenimientos = query_m.order_by(MantenimientoInventario.fecha_envio.desc(), MantenimientoInventario.id.desc()).limit(200).all()

        # -----------------------------------------------------------------
        # Consulta de Equipos para Catálogo de Hojas de Vida
        # -----------------------------------------------------------------
        query_eq = Inventario.query

        if sede_filtro and sede_filtro.isdigit():
            query_eq = query_eq.join(Bodega).filter(Bodega.sede_id == int(sede_filtro))

        if categoria_filtro:
            query_eq = query_eq.filter(Inventario.categoria == categoria_filtro)

        if busqueda and tab_activa == 'hojas_vida':
            t_eq = f"%{busqueda}%"
            query_eq = query_eq.filter(
                or_(
                    Inventario.numero_inventario.ilike(t_eq),
                    Inventario.item.ilike(t_eq),
                    Inventario.marca_modelo.ilike(t_eq),
                    Inventario.serial.ilike(t_eq),
                    Inventario.activo_fijo.ilike(t_eq),
                    Inventario.ubicacion_permanente.ilike(t_eq),
                    Inventario.procesador.ilike(t_eq),
                    Inventario.sistema_operativo.ilike(t_eq)
                )
            )

        equipos_hojas_vida = query_eq.order_by(Inventario.item.asc(), Inventario.numero_inventario.asc()).limit(120).all()

        # -----------------------------------------------------------------
        # KPIs y Estadísticas Globales
        # -----------------------------------------------------------------
        hoy = date.today()
        inicio_mes = hoy.replace(day=1)

        total_mantenimientos = MantenimientoInventario.query.count()
        mantenimientos_mes = MantenimientoInventario.query.filter(MantenimientoInventario.fecha_envio >= inicio_mes).count()
        equipos_en_mantenimiento = Inventario.query.filter(Inventario.estado.in_(['En Mantenimiento', 'En Reparación'])).count()
        
        # Conteo de software instalado y partes cambiadas
        total_software = MantenimientoInventario.query.filter(
            or_(
                MantenimientoInventario.tipo == 'Instalación de Software',
                MantenimientoInventario.software_instalado.isnot(None)
            )
        ).count()
        total_partes = MantenimientoInventario.query.filter(
            or_(
                MantenimientoInventario.tipo == 'Cambio de Partes / Repuestos',
                MantenimientoInventario.partes_cambiadas.isnot(None)
            )
        ).count()

        sedes = Sede.query.order_by(Sede.nombre).all()
        categorias = CategoriaInventario.query.order_by(CategoriaInventario.nombre).all()

        tipos_disponibles = [
            'Actualización de Equipo',
            'Instalación de Software',
            'Cambio de Partes / Repuestos',
            'Arreglo / Reparación',
            'Mantenimiento Preventivo',
            'Mantenimiento Correctivo',
            'Garantía / Diagnóstico'
        ]

        return render_template(
            'mantenimiento.html',
            tab_activa=tab_activa,
            mantenimientos=mantenimientos,
            equipos_hojas_vida=equipos_hojas_vida,
            total_mantenimientos=total_mantenimientos,
            mantenimientos_mes=mantenimientos_mes,
            equipos_en_mantenimiento=equipos_en_mantenimiento,
            total_software=total_software,
            total_partes=total_partes,
            sedes=sedes,
            categorias=categorias,
            tipos_disponibles=tipos_disponibles,
            filtros={
                'busqueda': busqueda,
                'tipo': tipo_filtro,
                'estado': estado_filtro,
                'fecha_desde': fecha_desde,
                'fecha_hasta': fecha_hasta,
                'sede': sede_filtro,
                'categoria': categoria_filtro
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error cargando dashboard de mantenimiento: {e}", exc_info=True)
        flash('Ocurrió un error al cargar el módulo de mantenimiento.', 'danger')
        return render_template(
            'mantenimiento.html',
            tab_activa='intervenciones',
            mantenimientos=[],
            equipos_hojas_vida=[],
            total_mantenimientos=0,
            mantenimientos_mes=0,
            equipos_en_mantenimiento=0,
            total_software=0,
            total_partes=0,
            sedes=[],
            categorias=[],
            tipos_disponibles=[
                'Actualización de Equipo',
                'Instalación de Software',
                'Cambio de Partes / Repuestos',
                'Arreglo / Reparación',
                'Mantenimiento Preventivo',
                'Mantenimiento Correctivo',
                'Garantía / Diagnóstico'
            ],
            filtros={}
        )


# =========================================================================
# 2. HOJA DE VIDA INDIVIDUAL DEL EQUIPO
# =========================================================================

@mantenimiento_bp.route('/hoja-de-vida/<int:inventario_id>')
@login_required
@permiso_requerido('mantenimiento', 'ver')
def hoja_vida(inventario_id):
    """Muestra la Hoja de Vida oficial, completa e imprimible de un equipo."""
    try:
        equipo = Inventario.query.get_or_404(inventario_id)

        # Historial de mantenimientos cronológico
        mantenimientos = MantenimientoInventario.query.filter_by(
            inventario_id=equipo.id
        ).order_by(MantenimientoInventario.fecha_envio.desc(), MantenimientoInventario.id.desc()).all()

        # Historial de préstamos recientes del equipo
        prestamos = []
        if equipo.numero_inventario:
            prestamos = PrestamoEquipo.query.filter_by(
                numero_inventario_equipo=equipo.numero_inventario
            ).order_by(PrestamoEquipo.id_prestamo.desc()).limit(20).all()

        # Resumen estadístico del equipo
        total_intervenciones = len(mantenimientos)
        costo_total_mantenimiento = sum(m.costo or 0.0 for m in mantenimientos)
        ultimo_mantenimiento = mantenimientos[0] if mantenimientos else None

        tipos_disponibles = [
            'Actualización de Equipo',
            'Instalación de Software',
            'Cambio de Partes / Repuestos',
            'Arreglo / Reparación',
            'Mantenimiento Preventivo',
            'Mantenimiento Correctivo',
            'Garantía / Diagnóstico'
        ]

        sedes = Sede.query.order_by(Sede.nombre).all()

        return render_template(
            'hoja_vida_equipo.html',
            equipo=equipo,
            mantenimientos=mantenimientos,
            prestamos=prestamos,
            total_intervenciones=total_intervenciones,
            costo_total_mantenimiento=costo_total_mantenimiento,
            ultimo_mantenimiento=ultimo_mantenimiento,
            tipos_disponibles=tipos_disponibles,
            sedes=sedes,
            hoy_str=date.today().strftime('%d/%m/%Y')
        )
    except Exception as e:
        current_app.logger.error(f"Error cargando hoja de vida {inventario_id}: {e}", exc_info=True)
        flash('No se pudo cargar la hoja de vida del equipo seleccionado.', 'danger')
        return redirect(url_for('mantenimiento.dashboard_mantenimiento', tab='hojas_vida'))


# =========================================================================
# 3. REGISTRAR NUEVO MANTENIMIENTO / INTERVENCIÓN
# =========================================================================

@mantenimiento_bp.route('/nuevo', methods=['POST'])
@login_required
@permiso_requerido('mantenimiento', 'crear')
def registrar_mantenimiento():
    """Registra una nueva intervención técnica sobre un equipo."""
    is_json = request.is_json or request.headers.get('Accept') == 'application/json'
    try:
        datos = request.form if request.form else (request.get_json(silent=True) or {})

        inventario_id = datos.get('inventario_id')
        numero_inventario = datos.get('numero_inventario', '').strip()

        equipo = None
        if inventario_id and str(inventario_id).isdigit():
            equipo = Inventario.query.get(int(inventario_id))
        elif numero_inventario:
            equipo = Inventario.query.filter(
                or_(
                    Inventario.numero_inventario == numero_inventario,
                    Inventario.activo_fijo == numero_inventario,
                    Inventario.serial == numero_inventario
                )
            ).first()

        if not equipo:
            msg = 'Debe seleccionar un equipo válido de inventario.'
            if is_json:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'warning')
            return redirect(url_for('mantenimiento.dashboard_mantenimiento'))

        tipo = datos.get('tipo', 'Mantenimiento Preventivo').strip()
        titulo = datos.get('titulo', '').strip() or f"{tipo} - {equipo.item}"
        motivo = datos.get('motivo', '').strip() or datos.get('descripcion', '').strip()

        if not motivo:
            motivo = f"Intervención de {tipo} registrada para el equipo {equipo.numero_inventario or equipo.item}."

        tecnico_responsable = (
            datos.get('tecnico_responsable') or 
            session.get('nombre_completo') or 
            session.get('usuario') or 
            'Técnico UNIMINUTO'
        ).strip()

        fecha_str = datos.get('fecha_envio') or datos.get('fecha_mantenimiento')
        try:
            fecha_envio = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else date.today()
        except ValueError:
            fecha_envio = date.today()

        proximo_str = datos.get('proximo_mantenimiento')
        proximo_mantenimiento = None
        if proximo_str:
            try:
                proximo_mantenimiento = datetime.strptime(proximo_str, '%Y-%m-%d').date()
            except ValueError:
                proximo_mantenimiento = None

        costo = 0.0
        try:
            costo_val = datos.get('costo')
            if costo_val:
                costo = float(costo_val)
        except (ValueError, TypeError):
            costo = 0.0

        software_instalado = datos.get('software_instalado', '').strip() or None
        partes_cambiadas = datos.get('partes_cambiadas', '').strip() or None
        diagnostico_solucion = datos.get('diagnostico_solucion', '').strip() or None
        trabajo_realizado = datos.get('trabajo_realizado', '').strip() or None
        estado_intervencion = datos.get('estado', 'Finalizado').strip()
        nuevo_estado_equipo = datos.get('nuevo_estado_equipo', '').strip()

        # Guardar fotos si fueron adjuntadas en multipart/form-data
        foto_evidencia_url = None
        if 'foto_evidencia' in request.files:
            foto_evidencia_url = _procesar_y_guardar_imagen(request.files['foto_evidencia'], subcarpeta='mantenimientos')

        # Si se subió foto del equipo directamente en este formulario
        if 'foto_equipo' in request.files and request.files['foto_equipo'].filename:
            url_foto_eq = _procesar_y_guardar_imagen(request.files['foto_equipo'], subcarpeta='equipos')
            if url_foto_eq:
                equipo.foto_url = url_foto_eq

        # Determinar sede_id
        sede_id = None
        if datos.get('sede_id') and str(datos.get('sede_id')).isdigit():
            sede_id = int(datos.get('sede_id'))
        elif equipo.bodega and equipo.bodega.sede_id:
            sede_id = equipo.bodega.sede_id
        elif session.get('sede_id'):
            sede_id = int(session.get('sede_id'))

        nuevo_registro = MantenimientoInventario(
            inventario_id=equipo.id,
            tipo=tipo,
            titulo=titulo,
            motivo=motivo,
            proveedor_tecnico=tecnico_responsable,
            costo=costo,
            software_instalado=software_instalado,
            partes_cambiadas=partes_cambiadas,
            diagnostico_solucion=diagnostico_solucion,
            trabajo_realizado=trabajo_realizado,
            proximo_mantenimiento=proximo_mantenimiento,
            foto_evidencia_url=foto_evidencia_url,
            fecha_envio=fecha_envio,
            fecha_retorno_real=fecha_envio if estado_intervencion == 'Finalizado' else None,
            estado=estado_intervencion,
            auxiliar_responsable=tecnico_responsable,
            sede_id=sede_id
        )
        db.session.add(nuevo_registro)

        # Actualizar estado del equipo si se indicó
        estado_anterior = equipo.estado
        if nuevo_estado_equipo in ('Disponible', 'En Mantenimiento', 'En Reparación', 'De Baja'):
            equipo.estado = nuevo_estado_equipo
        elif estado_intervencion == 'Finalizado' and equipo.estado in ('En Mantenimiento', 'En Reparación'):
            equipo.estado = 'Disponible'
        elif estado_intervencion == 'En Proceso':
            equipo.estado = 'En Mantenimiento'

        db.session.commit()

        registrar_auditoria(
            modulo='mantenimiento',
            entidad_tipo='MantenimientoInventario',
            entidad_id=str(nuevo_registro.id),
            accion='REGISTRAR_INTERVENCION',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'{tipo} en equipo {equipo.numero_inventario or equipo.item} por {tecnico_responsable}. Titulo: {titulo}',
            datos_antes={'estado_equipo': estado_anterior},
            datos_despues={'estado_equipo': equipo.estado, 'mantenimiento_id': nuevo_registro.id}
        )

        msg = f'Mantenimiento "{titulo}" registrado exitosamente para el equipo {equipo.numero_inventario}.'
        if is_json:
            return jsonify({
                'success': True,
                'message': msg,
                'id': nuevo_registro.id,
                'inventario_id': equipo.id
            })

        flash(msg, 'success')
        # Redirigir a la hoja de vida si se solicitó o vino desde allí
        if request.referrer and 'hoja-de-vida' in request.referrer:
            return redirect(url_for('mantenimiento.hoja_vida', inventario_id=equipo.id))
        return redirect(url_for('mantenimiento.dashboard_mantenimiento'))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al registrar mantenimiento: {e}", exc_info=True)
        msg = f"Error al guardar el mantenimiento: {str(e)}"
        if is_json:
            return jsonify({'success': False, 'message': msg}), 500
        flash(msg, 'danger')
        return redirect(url_for('mantenimiento.dashboard_mantenimiento'))


# =========================================================================
# 4. GESTIÓN DE FOTO DEL EQUIPO (SUBIDA / CAMBIO)
# =========================================================================

@mantenimiento_bp.route('/equipo/<int:inventario_id>/foto', methods=['POST'])
@login_required
@permiso_requerido('mantenimiento', 'editar')
def subir_foto_equipo(inventario_id):
    """Carga o actualiza la foto oficial de un equipo para su Hoja de Vida."""
    is_json = request.is_json or request.headers.get('Accept') == 'application/json'
    try:
        equipo = Inventario.query.get_or_404(inventario_id)

        if 'foto' not in request.files or not request.files['foto'].filename:
            msg = 'No se seleccionó ningún archivo de imagen válido.'
            if is_json:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'warning')
            return redirect(url_for('mantenimiento.hoja_vida', inventario_id=equipo.id))

        archivo = request.files['foto']
        foto_url = _procesar_y_guardar_imagen(archivo, subcarpeta='equipos')

        if not foto_url:
            msg = 'El formato de imagen no es soportado. Use JPG, PNG o WEBP.'
            if is_json:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'danger')
            return redirect(url_for('mantenimiento.hoja_vida', inventario_id=equipo.id))

        foto_anterior = equipo.foto_url
        equipo.foto_url = foto_url
        db.session.commit()

        registrar_auditoria(
            modulo='mantenimiento',
            entidad_tipo='Inventario',
            entidad_id=str(equipo.id),
            accion='ACTUALIZAR_FOTO',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Foto de hoja de vida actualizada para {equipo.numero_inventario}',
            datos_antes={'foto_url': foto_anterior},
            datos_despues={'foto_url': foto_url}
        )

        msg = 'Foto del equipo actualizada exitosamente.'
        if is_json:
            return jsonify({'success': True, 'message': msg, 'foto_url': foto_url})

        flash(msg, 'success')
        return redirect(url_for('mantenimiento.hoja_vida', inventario_id=equipo.id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error subiendo foto de equipo: {e}", exc_info=True)
        msg = f"Error al procesar la foto: {str(e)}"
        if is_json:
            return jsonify({'success': False, 'message': msg}), 500
        flash(msg, 'danger')
        return redirect(url_for('mantenimiento.hoja_vida', inventario_id=inventario_id))


# =========================================================================
# 5. ACTUALIZAR ESPECIFICACIONES TÉCNICAS DESDE HOJA DE VIDA
# =========================================================================

@mantenimiento_bp.route('/equipo/<int:inventario_id>/especificaciones', methods=['POST'])
@login_required
@permiso_requerido('mantenimiento', 'editar')
def actualizar_especificaciones_equipo(inventario_id):
    """Actualiza la ficha técnica y especificaciones de hardware del equipo."""
    is_json = request.is_json or request.headers.get('Accept') == 'application/json'
    try:
        equipo = Inventario.query.get_or_404(inventario_id)
        datos = request.get_json(silent=True) or request.form

        # Campos de hardware
        if 'hostname' in datos:
            equipo.hostname = (datos.get('hostname') or '').strip() or None
        equipo.procesador = (datos.get('procesador') or '').strip() or None
        equipo.ram_gb = (datos.get('ram_gb') or '').strip() or None
        equipo.almacenamiento = (datos.get('almacenamiento') or '').strip() or None
        equipo.sistema_operativo = (datos.get('sistema_operativo') or '').strip() or None
        equipo.especificaciones_tecnicas = (datos.get('especificaciones_tecnicas') or '').strip() or None
        equipo.proveedor = (datos.get('proveedor') or '').strip() or None

        # Fechas
        f_adq = datos.get('fecha_adquisicion')
        if f_adq:
            try:
                equipo.fecha_adquisicion = datetime.strptime(f_adq, '%Y-%m-%d').date()
            except ValueError:
                pass

        f_gar = datos.get('garantia_vencimiento')
        if f_gar:
            try:
                equipo.garantia_vencimiento = datetime.strptime(f_gar, '%Y-%m-%d').date()
            except ValueError:
                pass

        # Observaciones generales
        if 'observaciones' in datos:
            equipo.observaciones = (datos.get('observaciones') or '').strip() or None

        db.session.commit()

        registrar_auditoria(
            modulo='mantenimiento',
            entidad_tipo='Inventario',
            entidad_id=str(equipo.id),
            accion='ACTUALIZAR_ESPECIFICACIONES',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Ficha técnica actualizada para {equipo.numero_inventario}'
        )

        msg = 'Especificaciones técnicas actualizadas exitosamente.'
        if is_json:
            return jsonify({'success': True, 'message': msg})

        flash(msg, 'success')
        return redirect(url_for('mantenimiento.hoja_vida', inventario_id=equipo.id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error actualizando especificaciones: {e}", exc_info=True)
        msg = f"Error al guardar especificaciones: {str(e)}"
        if is_json:
            return jsonify({'success': False, 'message': msg}), 500
        flash(msg, 'danger')
        return redirect(url_for('mantenimiento.hoja_vida', inventario_id=inventario_id))


# =========================================================================
# 6. APIS DE APOYO (AUTOCOMPLETADO Y DETALLES)
# =========================================================================

@mantenimiento_bp.route('/api/buscar-equipo', methods=['GET'])
@login_required
def api_buscar_equipo():
    """Buscador en vivo de equipos para el selector de mantenimiento."""
    try:
        q = request.args.get('q', '').strip()
        if not q or len(q) < 1:
            return jsonify({'success': True, 'equipos': []})

        termino = f"%{q}%"
        query = Inventario.query.filter(
            or_(
                Inventario.numero_inventario.ilike(termino),
                Inventario.item.ilike(termino),
                Inventario.marca_modelo.ilike(termino),
                Inventario.serial.ilike(termino),
                Inventario.activo_fijo.ilike(termino)
            )
        )

        # Filtrar por sede si es auxiliar
        if session.get('rol') not in ('admin', 'superadmin') and session.get('sede_id'):
            query = query.join(Bodega).filter(Bodega.sede_id == int(session.get('sede_id')))

        items = query.limit(20).all()
        resultados = []
        for it in items:
            sede_nombre = it.bodega.sede.nombre if it.bodega and it.bodega.sede else 'Sin Sede'
            resultados.append({
                'id': it.id,
                'numero_inventario': it.numero_inventario or '--',
                'item': it.item,
                'marca_modelo': it.marca_modelo or '',
                'serial': it.serial or '',
                'activo_fijo': it.activo_fijo or '',
                'estado': it.estado,
                'sede': sede_nombre,
                'foto_url': it.foto_url or ''
            })

        return jsonify({'success': True, 'equipos': resultados})
    except Exception as e:
        current_app.logger.error(f"Error buscando equipo: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@mantenimiento_bp.route('/api/intervencion/<int:id>', methods=['GET'])
@login_required
def api_detalle_intervencion(id):
    """Retorna los datos completos en JSON de un registro de mantenimiento."""
    try:
        m = MantenimientoInventario.query.get_or_404(id)
        eq = m.equipo
        return jsonify({
            'success': True,
            'intervencion': {
                'id': m.id,
                'titulo': m.titulo or f"{m.tipo} - {eq.item if eq else ''}",
                'tipo': m.tipo,
                'motivo': m.motivo,
                'software_instalado': m.software_instalado or '',
                'partes_cambiadas': m.partes_cambiadas or '',
                'diagnostico_solucion': m.diagnostico_solucion or '',
                'trabajo_realizado': m.trabajo_realizado or '',
                'costo': m.costo or 0.0,
                'fecha_envio': m.fecha_envio.strftime('%d/%m/%Y') if m.fecha_envio else '--',
                'fecha_retorno': m.fecha_retorno_real.strftime('%d/%m/%Y') if m.fecha_retorno_real else '--',
                'proximo_mantenimiento': m.proximo_mantenimiento.strftime('%d/%m/%Y') if m.proximo_mantenimiento else '--',
                'estado': m.estado,
                'tecnico': m.auxiliar_responsable or m.proveedor_tecnico,
                'foto_evidencia_url': m.foto_evidencia_url or '',
                'equipo': {
                    'id': eq.id if eq else None,
                    'item': eq.item if eq else 'Equipo Eliminado',
                    'numero_inventario': eq.numero_inventario if eq else '--',
                    'serial': eq.serial if eq else '--',
                    'activo_fijo': eq.activo_fijo if eq else '--',
                    'foto_url': eq.foto_url if eq else ''
                }
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# =========================================================================
# 7. ELIMINAR INTERVENCIÓN
# =========================================================================

@mantenimiento_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
@permiso_requerido('mantenimiento', 'eliminar')
def eliminar_intervencion(id):
    """Elimina un registro de mantenimiento."""
    try:
        m = MantenimientoInventario.query.get_or_404(id)
        inv_id = m.inventario_id
        titulo = m.titulo or m.tipo

        db.session.delete(m)
        db.session.commit()

        registrar_auditoria(
            modulo='mantenimiento',
            entidad_tipo='MantenimientoInventario',
            entidad_id=str(id),
            accion='ELIMINAR_INTERVENCION',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Intervención técnica #{id} "{titulo}" eliminada'
        )

        flash(f'Registro de mantenimiento eliminado exitosamente.', 'success')
        if request.referrer and 'hoja-de-vida' in request.referrer:
            return redirect(url_for('mantenimiento.hoja_vida', inventario_id=inv_id))
        return redirect(url_for('mantenimiento.dashboard_mantenimiento'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error eliminando mantenimiento: {e}")
        flash(f'Error al eliminar el registro: {str(e)}', 'danger')
        return redirect(url_for('mantenimiento.dashboard_mantenimiento'))


# =========================================================================
# 8. EXPORTAR A EXCEL
# =========================================================================

@mantenimiento_bp.route('/exportar-excel')
@login_required
def exportar_excel():
    """Exporta el historial de mantenimientos en formato XLSX."""
    try:
        sede_id = request.args.get('sede')
        tipo = request.args.get('tipo')

        query = MantenimientoInventario.query.join(Inventario)
        if sede_id and sede_id.isdigit():
            query = query.outerjoin(Bodega, Inventario.bodega_id == Bodega.id).filter(
                or_(
                    MantenimientoInventario.sede_id == int(sede_id),
                    Bodega.sede_id == int(sede_id)
                )
            )
        if tipo:
            query = query.filter(MantenimientoInventario.tipo == tipo)

        registros = query.order_by(MantenimientoInventario.fecha_envio.desc()).all()

        filas = []
        for r in registros:
            eq = r.equipo
            filas.append({
                'ID': r.id,
                'Fecha': r.fecha_envio.strftime('%d/%m/%Y') if r.fecha_envio else '',
                'Tipo Intervención': r.tipo,
                'Título': r.titulo or '',
                'Equipo / Ítem': eq.item if eq else '',
                'N° Inventario': eq.numero_inventario if eq else '',
                'Activo Fijo': eq.activo_fijo if eq else '',
                'Serial': eq.serial if eq else '',
                'Técnico / Responsable': r.auxiliar_responsable or '',
                'Software Instalado': r.software_instalado or '',
                'Partes Cambiadas': r.partes_cambiadas or '',
                'Diagnóstico / Motivo': r.motivo or '',
                'Trabajo Realizado': r.trabajo_realizado or '',
                'Costo ($)': r.costo or 0.0,
                'Estado Mantenimiento': r.estado,
                'Próximo Mant.': r.proximo_mantenimiento.strftime('%d/%m/%Y') if r.proximo_mantenimiento else ''
            })

        df = pd.DataFrame(filas)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Mantenimientos')

        output.seek(0)
        nombre_descarga = f"Reporte_Mantenimiento_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return send_file(
            output,
            as_attachment=True,
            download_name=nombre_descarga,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        current_app.logger.error(f"Error exportando Excel de mantenimiento: {e}")
        flash('Error al generar el reporte de Excel.', 'danger')
        return redirect(url_for('mantenimiento.dashboard_mantenimiento'))
