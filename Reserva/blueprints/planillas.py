"""
Blueprint para el Módulo de Planillas Excel.
Permite descargar plantillas oficiales de Excel (.xlsx) y procesar cargas masivas de datos
para los diferentes módulos del sistema (Inventario, Profesores, Colaboradores, Estudiantes,
Salas de Cómputo y Usuarios del Sistema).
"""
import io
import os
import re
from datetime import datetime, date, time
from typing import Optional

import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from werkzeug.security import generate_password_hash
from flask import (
    Blueprint, render_template, request, jsonify, flash,
    redirect, url_for, session, send_file, current_app
)

from sqlalchemy import or_, and_
from database import (
    db, Inventario, CategoriaInventario, Sede, Bodega,
    Profesor, Colaborador, HorarioColaborador, Estudiante,
    ProgramaAcademico, ClaseSalaComputo, Auxiliar, Reserva,
    Recurso, Ubicacion, registrar_auditoria
)
from decorators import login_required, permiso_requerido
from validators import DataValidator

planillas_bp = Blueprint('planillas', __name__, url_prefix='/planillas')


# =========================================================================
# UTILIDADES DE GENERACIÓN Y ESTILO DE EXCEL
# =========================================================================

def _aplicar_estilo_plantilla(writer, sheet_name: str, titulo: str, instrucciones: list[list[str]]):
    """Aplica colores institucionales UNIMINUTO, formato y hoja de instrucciones."""
    wb = writer.book
    ws = writer.sheets[sheet_name]

    # Paleta UNIMINUTO
    header_fill = PatternFill(start_color="003366", end_color="003366", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=10, color="000000")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # Estilizar encabezados de la hoja principal
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    ws.row_dimensions[1].height = 28

    # Autoajustar ancho de columnas y bordes en filas de datos
    for col in ws.columns:
        col_letter = col[0].column_letter
        max_len = 0
        for cell in col:
            val_str = str(cell.value or '')
            if len(val_str) > max_len:
                max_len = len(val_str)
            if cell.row > 1:
                cell.font = data_font
                cell.border = thin_border
                cell.alignment = Alignment(vertical="center")
        ws.column_dimensions[col_letter].width = max(max_len + 5, 14)

    # Crear hoja de instrucciones si se proporcionan
    if instrucciones:
        ws_inst = wb.create_sheet(title="Instrucciones")
        ws_inst.views.sheetView[0].showGridLines = True
        
        # Título principal
        ws_inst['A1'] = titulo
        ws_inst['A1'].font = Font(name="Calibri", size=14, bold=True, color="003366")
        ws_inst.row_dimensions[1].height = 30

        for r_idx, row in enumerate(instrucciones, start=3):
            for c_idx, val in enumerate(row, start=1):
                cell = ws_inst.cell(row=r_idx, column=c_idx, value=val)
                if r_idx == 3:
                    cell.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
                    cell.font = Font(name="Calibri", size=11, bold=True, color="0F172A")
                else:
                    cell.font = Font(name="Calibri", size=10, color="334155")
                cell.border = thin_border

        for col in ws_inst.columns:
            col_letter = col[0].column_letter
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws_inst.column_dimensions[col_letter].width = max(max_len + 4, 18)


def _normalizar_texto(v) -> str:
    s = str(v or '').strip()
    return '' if s.lower() in ('nan', 'none', 'null') else s


def _normalizar_numero_str(v) -> str:
    """Evita conversiones raras de Excel como 1010.0 a texto."""
    s = _normalizar_texto(v)
    if not s:
        return ''
    if re.fullmatch(r'\d+\.0+', s):
        try:
            return str(int(float(s)))
        except Exception:
            return s
    return s


def _leer_archivo_excel_o_csv(archivo, expected_sheet: str) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """Lee y normaliza columnas de un archivo Excel o CSV."""
    if not archivo or not archivo.filename:
        return None, 'No se seleccionó ningún archivo.'

    ext = archivo.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('xlsx', 'xls', 'csv'):
        return None, 'Formato no válido. Debe ser un archivo .xlsx, .xls o .csv.'

    try:
        contenido = archivo.read()
        buf = io.BytesIO(contenido)
        if ext == 'csv':
            # Probar con punto y coma y luego coma
            try:
                df = pd.read_csv(buf, sep=';', dtype=str, encoding='utf-8-sig')
                if len(df.columns) <= 1:
                    buf.seek(0)
                    df = pd.read_csv(buf, sep=',', dtype=str, encoding='utf-8-sig')
            except Exception:
                buf.seek(0)
                df = pd.read_csv(buf, sep=',', dtype=str, encoding='latin-1')
        else:
            xl = pd.ExcelFile(buf)
            # Buscar la hoja esperada o usar la primera
            sheet_to_use = expected_sheet if expected_sheet in xl.sheet_names else xl.sheet_names[0]
            df = pd.read_excel(xl, sheet_name=sheet_to_use, dtype=str)

        df.columns = [str(c).strip().lower().replace(' ', '_').replace('.', '') for c in df.columns]
        return df, None
    except Exception as e:
        return None, f'Error al leer el archivo: {str(e)}'


# =========================================================================
# VISTA PRINCIPAL DEL MÓDULO DE PLANILLAS
# =========================================================================

@planillas_bp.route('/')
@login_required
def planillas_dashboard():
    """Centro de control para la descarga de plantillas y carga masiva de Excel."""
    tab_activa = request.args.get('tab', 'inventario')
    
    # Obtener sedes y bodegas para contexto
    sedes = Sede.query.order_by(Sede.nombre).all()
    user_sede_id = session.get('sede_id')
    user_sede_nombre = session.get('sede_nombre') or 'Sede General'
    
    # Estadísticas rápidas de registros por módulo
    stats = {
        'inventario': Inventario.query.count(),
        'profesores': Profesor.query.count(),
        'colaboradores': Colaborador.query.count(),
        'estudiantes': Estudiante.query.count(),
        'salas_computo': ClaseSalaComputo.query.count(),
        'usuarios': Auxiliar.query.count(),
        'reservas': Reserva.query.count(),
    }

    return render_template(
        'planillas.html',
        tab_activa=tab_activa,
        sedes=sedes,
        user_sede_id=user_sede_id,
        user_sede_nombre=user_sede_nombre,
        stats=stats
    )


# =========================================================================
# 1. PLANILLA DE INVENTARIO Y FICHA TÉCNICA (HOJA DE VIDA)
# =========================================================================

@planillas_bp.route('/plantilla/inventario')
@login_required
def descargar_plantilla_inventario():
    """Genera la plantilla Excel oficial para inventario con ficha técnica de Hoja de Vida."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        columnas = [
            'item', 'categoria', 'marca_modelo', 'serial', 'activo_fijo',
            'numero_inventario', 'hostname', 'ubicacion_permanente', 'estado', 'es_por_cantidad',
            'cantidad_total', 'procesador', 'ram_gb', 'almacenamiento',
            'sistema_operativo', 'especificaciones_tecnicas', 'proveedor',
            'fecha_adquisicion', 'garantia_vencimiento', 'observaciones'
        ]
        ejemplos = [
            {
                'item': 'Portátil HP ProBook 450 G9',
                'categoria': 'Cómputo',
                'marca_modelo': 'HP ProBook 450 G9',
                'serial': '5CD3456789',
                'activo_fijo': 'AF-100234',
                'numero_inventario': 'PORT-001',
                'hostname': 'PER-DOC-PORT01',
                'ubicacion_permanente': 'Bodega de Sistemas',
                'estado': 'Disponible',
                'es_por_cantidad': 'NO',
                'cantidad_total': '1',
                'procesador': 'Intel Core i5-1235U',
                'ram_gb': '16 GB DDR4',
                'almacenamiento': '512 GB SSD NVMe',
                'sistema_operativo': 'Windows 11 Pro',
                'especificaciones_tecnicas': 'Pantalla 15.6 FHD, WiFi 6, Teclado numérico',
                'proveedor': 'Distribuidora HP Colombia',
                'fecha_adquisicion': '2024-03-15',
                'garantia_vencimiento': '2027-03-15',
                'observaciones': 'Equipo para préstamo a docentes'
            },
            {
                'item': 'Cable HDMI 2.0 (1.8m)',
                'categoria': 'Audiovisuales',
                'marca_modelo': 'UGREEN High Speed',
                'serial': 'N/A',
                'activo_fijo': '',
                'numero_inventario': 'HDMI-LOTE-01',
                'ubicacion_permanente': 'Estante A-2',
                'estado': 'Disponible',
                'es_por_cantidad': 'SI',
                'cantidad_total': '25',
                'procesador': '',
                'ram_gb': '',
                'almacenamiento': '',
                'sistema_operativo': '',
                'especificaciones_tecnicas': '4K @ 60Hz, conectores dorados',
                'proveedor': 'TecnoAccesorios SAS',
                'fecha_adquisicion': '2024-05-10',
                'garantia_vencimiento': '2025-05-10',
                'observaciones': 'Lote de cables de reemplazo para salones'
            }
        ]
        df = pd.DataFrame(ejemplos, columns=columnas)
        df.to_excel(writer, sheet_name='Inventario', index=False)

        instrucciones = [
            ['Campo', 'Tipo', 'Obligatorio', 'Descripción y Valores Válidos'],
            ['item', 'Texto', 'SÍ', 'Nombre o descripción clara del elemento.'],
            ['categoria', 'Texto', 'NO', 'Ej: Cómputo, Audiovisuales, Redes, Accesorios. (Por defecto: General)'],
            ['numero_inventario', 'Texto', 'NO', 'Código único de inventario. Si se deja vacío, el sistema lo genera automáticamente.'],
            ['activo_fijo', 'Texto', 'NO', 'Placa de activo fijo institucional UNIMINUTO.'],
            ['serial', 'Texto', 'NO', 'Número de serie de fábrica del equipo.'],
            ['estado', 'Texto', 'NO', 'Disponible | En Préstamo | En Mantenimiento | En Reparación | De Baja. (Por defecto: Disponible)'],
            ['es_por_cantidad', 'Texto', 'NO', 'SI para lotes (cables, controles) o NO para equipos individuales serializados.'],
            ['cantidad_total', 'Número', 'NO', 'Cantidad inicial si es gestionado por lote.'],
            ['procesador', 'Texto', 'NO', 'Ficha Técnica: Procesador / CPU (ej: Intel Core i5-1235U, Apple M2).'],
            ['ram_gb', 'Texto', 'NO', 'Ficha Técnica: Memoria RAM (ej: 8 GB, 16 GB DDR4).'],
            ['almacenamiento', 'Texto', 'NO', 'Ficha Técnica: Disco o SSD (ej: 512 GB SSD NVMe).'],
            ['sistema_operativo', 'Texto', 'NO', 'Ficha Técnica: SO instalado (ej: Windows 11 Pro, Ubuntu 22.04).'],
            ['especificaciones_tecnicas', 'Texto', 'NO', 'Detalles adicionales de hardware y periféricos.'],
            ['fecha_adquisicion', 'Fecha', 'NO', 'Formato AAAA-MM-DD (ej: 2024-03-15).'],
            ['garantia_vencimiento', 'Fecha', 'NO', 'Formato AAAA-MM-DD (ej: 2027-03-15).'],
        ]
        _aplicar_estilo_plantilla(writer, 'Inventario', 'INSTRUCCIONES DE IMPORTACIÓN DE INVENTARIO Y HOJA DE VIDA', instrucciones)

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name='Plantilla_Oficial_Inventario_HojaDeVida.xlsx',
        as_attachment=True
    )


@planillas_bp.route('/descargar_plantilla_actualizacion_red')
@login_required
def descargar_plantilla_actualizacion_red():
    """Genera plantilla Excel ligera para actualización masiva de Hostnames / Nombres de Red y Ubicaciones sin alterar el resto del inventario."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        columnas = ['numero_inventario', 'serial', 'activo_fijo', 'hostname', 'ubicacion_permanente', 'bodega']
        ejemplos = [
            {
                'numero_inventario': 'POR01',
                'serial': '5CD3456789',
                'activo_fijo': 'AF-100234',
                'hostname': 'LAB101-PC01',
                'ubicacion_permanente': 'Laboratorio 101, Puesto 01',
                'bodega': 'Sistemas'
            },
            {
                'numero_inventario': 'POR02',
                'serial': '5CD3456790',
                'activo_fijo': 'AF-100235',
                'hostname': 'LAB101-PC02',
                'ubicacion_permanente': 'Laboratorio 101, Puesto 02',
                'bodega': 'Sistemas'
            },
            {
                'numero_inventario': 'ONE06',
                'serial': 'ON99281X',
                'activo_fijo': 'AF-100888',
                'hostname': 'ONESCREEN-SALA3',
                'ubicacion_permanente': 'Sala de Juntas 3',
                'bodega': 'Audiovisuales'
            }
        ]
        df = pd.DataFrame(ejemplos, columns=columnas)
        df.to_excel(writer, sheet_name='Actualizacion_Red', index=False)

        ws = writer.sheets['Actualizacion_Red']
        ws.views.sheetView[0].showGridLines = True
        for col_idx, col_name in enumerate(columnas, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = Font(bold=True, color='FFFFFF', name='Calibri', size=11)
            cell.fill = PatternFill('solid', fgColor='0284C7')  # Celeste corporativo
            cell.alignment = Alignment(horizontal='center', vertical='center')
            max_len = max(len(str(col_name)), max(len(str(e.get(col_name, ''))) for e in ejemplos)) + 5
            ws.column_dimensions[get_column_letter(col_idx)].width = max(max_len, 16)
        ws.row_dimensions[1].height = 26

    output.seek(0)
    return send_file(
        output,
        download_name='Plantilla_Actualizar_Hostnames_Ubicaciones.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@planillas_bp.route('/subir/inventario', methods=['POST'])
@login_required
@permiso_requerido('inventario', 'crear')
def subir_planilla_inventario():
    """Procesa la planilla de inventario con ficha técnica y asignación automática de sede."""
    archivo = request.files.get('archivo_excel') or request.files.get('archivo')
    df, error = _leer_archivo_excel_o_csv(archivo, expected_sheet='Inventario')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json

    if error:
        if is_ajax:
            return jsonify({'success': False, 'message': error}), 400
        flash(error, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='inventario'))

    if 'item' not in df.columns:
        msg = "La columna obligatoria 'item' no fue encontrada en el archivo."
        if is_ajax:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='inventario'))

    # Sede activa de la sesión
    user_sede_id = session.get('sede_id')
    default_bodega = None
    if user_sede_id:
        default_bodega = Bodega.query.filter_by(sede_id=user_sede_id).first()
    if not default_bodega:
        default_bodega = Bodega.query.first()

    insertados, actualizados, omitidos, errores = [], [], [], []

    def generar_num_inv_unico(item_nombre: str, cat_nombre: str) -> str:
        base = (item_nombre[:3] if len(item_nombre) >= 3 else item_nombre.ljust(3, 'X')).upper()
        base = re.sub(r'[^A-Z0-9]', '', base) or 'ITM'
        ultimos = db.session.query(Inventario.numero_inventario).filter(Inventario.numero_inventario.like(f"{base}%")).all()
        max_n = 0
        for (n_inv,) in ultimos:
            match = re.search(r'(\d+)$', n_inv or '')
            if match:
                max_n = max(max_n, int(match.group(1)))
        return f"{base}{max_n + 1:03d}"

    try:
        for idx, row in df.iterrows():
            fila_num = idx + 2
            item_nombre = _normalizar_texto(row.get('item'))
            if not item_nombre:
                continue

            num_inv = _normalizar_numero_str(row.get('numero_inventario'))
            cat_nombre = _normalizar_texto(row.get('categoria')) or 'General'
            marca_mod = _normalizar_texto(row.get('marca_modelo')) or None
            serial = _normalizar_texto(row.get('serial')) or None
            activo_fijo = _normalizar_numero_str(row.get('activo_fijo')) or None
            ubicacion = _normalizar_texto(row.get('ubicacion_permanente')) or None
            estado = _normalizar_texto(row.get('estado')) or 'Disponible'
            obs = _normalizar_texto(row.get('observaciones')) or None
            hostname = _normalizar_texto(row.get('hostname')) or None

            # Ficha técnica / Hoja de vida
            procesador = _normalizar_texto(row.get('procesador')) or None
            ram_gb = _normalizar_texto(row.get('ram_gb')) or None
            almacenamiento = _normalizar_texto(row.get('almacenamiento')) or None
            sistema_operativo = _normalizar_texto(row.get('sistema_operativo')) or None
            especificaciones = _normalizar_texto(row.get('especificaciones_tecnicas')) or None
            proveedor = _normalizar_texto(row.get('proveedor')) or None

            # Fechas
            fecha_adq = None
            f_adq_str = _normalizar_texto(row.get('fecha_adquisicion'))
            if f_adq_str:
                try:
                    fecha_adq = datetime.strptime(f_adq_str[:10], '%Y-%m-%d').date()
                except ValueError:
                    pass

            fecha_gar = None
            f_gar_str = _normalizar_texto(row.get('garantia_vencimiento'))
            if f_gar_str:
                try:
                    fecha_gar = datetime.strptime(f_gar_str[:10], '%Y-%m-%d').date()
                except ValueError:
                    pass

            # Gestión por cantidad
            es_por_cant_raw = _normalizar_texto(row.get('es_por_cantidad')).upper()
            es_por_cant = es_por_cant_raw in ('SI', 'YES', 'TRUE', '1', 'S')
            try:
                cant_tot = int(row.get('cantidad_total', 1)) if es_por_cant else None
            except (ValueError, TypeError):
                cant_tot = 1 if es_por_cant else None

            # Asegurar existencia de categoría
            cat_obj = CategoriaInventario.query.filter_by(nombre=cat_nombre).first()
            if not cat_obj:
                cat_obj = CategoriaInventario(nombre=cat_nombre)
                db.session.add(cat_obj)
                db.session.flush()

            # Buscar si ya existe por número de inventario
            item_existente = None
            if num_inv:
                item_existente = Inventario.query.filter_by(numero_inventario=num_inv).first()

            if item_existente:
                # Actualizar información y ficha técnica
                item_existente.item = item_nombre
                item_existente.categoria = cat_nombre
                if marca_mod: item_existente.marca_modelo = marca_mod
                if serial: item_existente.serial = serial
                if activo_fijo: item_existente.activo_fijo = activo_fijo
                if ubicacion: item_existente.ubicacion_permanente = ubicacion
                if estado: item_existente.estado = estado
                if obs: item_existente.observaciones = obs
                if hostname: item_existente.hostname = hostname
                
                # Ficha técnica
                if procesador: item_existente.procesador = procesador
                if ram_gb: item_existente.ram_gb = ram_gb
                if almacenamiento: item_existente.almacenamiento = almacenamiento
                if sistema_operativo: item_existente.sistema_operativo = sistema_operativo
                if especificaciones: item_existente.especificaciones_tecnicas = especificaciones
                if proveedor: item_existente.proveedor = proveedor
                if fecha_adq: item_existente.fecha_adquisicion = fecha_adq
                if fecha_gar: item_existente.garantia_vencimiento = fecha_gar

                actualizados.append({'fila': fila_num, 'id': item_existente.numero_inventario, 'item': item_nombre})
            else:
                if not num_inv:
                    num_inv = generar_num_inv_unico(item_nombre, cat_nombre)

                nuevo = Inventario(
                    categoria=cat_nombre,
                    item=item_nombre,
                    marca_modelo=marca_mod,
                    serial=serial,
                    activo_fijo=activo_fijo,
                    numero_inventario=num_inv,
                    ubicacion_permanente=ubicacion,
                    estado=estado,
                    bodega_id=default_bodega.id if default_bodega else None,
                    es_por_cantidad=es_por_cant,
                    cantidad_total=cant_tot,
                    cantidad_disponible=cant_tot,
                    procesador=procesador,
                    ram_gb=ram_gb,
                    almacenamiento=almacenamiento,
                    sistema_operativo=sistema_operativo,
                    especificaciones_tecnicas=especificaciones,
                    proveedor=proveedor,
                    fecha_adquisicion=fecha_adq,
                    garantia_vencimiento=fecha_gar,
                    hostname=hostname,
                    observaciones=obs
                )
                db.session.add(nuevo)
                insertados.append({'fila': fila_num, 'id': num_inv, 'item': item_nombre})

        db.session.commit()

        registrar_auditoria(
            modulo='planillas',
            entidad_tipo='Inventario',
            entidad_id='MASIVO',
            accion='IMPORTAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Carga masiva de inventario: {len(insertados)} nuevos, {len(actualizados)} actualizados.'
        )

        resultado = {
            'success': True,
            'modulo': 'Inventario',
            'insertados': len(insertados),
            'actualizados': len(actualizados),
            'omitidos': len(omitidos),
            'errores': errores,
            'mensaje': f'Planilla de inventario procesada: {len(insertados)} creados, {len(actualizados)} actualizados.'
        }
        if is_ajax:
            return jsonify(resultado)

        flash(resultado['mensaje'], 'success')
        return render_template('planillas.html', tab_activa='inventario', resultado=resultado)

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error procesando planilla de inventario: %s", str(e))
        if is_ajax:
            return jsonify({'success': False, 'message': f'Error en base de datos: {str(e)}'}), 500
        flash(f'Error al procesar la planilla: {str(e)}', 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='inventario'))


# =========================================================================
# 2. PLANILLA DE PROFESORES / DOCENTES
# =========================================================================

@planillas_bp.route('/plantilla/profesores')
@login_required
def descargar_plantilla_profesores():
    """Genera la plantilla Excel oficial para profesores/docentes."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df = pd.DataFrame([
            {
                'cedula': '1012345678',
                'nombre_completo': 'Carlos Andrés Restrepo Gómez',
                'correo': 'carlos.restrepo@uniminuto.edu.co',
                'telefono': '3104567890',
                'programa': 'Ingeniería de Sistemas'
            },
            {
                'cedula': '1023456789',
                'nombre_completo': 'María Fernanda López Torres',
                'correo': 'maria.lopez@uniminuto.edu.co',
                'telefono': '3209876543',
                'programa': 'Administración de Empresas'
            }
        ], columns=['cedula', 'nombre_completo', 'correo', 'telefono', 'programa'])
        df.to_excel(writer, sheet_name='Profesores', index=False)

        instrucciones = [
            ['Campo', 'Tipo', 'Obligatorio', 'Descripción y Formato'],
            ['cedula', 'Número/Texto', 'SÍ', 'Cédula de ciudadanía o extranjería (mínimo 5 dígitos). Única.'],
            ['nombre_completo', 'Texto', 'SÍ', 'Nombres y apellidos completos del docente.'],
            ['correo', 'Texto', 'NO', 'Correo electrónico institucional o personal válido.'],
            ['telefono', 'Texto', 'NO', 'Número de contacto móvil o fijo.'],
            ['programa', 'Texto', 'NO', 'Programa académico al que está adscrito el docente.'],
        ]
        _aplicar_estilo_plantilla(writer, 'Profesores', 'INSTRUCCIONES DE IMPORTACIÓN DE PROFESORES', instrucciones)

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name='Plantilla_Oficial_Profesores.xlsx',
        as_attachment=True
    )


@planillas_bp.route('/actualizar_red_masivo', methods=['POST'])
@login_required
@permiso_requerido('inventario', 'editar')
def actualizar_red_masivo():
    """
    Actualización masiva segura de Hostnames / Nombres de Red y Ubicaciones / Bodegas.
    Busca por numero_inventario, serial o activo_fijo. No crea registros nuevos ni elimina datos preexistentes.
    """
    archivo = request.files.get('archivo_excel') or request.files.get('archivo')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json
    df, error = _leer_archivo_excel_o_csv(archivo, expected_sheet='Actualizacion_Red')

    if error:
        if is_ajax:
            return jsonify({'success': False, 'message': error}), 400
        flash(error, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='inventario'))

    # Normalizar columnas
    df.columns = [str(c).strip().lower().replace(' ', '_').replace('/', '_') for c in df.columns]

    actualizados = []
    no_encontrados = []

    # Mapas de bodegas
    sedes_map = {s.nombre.lower(): s.id for s in Sede.query.all()}
    user_sede_id = session.get('sede_id')
    bodegas_all = Bodega.query.all()
    bodegas_map = {(b.sede_id, b.nombre.lower()): b.id for b in bodegas_all}

    for idx, row in df.iterrows():
        fila_num = idx + 2
        num_inv = _normalizar_numero_str(row.get('numero_inventario'))
        serial = _normalizar_texto(row.get('serial'))
        activo_fijo = _normalizar_numero_str(row.get('activo_fijo'))

        hostname = _normalizar_texto(row.get('hostname'))
        ubicacion = _normalizar_texto(row.get('ubicacion_permanente') or row.get('ubicacion'))
        bodega_str = _normalizar_texto(row.get('bodega'))

        if not num_inv and not serial and not activo_fijo:
            continue

        # Búsqueda escalonada: número de inventario -> serial -> activo fijo
        item = None
        if num_inv:
            item = Inventario.query.filter_by(numero_inventario=num_inv).first()
        if not item and serial:
            item = Inventario.query.filter_by(serial=serial).first()
        if not item and activo_fijo:
            item = Inventario.query.filter_by(activo_fijo=activo_fijo).first()

        if not item:
            ref_id = num_inv or serial or activo_fijo
            no_encontrados.append({'fila': fila_num, 'id': ref_id})
            continue

        cambios = {}
        if hostname and hostname != (item.hostname or ''):
            cambios['hostname'] = {'antes': item.hostname, 'despues': hostname}
            item.hostname = hostname

        if ubicacion and ubicacion != (item.ubicacion_permanente or ''):
            cambios['ubicacion_permanente'] = {'antes': item.ubicacion_permanente, 'despues': ubicacion}
            item.ubicacion_permanente = ubicacion

        if bodega_str:
            sede_target = item.bodega.sede_id if item.bodega else user_sede_id
            target_bodega_id = bodegas_map.get((sede_target, bodega_str.lower()))
            if target_bodega_id and item.bodega_id != target_bodega_id:
                cambios['bodega_id'] = {'antes': item.bodega_id, 'despues': target_bodega_id}
                item.bodega_id = target_bodega_id

        if cambios:
            actualizados.append({
                'fila': fila_num,
                'id': item.numero_inventario,
                'item': item.item,
                'hostname': item.hostname,
                'ubicacion': item.ubicacion_permanente
            })

    try:
        db.session.commit()
        registrar_auditoria(
            modulo='inventario',
            entidad_tipo='Inventario',
            entidad_id='MASIVO_RED',
            accion='ACTUALIZAR_RED',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Actualización masiva de red/ubicación: {len(actualizados)} equipos modificados.'
        )

        msg = f"Se actualizaron exitosamente {len(actualizados)} equipos."
        if no_encontrados:
            msg += f" (Se ignoraron {len(no_encontrados)} filas cuyos identificadores no existen en el sistema)."

        if is_ajax:
            return jsonify({
                'success': True,
                'message': msg,
                'actualizados': len(actualizados),
                'no_encontrados': len(no_encontrados)
            })

        flash(msg, 'success')
        return redirect(url_for('planillas.planillas_dashboard', tab='inventario'))

    except Exception as e:
        db.session.rollback()
        err_msg = f"Error al procesar la actualización: {str(e)}"
        if is_ajax:
            return jsonify({'success': False, 'message': err_msg}), 500
        flash(err_msg, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='inventario'))


@planillas_bp.route('/subir/profesores', methods=['POST'])
@login_required
@permiso_requerido('profesores', 'crear')
def subir_planilla_profesores():
    """Procesa la planilla de profesores."""
    archivo = request.files.get('archivo_excel') or request.files.get('archivo')
    df, error = _leer_archivo_excel_o_csv(archivo, expected_sheet='Profesores')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json

    if error:
        if is_ajax: return jsonify({'success': False, 'message': error}), 400
        flash(error, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='profesores'))

    if 'cedula' not in df.columns or 'nombre_completo' not in df.columns:
        msg = "Las columnas obligatorias 'cedula' y 'nombre_completo' son requeridas."
        if is_ajax: return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='profesores'))

    insertados, actualizados, omitidos, errores = [], [], [], []

    try:
        for idx, row in df.iterrows():
            fila_num = idx + 2
            cedula_str = _normalizar_numero_str(row.get('cedula'))
            nombre = _normalizar_texto(row.get('nombre_completo'))
            correo = _normalizar_texto(row.get('correo')) or None
            telefono = _normalizar_numero_str(row.get('telefono')) or None
            programa = _normalizar_texto(row.get('programa')) or None

            if not cedula_str or not nombre:
                continue

            try:
                cedula_int = int(cedula_str)
            except ValueError:
                errores.append({'fila': fila_num, 'id': cedula_str, 'razon': 'Cédula debe ser un número entero'})
                continue

            profe = Profesor.query.get(cedula_int)
            if profe:
                profe.nombre_completo = nombre
                if correo: profe.correo = correo
                if telefono: profe.telefono = telefono
                if programa: profe.programa = programa
                actualizados.append({'fila': fila_num, 'id': cedula_str, 'item': nombre})
            else:
                nuevo = Profesor(
                    cedula=cedula_int,
                    nombre_completo=nombre,
                    correo=correo,
                    telefono=telefono,
                    programa=programa
                )
                db.session.add(nuevo)
                insertados.append({'fila': fila_num, 'id': cedula_str, 'item': nombre})

        db.session.commit()

        registrar_auditoria(
            modulo='planillas',
            entidad_tipo='Profesor',
            entidad_id='MASIVO',
            accion='IMPORTAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Carga masiva de profesores: {len(insertados)} nuevos, {len(actualizados)} actualizados.'
        )

        resultado = {
            'success': True,
            'modulo': 'Profesores',
            'insertados': len(insertados),
            'actualizados': len(actualizados),
            'omitidos': len(omitidos),
            'errores': errores,
            'mensaje': f'Planilla de profesores procesada: {len(insertados)} creados, {len(actualizados)} actualizados.'
        }
        if is_ajax: return jsonify(resultado)
        flash(resultado['mensaje'], 'success')
        return render_template('planillas.html', tab_activa='profesores', resultado=resultado)

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error procesando planilla de profesores: %s", str(e))
        if is_ajax: return jsonify({'success': False, 'message': f'Error en base de datos: {str(e)}'}), 500
        flash(f'Error al procesar la planilla: {str(e)}', 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='profesores'))


# =========================================================================
# 3. PLANILLA DE COLABORADORES (HORARIOS 42H Y TURNOS)
# =========================================================================

@planillas_bp.route('/plantilla/colaboradores')
@login_required
def descargar_plantilla_colaboradores():
    """Genera la plantilla Excel oficial para colaboradores operativos."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df = pd.DataFrame([
            {
                'documento': '1030456789',
                'nombre_completo': 'Omar Morales Vargas',
                'cargo': 'Auxiliar de Soporte Técnico',
                'correo': 'omar.morales@uniminuto.edu.co',
                'telefono': '3112345678',
                'total_horas_semana': '42',
                'sede': 'ENGATIVA SEDE PRINCIPAL',
                'horario_resumen': 'Lunes a Viernes 06:30 - 15:30 (42h semanales)',
                'observaciones': 'Turno rotativo de mañana'
            },
            {
                'documento': '1040567890',
                'nombre_completo': 'Laura Patricia Rojas Peña',
                'cargo': 'Auxiliar Audiovisuales',
                'correo': 'laura.rojas@uniminuto.edu.co',
                'telefono': '3123456789',
                'total_horas_semana': '42',
                'sede': 'PERDOMO',
                'horario_resumen': 'Lunes a Viernes 13:00 - 22:00 (42h semanales)',
                'observaciones': 'Atención aulas y entrega de turno'
            }
        ], columns=[
            'documento', 'nombre_completo', 'cargo', 'correo', 'telefono',
            'total_horas_semana', 'sede', 'horario_resumen', 'observaciones'
        ])
        df.to_excel(writer, sheet_name='Colaboradores', index=False)

        instrucciones = [
            ['Campo', 'Tipo', 'Obligatorio', 'Descripción y Formato'],
            ['documento', 'Texto', 'SÍ', 'Número de identificación del colaborador (único).'],
            ['nombre_completo', 'Texto', 'SÍ', 'Nombres y apellidos completos.'],
            ['cargo', 'Texto', 'NO', 'Cargo u ocupación laboral.'],
            ['correo', 'Texto', 'NO', 'Correo institucional o personal.'],
            ['telefono', 'Texto', 'NO', 'Celular o teléfono fijo.'],
            ['total_horas_semana', 'Número', 'NO', 'Jornada semanal legal (por defecto: 42 horas).'],
            ['sede', 'Texto', 'NO', 'Nombre de la sede (ej: PERDOMO, ENGATIVA SEDE PRINCIPAL). Si se omite, se asigna la sede actual.'],
            ['horario_resumen', 'Texto', 'NO', 'Descripción del horario semanal o turno asignado.'],
            ['observaciones', 'Texto', 'NO', 'Notas adicionales sobre cobertura o responsabilidades.'],
        ]
        _aplicar_estilo_plantilla(writer, 'Colaboradores', 'INSTRUCCIONES DE IMPORTACIÓN DE COLABORADORES', instrucciones)

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name='Plantilla_Oficial_Colaboradores.xlsx',
        as_attachment=True
    )


@planillas_bp.route('/subir/colaboradores', methods=['POST'])
@login_required
@permiso_requerido('colaboradores', 'crear')
def subir_planilla_colaboradores():
    """Procesa la planilla de colaboradores."""
    archivo = request.files.get('archivo_excel') or request.files.get('archivo')
    df, error = _leer_archivo_excel_o_csv(archivo, expected_sheet='Colaboradores')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json

    if error:
        if is_ajax: return jsonify({'success': False, 'message': error}), 400
        flash(error, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='colaboradores'))

    if 'nombre_completo' not in df.columns:
        msg = "La columna obligatoria 'nombre_completo' no fue encontrada en el archivo."
        if is_ajax: return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='colaboradores'))

    user_sede_id = session.get('sede_id')
    sedes_map = {s.nombre.strip().lower(): s.id for s in Sede.query.all()}
    insertados, actualizados, omitidos, errores = [], [], [], []

    try:
        for idx, row in df.iterrows():
            fila_num = idx + 2
            nombre = _normalizar_texto(row.get('nombre_completo'))
            if not nombre:
                continue

            doc = _normalizar_numero_str(row.get('documento')) or None
            cargo = _normalizar_texto(row.get('cargo')) or None
            correo = _normalizar_texto(row.get('correo')) or None
            telefono = _normalizar_numero_str(row.get('telefono')) or None
            horario_txt = _normalizar_texto(row.get('horario_resumen')) or None
            obs = _normalizar_texto(row.get('observaciones')) or None

            try:
                horas_sem = int(row.get('total_horas_semana', 42))
            except (ValueError, TypeError):
                horas_sem = 42

            sede_txt = _normalizar_texto(row.get('sede')).lower()
            colab_sede_id = sedes_map.get(sede_txt) or user_sede_id

            colab = None
            if doc:
                colab = Colaborador.query.filter_by(documento=doc).first()

            if colab:
                colab.nombre_completo = nombre
                if cargo: colab.cargo = cargo
                if correo: colab.correo = correo
                if telefono: colab.telefono = telefono
                if colab_sede_id: colab.sede_id = colab_sede_id
                colab.total_horas_semana = horas_sem
                if horario_txt: colab.horario_texto = horario_txt
                if obs: colab.observaciones = obs
                actualizados.append({'fila': fila_num, 'id': doc or str(colab.id), 'item': nombre})
            else:
                nuevo = Colaborador(
                    nombre_completo=nombre,
                    documento=doc,
                    cargo=cargo,
                    correo=correo,
                    telefono=telefono,
                    sede_id=colab_sede_id,
                    total_horas_semana=horas_sem,
                    fecha_inicio_horario='A partir del 15 de julio 2026',
                    horario_texto=horario_txt,
                    activo=True,
                    observaciones=obs
                )
                db.session.add(nuevo)
                insertados.append({'fila': fila_num, 'id': doc or 'Nuevo', 'item': nombre})

        db.session.commit()

        registrar_auditoria(
            modulo='planillas',
            entidad_tipo='Colaborador',
            entidad_id='MASIVO',
            accion='IMPORTAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Carga masiva de colaboradores: {len(insertados)} nuevos, {len(actualizados)} actualizados.'
        )

        resultado = {
            'success': True,
            'modulo': 'Colaboradores',
            'insertados': len(insertados),
            'actualizados': len(actualizados),
            'omitidos': len(omitidos),
            'errores': errores,
            'mensaje': f'Planilla de colaboradores procesada: {len(insertados)} creados, {len(actualizados)} actualizados.'
        }
        if is_ajax: return jsonify(resultado)
        flash(resultado['mensaje'], 'success')
        return render_template('planillas.html', tab_activa='colaboradores', resultado=resultado)

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error procesando planilla de colaboradores: %s", str(e))
        if is_ajax: return jsonify({'success': False, 'message': f'Error en base de datos: {str(e)}'}), 500
        flash(f'Error al procesar la planilla: {str(e)}', 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='colaboradores'))


# =========================================================================
# 4. PLANILLA DE ESTUDIANTES
# =========================================================================

@planillas_bp.route('/plantilla/estudiantes')
@login_required
def descargar_plantilla_estudiantes():
    """Genera la plantilla Excel oficial para estudiantes."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df = pd.DataFrame([
            {
                'codigo_banner': '000854321',
                'documento': '1014567890',
                'tipo_documento': 'CC',
                'nombre_completo': 'Alejandro Morales Rivera',
                'correo': 'alejandro.morales@uniminuto.edu.co',
                'telefono': '3157891234',
                'programa': 'Ingeniería de Sistemas',
                'sede': 'ENGATIVA SEDE PRINCIPAL',
                'jornada': 'NOCTURNA',
                'semestre': '5'
            },
            {
                'codigo_banner': '000896542',
                'documento': '1025678901',
                'tipo_documento': 'CC',
                'nombre_completo': 'Daniela Castro Beltrán',
                'correo': 'daniela.castro@uniminuto.edu.co',
                'telefono': '3176549870',
                'programa': 'Psicología',
                'sede': 'PERDOMO',
                'jornada': 'DIURNA',
                'semestre': '3'
            }
        ], columns=[
            'codigo_banner', 'documento', 'tipo_documento', 'nombre_completo',
            'correo', 'telefono', 'programa', 'sede', 'jornada', 'semestre'
        ])
        df.to_excel(writer, sheet_name='Estudiantes', index=False)

        instrucciones = [
            ['Campo', 'Tipo', 'Obligatorio', 'Descripción y Formato'],
            ['codigo_banner', 'Texto', 'SÍ', 'ID Banner o código institucional único del estudiante.'],
            ['nombre_completo', 'Texto', 'SÍ', 'Nombres y apellidos completos.'],
            ['documento', 'Texto', 'NO', 'Número de identificación del estudiante.'],
            ['tipo_documento', 'Texto', 'NO', 'CC, TI, CE, PAS. (Por defecto: CC)'],
            ['correo', 'Texto', 'NO', 'Correo institucional o personal.'],
            ['telefono', 'Texto', 'NO', 'Número de contacto móvil o fijo.'],
            ['programa', 'Texto', 'NO', 'Nombre o código del programa académico.'],
            ['sede', 'Texto', 'NO', 'Nombre de la sede. Si se omite, se asigna la sede actual.'],
            ['jornada', 'Texto', 'NO', 'DIURNA, NOCTURNA, SABATINA o VIRTUAL.'],
            ['semestre', 'Número', 'NO', 'Semestre académico actual (1 al 10).'],
        ]
        _aplicar_estilo_plantilla(writer, 'Estudiantes', 'INSTRUCCIONES DE IMPORTACIÓN DE ESTUDIANTES', instrucciones)

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name='Plantilla_Oficial_Estudiantes.xlsx',
        as_attachment=True
    )


@planillas_bp.route('/subir/estudiantes', methods=['POST'])
@login_required
@permiso_requerido('estudiantes', 'crear')
def subir_planilla_estudiantes():
    """Procesa la planilla de estudiantes."""
    archivo = request.files.get('archivo_excel') or request.files.get('archivo')
    df, error = _leer_archivo_excel_o_csv(archivo, expected_sheet='Estudiantes')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json

    if error:
        if is_ajax: return jsonify({'success': False, 'message': error}), 400
        flash(error, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='estudiantes'))

    if 'codigo_banner' not in df.columns or 'nombre_completo' not in df.columns:
        msg = "Las columnas obligatorias 'codigo_banner' y 'nombre_completo' son requeridas."
        if is_ajax: return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='estudiantes'))

    user_sede_id = session.get('sede_id')
    sedes_map = {s.nombre.strip().lower(): s.id for s in Sede.query.all()}
    programas_map = {p.nombre.strip().lower(): p.id for p in ProgramaAcademico.query.all()}

    insertados, actualizados, omitidos, errores = [], [], [], []

    try:
        for idx, row in df.iterrows():
            fila_num = idx + 2
            cod_banner = _normalizar_numero_str(row.get('codigo_banner'))
            nombre = _normalizar_texto(row.get('nombre_completo'))
            if not cod_banner or not nombre:
                continue

            doc = _normalizar_numero_str(row.get('documento')) or None
            tipo_doc = _normalizar_texto(row.get('tipo_documento')).upper() or 'CC'
            correo = _normalizar_texto(row.get('correo')) or None
            telefono = _normalizar_numero_str(row.get('telefono')) or None
            prog_txt = _normalizar_texto(row.get('programa'))
            sede_txt = _normalizar_texto(row.get('sede')).lower()
            jornada = _normalizar_texto(row.get('jornada')).upper() or None

            try:
                semestre = int(row.get('semestre', 0)) if row.get('semestre') else None
            except (ValueError, TypeError):
                semestre = None

            # Asignar sede
            est_sede_id = sedes_map.get(sede_txt) or user_sede_id

            # Programa
            prog_id = programas_map.get(prog_txt.lower()) if prog_txt else None

            est = Estudiante.query.filter_by(codigo_banner=cod_banner).first()
            if est:
                est.nombre_completo = nombre
                if doc: est.documento = doc
                est.tipo_documento = tipo_doc
                if correo: est.correo = correo
                if telefono: est.telefono = telefono
                if prog_id: est.programa_id = prog_id
                if est_sede_id: est.sede_id = est_sede_id
                if jornada: est.jornada = jornada
                if semestre: est.semestre = semestre
                actualizados.append({'fila': fila_num, 'id': cod_banner, 'item': nombre})
            else:
                nuevo = Estudiante(
                    codigo_banner=cod_banner,
                    documento=doc,
                    tipo_documento=tipo_doc,
                    nombre_completo=nombre,
                    correo=correo,
                    telefono=telefono,
                    programa_id=prog_id,
                    sede_id=est_sede_id,
                    jornada=jornada,
                    semestre=semestre,
                    activo=True
                )
                db.session.add(nuevo)
                insertados.append({'fila': fila_num, 'id': cod_banner, 'item': nombre})

        db.session.commit()

        registrar_auditoria(
            modulo='planillas',
            entidad_tipo='Estudiante',
            entidad_id='MASIVO',
            accion='IMPORTAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Carga masiva de estudiantes: {len(insertados)} nuevos, {len(actualizados)} actualizados.'
        )

        resultado = {
            'success': True,
            'modulo': 'Estudiantes',
            'insertados': len(insertados),
            'actualizados': len(actualizados),
            'omitidos': len(omitidos),
            'errores': errores,
            'mensaje': f'Planilla de estudiantes procesada: {len(insertados)} creados, {len(actualizados)} actualizados.'
        }
        if is_ajax: return jsonify(resultado)
        flash(resultado['mensaje'], 'success')
        return render_template('planillas.html', tab_activa='estudiantes', resultado=resultado)

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error procesando planilla de estudiantes: %s", str(e))
        if is_ajax: return jsonify({'success': False, 'message': f'Error en base de datos: {str(e)}'}), 500
        flash(f'Error al procesar la planilla: {str(e)}', 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='estudiantes'))


# =========================================================================
# 5. PLANILLA DE SALAS DE CÓMPUTO Y PROGRAMACIÓN DE CLASES
# =========================================================================

@planillas_bp.route('/plantilla/salas-computo')
@login_required
def descargar_plantilla_salas_computo():
    """Genera la plantilla Excel oficial para programación de clases en salas de cómputo."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df = pd.DataFrame([
            {
                'fecha': '2026-10-28',
                'hora_inicio': '07:00',
                'hora_fin': '09:00',
                'salon': 'LS1',
                'nombre_profesor': 'Carlos Andrés Restrepo',
                'materia': 'Estructuras de Datos',
                'asistencia': 'SI',
                'horas_academicas': '2',
                'jornada': 'MAÑANA',
                'num_estudiantes': '30',
                'programa': 'Ingeniería de Sistemas',
                'modalidad': 'Presencial',
                'observaciones': 'Requiere software Visual Studio Code y Python 3'
            },
            {
                'fecha': '2026-10-28',
                'hora_inicio': '09:00',
                'hora_fin': '11:00',
                'salon': 'LS2',
                'nombre_profesor': 'María Fernanda López',
                'materia': 'Contabilidad Financiera',
                'asistencia': 'NO',
                'horas_academicas': '2',
                'jornada': 'MAÑANA',
                'num_estudiantes': '28',
                'programa': 'Contaduría Pública',
                'modalidad': 'Presencial',
                'observaciones': 'Requiere software SIIGO'
            }
        ], columns=[
            'fecha', 'hora_inicio', 'hora_fin', 'salon', 'nombre_profesor',
            'materia', 'asistencia', 'horas_academicas', 'jornada',
            'num_estudiantes', 'programa', 'modalidad', 'observaciones'
        ])
        df.to_excel(writer, sheet_name='SalasComputo', index=False)

        instrucciones = [
            ['Campo', 'Tipo', 'Obligatorio', 'Descripción y Formato'],
            ['fecha', 'Fecha', 'SÍ', 'Fecha de la clase en formato AAAA-MM-DD.'],
            ['hora_inicio', 'Hora', 'SÍ', 'Hora de inicio en formato militar HH:MM (ej: 07:00).'],
            ['hora_fin', 'Hora', 'SÍ', 'Hora de fin en formato militar HH:MM (ej: 09:00).'],
            ['salon', 'Texto', 'SÍ', 'Salón o laboratorio asignado (ej: LS1, LS2, A-201).'],
            ['nombre_profesor', 'Texto', 'SÍ', 'Nombre del docente a cargo.'],
            ['materia', 'Texto', 'SÍ', 'Nombre de la asignatura o materia.'],
            ['asistencia', 'Texto', 'NO', 'SI o NO. (Por defecto: NO)'],
            ['horas_academicas', 'Número', 'NO', 'Duración en horas académicas.'],
            ['jornada', 'Texto', 'NO', 'MAÑANA, TARDE o NOCHE.'],
            ['num_estudiantes', 'Número', 'NO', 'Cantidad proyectada o real de alumnos.'],
            ['programa', 'Texto', 'NO', 'Programa académico de los estudiantes.'],
            ['modalidad', 'Texto', 'NO', 'Presencial o Virtual.'],
            ['observaciones', 'Texto', 'NO', 'Requerimientos de software o notas técnicas.'],
        ]
        _aplicar_estilo_plantilla(writer, 'SalasComputo', 'INSTRUCCIONES DE IMPORTACIÓN DE SALAS Y CLASES', instrucciones)

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name='Plantilla_Oficial_Salas_Computo.xlsx',
        as_attachment=True
    )


@planillas_bp.route('/subir/salas-computo', methods=['POST'])
@login_required
@permiso_requerido('salas_computo', 'crear')
def subir_planilla_salas_computo():
    """Procesa la planilla de clases y programación de salas de cómputo."""
    archivo = request.files.get('archivo_excel') or request.files.get('archivo')
    df, error = _leer_archivo_excel_o_csv(archivo, expected_sheet='SalasComputo')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json

    if error:
        if is_ajax: return jsonify({'success': False, 'message': error}), 400
        flash(error, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='salas_computo'))

    req_cols = {'fecha', 'hora_inicio', 'hora_fin', 'salon', 'nombre_profesor', 'materia'}
    faltantes = req_cols - set(df.columns)
    if faltantes:
        msg = f"Faltan columnas requeridas: {', '.join(sorted(faltantes))}."
        if is_ajax: return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='salas_computo'))

    insertados, actualizados, omitidos, errores = [], [], [], []

    try:
        for idx, row in df.iterrows():
            fila_num = idx + 2
            fecha_str = _normalizar_texto(row.get('fecha'))
            h_ini_str = _normalizar_texto(row.get('hora_inicio'))
            h_fin_str = _normalizar_texto(row.get('hora_fin'))
            salon = _normalizar_texto(row.get('salon'))
            profesor = _normalizar_texto(row.get('nombre_profesor'))
            materia = _normalizar_texto(row.get('materia'))

            if not fecha_str or not salon or not profesor or not materia:
                continue

            try:
                f_val = datetime.strptime(fecha_str[:10], '%Y-%m-%d').date()
            except ValueError:
                errores.append({'fila': fila_num, 'id': salon, 'razon': f"Fecha '{fecha_str}' no válida (use AAAA-MM-DD)"})
                continue

            try:
                h_ini_val = datetime.strptime(h_ini_str[:5], '%H:%M').time()
            except ValueError:
                errores.append({'fila': fila_num, 'id': salon, 'razon': f"Hora inicio '{h_ini_str}' no válida (use HH:MM)"})
                continue

            try:
                h_fin_val = datetime.strptime(h_fin_str[:5], '%H:%M').time()
            except ValueError:
                errores.append({'fila': fila_num, 'id': salon, 'razon': f"Hora fin '{h_fin_str}' no válida (use HH:MM)"})
                continue

            asistencia_raw = _normalizar_texto(row.get('asistencia')).upper()
            asistencia = 'Sí' if asistencia_raw in ('SI', 'SÍ', 'YES', '1', 'S') else 'No'

            try:
                h_acad = float(row.get('horas_academicas', 2))
            except (ValueError, TypeError):
                h_acad = 2.0

            try:
                n_est = int(float(row.get('num_estudiantes', 0))) if row.get('num_estudiantes') else None
            except (ValueError, TypeError):
                n_est = None

            jornada = _normalizar_texto(row.get('jornada')).upper() or None
            programa = _normalizar_texto(row.get('programa')) or None
            modalidad = _normalizar_texto(row.get('modalidad')).capitalize() or 'Presencial'
            obs = _normalizar_texto(row.get('observaciones')) or None

            nueva_clase = ClaseSalaComputo(
                fecha=f_val,
                hora_inicio=h_ini_val,
                hora_fin=h_fin_val,
                salon=salon,
                nombre_profesor=profesor,
                materia=materia,
                asistencia=asistencia,
                horas_academicas=h_acad,
                jornada=jornada,
                num_estudiantes=n_est,
                programa=programa,
                modalidad=modalidad,
                observaciones=obs,
                estado='Programada'
            )
            db.session.add(nueva_clase)
            insertados.append({'fila': fila_num, 'id': f"{salon} ({fecha_str})", 'item': materia})

        db.session.commit()

        registrar_auditoria(
            modulo='planillas',
            entidad_tipo='ClaseSalaComputo',
            entidad_id='MASIVO',
            accion='IMPORTAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Carga masiva de programación de salas: {len(insertados)} clases programadas.'
        )

        resultado = {
            'success': True,
            'modulo': 'Salas de Cómputo',
            'insertados': len(insertados),
            'actualizados': 0,
            'omitidos': len(omitidos),
            'errores': errores,
            'mensaje': f'Planilla de programación procesada: {len(insertados)} clases programadas exitosamente.'
        }
        if is_ajax: return jsonify(resultado)
        flash(resultado['mensaje'], 'success')
        return render_template('planillas.html', tab_activa='salas_computo', resultado=resultado)

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error procesando planilla de salas de cómputo: %s", str(e))
        if is_ajax: return jsonify({'success': False, 'message': f'Error en base de datos: {str(e)}'}), 500
        flash(f'Error al procesar la planilla: {str(e)}', 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='salas_computo'))


# =========================================================================
# 6. PLANILLA DE USUARIOS Y ROLES (ADMIN / AUXILIARES)
# =========================================================================

@planillas_bp.route('/plantilla/usuarios')
@login_required
@permiso_requerido('admin', 'crear')
def descargar_plantilla_usuarios():
    """Genera la plantilla Excel oficial para usuarios del sistema (Auxiliares/Admins)."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df = pd.DataFrame([
            {
                'documento': '1015678901',
                'nombre_completo': 'Juan Carlos Méndez Soto',
                'correo': 'juan.mendez@uniminuto.edu.co',
                'contrasena': 'Uniminuto2026*',
                'rol': 'auxiliar'
            },
            {
                'documento': '1016789012',
                'nombre_completo': 'Ana María Gómez Rivas',
                'correo': 'ana.gomez@uniminuto.edu.co',
                'contrasena': 'Uniminuto2026*',
                'rol': 'auxiliar'
            }
        ], columns=['documento', 'nombre_completo', 'correo', 'contrasena', 'rol'])
        df.to_excel(writer, sheet_name='Usuarios', index=False)

        instrucciones = [
            ['Campo', 'Tipo', 'Obligatorio', 'Descripción y Formato'],
            ['documento', 'Texto', 'SÍ', 'Número de identificación del usuario (mínimo 3 caracteres).'],
            ['nombre_completo', 'Texto', 'SÍ', 'Nombres y apellidos completos.'],
            ['correo', 'Texto', 'SÍ', 'Correo electrónico único en el sistema.'],
            ['contrasena', 'Texto', 'SÍ', 'Contraseña inicial (mínimo 8 caracteres, al menos 1 letra y 1 número).'],
            ['rol', 'Texto', 'NO', 'auxiliar o admin. (Por defecto: auxiliar)'],
        ]
        _aplicar_estilo_plantilla(writer, 'Usuarios', 'INSTRUCCIONES DE IMPORTACIÓN DE USUARIOS', instrucciones)

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name='Plantilla_Oficial_Usuarios.xlsx',
        as_attachment=True
    )


@planillas_bp.route('/subir/usuarios', methods=['POST'])
@login_required
@permiso_requerido('admin', 'crear')
def subir_planilla_usuarios():
    """Procesa la planilla de usuarios (auxiliares / administradores)."""
    archivo = request.files.get('archivo_excel') or request.files.get('archivo')
    df, error = _leer_archivo_excel_o_csv(archivo, expected_sheet='Usuarios')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json

    if error:
        if is_ajax: return jsonify({'success': False, 'message': error}), 400
        flash(error, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='usuarios'))

    req_cols = {'documento', 'nombre_completo', 'correo', 'contrasena'}
    faltantes = req_cols - set(df.columns)
    if faltantes:
        msg = f"Faltan columnas requeridas: {', '.join(sorted(faltantes))}."
        if is_ajax: return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='usuarios'))

    insertados, actualizados, omitidos, errores = [], [], [], []

    try:
        for idx, row in df.iterrows():
            fila_num = idx + 2
            doc = _normalizar_numero_str(row.get('documento'))
            nombre = _normalizar_texto(row.get('nombre_completo'))
            correo = _normalizar_texto(row.get('correo')).lower()
            pwd = _normalizar_texto(row.get('contrasena'))
            rol = _normalizar_texto(row.get('rol')).lower() or 'auxiliar'

            if not doc and not nombre and not correo:
                continue

            if not doc or len(doc) < 3:
                errores.append({'fila': fila_num, 'id': doc or 'N/A', 'razon': 'Documento inválido (mín. 3 caracteres)'})
                continue
            if not nombre or len(nombre) < 3:
                errores.append({'fila': fila_num, 'id': doc, 'razon': 'Nombre inválido'})
                continue
            if not correo or '@' not in correo:
                errores.append({'fila': fila_num, 'id': doc, 'razon': 'Correo inválido'})
                continue
            if not pwd or len(pwd) < 8:
                errores.append({'fila': fila_num, 'id': doc, 'razon': 'Contraseña muy corta (mín. 8 caracteres)'})
                continue

            if rol not in ('admin', 'auxiliar', 'superadmin'):
                rol = 'auxiliar'

            # Verificar si ya existe por documento o correo
            aux_doc = Auxiliar.query.get(doc)
            if aux_doc:
                omitidos.append({'fila': fila_num, 'id': doc, 'razon': 'Documento de usuario ya registrado'})
                continue

            aux_mail = Auxiliar.query.filter_by(correo=correo).first()
            if aux_mail:
                omitidos.append({'fila': fila_num, 'id': doc, 'razon': 'Correo ya registrado con otro usuario'})
                continue

            nuevo = Auxiliar(
                documento=doc,
                nombre_completo=nombre,
                correo=correo,
                contraseña=generate_password_hash(pwd),
                rol=rol
            )
            db.session.add(nuevo)
            insertados.append({'fila': fila_num, 'id': doc, 'item': nombre})

        db.session.commit()

        registrar_auditoria(
            modulo='planillas',
            entidad_tipo='Auxiliar',
            entidad_id='MASIVO',
            accion='IMPORTAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Carga masiva de usuarios: {len(insertados)} usuarios creados.'
        )

        resultado = {
            'success': True,
            'modulo': 'Usuarios',
            'insertados': len(insertados),
            'actualizados': 0,
            'omitidos': len(omitidos),
            'errores': errores,
            'mensaje': f'Planilla de usuarios procesada: {len(insertados)} usuarios creados exitosamente.'
        }
        if is_ajax: return jsonify(resultado)
        flash(resultado['mensaje'], 'success')
        return render_template('planillas.html', tab_activa='usuarios', resultado=resultado)

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error procesando planilla de usuarios: %s", str(e))
        if is_ajax: return jsonify({'success': False, 'message': f'Error en base de datos: {str(e)}'}), 500
        flash(f'Error al procesar la planilla: {str(e)}', 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='usuarios'))


# =========================================================================
# 7. PLANILLA DE RESERVAS DE ESPACIOS, SALONES Y RECURSOS
# =========================================================================

@planillas_bp.route('/plantilla/reservas')
@login_required
def descargar_plantilla_reservas():
    """Genera la plantilla Excel oficial para reservas de salones, espacios y niñeras."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Cargar datos oficiales precargados si existen en data/
        excel_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'Plantilla_Reservas_Salas_Computo_Perdomo.xlsx'))
        if os.path.exists(excel_path):
            try:
                df_real = pd.read_excel(excel_path, sheet_name='Reservas')
                ejemplos = df_real.to_dict(orient='records')
            except Exception:
                pass

        if not ejemplos:
            ejemplos = [
                {
                    'cedula_profesor': '1018273645',
                    'nombre_profesor': 'Carlos Alberto Rodríguez',
                    'recurso_tipo': 'Salón',
                    'recurso_nombre': '704LS1',
                    'fecha': '2026-10-26',
                    'hora_inicio': '07:00',
                    'hora_fin': '08:29',
                    'jornada': 'MAÑANA',
                    'nrc': '89315',
                    'programa': 'Ingeniería de Sistemas',
                    'sede': 'PERDOMO',
                    'tipo_reserva': 'Clase',
                    'observaciones': 'Dibujo'
                }
            ]

        columnas = [
            'cedula_profesor', 'nombre_profesor', 'recurso_tipo', 'recurso_nombre',
            'fecha', 'hora_inicio', 'hora_fin', 'jornada', 'nrc', 'programa',
            'sede', 'tipo_reserva', 'observaciones'
        ]
        df = pd.DataFrame(ejemplos)
        for col in columnas:
            if col not in df.columns:
                df[col] = ''
        df = df[columnas]
        df.to_excel(writer, sheet_name='Reservas', index=False)

        instrucciones = [
            ['Campo', 'Tipo', 'Obligatorio', 'Descripción y Formato'],
            ['cedula_profesor', 'Número', 'SÍ', 'Cédula de ciudadanía del docente solicitante.'],
            ['nombre_profesor', 'Texto', 'NO', 'Nombre completo del docente. Si no existe en sistema, se registrará con este nombre.'],
            ['recurso_tipo', 'Texto', 'NO', 'Tipo: Salón, Niñera, Audiovisual, Espacio. (Por defecto se deduce del nombre o Salón).'],
            ['recurso_nombre', 'Texto', 'SÍ', 'Código o nombre del espacio (ej: A-301, LS1, LS2, Niñera 1, Torre A-204).'],
            ['fecha', 'Fecha', 'SÍ', 'Fecha de la reserva en formato AAAA-MM-DD (ej: 2026-11-03).'],
            ['hora_inicio', 'Hora', 'SÍ', 'Hora militar de inicio HH:MM (ej: 07:00 o 18:15).'],
            ['hora_fin', 'Hora', 'SÍ', 'Hora militar de fin HH:MM (ej: 09:00 o 20:30).'],
            ['jornada', 'Texto', 'NO', 'MAÑANA, TARDE o NOCHE. Si se deja vacía, se calcula automáticamente según la hora de inicio.'],
            ['nrc', 'Texto', 'NO', 'Código NRC de la asignatura o evento.'],
            ['programa', 'Texto', 'NO', 'Programa académico asociado al docente o grupo.'],
            ['sede', 'Texto', 'NO', 'Nombre o coincidencia de la sede (ej: Sede Principal, Sede Perdomo). Si se omite, usa la sede activa.'],
            ['tipo_reserva', 'Texto', 'NO', 'Clase, Taller, Evento, Examen, Mantenimiento. (Por defecto: Clase)'],
            ['observaciones', 'Texto', 'NO', 'Requerimientos técnicos o justificación.'],
        ]
        _aplicar_estilo_plantilla(writer, 'Reservas', 'INSTRUCCIONES DE IMPORTACIÓN DE RESERVAS DE ESPACIOS Y RECURSOS', instrucciones)

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name='Plantilla_Oficial_Reservas.xlsx',
        as_attachment=True
    )


@planillas_bp.route('/subir/reservas', methods=['POST'])
@login_required
@permiso_requerido('reservas', 'crear')
def subir_planilla_reservas():
    """Procesa la planilla de reservas de salones, espacios y recursos."""
    archivo = request.files.get('archivo_excel') or request.files.get('archivo')
    df, error = _leer_archivo_excel_o_csv(archivo, expected_sheet='Reservas')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json

    if error:
        if is_ajax: return jsonify({'success': False, 'message': error}), 400
        flash(error, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='reservas'))

    # Permitir alias comunes de columnas
    col_map = {
        'cedula': 'cedula_profesor',
        'documento': 'cedula_profesor',
        'cedula_docente': 'cedula_profesor',
        'identificacion': 'cedula_profesor',
        'profesor': 'nombre_profesor',
        'docente': 'nombre_profesor',
        'nombre_docente': 'nombre_profesor',
        'salon': 'recurso_nombre',
        'espacio': 'recurso_nombre',
        'recurso': 'recurso_nombre',
        'tipo': 'recurso_tipo',
        'dia': 'dia',
        'titulo': 'observaciones',
        'materia': 'observaciones',
        'asignatura': 'observaciones',
    }
    df.rename(columns={k: v for k, v in col_map.items() if k in df.columns and v not in df.columns}, inplace=True)

    # Si viene columna 'dia' pero no 'fecha', mapear a 'fecha'
    if 'fecha' not in df.columns and 'dia' in df.columns:
        df['fecha'] = df['dia']

    req_cols = {'cedula_profesor', 'recurso_nombre', 'fecha', 'hora_inicio', 'hora_fin'}
    faltantes = req_cols - set(df.columns)
    if faltantes:
        msg = f"Faltan columnas requeridas en la planilla: {', '.join(sorted(faltantes))}."
        if is_ajax: return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='reservas'))

    # Sede de la sesión por defecto
    user_sede_id = session.get('sede_id')
    default_sede = Sede.query.get(user_sede_id) if user_sede_id else Sede.query.first()

    insertados, actualizados, omitidos, errores = [], [], [], []

    try:
        for idx, row in df.iterrows():
            fila_num = idx + 2
            
            # 1. Cédula y profesor
            ced_raw = _normalizar_numero_str(row.get('cedula_profesor'))
            nom_prof = _normalizar_texto(row.get('nombre_profesor'))
            rec_nombre = _normalizar_texto(row.get('recurso_nombre'))
            fecha_str = _normalizar_texto(row.get('fecha'))
            h_ini_str = _normalizar_texto(row.get('hora_inicio'))
            h_fin_str = _normalizar_texto(row.get('hora_fin'))

            if not ced_raw and not rec_nombre and not fecha_str:
                continue

            # Validar cédula
            ced_valida, ced_int, err_ced = DataValidator.validate_cedula(ced_raw)
            if not ced_valida:
                errores.append({'fila': fila_num, 'id': ced_raw or 'N/A', 'razon': f"Cédula inválida: {err_ced}"})
                continue

            # Buscar o crear profesor
            profesor = Profesor.query.get(ced_int)
            if not profesor:
                if nom_prof and len(nom_prof) >= 3:
                    profesor = Profesor(
                        cedula=ced_int,
                        nombre_completo=nom_prof,
                        correo=f"prof_{ced_int}@uniminuto.edu.co",
                        programa=_normalizar_texto(row.get('programa')) or None
                    )
                    db.session.add(profesor)
                    db.session.flush()
                else:
                    errores.append({'fila': fila_num, 'id': str(ced_int), 'razon': f"Profesor con cédula {ced_int} no existe en el sistema y no se indicó nombre_profesor"})
                    continue

            nombre_docente = profesor.nombre_completo or nom_prof or f"Profesor CC {ced_int}"

            # 2. Recurso
            if not rec_nombre:
                errores.append({'fila': fila_num, 'id': str(ced_int), 'razon': "El campo 'recurso_nombre' está vacío"})
                continue

            rec_tipo = _normalizar_texto(row.get('recurso_tipo'))
            if not rec_tipo:
                rec_tipo_lower = rec_nombre.lower()
                if 'niñera' in rec_tipo_lower or 'ninera' in rec_tipo_lower:
                    rec_tipo = 'Niñera'
                elif any(k in rec_tipo_lower for k in ('auditorio', 'aula magna', 'cancha', 'laboratorio', 'sala')):
                    rec_tipo = 'Espacio'
                else:
                    rec_tipo = 'Salón'

            # 3. Sede
            sede_texto = _normalizar_texto(row.get('sede'))
            target_sede = None
            if sede_texto:
                target_sede = Sede.query.filter(Sede.nombre.ilike(f"%{sede_texto}%")).first()
            if not target_sede:
                target_sede = default_sede
            target_sede_id = target_sede.id if target_sede else None

            # Buscar Recurso en DB si existe
            recurso_obj = None
            if target_sede_id:
                recurso_obj = Recurso.query.filter(
                    Recurso.nombre.ilike(rec_nombre),
                    Recurso.activo == True
                ).join(Recurso.ubicacion).filter(Ubicacion.sede_id == target_sede_id).first()
                if not recurso_obj:
                    recurso_obj = Recurso.query.filter(Recurso.nombre.ilike(rec_nombre), Recurso.activo == True).first()
            recurso_id = recurso_obj.id if recurso_obj else None

            # 4. Fecha / Día de la semana
            f_val = None
            raw_fecha_val = row.get('fecha') or row.get('dia')
            if isinstance(raw_fecha_val, (date, datetime)):
                f_val = raw_fecha_val.date() if isinstance(raw_fecha_val, datetime) else raw_fecha_val
            else:
                fecha_str_clean = _normalizar_texto(raw_fecha_val).lower()
                dias_semana_map = {
                    'lunes': 0, 'martes': 1, 'miercoles': 2, 'miércoles': 2,
                    'jueves': 3, 'viernes': 4, 'sabado': 5, 'sábado': 5, 'domingo': 6
                }
                if fecha_str_clean in dias_semana_map:
                    hoy = date.today()
                    lunes_actual = hoy - timedelta(days=hoy.weekday())
                    f_val = lunes_actual + timedelta(days=dias_semana_map[fecha_str_clean])
                else:
                    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y'):
                        try:
                            f_val = datetime.strptime(fecha_str[:10], fmt).date()
                            break
                        except (ValueError, TypeError):
                            pass
            if not f_val:
                errores.append({'fila': fila_num, 'id': rec_nombre, 'razon': f"Fecha '{fecha_str}' inválida (use AAAA-MM-DD o día de la semana como Lunes, Martes...)"})
                continue

            # 5. Horas
            def parse_time(v):
                if isinstance(v, time):
                    return v
                if isinstance(v, datetime):
                    return v.time()
                s = _normalizar_texto(v)
                for fmt in ('%H:%M:%S', '%H:%M', '%I:%M %p', '%I:%M%p'):
                    try:
                        return datetime.strptime(s, fmt).time()
                    except (ValueError, TypeError):
                        pass
                if len(s) == 4 and s.isdigit():
                    try:
                        return datetime.strptime(s, '%H%M').time()
                    except (ValueError, TypeError):
                        pass
                return None

            h_ini_val = parse_time(row.get('hora_inicio'))
            h_fin_val = parse_time(row.get('hora_fin'))

            if not h_ini_val:
                errores.append({'fila': fila_num, 'id': rec_nombre, 'razon': f"Hora inicio '{h_ini_str}' inválida (use HH:MM)"})
                continue
            if not h_fin_val:
                errores.append({'fila': fila_num, 'id': rec_nombre, 'razon': f"Hora fin '{h_fin_str}' inválida (use HH:MM)"})
                continue
            if h_ini_val >= h_fin_val:
                errores.append({'fila': fila_num, 'id': rec_nombre, 'razon': f"La hora de inicio ({h_ini_val.strftime('%H:%M')}) debe ser menor a la hora de fin ({h_fin_val.strftime('%H:%M')})"})
                continue

            # 6. Jornada
            jornada_val = _normalizar_texto(row.get('jornada')).upper()
            if not jornada_val:
                if h_ini_val.hour < 12:
                    jornada_val = 'MAÑANA'
                elif h_ini_val.hour < 18:
                    jornada_val = 'TARDE'
                else:
                    jornada_val = 'NOCHE'

            # 7. Programa Académico
            prog_str = _normalizar_texto(row.get('programa'))
            prog_id = None
            if prog_str:
                prog_obj = ProgramaAcademico.query.filter(
                    or_(
                        ProgramaAcademico.codigo.ilike(prog_str),
                        ProgramaAcademico.nombre.ilike(f"%{prog_str}%")
                    )
                ).first()
                if prog_obj:
                    prog_id = prog_obj.id

            # 8. Verificación de conflicto de horario en el recurso
            filtro_conflicto = [
                Reserva.fecha == f_val,
                Reserva.recurso_nombre == rec_nombre,
                Reserva.estado == 'Activa',
                or_(
                    and_(Reserva.hora_inicio < h_fin_val, Reserva.hora_fin > h_ini_val)
                )
            ]
            if target_sede_id:
                filtro_conflicto.append(or_(Reserva.sede_id == target_sede_id, Reserva.sede_id.is_(None)))

            conflicto = Reserva.query.filter(*filtro_conflicto).first()
            if conflicto:
                errores.append({
                    'fila': fila_num,
                    'id': f"{rec_nombre} ({f_val})",
                    'razon': f"Conflicto de horario: {rec_nombre} ya tiene una reserva activa ({conflicto.hora_inicio.strftime('%H:%M')} - {conflicto.hora_fin.strftime('%H:%M')}) para el docente {conflicto.nombre_profesor}"
                })
                continue

            # 9. Crear la reserva
            tipo_res = _normalizar_texto(row.get('tipo_reserva')) or 'Clase'
            nrc_val = _normalizar_texto(row.get('nrc')) or None
            obs_val = _normalizar_texto(row.get('observaciones')) or None

            nueva_reserva = Reserva(
                cedula_profesor=ced_int,
                nombre_profesor=nombre_docente,
                sede_id=target_sede_id,
                nrc=nrc_val,
                recurso_id=recurso_id,
                programa_id=prog_id,
                programa=prog_str or (profesor.programa if profesor else None),
                recurso_tipo=rec_tipo,
                recurso_nombre=rec_nombre,
                fecha=f_val,
                jornada=jornada_val,
                hora_inicio=h_ini_val,
                hora_fin=h_fin_val,
                tipo_reserva=tipo_res,
                estado='Activa',
                observaciones=obs_val
            )
            db.session.add(nueva_reserva)
            insertados.append({
                'fila': fila_num,
                'id': f"{rec_nombre} [{f_val}]",
                'item': f"{nombre_docente} ({h_ini_val.strftime('%H:%M')}-{h_fin_val.strftime('%H:%M')})"
            })

        db.session.commit()

        registrar_auditoria(
            modulo='planillas',
            entidad_tipo='Reserva',
            entidad_id='MASIVO',
            accion='IMPORTAR',
            usuario_documento=session.get('usuario', ''),
            usuario_nombre=session.get('nombre_completo', ''),
            descripcion=f'Carga masiva de reservas: {len(insertados)} reservas creadas.'
        )

        resultado = {
            'success': True,
            'modulo': 'Reservas',
            'insertados': len(insertados),
            'actualizados': 0,
            'omitidos': len(omitidos),
            'errores': errores,
            'mensaje': f'Planilla de reservas procesada: {len(insertados)} reservas creadas exitosamente.'
        }
        if is_ajax: return jsonify(resultado)
        flash(resultado['mensaje'], 'success')
        return render_template('planillas.html', tab_activa='reservas', resultado=resultado)

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error procesando planilla de reservas: %s", str(e))
        if is_ajax: return jsonify({'success': False, 'message': f'Error en base de datos: {str(e)}'}), 500
        flash(f'Error al procesar la planilla: {str(e)}', 'danger')
        return redirect(url_for('planillas.planillas_dashboard', tab='reservas'))
