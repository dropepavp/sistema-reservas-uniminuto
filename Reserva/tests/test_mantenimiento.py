"""
Suite de Pruebas Automatizadas para el Módulo de Mantenimiento y Hojas de Vida.
Valida:
1. Acceso y visualización del Dashboard de Mantenimiento y KPIs.
2. Búsqueda y autocompletado en vivo de equipos (/mantenimiento/api/buscar-equipo).
3. Registro de intervenciones técnicas:
   - Actualización de equipos
   - Instalación de software y registro de versiones
   - Cambio de partes / repuestos
   - Arreglos y reparaciones correctivas/preventivas
   - Impacto en el estado del equipo (En Mantenimiento -> Disponible)
4. Hoja de Vida del equipo (/mantenimiento/hoja-de-vida/<id>):
   - Renderizado con especificaciones de hardware y trazabilidad
5. Actualización de especificaciones técnicas (procesador, RAM, disco, SO, garantía).
6. Subida y actualización de la foto oficial del equipo (con procesamiento de imagen).
7. Consulta de detalles JSON de intervenciones (/mantenimiento/api/intervencion/<id>).
8. Eliminación de intervenciones y auditoría.
9. Exportación a Excel de mantenimientos.
"""
import io
import pytest
from datetime import date, datetime
from PIL import Image

from database import db, Sede, Bodega, Inventario, CategoriaInventario, MantenimientoInventario


@pytest.fixture(scope='function')
def setup_mantenimiento(app):
    """Crea los datos base para las pruebas de mantenimiento."""
    with app.app_context():
        # Sede
        sede = Sede.query.filter_by(nombre="SEDE TEST MANTENIMIENTO").first()
        if not sede:
            sede = Sede(nombre="SEDE TEST MANTENIMIENTO")
            db.session.add(sede)
            db.session.commit()

        # Bodega
        bodega = Bodega.query.filter_by(nombre="Bodega Mant Test", sede_id=sede.id).first()
        if not bodega:
            bodega = Bodega(nombre="Bodega Mant Test", sede_id=sede.id)
            db.session.add(bodega)
            db.session.commit()

        # Categoría
        cat = CategoriaInventario.query.filter_by(nombre="Cómputo Portátil").first()
        if not cat:
            cat = CategoriaInventario(nombre="Cómputo Portátil")
            db.session.add(cat)
            db.session.commit()

        # Equipo 1: Laptop para pruebas
        equipo1 = Inventario.query.filter_by(numero_inventario="MANT-LAP-001").first()
        if not equipo1:
            equipo1 = Inventario(
                item="Portátil Dell Latitude 5420",
                marca_modelo="Dell Latitude 5420",
                serial="SN-DELL-5420-XYZ",
                activo_fijo="AF-998811",
                numero_inventario="MANT-LAP-001",
                categoria="Cómputo Portátil",
                estado="Disponible",
                bodega_id=bodega.id,
                procesador="Intel Core i5-1145G7",
                ram_gb="16 GB",
                almacenamiento="512 GB SSD NVMe",
                sistema_operativo="Windows 11 Pro",
                especificaciones_tecnicas="Pantalla 14 FHD, Teclado Retroiluminado",
                proveedor="Dell Colombia",
                garantia_vencimiento=date(2027, 5, 20)
            )
            db.session.add(equipo1)
            db.session.commit()

        # Equipo 2: Equipo de escritorio
        equipo2 = Inventario.query.filter_by(numero_inventario="MANT-PC-002").first()
        if not equipo2:
            equipo2 = Inventario(
                item="PC Escritorio Lenovo ThinkCentre",
                marca_modelo="Lenovo M70s",
                serial="SN-LENOVO-002",
                activo_fijo="AF-998822",
                numero_inventario="MANT-PC-002",
                categoria="Cómputo Portátil",
                estado="Disponible",
                bodega_id=bodega.id
            )
            db.session.add(equipo2)
            db.session.commit()

        yield {
            'sede': sede,
            'bodega': bodega,
            'equipo1': equipo1,
            'equipo2': equipo2
        }


def _crear_imagen_bytes():
    """Genera una imagen PNG pequeña en memoria para pruebas de subida."""
    img = Image.new('RGB', (100, 100), color='navy')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


# =========================================================================
# 1. PRUEBAS DE DASHBOARD Y PERMISOS
# =========================================================================

def test_dashboard_requiere_login(client):
    """Verifica que usuarios no autenticados sean redirigidos."""
    res = client.get('/mantenimiento/')
    assert res.status_code == 302
    assert '/login' in res.location


def test_dashboard_admin_carga_correctamente(client, admin_user, setup_mantenimiento):
    """Verifica que el panel principal cargue con KPIs y catálogo de hojas de vida."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'

    res = client.get('/mantenimiento/')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Mantenimiento & Hojas de Vida' in html
    assert 'Nueva Intervención' in html

    # Pestaña de Catálogo de Hojas de Vida
    res_hv = client.get('/mantenimiento/?tab=hojas_vida')
    assert res_hv.status_code == 200
    html_hv = res_hv.get_data(as_text=True)
    assert 'MANT-LAP-001' in html_hv
    assert 'Dell Latitude 5420' in html_hv


def test_api_buscar_equipo(client, admin_user, setup_mantenimiento):
    """Verifica el endpoint de autocompletado en vivo de equipos."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'

    # Búsqueda por número de inventario
    res = client.get('/mantenimiento/api/buscar-equipo?q=MANT-LAP')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert len(data['equipos']) >= 1
    assert data['equipos'][0]['numero_inventario'] == 'MANT-LAP-001'

    # Búsqueda por serial
    res_sn = client.get('/mantenimiento/api/buscar-equipo?q=SN-LENOVO')
    assert res_sn.status_code == 200
    data_sn = res_sn.get_json()
    assert len(data_sn['equipos']) >= 1
    assert data_sn['equipos'][0]['numero_inventario'] == 'MANT-PC-002'


# =========================================================================
# 2. PRUEBAS DE REGISTRO DE INTERVENCIONES
# =========================================================================

def test_registrar_instalacion_software(client, admin_user, setup_mantenimiento):
    """Registra una instalación de software sobre un equipo."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['nombre_completo'] = 'Ing. Administrador'
        sess['rol'] = 'superadmin'

    equipo = setup_mantenimiento['equipo1']

    payload = {
        'inventario_id': equipo.id,
        'tipo': 'Instalación de Software',
        'titulo': 'Instalación de Suite Adobe 2026',
        'software_instalado': 'Photoshop 2026 v27.1, Illustrator 2026 v30.0 (Licencia Campus)',
        'motivo': 'Requerimiento del docente para laboratorio de diseño digital',
        'tecnico_responsable': 'Técnico Especialista UNIMINUTO',
        'costo': '150000',
        'estado': 'Finalizado',
        'nuevo_estado_equipo': 'Disponible'
    }

    res = client.post('/mantenimiento/nuevo', data=payload, headers={'Accept': 'application/json'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True

    # Verificar en BD
    mant = MantenimientoInventario.query.get(data['id'])
    assert mant is not None
    assert mant.tipo == 'Instalación de Software'
    assert 'Photoshop 2026' in mant.software_instalado
    assert mant.costo == 150000.0
    assert mant.inventario_id == equipo.id


def test_registrar_cambio_de_partes_y_reparacion(client, admin_user, setup_mantenimiento):
    """Registra sustitución de partes / repuestos y arreglo de equipo."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['nombre_completo'] = 'Ing. Administrador'
        sess['rol'] = 'superadmin'

    equipo = setup_mantenimiento['equipo2']

    payload = {
        'inventario_id': equipo.id,
        'tipo': 'Cambio de Partes / Repuestos',
        'titulo': 'Reemplazo de disco mecánico por SSD NVMe 1TB y cambio de pasta térmica',
        'partes_cambiadas': 'SSD Kingston NV2 1TB PCIe 4.0, Fan Cooler CPU 80mm',
        'motivo': 'Lentitud crítica al encendido y sobrecalentamiento del procesador',
        'diagnostico_solucion': 'Sector de arranque con fallas. Se clona sistema operativo a SSD nuevo y se limpia disipador.',
        'trabajo_realizado': 'Desensamble completo, soplado, cambio de pasta térmica Arctic MX-4, ensamble y pruebas de estrés 2h.',
        'tecnico_responsable': 'Soporte Hardware UNIMINUTO',
        'costo': '280000',
        'estado': 'Finalizado',
        'nuevo_estado_equipo': 'Disponible'
    }

    res = client.post('/mantenimiento/nuevo', data=payload, headers={'Accept': 'application/json'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True

    mant = MantenimientoInventario.query.get(data['id'])
    assert mant is not None
    assert 'Kingston NV2 1TB' in mant.partes_cambiadas
    assert 'Arctic MX-4' in mant.trabajo_realizado


def test_registrar_actualizacion_cambia_estado_a_en_proceso(client, admin_user, setup_mantenimiento):
    """Verifica que una intervención En Proceso cambie el estado del equipo a 'En Mantenimiento'."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'

    equipo = setup_mantenimiento['equipo1']

    payload = {
        'inventario_id': equipo.id,
        'tipo': 'Actualización de Equipo',
        'titulo': 'Actualización de memoria RAM a 32GB y actualización de BIOS',
        'motivo': 'Upgrade para laboratorio de Inteligencia Artificial',
        'estado': 'En Proceso',
        'nuevo_estado_equipo': 'En Mantenimiento'
    }

    res = client.post('/mantenimiento/nuevo', data=payload, headers={'Accept': 'application/json'})
    assert res.status_code == 200

    # Refrescar equipo desde BD
    db.session.refresh(equipo)
    assert equipo.estado == 'En Mantenimiento'


# =========================================================================
# 3. PRUEBAS DE HOJA DE VIDA Y ESPECIFICACIONES TÉCNICAS
# =========================================================================

def test_ver_hoja_de_vida(client, admin_user, setup_mantenimiento):
    """Verifica que la página de la Hoja de Vida oficial cargue correctamente."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'

    equipo = setup_mantenimiento['equipo1']
    res = client.get(f'/mantenimiento/hoja-de-vida/{equipo.id}')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'HOJA DE VIDA DE EQUIPO' in html
    assert equipo.numero_inventario in html
    assert 'Intel Core i5-1145G7' in html
    assert '16 GB' in html
    assert 'Windows 11 Pro' in html


def test_actualizar_especificaciones_tecnicas(client, admin_user, setup_mantenimiento):
    """Actualiza la ficha técnica del equipo desde la Hoja de Vida."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'

    equipo = setup_mantenimiento['equipo1']

    specs_payload = {
        'procesador': 'Intel Core i7-12700H',
        'ram_gb': '32 GB DDR4 3200MHz',
        'almacenamiento': '1 TB SSD NVMe Samsung 980',
        'sistema_operativo': 'Windows 11 Enterprise 64-bit',
        'especificaciones_tecnicas': 'Pantalla 14 2K, Thunderbolt 4, Lector Huella',
        'proveedor': 'Canal Mayorista Dell',
        'fecha_adquisicion': '2024-02-15',
        'garantia_vencimiento': '2027-02-15'
    }

    res = client.post(
        f'/mantenimiento/equipo/{equipo.id}/especificaciones',
        json=specs_payload,
        headers={'Accept': 'application/json'}
    )
    assert res.status_code == 200
    assert res.get_json()['success'] is True

    # Verificar en BD
    db.session.refresh(equipo)
    assert equipo.procesador == 'Intel Core i7-12700H'
    assert equipo.ram_gb == '32 GB DDR4 3200MHz'
    assert equipo.almacenamiento == '1 TB SSD NVMe Samsung 980'
    assert equipo.sistema_operativo == 'Windows 11 Enterprise 64-bit'


def test_subir_foto_equipo(client, admin_user, setup_mantenimiento):
    """Verifica la carga y procesamiento de la foto para la Hoja de Vida del equipo."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'

    equipo = setup_mantenimiento['equipo1']
    img_stream = _crear_imagen_bytes()

    data = {
        'foto': (img_stream, 'foto_laptop.png')
    }

    res = client.post(
        f'/mantenimiento/equipo/{equipo.id}/foto',
        data=data,
        content_type='multipart/form-data',
        headers={'Accept': 'application/json'}
    )
    assert res.status_code == 200
    res_json = res.get_json()
    assert res_json['success'] is True
    assert 'foto_url' in res_json
    assert res_json['foto_url'].startswith('/static/uploads/equipos/')

    # Verificar que el equipo guardó la URL
    db.session.refresh(equipo)
    assert equipo.foto_url is not None
    assert '/static/uploads/equipos/' in equipo.foto_url


# =========================================================================
# 4. PRUEBAS DE DETALLE JSON Y ELIMINACIÓN
# =========================================================================

def test_api_detalle_intervencion(client, admin_user, setup_mantenimiento):
    """Verifica el endpoint JSON que provee los datos de una intervención para modal."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'

    equipo = setup_mantenimiento['equipo1']
    # Crear un registro directamente
    mant = MantenimientoInventario(
        inventario_id=equipo.id,
        tipo='Mantenimiento Preventivo',
        titulo='Mantenimiento Periódico Preventivo Trimestral',
        motivo='Limpieza interna y verificación de salud de disco',
        trabajo_realizado='Limpieza de cooler, aplicación de pasta térmica, escaneo SMART',
        auxiliar_responsable='Técnico Prueba',
        fecha_envio=date.today(),
        estado='Finalizado',
        costo=45000.0
    )
    db.session.add(mant)
    db.session.commit()

    res = client.get(f'/mantenimiento/api/intervencion/{mant.id}')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['intervencion']['titulo'] == 'Mantenimiento Periódico Preventivo Trimestral'
    assert data['intervencion']['costo'] == 45000.0
    assert data['intervencion']['equipo']['numero_inventario'] == equipo.numero_inventario


def test_eliminar_intervencion(client, admin_user, setup_mantenimiento):
    """Verifica la eliminación segura de un registro de mantenimiento."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'

    equipo = setup_mantenimiento['equipo1']
    mant = MantenimientoInventario(
        inventario_id=equipo.id,
        tipo='Diagnóstico',
        motivo='Prueba a eliminar',
        auxiliar_responsable='Técnico Prueba',
        fecha_envio=date.today(),
        estado='Finalizado'
    )
    db.session.add(mant)
    db.session.commit()
    mant_id = mant.id

    res = client.post(f'/mantenimiento/eliminar/{mant_id}', follow_redirects=True)
    assert res.status_code == 200

    # Debe haber sido eliminado de la BD
    assert MantenimientoInventario.query.get(mant_id) is None


# =========================================================================
# 5. PRUEBA DE EXPORTACIÓN A EXCEL
# =========================================================================

def test_exportar_excel_mantenimientos(client, admin_user, setup_mantenimiento):
    """Verifica la generación y descarga del reporte Excel."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'

    res = client.get('/mantenimiento/exportar-excel')
    assert res.status_code == 200
    assert 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in res.content_type
    assert len(res.data) > 0


# =========================================================================
# 6. VERIFICACIÓN DE BOTONES GUARDAR VISIBLES EN MODALES
# =========================================================================

def test_botones_guardar_mantenimiento_visibles(client, admin_user, setup_mantenimiento):
    """Verifica que el modal de registrar mantenimiento contenga el botón Guardar en header y footer."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'

    # 1. En Dashboard de mantenimiento
    res_dash = client.get('/mantenimiento/', follow_redirects=True)
    assert res_dash.status_code == 200
    html_dash = res_dash.get_data(as_text=True)
    assert 'btnGuardarMantenimientoTop' in html_dash
    assert 'btnGuardarMantenimiento' in html_dash
    assert 'Guardar Mantenimiento' in html_dash
    assert 'formNuevoMantenimiento' in html_dash

    # 2. En Hoja de Vida
    equipo = setup_mantenimiento['equipo1']
    res_hv = client.get(f'/mantenimiento/hoja-de-vida/{equipo.id}', follow_redirects=True)
    assert res_hv.status_code == 200
    html_hv = res_hv.get_data(as_text=True)
    assert 'modalNuevoMantenimiento' in html_hv
    assert 'Guardar Mantenimiento' in html_hv
