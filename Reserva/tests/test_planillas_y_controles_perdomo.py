"""
Suite de Pruebas Automatizadas para:
1. Comportamiento de Controles en Sede Perdomo vs Sede Principal:
   - En Sede Perdomo la opción automática de controles no va (es manual).
   - En Sede Principal la opción automática de controles sigue activa.
2. Módulo de Planillas Excel:
   - Descarga de plantillas oficiales (.xlsx) para todos los módulos.
   - Carga masiva de inventario (con Ficha Técnica de Hoja de Vida y sede de sesión).
   - Carga masiva de profesores, colaboradores (42h), estudiantes y salas de cómputo.
"""
import io
import pytest
import pandas as pd
from database import (
    db, Sede, Bodega, Inventario, Profesor, Colaborador,
    Estudiante, ClaseSalaComputo, Auxiliar, Reserva
)


@pytest.fixture(scope='function')
def setup_sedes_y_datos(app):
    """Crea datos base para pruebas de sedes y planillas."""
    with app.app_context():
        # Sede Principal
        sede_princ = Sede.query.filter(Sede.nombre.ilike('%PRINCIPAL%')).first()
        if not sede_princ:
            sede_princ = Sede(nombre="ENGATIVA SEDE PRINCIPAL")
            db.session.add(sede_princ)
            db.session.commit()

        bodega_princ = Bodega.query.filter_by(sede_id=sede_princ.id).first()
        if not bodega_princ:
            bodega_princ = Bodega(nombre="Bodega Principal", sede_id=sede_princ.id)
            db.session.add(bodega_princ)
            db.session.commit()

        # Sede Perdomo
        sede_perdomo = Sede.query.filter(Sede.nombre.ilike('%PERDOMO%')).first()
        if not sede_perdomo:
            sede_perdomo = Sede(nombre="PERDOMO")
            db.session.add(sede_perdomo)
            db.session.commit()

        bodega_perdomo = Bodega.query.filter_by(sede_id=sede_perdomo.id).first()
        if not bodega_perdomo:
            bodega_perdomo = Bodega(nombre="BODEGA PERDOMO", sede_id=sede_perdomo.id)
            db.session.add(bodega_perdomo)
            db.session.commit()

        # Auxiliar admin de prueba
        aux = Auxiliar.query.filter_by(documento="99998888").first()
        if not aux:
            aux = Auxiliar(
                documento="99998888",
                nombre_completo="Admin Pruebas Planillas",
                correo="admin.planillas@uniminuto.edu.co",
                contraseña="dummy",
                rol="admin"
            )
            db.session.add(aux)
            db.session.commit()

        res_dict = {
            'sede_principal_id': sede_princ.id,
            'sede_principal_nombre': sede_princ.nombre,
            'bodega_principal_id': bodega_princ.id,
            'sede_perdomo_id': sede_perdomo.id,
            'sede_perdomo_nombre': sede_perdomo.nombre,
            'bodega_perdomo_id': bodega_perdomo.id,
            'auxiliar_documento': str(aux.documento),
            'auxiliar_nombre': str(aux.nombre_completo),
        }
        return res_dict


# =========================================================================
# 1. PRUEBAS: CONTROLES EN SEDE PERDOMO VS SEDE PRINCIPAL
# =========================================================================

def test_prestamos_sede_perdomo_desactiva_controles_automaticos(client, setup_sedes_y_datos):
    """Verifica que en Sede Perdomo se desactive la automatización de controles y se sugieran salones LS."""
    datos = setup_sedes_y_datos
    with client.session_transaction() as sess:
        sess['usuario'] = datos['auxiliar_documento']
        sess['nombre_completo'] = datos['auxiliar_nombre']
        sess['rol'] = 'admin'
        sess['sede_id'] = datos['sede_perdomo_id']
        sess['sede_nombre'] = datos['sede_perdomo_nombre']

    res = client.get('/prestamos/')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Debe contener el flag JavaScript de Sede Perdomo activo
    assert 'const ES_SEDE_PERDOMO = true;' in html
    assert 'const ES_SEDE_PRINCIPAL = false;' in html

    # Debe sugerir salones de Perdomo (LS1, LS2, LS3) y no torres A/B/C/D
    assert 'value="LS1"' in html
    assert 'value="LS2"' in html
    assert 'value="LS3"' in html
    assert 'Sede Perdomo: Controles manuales' in html


def test_prestamos_sede_principal_mantiene_controles_automaticos(client, setup_sedes_y_datos):
    """Verifica que en Sede Principal la sugerencia de controles automáticos siga activa."""
    datos = setup_sedes_y_datos
    with client.session_transaction() as sess:
        sess['usuario'] = datos['auxiliar_documento']
        sess['nombre_completo'] = datos['auxiliar_nombre']
        sess['rol'] = 'admin'
        sess['sede_id'] = datos['sede_principal_id']
        sess['sede_nombre'] = datos['sede_principal_nombre']

    res = client.get('/prestamos/')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Flag de Sede Principal
    assert 'const ES_SEDE_PERDOMO = false;' in html
    assert 'const ES_SEDE_PRINCIPAL = true;' in html

    # Debe sugerir torres de Principal y el badge de control sugerido
    assert 'value="A501"' in html
    assert 'badgeControlSugerido' in html
    assert 'Control sugerido:' in html


# =========================================================================
# 2. PRUEBAS: DESCARGA DE PLANTILLAS OFICIALES (.XLSX)
# =========================================================================

def test_descargar_todas_las_plantillas_oficiales(client, setup_sedes_y_datos):
    """Verifica la descarga de las 6 plantillas oficiales en formato Excel .xlsx."""
    datos = setup_sedes_y_datos
    with client.session_transaction() as sess:
        sess['usuario'] = datos['auxiliar_documento']
        sess['rol'] = 'admin'
        sess['sede_id'] = datos['sede_principal_id']

    rutas = [
        ('/planillas/plantilla/inventario', 'Plantilla_Oficial_Inventario_HojaDeVida.xlsx'),
        ('/planillas/plantilla/profesores', 'Plantilla_Oficial_Profesores.xlsx'),
        ('/planillas/plantilla/colaboradores', 'Plantilla_Oficial_Colaboradores.xlsx'),
        ('/planillas/plantilla/estudiantes', 'Plantilla_Oficial_Estudiantes.xlsx'),
        ('/planillas/plantilla/salas-computo', 'Plantilla_Oficial_Salas_Computo.xlsx'),
        ('/planillas/plantilla/usuarios', 'Plantilla_Oficial_Usuarios.xlsx'),
        ('/planillas/plantilla/reservas', 'Plantilla_Oficial_Reservas.xlsx'),
    ]

    for ruta, filename in rutas:
        res = client.get(ruta)
        assert res.status_code == 200
        assert 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in res.content_type
        assert filename in res.headers.get('Content-Disposition', '')
        # Verificar que es un Excel válido leyendo con pandas
        buf = io.BytesIO(res.data)
        xl = pd.ExcelFile(buf)
        assert len(xl.sheet_names) >= 1


# =========================================================================
# 3. PRUEBAS: SUBIDA DE PLANILLAS Y CARGA MASIVA DE DATOS
# =========================================================================

def test_subir_planilla_inventario_con_ficha_tecnica(client, setup_sedes_y_datos):
    """Verifica la carga masiva de inventario con ficha técnica y asignación de sede automática."""
    datos = setup_sedes_y_datos
    with client.session_transaction() as sess:
        sess['usuario'] = datos['auxiliar_documento']
        sess['rol'] = 'admin'
        sess['sede_id'] = datos['sede_perdomo_id']
        sess['sede_nombre'] = datos['sede_perdomo_nombre']

    # Crear buffer Excel en memoria
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df = pd.DataFrame([{
            'item': 'Portátil Lenovo ThinkPad E14',
            'categoria': 'Cómputo',
            'marca_modelo': 'Lenovo ThinkPad',
            'serial': 'PF998877',
            'activo_fijo': 'AF-778899',
            'numero_inventario': 'LEN-E14-TEST-01',
            'ubicacion_permanente': 'Laboratorio 1',
            'estado': 'Disponible',
            'es_por_cantidad': 'NO',
            'procesador': 'AMD Ryzen 7 5700U',
            'ram_gb': '16 GB',
            'almacenamiento': '1 TB SSD',
            'sistema_operativo': 'Windows 11 Pro',
            'proveedor': 'Lenovo Colombia'
        }])
        df.to_excel(writer, sheet_name='Inventario', index=False)
    buf.seek(0)

    res = client.post(
        '/planillas/subir/inventario',
        data={'archivo_excel': (buf, 'carga_inventario.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['insertados'] == 1

    # Verificar en la base de datos
    item = Inventario.query.filter_by(numero_inventario='LEN-E14-TEST-01').first()
    assert item is not None
    assert item.item == 'Portátil Lenovo ThinkPad E14'
    assert item.procesador == 'AMD Ryzen 7 5700U'
    assert item.almacenamiento == '1 TB SSD'
    # Debe pertenecer a la bodega de la sede de la sesión (Perdomo)
    assert item.bodega.sede_id == datos['sede_perdomo_id']


def test_subir_planilla_profesores(client, setup_sedes_y_datos):
    """Verifica la carga masiva de profesores."""
    datos = setup_sedes_y_datos
    with client.session_transaction() as sess:
        sess['usuario'] = datos['auxiliar_documento']
        sess['rol'] = 'admin'
        sess['sede_id'] = datos['sede_principal_id']

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df = pd.DataFrame([{
            'cedula': '80998877',
            'nombre_completo': 'Profesor Excel Prueba',
            'correo': 'profe.prueba@uniminuto.edu.co',
            'telefono': '3009998888',
            'programa': 'Comunicación Social'
        }])
        df.to_excel(writer, sheet_name='Profesores', index=False)
    buf.seek(0)

    res = client.post(
        '/planillas/subir/profesores',
        data={'archivo_excel': (buf, 'carga_profesores.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert res.status_code == 200
    assert res.get_json()['success'] is True

    profe = Profesor.query.get(80998877)
    assert profe is not None
    assert profe.nombre_completo == 'Profesor Excel Prueba'
    assert profe.programa == 'Comunicación Social'


def test_subir_planilla_colaboradores(client, setup_sedes_y_datos):
    """Verifica la carga masiva de colaboradores con horas de 42h."""
    datos = setup_sedes_y_datos
    with client.session_transaction() as sess:
        sess['usuario'] = datos['auxiliar_documento']
        sess['rol'] = 'admin'
        sess['sede_id'] = datos['sede_perdomo_id']
        sess['sede_nombre'] = datos['sede_perdomo_nombre']

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df = pd.DataFrame([{
            'documento': 'COLAB_PLANILLA_01',
            'nombre_completo': 'Auxiliar Planilla Perdomo',
            'cargo': 'Auxiliar Soporte Perdomo',
            'correo': 'aux.perdomo@uniminuto.edu.co',
            'telefono': '3119998877',
            'total_horas_semana': '42',
            'horario_resumen': 'L-V 06:30 a 15:30'
        }])
        df.to_excel(writer, sheet_name='Colaboradores', index=False)
    buf.seek(0)

    res = client.post(
        '/planillas/subir/colaboradores',
        data={'archivo_excel': (buf, 'carga_colaboradores.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert res.status_code == 200
    assert res.get_json()['success'] is True

    colab = Colaborador.query.filter_by(documento='COLAB_PLANILLA_01').first()
    assert colab is not None
    assert colab.nombre_completo == 'Auxiliar Planilla Perdomo'
    assert colab.total_horas_semana == 42
    # Hereda la sede de la sesión (Perdomo)
    assert colab.sede_id == datos['sede_perdomo_id']


def test_subir_planilla_estudiantes(client, setup_sedes_y_datos):
    """Verifica la carga masiva de estudiantes."""
    datos = setup_sedes_y_datos
    with client.session_transaction() as sess:
        sess['usuario'] = datos['auxiliar_documento']
        sess['rol'] = 'admin'
        sess['sede_id'] = datos['sede_principal_id']

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df = pd.DataFrame([{
            'codigo_banner': 'EST_PLANILLA_01',
            'nombre_completo': 'Estudiante Excel Prueba',
            'correo': 'est.prueba@uniminuto.edu.co',
            'programa': 'Ingeniería de Sistemas',
            'jornada': 'Diurna',
            'semestre': '5'
        }])
        df.to_excel(writer, sheet_name='Estudiantes', index=False)
    buf.seek(0)

    res = client.post(
        '/planillas/subir/estudiantes',
        data={'archivo_excel': (buf, 'carga_estudiantes.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert res.status_code == 200
    assert res.get_json()['success'] is True

    est = Estudiante.query.filter_by(codigo_banner='EST_PLANILLA_01').first()
    assert est is not None
    assert est.nombre_completo == 'Estudiante Excel Prueba'


def test_subir_planilla_salas_computo(client, setup_sedes_y_datos):
    """Verifica la carga masiva de programación académica de salas de cómputo."""
    datos = setup_sedes_y_datos
    with client.session_transaction() as sess:
        sess['usuario'] = datos['auxiliar_documento']
        sess['rol'] = 'admin'
        sess['sede_id'] = datos['sede_principal_id']

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df = pd.DataFrame([{
            'salon': 'LS1',
            'materia': 'Estructuras de Datos',
            'nombre_profesor': 'Ing. Carlos Pérez',
            'fecha': '2026-11-01',
            'hora_inicio': '08:00',
            'hora_fin': '10:00',
            'programa': 'Ingeniería de Sistemas',
            'estudiantes_estimados': '28',
            'software_requerido': 'VS Code, Python'
        }])
        df.to_excel(writer, sheet_name='SalasComputo', index=False)
    buf.seek(0)

    res = client.post(
        '/planillas/subir/salas-computo',
        data={'archivo_excel': (buf, 'carga_salas.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert res.status_code == 200
    assert res.get_json()['success'] is True

    clase = ClaseSalaComputo.query.filter_by(materia='Estructuras de Datos').first()
    assert clase is not None
    assert clase.salon == 'LS1'


def test_subir_planilla_usuarios(client, setup_sedes_y_datos):
    """Verifica la carga masiva de usuarios y auxiliares."""
    datos = setup_sedes_y_datos
    with client.session_transaction() as sess:
        sess['usuario'] = datos['auxiliar_documento']
        sess['rol'] = 'admin'
        sess['sede_id'] = datos['sede_principal_id']

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df = pd.DataFrame([{
            'documento': 'USER_PLANILLA_99',
            'nombre_completo': 'Auxiliar Nuevo Planilla',
            'correo': 'aux.nuevo@uniminuto.edu.co',
            'contrasena': 'ClaveSegura2026*',
            'rol': 'auxiliar'
        }])
        df.to_excel(writer, sheet_name='Usuarios', index=False)
    buf.seek(0)

    res = client.post(
        '/planillas/subir/usuarios',
        data={'archivo_excel': (buf, 'carga_usuarios.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert res.status_code == 200
    assert res.get_json()['success'] is True

    user = Auxiliar.query.get('USER_PLANILLA_99')
    assert user is not None
    assert user.nombre_completo == 'Auxiliar Nuevo Planilla'


def test_subir_planilla_reservas_exitosa(client, setup_sedes_y_datos):
    """Verifica la carga masiva exitosa de reservas de salones y recursos."""
    datos = setup_sedes_y_datos
    with client.session_transaction() as sess:
        sess['usuario'] = datos['auxiliar_documento']
        sess['rol'] = 'admin'
        sess['sede_id'] = datos['sede_principal_id']

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df = pd.DataFrame([
            {
                'cedula_profesor': '1099887766',
                'nombre_profesor': 'Profesor Carga Planilla',
                'recurso_tipo': 'Salón',
                'recurso_nombre': 'A-405',
                'fecha': '2026-11-15',
                'hora_inicio': '08:00',
                'hora_fin': '10:00',
                'jornada': 'MAÑANA',
                'nrc': '99001',
                'programa': 'Ingeniería',
                'tipo_reserva': 'Clase',
                'observaciones': 'Reserva cargada por planilla Excel'
            }
        ])
        df.to_excel(writer, sheet_name='Reservas', index=False)
    buf.seek(0)

    res = client.post(
        '/planillas/subir/reservas',
        data={'archivo_excel': (buf, 'carga_reservas.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data['success'] is True
    assert json_data['insertados'] == 1

    reserva = Reserva.query.filter_by(recurso_nombre='A-405', cedula_profesor=1099887766).first()
    assert reserva is not None
    assert reserva.nombre_profesor == 'Profesor Carga Planilla'
    assert str(reserva.fecha) == '2026-11-15'
    assert reserva.estado == 'Activa'


def test_subir_planilla_reservas_detecta_conflicto(client, setup_sedes_y_datos):
    """Verifica que el sistema detecte conflictos de horario al subir una reserva que se cruza con otra activa."""
    datos = setup_sedes_y_datos
    with client.session_transaction() as sess:
        sess['usuario'] = datos['auxiliar_documento']
        sess['rol'] = 'admin'
        sess['sede_id'] = datos['sede_principal_id']

    # Subir reserva que entra en conflicto con A-405 (08:30 a 09:30 en la misma fecha)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df = pd.DataFrame([
            {
                'cedula_profesor': '1099887766',
                'nombre_profesor': 'Profesor Carga Planilla',
                'recurso_tipo': 'Salón',
                'recurso_nombre': 'A-405',
                'fecha': '2026-11-15',
                'hora_inicio': '08:30',
                'hora_fin': '09:30',
            }
        ])
        df.to_excel(writer, sheet_name='Reservas', index=False)
    buf.seek(0)

    res = client.post(
        '/planillas/subir/reservas',
        data={'archivo_excel': (buf, 'carga_conflicto.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data['success'] is True
    assert json_data['insertados'] == 0
    assert len(json_data['errores']) == 1
    assert 'Conflicto de horario' in json_data['errores'][0]['razon']

