"""
Suite de Pruebas Automatizadas para el Sistema de Entregas de Turno y Mensajería Interna UNIMINUTO.
Valida:
1. Control de acceso y redirección a login para usuarios no autenticados.
2. Carga del Buzón Principal estilo correo interno (/entregas-turno/) y carpetas (Recibidos, Enviados, Mañana, Tarde, Pendientes).
3. Carga del formulario de redacción (/entregas-turno/redactar).
4. Redacción y emisión de entregas de turno (Jornada Mañana y Tarde) con generación de consecutivo secuencial.
5. Emisión vía POST normal y vía API JSON.
6. Lectura del detalle y actualización automática de estado leído/no leído.
7. Certificación y acuse de recibo formal por parte del operador del turno entrante (Recibido Conforme / Con Observaciones).
8. Hilo de conversación y comentarios de seguimiento en la entrega.
9. Endpoint de auto-carga inteligente de novedades del día (/entregas-turno/api/resumen-automatico).
10. Vista imprimible del Acta Oficial de Entrega de Turno (/entregas-turno/<id>/imprimir).
11. Presencia del acceso en navbar y en accesos rápidos del index.
"""
from datetime import date, time, datetime
import pytest
from database import (
    db, EntregaTurno, ComentarioEntregaTurno, Sede, Auxiliar,
    PrestamoEquipo, NovedadTecnicaSala, Recurso
)


@pytest.fixture(scope='function')
def setup_turnos(app):
    """Crea los datos base para las pruebas de entregas de turno."""
    with app.app_context():
        # Sede
        sede = Sede.query.filter_by(nombre="SEDE PRUEBA TURNOS").first()
        if not sede:
            sede = Sede(nombre="SEDE PRUEBA TURNOS")
            db.session.add(sede)
            db.session.commit()

        # Auxiliar 1 (Emisor - Mañana)
        aux_emisor = Auxiliar.query.filter_by(documento="100100100").first()
        if not aux_emisor:
            aux_emisor = Auxiliar(
                documento="100100100",
                nombre_completo="Carlos Auxiliar Mañana",
                correo="carlos.manana@uniminuto.edu",
                contraseña="hash_password_123",
                rol="auxiliar",
                activo=True
            )
            db.session.add(aux_emisor)

        # Auxiliar 2 (Receptor - Tarde)
        aux_receptor = Auxiliar.query.filter_by(documento="200200200").first()
        if not aux_receptor:
            aux_receptor = Auxiliar(
                documento="200200200",
                nombre_completo="Diana Operadora Tarde",
                correo="diana.tarde@uniminuto.edu",
                contraseña="hash_password_456",
                rol="auxiliar",
                activo=True
            )
            db.session.add(aux_receptor)

        db.session.commit()

        yield {
            'sede': sede,
            'emisor': aux_emisor,
            'receptor': aux_receptor
        }


# =========================================================================
# 1. PRUEBAS DE SEGURIDAD Y CONTROL DE ACCESO
# =========================================================================

def test_buzon_requiere_login(client):
    """Verifica que el buzón requiera sesión activa."""
    res = client.get('/entregas-turno/')
    assert res.status_code == 302
    assert '/login' in res.location


def test_redactar_requiere_login(client):
    """Verifica que la vista de redacción requiera sesión activa."""
    res = client.get('/entregas-turno/redactar')
    assert res.status_code == 302
    assert '/login' in res.location


def test_alias_turnos_redirige_a_entregas(client, admin_user):
    """Verifica que la ruta /turnos redirija al buzón /entregas-turno/."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'

    res = client.get('/turnos', follow_redirects=False)
    assert res.status_code == 302
    assert '/entregas-turno/' in res.location


# =========================================================================
# 2. PRUEBAS DEL BUZÓN (DASHBOARD) Y CARPETAS
# =========================================================================

def test_buzon_dashboard_carga_carpetas_y_kpis(client, admin_user, setup_turnos):
    """Verifica que el buzón cargue correctamente con carpetas y estadísticas."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'
        sess['sede_id'] = setup_turnos['sede'].id

    res = client.get('/entregas-turno/')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Entregas de Turno' in html
    assert 'Bandeja de Entrada' in html
    assert 'Enviados' in html
    assert 'Jornada Mañana' in html
    assert 'Jornada Tarde' in html
    assert 'Pendientes de Acuse' in html


def test_buzon_filtrado_por_carpeta(client, admin_user, setup_turnos):
    """Verifica que se pueda navegar entre carpetas (enviados, manana, tarde)."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'

    for tab in ['recibidos', 'enviados', 'manana', 'tarde', 'pendientes', 'todas']:
        res = client.get(f'/entregas-turno/?tab={tab}')
        assert res.status_code == 200


# =========================================================================
# 3. PRUEBAS DE REDACCIÓN Y EMISIÓN DE ENTREGAS
# =========================================================================

def test_redactar_vista_renderiza_campos(client, admin_user, setup_turnos):
    """Verifica que el formulario completo de redacción cargue las secciones requeridas."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'
        sess['sede_id'] = setup_turnos['sede'].id

    res = client.get('/entregas-turno/redactar')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Redactar Entrega de Turno' in html
    assert 'Jornada de la Mañana' in html
    assert 'Jornada de la Tarde' in html
    assert 'Actividades Realizadas en la Jornada' in html
    assert 'Equipos y Préstamos Pendientes por Devolver' in html
    assert 'Novedades Técnicas en Salas o Equipos' in html
    assert 'Tareas e Instrucciones para el Turno Entrante' in html
    assert 'Auto-Cargar Novedades' in html


def test_emitir_entrega_turno_manana_exitoso(client, setup_turnos):
    """Verifica la emisión de una entrega formal de turno de la mañana."""
    with client.session_transaction() as sess:
        sess['usuario'] = setup_turnos['emisor'].documento
        sess['nombre_completo'] = setup_turnos['emisor'].nombre_completo
        sess['rol'] = 'auxiliar'
        sess['sede_id'] = setup_turnos['sede'].id

    payload = {
        'jornada': 'Mañana',
        'sede_id': str(setup_turnos['sede'].id),
        'usuario_receptor_doc': setup_turnos['receptor'].documento,
        'fecha': date.today().strftime('%Y-%m-%d'),
        'hora': '14:00',
        'prioridad': 'Normal',
        'asunto': 'Entrega de Turno Mañana — Normalidad Operativa',
        'actividades_realizadas': 'Apertura de salones, verificación de salas y atención a docentes.',
        'equipos_pendientes': '2 portátiles en salón 301 con Prof. Martínez.',
        'novedades_salas': 'Sala 204 todo operativo.',
        'pendientes_siguiente_turno': 'Recibir portátiles de salón 301 a las 15:00.',
        'observaciones': 'Sin novedades graves.'
    }

    res = client.post('/entregas-turno/redactar', data=payload, follow_redirects=True)
    assert res.status_code == 200

    # Validar en base de datos
    entrega = EntregaTurno.query.filter_by(asunto='Entrega de Turno Mañana — Normalidad Operativa').first()
    assert entrega is not None
    assert entrega.jornada == 'Mañana'
    assert entrega.usuario_emisor_doc == setup_turnos['emisor'].documento
    assert entrega.usuario_receptor_doc == setup_turnos['receptor'].documento
    assert entrega.consecutivo.startswith('ET-')
    assert entrega.estado == 'Pendiente'
    assert entrega.leido is False


def test_emitir_entrega_turno_tarde_via_json(client, setup_turnos):
    """Verifica la emisión de una entrega de la jornada tarde mediante llamada JSON."""
    with client.session_transaction() as sess:
        sess['usuario'] = setup_turnos['emisor'].documento
        sess['nombre_completo'] = setup_turnos['emisor'].nombre_completo
        sess['rol'] = 'auxiliar'
        sess['sede_id'] = setup_turnos['sede'].id

    json_payload = {
        'jornada': 'Tarde',
        'sede_id': setup_turnos['sede'].id,
        'usuario_receptor_doc': '',
        'para_toda_sede': True,
        'prioridad': 'Importante',
        'asunto': 'Entrega Turno Tarde — Cierre de Sede',
        'actividades_realizadas': 'Revisión y apagado general de equipos en salas.',
        'equipos_pendientes': 'Todos devueltos a bodega.',
        'novedades_salas': 'Proyector salón 102 con aviso de lámpara.',
        'pendientes_siguiente_turno': 'Reportar lámpara a mantenimiento en la mañana.'
    }

    res = client.post('/entregas-turno/redactar', json=json_payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'consecutivo' in data

    # Validar en DB
    entrega = EntregaTurno.query.get(data['id'])
    assert entrega is not None
    assert entrega.jornada == 'Tarde'
    assert entrega.prioridad == 'Importante'
    assert entrega.para_toda_sede is True


# =========================================================================
# 4. PRUEBAS DE LECTURA, ACUSE DE RECIBO Y COMENTARIOS
# =========================================================================

def test_ver_entrega_y_marcar_leido_automatico(client, setup_turnos):
    """Verifica que al abrir una entrega el operador receptor la marque como leída."""
    # Crear entrega previa
    entrega = EntregaTurno(
        consecutivo='ET-TEST-001',
        sede_id=setup_turnos['sede'].id,
        jornada='Mañana',
        fecha=date.today(),
        hora=time(13, 50),
        usuario_emisor_doc=setup_turnos['emisor'].documento,
        usuario_receptor_doc=setup_turnos['receptor'].documento,
        asunto='Entrega para lectura',
        actividades_realizadas='Actividades de prueba',
        leido=False
    )
    db.session.add(entrega)
    db.session.commit()

    # Iniciar sesión como receptor
    with client.session_transaction() as sess:
        sess['usuario'] = setup_turnos['receptor'].documento
        sess['nombre_completo'] = setup_turnos['receptor'].nombre_completo
        sess['rol'] = 'auxiliar'

    res = client.get(f'/entregas-turno/{entrega.id}')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Entrega para lectura' in html

    # Verificar que se actualizó en base de datos
    db.session.refresh(entrega)
    assert entrega.leido is True
    assert entrega.fecha_lectura is not None


def test_confirmar_acuse_de_recibo_conforme(client, setup_turnos):
    """Verifica que el turno entrante certifique la recepción conforme del turno."""
    entrega = EntregaTurno(
        consecutivo='ET-TEST-002',
        sede_id=setup_turnos['sede'].id,
        jornada='Mañana',
        fecha=date.today(),
        hora=time(14, 0),
        usuario_emisor_doc=setup_turnos['emisor'].documento,
        usuario_receptor_doc=setup_turnos['receptor'].documento,
        asunto='Turno para acuse conforme',
        actividades_realizadas='Todas las tareas al día',
        estado='Pendiente'
    )
    db.session.add(entrega)
    db.session.commit()

    # Receptor confirma el turno
    with client.session_transaction() as sess:
        sess['usuario'] = setup_turnos['receptor'].documento
        sess['nombre_completo'] = setup_turnos['receptor'].nombre_completo
        sess['rol'] = 'auxiliar'

    res = client.post(f'/entregas-turno/{entrega.id}/acuse', data={
        'tipo_acuse': 'Recibido Conforme',
        'observaciones_acuse': 'Se verificaron todas las salas y los equipos en bodega.'
    }, follow_redirects=True)

    assert res.status_code == 200
    db.session.refresh(entrega)
    assert entrega.estado == 'Recibido Conforme'
    assert entrega.usuario_acuse_doc == setup_turnos['receptor'].documento
    assert entrega.fecha_acuse is not None
    assert 'Se verificaron todas las salas' in (entrega.observaciones_acuse or '')

    # Validar comentario automático en el hilo
    comentarios = ComentarioEntregaTurno.query.filter_by(entrega_id=entrega.id).all()
    assert len(comentarios) >= 1
    assert 'Acuse de recibo registrado' in comentarios[0].mensaje


def test_confirmar_acuse_con_observaciones(client, setup_turnos):
    """Verifica que el turno entrante pueda recibir con observaciones."""
    entrega = EntregaTurno(
        consecutivo='ET-TEST-003',
        sede_id=setup_turnos['sede'].id,
        jornada='Mañana',
        fecha=date.today(),
        hora=time(14, 0),
        usuario_emisor_doc=setup_turnos['emisor'].documento,
        usuario_receptor_doc=setup_turnos['receptor'].documento,
        asunto='Turno para acuse con novedades',
        actividades_realizadas='Jornada regular',
        estado='Pendiente'
    )
    db.session.add(entrega)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['usuario'] = setup_turnos['receptor'].documento
        sess['nombre_completo'] = setup_turnos['receptor'].nombre_completo
        sess['rol'] = 'auxiliar'

    res = client.post(f'/entregas-turno/{entrega.id}/acuse', json={
        'tipo_acuse': 'Con Observaciones',
        'observaciones_acuse': 'Falta la llave del aula 205, se contacta a emisor.'
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['estado'] == 'Con Observaciones'

    db.session.refresh(entrega)
    assert entrega.estado == 'Con Observaciones'


def test_agregar_comentario_al_hilo(client, setup_turnos):
    """Verifica que se puedan enviar respuestas y notas de seguimiento en el hilo del correo."""
    entrega = EntregaTurno(
        consecutivo='ET-TEST-004',
        sede_id=setup_turnos['sede'].id,
        jornada='Mañana',
        fecha=date.today(),
        hora=time(14, 0),
        usuario_emisor_doc=setup_turnos['emisor'].documento,
        asunto='Turno para seguimiento',
        actividades_realizadas='Labores del día'
    )
    db.session.add(entrega)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['usuario'] = setup_turnos['emisor'].documento
        sess['nombre_completo'] = setup_turnos['emisor'].nombre_completo
        sess['rol'] = 'auxiliar'

    res = client.post(f'/entregas-turno/{entrega.id}/comentario', data={
        'mensaje': 'Actualización: los portátiles pendientes ya fueron entregados por el profesor.'
    }, follow_redirects=True)
    assert res.status_code == 200

    db.session.refresh(entrega)
    assert len(entrega.comentarios) == 1
    assert 'los portátiles pendientes ya fueron entregados' in entrega.comentarios[0].mensaje


# =========================================================================
# 5. PRUEBAS DE AUTO-CARGA INTELIGENTE Y ACTA IMPRIMIBLE
# =========================================================================

def test_api_resumen_automatico(client, setup_turnos):
    """Verifica que la API retorne texto de resumen de préstamos y salas de hoy."""
    with client.session_transaction() as sess:
        sess['usuario'] = setup_turnos['emisor'].documento
        sess['rol'] = 'auxiliar'
        sess['sede_id'] = setup_turnos['sede'].id

    res = client.get(f'/entregas-turno/api/resumen-automatico?sede_id={setup_turnos["sede"].id}')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'equipos_pendientes_sugerido' in data
    assert 'novedades_salas_sugerido' in data
    assert 'total_prestamos_pendientes' in data
    assert 'total_novedades_salas' in data


def test_imprimir_acta_oficial(client, setup_turnos):
    """Verifica la generación del acta formal limpia e imprimible."""
    entrega = EntregaTurno(
        consecutivo='ET-ACTA-999',
        sede_id=setup_turnos['sede'].id,
        jornada='Mañana',
        fecha=date.today(),
        hora=time(14, 0),
        usuario_emisor_doc=setup_turnos['emisor'].documento,
        usuario_receptor_doc=setup_turnos['receptor'].documento,
        asunto='Entrega Formal para Acta',
        actividades_realizadas='Operación continua de 06:00 a 14:00',
        equipos_pendientes='Ninguno',
        novedades_salas='Ninguna',
        estado='Recibido Conforme',
        usuario_acuse_doc=setup_turnos['receptor'].documento,
        fecha_acuse=datetime.now(),
        observaciones_acuse='Recibido a satisfacción.'
    )
    db.session.add(entrega)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['usuario'] = setup_turnos['receptor'].documento
        sess['rol'] = 'auxiliar'

    res = client.get(f'/entregas-turno/{entrega.id}/imprimir')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'ACTA OFICIAL DE ENTREGA Y RECEPCIÓN DE TURNO OPERATIVO' in html
    assert 'ET-ACTA-999' in html
    assert 'Jornada Mañana' in html
    assert 'Operador Turno Saliente' in html
    assert 'Operador Turno Entrante' in html


# =========================================================================
# 6. PRUEBAS DE INTEGRACIÓN EN NAVBAR Y HOME
# =========================================================================

def test_acceso_en_navbar_e_index(client, admin_user):
    """Verifica que el enlace a Entregas de Turno esté presente en la navegación y en el index."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'

    res = client.get('/')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Entregas de Turno' in html
    assert '/entregas-turno/' in html
