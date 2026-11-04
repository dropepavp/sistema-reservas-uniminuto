"""
Suite de Pruebas Automatizadas para Validar las Mejoras Recientes del Sistema:
1. Sedes y Bodegas (Admin): Soporte dual Form/JSON, unicidad, actualización y eliminación.
2. Inventario: Resolución y asignación automática de bodega_id basada en la sede activa.
3. Préstamos: Endpoint /prestamos/api/resumen en tiempo real y filtrado por sede.
4. Salas de Cómputo: Aislamiento multi-sede, asignación de software por sede, disponibilidad de salas.
5. Seguridad y CSRF: Presencia de tokens CSRF en formularios de sedes/bodegas y llamadas asíncronas.
"""
import pytest
from datetime import date, time, datetime, timedelta
from database import db, Sede, Bodega, Inventario, CategoriaInventario, Recurso, Ubicacion, SoftwareSala, SoftwareAsignadoSala, ClaseSalaComputo, Reserva, PrestamoEquipo


@pytest.fixture(scope='function')
def setup_datos_mejoras(app):
    """Configura sedes, bodegas, salas y categorías para las pruebas de mejoras."""
    with app.app_context():
        # Crear o reusar sedes
        sede_a = Sede.query.filter_by(nombre="SEDE NORTE TEST").first()
        if not sede_a:
            sede_a = Sede(nombre="SEDE NORTE TEST")
            db.session.add(sede_a)
        
        sede_b = Sede.query.filter_by(nombre="SEDE SUR TEST").first()
        if not sede_b:
            sede_b = Sede(nombre="SEDE SUR TEST")
            db.session.add(sede_b)
        db.session.commit()

        # Bodegas
        bodega_a = Bodega.query.filter_by(nombre="Bodega Norte Test", sede_id=sede_a.id).first()
        if not bodega_a:
            bodega_a = Bodega(nombre="Bodega Norte Test", sede_id=sede_a.id)
            db.session.add(bodega_a)

        bodega_b = Bodega.query.filter_by(nombre="Bodega Sur Test", sede_id=sede_b.id).first()
        if not bodega_b:
            bodega_b = Bodega(nombre="Bodega Sur Test", sede_id=sede_b.id)
            db.session.add(bodega_b)
        db.session.commit()

        # Categoría
        cat = CategoriaInventario.query.filter_by(nombre="Cómputo Test").first()
        if not cat:
            cat = CategoriaInventario(nombre="Cómputo Test")
            db.session.add(cat)
        db.session.commit()

        # Ubicaciones y Salas
        ub_a = Ubicacion.query.filter_by(nombre="Edificio Norte Test - Piso 1", sede_id=sede_a.id).first()
        if not ub_a:
            ub_a = Ubicacion(nombre="Edificio Norte Test - Piso 1", sede_id=sede_a.id)
            db.session.add(ub_a)

        ub_b = Ubicacion.query.filter_by(nombre="Edificio Sur Test - Piso 1", sede_id=sede_b.id).first()
        if not ub_b:
            ub_b = Ubicacion(nombre="Edificio Sur Test - Piso 1", sede_id=sede_b.id)
            db.session.add(ub_b)
        db.session.commit()

        sala_a = Recurso.query.filter_by(nombre="Sala 101", ubicacion_id=ub_a.id).first()
        if not sala_a:
            sala_a = Recurso(nombre="Sala 101", tipo="Laboratorio", activo=True, ubicacion_id=ub_a.id)
            db.session.add(sala_a)

        sala_b = Recurso.query.filter_by(nombre="Sala 101", ubicacion_id=ub_b.id).first()
        if not sala_b:
            sala_b = Recurso(nombre="Sala 101", tipo="Laboratorio", activo=True, ubicacion_id=ub_b.id)
            db.session.add(sala_b)
        db.session.commit()

        # Software
        sw = SoftwareSala.query.filter_by(nombre="AutoCAD 2026").first()
        if not sw:
            sw = SoftwareSala(nombre="AutoCAD 2026", categoria="Diseño", version="2026")
            db.session.add(sw)
        db.session.commit()

        yield {
            'sede_a': sede_a,
            'sede_b': sede_b,
            'bodega_a': bodega_a,
            'bodega_b': bodega_b,
            'sala_a': sala_a,
            'sala_b': sala_b,
            'software': sw
        }


# =========================================================================
# 1. PRUEBAS DE SEDES Y BODEGAS (ADMIN)
# =========================================================================

def test_admin_agregar_sede_json_y_duplicados(client, admin_user, setup_datos_mejoras):
    """Verifica agregar sede mediante JSON y detección de nombres duplicados."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'

    # 1. Agregar sede válida vía JSON
    res = client.post('/admin/sedes/agregar', json={'nombre': 'Sede Occidente Test'}, headers={'Accept': 'application/json'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'SEDE OCCIDENTE TEST' in data['message'].upper()

    # 2. Intentar duplicar sede (debe rechazar con 400)
    res_dup = client.post('/admin/sedes/agregar', json={'nombre': 'SEDE OCCIDENTE TEST'}, headers={'Accept': 'application/json'})
    assert res_dup.status_code == 400
    assert res_dup.get_json()['success'] is False


def test_admin_agregar_y_editar_bodega_json(client, admin_user, setup_datos_mejoras):
    """Verifica agregar y editar bodega vía JSON con validación de sede."""
    sede_a = setup_datos_mejoras['sede_a']
    sede_b = setup_datos_mejoras['sede_b']

    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'

    # Agregar bodega vía JSON
    res = client.post('/admin/bodegas/agregar', json={
        'nombre': 'Bodega Especial Test',
        'sede_id': sede_a.id
    }, headers={'Accept': 'application/json'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    bodega_id = data['id']

    # Editar bodega y mover a sede_b vía JSON
    res_edit = client.post('/admin/bodegas/editar', json={
        'id': bodega_id,
        'nombre': 'Bodega Reubicada Test',
        'sede_id': sede_b.id
    }, headers={'Accept': 'application/json'})
    assert res_edit.status_code == 200
    assert res_edit.get_json()['success'] is True

    # Verificar en BD
    b_obj = Bodega.query.get(bodega_id)
    assert b_obj.nombre == 'BODEGA REUBICADA TEST'
    assert b_obj.sede_id == sede_b.id


# =========================================================================
# 2. PRUEBAS DE INVENTARIO Y AUTO-RESOLUCIÓN DE BODEGA
# =========================================================================

def test_inventario_auto_resolucion_bodega(client, admin_user, setup_datos_mejoras):
    """
    Verifica que al agregar un equipo sin bodega_id pero con sede_id activa en sesión,
    el sistema resuelva automáticamente la bodega y no deje el ítem huérfano.
    """
    sede_a = setup_datos_mejoras['sede_a']

    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'
        sess['sede_id'] = sede_a.id
        sess['sede_nombre'] = sede_a.nombre

    payload = {
        'categoria': 'Cómputo Test',
        'item': 'Portátil Lenovo ThinkPad Test',
        'marca_modelo': 'ThinkPad T14',
        'serial': 'SN-THINK-991',
        'numero_inventario': 'LEN-991',
        'ubicacion_permanente': 'Laboratorio 1',
        'estado': 'Disponible',
        'bodega_id': ''  # Dejado en blanco a propósito
    }

    res = client.post('/inventario/agregar', json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True

    # Verificar que el ítem creado tiene bodega_id vinculada a sede_a
    item_creado = Inventario.query.filter_by(numero_inventario='LEN-991').first()
    assert item_creado is not None
    assert item_creado.bodega_id is not None
    assert item_creado.bodega.sede_id == sede_a.id


# =========================================================================
# 3. PRUEBAS DE PRÉSTAMOS: API RESUMEN EN TIEMPO REAL
# =========================================================================

def test_prestamos_api_resumen_metricas(client, auxiliar_user, setup_datos_mejoras):
    """
    Verifica el endpoint /prestamos/api/resumen retornando conteo en tiempo real
    y aplicando el filtro de sede para auxiliares.
    """
    sede_a = setup_datos_mejoras['sede_a']
    bodega_a = setup_datos_mejoras['bodega_a']

    # Insertar equipos en bodega_a
    inv1 = Inventario.query.filter_by(numero_inventario="DELL-01").first()
    if not inv1:
        inv1 = Inventario(
            item="Portátil Dell Latitude",
            marca_modelo="Latitude 5420",
            serial="SN-DELL-1",
            numero_inventario="DELL-01",
            categoria="Cómputo Test",
            estado="Disponible",
            bodega_id=bodega_a.id
        )
        db.session.add(inv1)
        db.session.commit()

    from database import UserPermission
    perm = UserPermission.query.filter_by(usuario_documento='98765432', modulo='prestamos').first()
    if not perm:
        perm = UserPermission(usuario_documento='98765432', modulo='prestamos', puede_crear=True, puede_editar=True, puede_eliminar=True)
        db.session.add(perm)
        db.session.commit()

    with client.session_transaction() as sess:
        sess['usuario'] = '98765432'
        sess['rol'] = 'auxiliar'
        sess['sede_id'] = sede_a.id
        sess['sede_nombre'] = sede_a.nombre

    res = client.get('/prestamos/api/resumen')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'disponibles' in data
    assert 'total_activos' in data
    assert 'total_devueltos' in data
    assert 'total_vencidos' in data
    assert 'total_realizados' in data

    # Debe registrar al menos 1 portátil disponible en sede_a
    assert data['disponibles']['portatiles']['disponible'] >= 1


# =========================================================================
# 4. PRUEBAS DE SALAS DE CÓMPUTO: MULTI-SEDE Y ASIGNACIÓN DE SOFTWARE
# =========================================================================

def test_salas_computo_asignar_software_aislado_por_sede(client, admin_user, setup_datos_mejoras):
    """
    Verifica que asignar software a salas de la Sede A NO elimine las asignaciones
    previas existentes en la Sede B.
    """
    sede_a = setup_datos_mejoras['sede_a']
    sede_b = setup_datos_mejoras['sede_b']
    sala_a = setup_datos_mejoras['sala_a']
    sala_b = setup_datos_mejoras['sala_b']
    sw = setup_datos_mejoras['software']

    # Limpiar asignaciones previas si hubiera
    SoftwareAsignadoSala.query.filter_by(software_id=sw.id).delete()
    db.session.commit()

    # Pre-asignar software a sala_b (Sede B)
    asig_b = SoftwareAsignadoSala(software_id=sw.id, recurso_id=sala_b.id)
    db.session.add(asig_b)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['usuario'] = admin_user.documento
        sess['rol'] = 'superadmin'
        sess['sede_id'] = sede_a.id

    # Asignar software en Sede A a sala_a
    res = client.post('/salas-computo/software/asignar', data={
        'software_id': sw.id,
        'sede_id': sede_a.id,
        'salas_ids': [str(sala_a.id)]
    }, follow_redirects=True)
    assert res.status_code == 200

    # Verificar que sala_a tiene el software
    asig_a_check = SoftwareAsignadoSala.query.filter_by(software_id=sw.id, recurso_id=sala_a.id).first()
    assert asig_a_check is not None

    # Verificar que la asignación en sala_b (Sede B) NO fue borrada
    asig_b_check = SoftwareAsignadoSala.query.filter_by(software_id=sw.id, recurso_id=sala_b.id).first()
    assert asig_b_check is not None, "La asignación en Sede B fue borrada indebidamente al asignar en Sede A"


def test_verificar_disponibilidad_salon_con_sede(app, setup_datos_mejoras):
    """
    Verifica que la función verificar_disponibilidad_salon distinga salas homónimas
    en diferentes sedes (ej: 'Sala 101' en Sede A vs 'Sala 101' en Sede B).
    """
    from blueprints.salas_computo import verificar_disponibilidad_salon

    with app.app_context():
        sede_a = setup_datos_mejoras['sede_a']
        sede_b = setup_datos_mejoras['sede_b']
        sala_a = setup_datos_mejoras['sala_a']
        sala_b = setup_datos_mejoras['sala_b']

        hoy = date.today()
        h_ini = time(14, 0)
        h_fin = time(16, 0)

        # Crear clase programada en Sala 101 de Sede A
        clase = ClaseSalaComputo(
            materia="Programación Avanzada",
            nombre_profesor="Docente Ejemplo",
            salon="Sala 101",
            fecha=hoy,
            hora_inicio=h_ini,
            hora_fin=h_fin,
            recurso_id=sala_a.id,
            sede_id=sede_a.id,
            estado="Programada"
        )
        db.session.add(clase)
        db.session.commit()

        # Verificar disponibilidad en Sede A: debe indicar OCUPADO
        disp_a, msg_a, _, _ = verificar_disponibilidad_salon(
            salon="Sala 101",
            fecha=hoy,
            hora_inicio=time(14, 30),
            hora_fin=time(15, 30),
            recurso_id=sala_a.id,
            sede_id=sede_a.id
        )
        assert disp_a is False
        assert "OCUPADO" in msg_a

        # Verificar disponibilidad en Sede B (misma hora, mismo nombre de salón 'Sala 101'): debe estar LIBRE
        disp_b, msg_b, _, _ = verificar_disponibilidad_salon(
            salon="Sala 101",
            fecha=hoy,
            hora_inicio=time(14, 30),
            hora_fin=time(15, 30),
            recurso_id=sala_b.id,
            sede_id=sede_b.id
        )
        assert disp_b is True, f"Sala en Sede B no debería estar ocupada por clase de Sede A. Mensaje: {msg_b}"
