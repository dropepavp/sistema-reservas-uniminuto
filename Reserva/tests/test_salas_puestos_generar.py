import pytest
from database import db, Recurso, PuestoComputo, Sede, Ubicacion
from config import Config

def test_config_csrf_time_limit():
    assert Config.WTF_CSRF_TIME_LIMIT is None

def test_generar_puestos_get_redirects(client):
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'admin'
        sess['nombre_completo'] = 'Administrador'
        sess['sede_id'] = 1

    res = client.get('/salas-computo/puestos/generar')
    assert res.status_code == 302
    assert 'tab=puestos' in res.headers.get('Location', '')

def test_generar_puestos_empty_recurso_id(client):
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'admin'
        sess['nombre_completo'] = 'Administrador'
        sess['sede_id'] = 1

    # Missing recurso_id
    res = client.post('/salas-computo/puestos/generar', data={
        'recurso_id': '',
        'cantidad_puestos': '20'
    })
    assert res.status_code == 302
    assert 'tab=puestos' in res.headers.get('Location', '')

def test_generar_puestos_json_empty_recurso_id(client):
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'admin'
        sess['nombre_completo'] = 'Administrador'
        sess['sede_id'] = 1

    res = client.post('/salas-computo/puestos/generar', json={
        'recurso_id': ''
    })
    assert res.status_code == 400
    json_data = res.get_json()
    assert json_data['success'] is False

def test_generar_puestos_success(app, client):
    with app.app_context():
        sede = Sede(nombre="Sede Puestos Test")
        db.session.add(sede)
        db.session.commit()
        sede_id = sede.id

        ubicacion = Ubicacion(nombre="Bloque B Piso 1", sede_id=sede_id)
        db.session.add(ubicacion)
        db.session.commit()

        sala = Recurso(nombre="Sala-Test-Generar", tipo="Salón", ubicacion_id=ubicacion.id, activo=True)
        db.session.add(sala)
        db.session.commit()
        sala_id = sala.id

    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'admin'
        sess['nombre_completo'] = 'Administrador'
        sess['sede_id'] = sede_id

    res = client.post('/salas-computo/puestos/generar', data={
        'recurso_id': str(sala_id),
        'cantidad_puestos': '15'
    })
    assert res.status_code == 302

    with app.app_context():
        puestos = PuestoComputo.query.filter_by(recurso_id=sala_id).all()
        assert len(puestos) == 15
        assert puestos[0].numero_puesto == 1
        assert puestos[14].numero_puesto == 15
