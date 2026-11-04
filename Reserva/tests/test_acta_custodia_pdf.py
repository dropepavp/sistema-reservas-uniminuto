"""
Pruebas automatizadas para la generación de Acta de Custodia en PDF:
- Generador ReportLab con estética institucional UNIMINUTO (NumberedCanvas, tabla apaisada, cláusula legal, firmas).
- Descarga masiva / filtrada vía /inventario/acta-custodia/pdf.
- Descarga individual vía /inventario/acta-custodia/<id>/pdf.
"""
import pytest
from database import db, Sede, InventarioCustodia
from services.acta_custodia_service import ActaCustodiaService


@pytest.fixture
def sample_custodia(app):
    """Crea un registro de prueba de InventarioCustodia."""
    with app.app_context():
        sede = Sede.query.filter_by(nombre="SEDE PERDOMO TEST").first()
        if not sede:
            sede = Sede(nombre="SEDE PERDOMO TEST")
            db.session.add(sede)
            db.session.commit()

        custodia = InventarioCustodia(
            tipo_inventario="ACTIVO_FIJO",
            placa="PLACA-TEST-999",
            serie="SERIE-XYZ-123",
            descripcion="COMPUTADOR PORTATIL HP PROBOOK",
            marca="HP",
            estado="Configurado",
            cantidad=1,
            edificio="TORRE A",
            ubicacion="AULA 204",
            centro_costo="22002915",
            nombre_centro_costo="Laboratorios de Informática",
            responsable_custodia="Ing. Andrea Gomez",
            cedula_custodio="1020304050",
            cargo_custodio="Coordinadora de Laboratorios",
            programa_area="INGENIERIA DE SISTEMAS",
            funcionario_inventario="Carlos Perez",
            fecha_inventario="2026-10-23",
            anio_llegada="2024",
            es_investigacion="No",
            observaciones="Equipo en óptimas condiciones físicas y funcionales.",
            sede_id=sede.id
        )
        db.session.add(custodia)
        db.session.commit()
        custodia_id = custodia.id

        yield custodia_id

        # Limpieza
        c = db.session.get(InventarioCustodia, custodia_id)
        if c:
            db.session.delete(c)
            db.session.commit()


def test_generar_acta_pdf_service(app, sample_custodia):
    """Verifica que el servicio genera un buffer PDF válido y no vacío."""
    with app.app_context():
        c = db.session.get(InventarioCustodia, sample_custodia)
        pdf_buffer = ActaCustodiaService.generar_acta_pdf(
            custodias=[c],
            consecutivo="ACTA-TEST-001",
            usuario_emisor="Administrador Test",
            sede_nombre="PERDOMO TEST"
        )
        data = pdf_buffer.getvalue()
        assert len(data) > 1000
        assert data.startswith(b"%PDF")


def test_ruta_descargar_acta_pdf_masiva(client, sample_custodia):
    """Verifica la ruta /inventario/acta-custodia/pdf para descarga grupal."""
    with client.session_transaction() as sess:
        sess['usuario'] = 'admin'
        sess['rol'] = 'admin'
        sess['nombre_completo'] = 'Administrador Test'
        sess['sede_id'] = None

    response = client.get('/inventario/acta-custodia/pdf')
    assert response.status_code == 200
    assert response.content_type == 'application/pdf'
    assert response.data.startswith(b"%PDF")
    assert len(response.data) > 1000


def test_ruta_descargar_acta_pdf_individual(client, sample_custodia):
    """Verifica la ruta /inventario/acta-custodia/<id>/pdf para un activo individual."""
    with client.session_transaction() as sess:
        sess['usuario'] = 'admin'
        sess['rol'] = 'admin'
        sess['nombre_completo'] = 'Administrador Test'
        sess['sede_id'] = None

    response = client.get(f'/inventario/acta-custodia/{sample_custodia}/pdf')
    assert response.status_code == 200
    assert response.content_type == 'application/pdf'
    assert response.data.startswith(b"%PDF")
    assert len(response.data) > 1000


def test_ruta_descargar_acta_pdf_filtro_vacio(client):
    """Verifica redirección y alerta si no hay registros que coincidan con los filtros."""
    with client.session_transaction() as sess:
        sess['usuario'] = 'admin'
        sess['rol'] = 'admin'
        sess['nombre_completo'] = 'Administrador Test'
        sess['sede_id'] = None

    response = client.get('/inventario/acta-custodia/pdf?busqueda=NO_EXISTE_ESTA_PLACA_9999999')
    assert response.status_code == 302
    assert 'tab=custodia' in response.headers.get('Location', '')


def test_ruta_descargar_acta_pdf_seleccion_multiple(client, sample_custodia, app):
    """Verifica la generación de acta única para múltiples bienes seleccionados por IDs agrupados por categoría."""
    with app.app_context():
        # Crear un segundo activo de categoría distinta
        c2 = InventarioCustodia(
            tipo_inventario="ACTIVO_FIJO",
            placa="PLACA-AUDIO-888",
            serie="SERIE-MIC-456",
            descripcion="CONSOLA DE AUDIO BEHRINGER 16 CANALES",
            marca="Behringer",
            estado="Configurado",
            cantidad=1,
            edificio="TORRE B",
            ubicacion="ESTUDIO DE GRABACION",
            centro_costo="22002915",
            nombre_centro_costo="Laboratorios de Informática",
            responsable_custodia="Ing. Andrea Gomez",
            cedula_custodio="1020304050",
            cargo_custodio="Coordinadora de Laboratorios",
            sede_id=db.session.get(InventarioCustodia, sample_custodia).sede_id
        )
        db.session.add(c2)
        db.session.commit()
        c2_id = c2.id

    with client.session_transaction() as sess:
        sess['usuario'] = 'admin'
        sess['rol'] = 'admin'
        sess['nombre_completo'] = 'Administrador Test'
        sess['sede_id'] = None

    response = client.get(f'/inventario/acta-custodia/pdf?ids={sample_custodia},{c2_id}&organizar_por=categoria')
    assert response.status_code == 200
    assert response.content_type == 'application/pdf'
    assert response.data.startswith(b"%PDF")
    assert len(response.data) > 1000

    # Limpieza
    with app.app_context():
        item = db.session.get(InventarioCustodia, c2_id)
        if item:
            db.session.delete(item)
            db.session.commit()
