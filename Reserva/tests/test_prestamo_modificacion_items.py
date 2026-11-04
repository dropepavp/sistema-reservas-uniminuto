"""
Pruebas para modificación de préstamos:
- Quitar equipos por equivocación (e.g. no era un cable) y verificar que vuelven a Disponible.
- Añadir equipos adicionales a un préstamo activo ya existente.
- Cambiar números de equipo (swap) con actualización de inventario.
- Anular préstamo completo liberando todos los equipos.
"""
import pytest
from datetime import date, time
from database import db, Sede, Bodega, Inventario, Profesor, PrestamoEquipo, CategoriaInventario


@pytest.fixture
def setup_datos_prestamos(app):
    """Configura profesor, sede, bodega y equipos de inventario para las pruebas."""
    with app.app_context():
        # Sede y Bodega
        sede = Sede.query.filter_by(nombre="SEDE PRUEBAS EDITAR").first()
        if not sede:
            sede = Sede(nombre="SEDE PRUEBAS EDITAR")
            db.session.add(sede)
            db.session.commit()

        bodega = Bodega.query.filter_by(nombre="Bodega Editar Test", sede_id=sede.id).first()
        if not bodega:
            bodega = Bodega(nombre="Bodega Editar Test", sede_id=sede.id)
            db.session.add(bodega)
            db.session.commit()

        # Categoría
        cat = CategoriaInventario.query.filter_by(nombre="Equipos Edit Test").first()
        if not cat:
            cat = CategoriaInventario(nombre="Equipos Edit Test")
            db.session.add(cat)
            db.session.commit()

        # Profesor
        profesor = Profesor.query.filter_by(cedula=888999111).first()
        if not profesor:
            profesor = Profesor(
                cedula=888999111,
                nombre_completo="Profesor Pruebas Modificar",
                correo="prof.modificar@uniminuto.edu.co",
                telefono="3001234567"
            )
            db.session.add(profesor)
            db.session.commit()

        yield {
            'sede': sede,
            'bodega': bodega,
            'profesor': profesor,
            'cat': cat
        }


def test_quitar_cable_equivocado_y_liberar_inventario(client, app, setup_datos_prestamos):
    """Verifica que al quitar un equipo del préstamo por equivocación, este vuelve a Disponible en inventario."""
    with app.app_context():
        bodega = setup_datos_prestamos['bodega']
        prof = setup_datos_prestamos['profesor']

        # Crear 3 equipos en inventario
        eq1 = Inventario(numero_inventario="INV-MOD-LAP-01", item="Portátil Dell 01", categoria="Cómputo", estado="En Préstamo", bodega_id=bodega.id)
        eq2 = Inventario(numero_inventario="INV-MOD-CARG-01", item="Cargador Dell 01", categoria="Cómputo", estado="En Préstamo", bodega_id=bodega.id)
        eq3 = Inventario(numero_inventario="INV-MOD-HDMI-01", item="Cable HDMI 01", categoria="Cómputo", estado="En Préstamo", bodega_id=bodega.id)
        db.session.add_all([eq1, eq2, eq3])
        db.session.commit()

        # Crear préstamo grupal con los 3 equipos
        p1 = PrestamoEquipo(
            cedula_profesor=prof.cedula,
            nombre_profesor=prof.nombre_completo,
            equipo_prestado="Portátil Dell (01)",
            numero_inventario_equipo="INV-MOD-LAP-01",
            ubicacion="A-101",
            fecha_prestamo=date.today(),
            hora_inicio=time(8, 0),
            hora_fin=time(10, 0),
            auxiliar_entrega="Admin",
            estado="Prestado",
            sede_id=setup_datos_prestamos['sede'].id
        )
        db.session.add(p1)
        db.session.flush()

        p1.id_grupo_prestamo = p1.id_prestamo
        id_grupo = p1.id_prestamo

        p2 = PrestamoEquipo(
            id_grupo_prestamo=id_grupo,
            cedula_profesor=prof.cedula,
            nombre_profesor=prof.nombre_completo,
            equipo_prestado="Cargador Dell (01)",
            numero_inventario_equipo="INV-MOD-CARG-01",
            ubicacion="A-101",
            fecha_prestamo=date.today(),
            hora_inicio=time(8, 0),
            hora_fin=time(10, 0),
            auxiliar_entrega="Admin",
            estado="Prestado",
            sede_id=setup_datos_prestamos['sede'].id
        )
        p3 = PrestamoEquipo(
            id_grupo_prestamo=id_grupo,
            cedula_profesor=prof.cedula,
            nombre_profesor=prof.nombre_completo,
            equipo_prestado="Cable HDMI (01)",
            numero_inventario_equipo="INV-MOD-HDMI-01",
            ubicacion="A-101",
            fecha_prestamo=date.today(),
            hora_inicio=time(8, 0),
            hora_fin=time(10, 0),
            auxiliar_entrega="Admin",
            estado="Prestado",
            sede_id=setup_datos_prestamos['sede'].id
        )
        db.session.add_all([p2, p3])
        db.session.commit()

        id_p1 = p1.id_prestamo
        id_p2 = p2.id_prestamo
        id_p3_cable = p3.id_prestamo

    with client.session_transaction() as sess:
        sess['usuario'] = 'admin_test'
        sess['rol'] = 'admin'
        sess['sede_id'] = setup_datos_prestamos['sede'].id

    # 1. GET /prestamos/editar/<id_grupo> para verificar respuesta con cables/otros
    resp_get = client.get(f'/prestamos/editar/{id_grupo}')
    assert resp_get.status_code == 200
    data_get = resp_get.get_json()
    assert data_get['success'] is True
    assert len(data_get['prestamo']['lista_equipos']) == 3

    # 2. PUT /prestamos/editar/<id_grupo> eliminando el cable HDMI
    payload = {
        'ubicacion': 'A-101',
        'hora_inicio': '08:00',
        'hora_fin': '10:00',
        'observaciones': 'Se quitó el cable HDMI por equivocación',
        'items': [
            {'id_prestamo': id_p1, 'numero_inventario': 'INV-MOD-LAP-01'},
            {'id_prestamo': id_p2, 'numero_inventario': 'INV-MOD-CARG-01'}
        ],
        'items_eliminar': [id_p3_cable],
        'items_agregar': []
    }

    resp_put = client.put(
        f'/prestamos/editar/{id_grupo}',
        json=payload,
        headers={'Content-Type': 'application/json'}
    )
    assert resp_put.status_code == 200
    data_put = resp_put.get_json()
    assert data_put['success'] is True
    assert data_put['eliminados'] == 1

    # 3. Verificar en la base de datos
    with app.app_context():
        # El cable HDMI debe haber vuelto a 'Disponible'
        cable_inv = Inventario.query.filter_by(numero_inventario="INV-MOD-HDMI-01").first()
        assert cable_inv.estado == "Disponible"

        # La laptop y el cargador siguen 'En Préstamo'
        lap_inv = Inventario.query.filter_by(numero_inventario="INV-MOD-LAP-01").first()
        carg_inv = Inventario.query.filter_by(numero_inventario="INV-MOD-CARG-01").first()
        assert lap_inv.estado == "En Préstamo"
        assert carg_inv.estado == "En Préstamo"

        # El registro PrestamoEquipo del cable ya no debe existir
        p_cable_db = PrestamoEquipo.query.get(id_p3_cable)
        assert p_cable_db is None

        # El grupo ahora solo tiene 2 equipos
        grupo_restante = PrestamoEquipo.query.filter_by(id_grupo_prestamo=id_grupo).all()
        assert len(grupo_restante) == 2


def test_agregar_nuevo_equipo_a_prestamo_activo(client, app, setup_datos_prestamos):
    """Verifica que se puede añadir un nuevo equipo a un préstamo activo ya existente."""
    with app.app_context():
        bodega = setup_datos_prestamos['bodega']
        prof = setup_datos_prestamos['profesor']

        # Laptop prestada y cargador disponible
        eq_lap = Inventario(numero_inventario="INV-ADD-LAP-02", item="Laptop HP 02", categoria="Cómputo", estado="En Préstamo", bodega_id=bodega.id)
        eq_carg = Inventario(numero_inventario="INV-ADD-CARG-02", item="Cargador HP 02", categoria="Cómputo", estado="Disponible", bodega_id=bodega.id)
        db.session.add_all([eq_lap, eq_carg])
        db.session.commit()

        p1 = PrestamoEquipo(
            cedula_profesor=prof.cedula,
            nombre_profesor=prof.nombre_completo,
            equipo_prestado="Laptop HP (02)",
            numero_inventario_equipo="INV-ADD-LAP-02",
            ubicacion="Lab-2",
            fecha_prestamo=date.today(),
            hora_inicio=time(14, 0),
            hora_fin=time(16, 0),
            auxiliar_entrega="Admin",
            estado="Prestado",
            sede_id=setup_datos_prestamos['sede'].id
        )
        db.session.add(p1)
        db.session.flush()
        p1.id_grupo_prestamo = p1.id_prestamo
        id_grupo = p1.id_prestamo
        db.session.commit()

    with client.session_transaction() as sess:
        sess['usuario'] = 'admin_test'
        sess['rol'] = 'admin'
        sess['sede_id'] = setup_datos_prestamos['sede'].id

    # Añadir el cargador al préstamo existente
    payload = {
        'ubicacion': 'Lab-2',
        'hora_inicio': '14:00',
        'hora_fin': '16:00',
        'observaciones': 'Profesor solicitó adicionalmente el cargador',
        'items': [
            {'id_prestamo': id_grupo, 'numero_inventario': 'INV-ADD-LAP-02'}
        ],
        'items_eliminar': [],
        'items_agregar': [
            {'numero_inventario': 'INV-ADD-CARG-02', 'item': 'Cargador HP 02'}
        ]
    }

    resp = client.put(
        f'/prestamos/editar/{id_grupo}',
        json=payload,
        headers={'Content-Type': 'application/json'}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['agregados'] == 1

    # Verificar inventario y nuevo registro de préstamo
    with app.app_context():
        carg_inv = Inventario.query.filter_by(numero_inventario="INV-ADD-CARG-02").first()
        assert carg_inv.estado == "En Préstamo"

        # Debe existir nuevo registro en el grupo
        equipos_grupo = PrestamoEquipo.query.filter_by(id_grupo_prestamo=id_grupo).all()
        assert len(equipos_grupo) == 2
        numeros = [p.numero_inventario_equipo for p in equipos_grupo]
        assert "INV-ADD-LAP-02" in numeros
        assert "INV-ADD-CARG-02" in numeros


def test_swap_equipo_en_prestamo(client, app, setup_datos_prestamos):
    """Verifica que al cambiar un equipo por otro, el anterior se libera y el nuevo se ocupa."""
    with app.app_context():
        bodega = setup_datos_prestamos['bodega']
        prof = setup_datos_prestamos['profesor']

        eq_old = Inventario(numero_inventario="INV-SWAP-01", item="Laptop Lenovo 01", categoria="Cómputo", estado="En Préstamo", bodega_id=bodega.id)
        eq_new = Inventario(numero_inventario="INV-SWAP-02", item="Laptop Lenovo 02", categoria="Cómputo", estado="Disponible", bodega_id=bodega.id)
        db.session.add_all([eq_old, eq_new])
        db.session.commit()

        p = PrestamoEquipo(
            cedula_profesor=prof.cedula,
            nombre_profesor=prof.nombre_completo,
            equipo_prestado="Laptop Lenovo (01)",
            numero_inventario_equipo="INV-SWAP-01",
            ubicacion="B-201",
            fecha_prestamo=date.today(),
            hora_inicio=time(10, 0),
            hora_fin=time(12, 0),
            auxiliar_entrega="Admin",
            estado="Prestado",
            sede_id=setup_datos_prestamos['sede'].id
        )
        db.session.add(p)
        db.session.flush()
        p.id_grupo_prestamo = p.id_prestamo
        id_grupo = p.id_prestamo
        db.session.commit()

    with client.session_transaction() as sess:
        sess['usuario'] = 'admin_test'
        sess['rol'] = 'admin'
        sess['sede_id'] = setup_datos_prestamos['sede'].id

    # Cambiar INV-SWAP-01 por INV-SWAP-02
    payload = {
        'ubicacion': 'B-201',
        'hora_inicio': '10:00',
        'hora_fin': '12:00',
        'observaciones': 'Cambio de portátil por batería baja',
        'items': [
            {'id_prestamo': id_grupo, 'numero_inventario': 'INV-SWAP-02'}
        ],
        'items_eliminar': [],
        'items_agregar': []
    }

    resp = client.put(f'/prestamos/editar/{id_grupo}', json=payload)
    assert resp.status_code == 200

    with app.app_context():
        old_inv = Inventario.query.filter_by(numero_inventario="INV-SWAP-01").first()
        new_inv = Inventario.query.filter_by(numero_inventario="INV-SWAP-02").first()
        assert old_inv.estado == "Disponible"
        assert new_inv.estado == "En Préstamo"

        p_db = PrestamoEquipo.query.get(id_grupo)
        assert p_db.numero_inventario_equipo == "INV-SWAP-02"


def test_anular_prestamo_completo_libera_equipos(client, app, setup_datos_prestamos):
    """Verifica que anular un préstamo completo libera todos sus equipos inmediatamente a Disponible."""
    with app.app_context():
        bodega = setup_datos_prestamos['bodega']
        prof = setup_datos_prestamos['profesor']

        eq1 = Inventario(numero_inventario="INV-ANUL-01", item="Laptop 01", categoria="Cómputo", estado="En Préstamo", bodega_id=bodega.id)
        eq2 = Inventario(numero_inventario="INV-ANUL-02", item="Cargador 02", categoria="Cómputo", estado="En Préstamo", bodega_id=bodega.id)
        db.session.add_all([eq1, eq2])
        db.session.commit()

        p1 = PrestamoEquipo(
            cedula_profesor=prof.cedula,
            nombre_profesor=prof.nombre_completo,
            equipo_prestado="Laptop (01)",
            numero_inventario_equipo="INV-ANUL-01",
            ubicacion="C-301",
            fecha_prestamo=date.today(),
            hora_inicio=time(7, 0),
            hora_fin=time(9, 0),
            auxiliar_entrega="Admin",
            estado="Prestado",
            sede_id=setup_datos_prestamos['sede'].id
        )
        db.session.add(p1)
        db.session.flush()
        id_grupo = p1.id_prestamo
        p1.id_grupo_prestamo = id_grupo

        p2 = PrestamoEquipo(
            id_grupo_prestamo=id_grupo,
            cedula_profesor=prof.cedula,
            nombre_profesor=prof.nombre_completo,
            equipo_prestado="Cargador (02)",
            numero_inventario_equipo="INV-ANUL-02",
            ubicacion="C-301",
            fecha_prestamo=date.today(),
            hora_inicio=time(7, 0),
            hora_fin=time(9, 0),
            auxiliar_entrega="Admin",
            estado="Prestado",
            sede_id=setup_datos_prestamos['sede'].id
        )
        db.session.add(p2)
        db.session.commit()

    with client.session_transaction() as sess:
        sess['usuario'] = 'admin_test'
        sess['rol'] = 'admin'
        sess['sede_id'] = setup_datos_prestamos['sede'].id

    # Llamar POST /prestamos/anular/<id_grupo>
    resp = client.post(f'/prestamos/anular/{id_grupo}')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True

    with app.app_context():
        # Ambos equipos deben estar 'Disponible'
        e1 = Inventario.query.filter_by(numero_inventario="INV-ANUL-01").first()
        e2 = Inventario.query.filter_by(numero_inventario="INV-ANUL-02").first()
        assert e1.estado == "Disponible"
        assert e2.estado == "Disponible"

        # Los registros de préstamo deben haber sido eliminados
        prestamos = PrestamoEquipo.query.filter_by(id_grupo_prestamo=id_grupo).all()
        assert len(prestamos) == 0
