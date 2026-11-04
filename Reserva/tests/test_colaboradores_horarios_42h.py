"""
Suite de Pruebas Automatizadas para Horarios de Colaboradores:
- Horas en formato militar estricto (00:00 a 24:00).
- Meta y total semanal de 42 horas.
- Vigencia "A partir del 15 de julio 2026".
- Asignación y filtrado de sede heredados de la sesión de inicio de sesión.
"""
import pytest
from datetime import datetime
from database import db, Sede, Colaborador, HorarioColaborador


@pytest.fixture(scope='function')
def setup_colaboradores_42h(app):
    """Crea sedes y colaboradores de prueba para validar horarios de 42 horas."""
    with app.app_context():
        # Sedes
        sede_eng = Sede.query.filter_by(nombre="SEDE ENGATIVA 42H TEST").first()
        if not sede_eng:
            sede_eng = Sede(nombre="SEDE ENGATIVA 42H TEST")
            db.session.add(sede_eng)

        sede_per = Sede.query.filter_by(nombre="SEDE PERDOMO 42H TEST").first()
        if not sede_per:
            sede_per = Sede(nombre="SEDE PERDOMO 42H TEST")
            db.session.add(sede_per)
        db.session.commit()

        # Colaborador de prueba con 42 horas exactas
        colab = Colaborador.query.filter_by(documento="COLAB42_001").first()
        if not colab:
            colab = Colaborador(
                nombre_completo="Omar Morales Hernandez Test",
                documento="COLAB42_001",
                cargo="Auxiliar TI",
                sede_id=sede_eng.id,
                total_horas_semana=42,
                fecha_inicio_horario="A partir del 15 de julio 2026",
                horario_texto="Lunes 06:30 a 14:00, Martes a Viernes 06:30 a 13:15, Sábado 06:30 a 14:00.",
                activo=True
            )
            db.session.add(colab)
            db.session.flush()

            # Lunes: 06:30 a 14:00 (7.5h)
            db.session.add(HorarioColaborador(colaborador_id=colab.id, dia="Lunes", hora_entrada="06:30", hora_salida="14:00", horas_dia=7.5))
            # Martes a Viernes: 06:30 a 13:15 (6.75h c/u = 27h)
            for d in ["Martes", "Miércoles", "Jueves", "Viernes"]:
                db.session.add(HorarioColaborador(colaborador_id=colab.id, dia=d, hora_entrada="06:30", hora_salida="13:15", horas_dia=6.75))
            # Sábado: 06:30 a 14:00 (7.5h)
            db.session.add(HorarioColaborador(colaborador_id=colab.id, dia="Sábado", hora_entrada="06:30", hora_salida="14:00", horas_dia=7.5))

            db.session.commit()

        yield {
            'sede_eng': sede_eng,
            'sede_per': sede_per,
            'colaborador': colab
        }


def _login_session(client, sede_id=None, sede_nombre="ENGATIVA SEDE PRINCIPAL"):
    """Configura una sesión autenticada con rol superadmin y sede."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'
        sess['nombre_completo'] = 'Administrador de Pruebas'
        if sede_id:
            sess['sede_id'] = sede_id
            sess['sede_nombre'] = sede_nombre


# =========================================================================
# 1. VERIFICACIÓN DE TOTAL DE 42 HORAS Y VIGENCIA
# =========================================================================

def test_colaborador_total_42h_y_vigencia(setup_colaboradores_42h):
    """Verifica que el colaborador sume exactamente 42.0 horas y tenga vigencia 'A partir del 15 de julio 2026'."""
    colab = setup_colaboradores_42h['colaborador']
    assert colab.total_horas_semana == 42
    assert colab.fecha_inicio_horario == "A partir del 15 de julio 2026"
    assert round(colab.horas_programadas_total, 2) == 42.0


def test_formato_militar_horas(setup_colaboradores_42h):
    """Verifica que las horas de entrada y salida cumplan con el formato militar HH:MM (00:00 a 24:00)."""
    colab = setup_colaboradores_42h['colaborador']
    for h in colab.horarios:
        if h.hora_entrada:
            assert len(h.hora_entrada) == 5
            partes = h.hora_entrada.split(':')
            assert len(partes) == 2
            hora, minuto = int(partes[0]), int(partes[1])
            assert 0 <= hora <= 24
            assert 0 <= minuto <= 59
        if h.hora_salida:
            assert len(h.hora_salida) == 5
            partes = h.hora_salida.split(':')
            assert len(partes) == 2
            hora, minuto = int(partes[0]), int(partes[1])
            assert 0 <= hora <= 24
            assert 0 <= minuto <= 59


# =========================================================================
# 2. SEDE DETERMINADA DE ACUERDO AL INICIO DE SESIÓN
# =========================================================================

def test_creacion_colaborador_hereda_sede_de_sesion(client, setup_colaboradores_42h):
    """Al crear un colaborador sin especificar sede_id en el payload, se asigna automáticamente la sede de la sesión."""
    sede_eng = setup_colaboradores_42h['sede_eng']
    _login_session(client, sede_id=sede_eng.id, sede_nombre="SEDE ENGATIVA 42H TEST")

    payload = {
        'nombre_completo': 'Colaborador Sede Automatica Test',
        'documento': 'DOC_AUTO_SEDE_999',
        'cargo': 'Auxiliar Soporte',
        'total_horas_semana': 42
    }

    res = client.post('/colaboradores/api/colaboradores', json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data['success'] is True
    assert data['colaborador']['sede_id'] == sede_eng.id
    assert data['colaborador']['fecha_inicio_horario'] == "A partir del 15 de julio 2026"


def test_filtro_por_sede_de_sesion_en_api_todos_horarios(client, setup_colaboradores_42h):
    """La API /colaboradores/api/horarios-todos debe filtrar por la sede activa de la sesión."""
    sede_eng = setup_colaboradores_42h['sede_eng']
    sede_per = setup_colaboradores_42h['sede_per']

    # Crear colaborador en sede Perdomo
    with client.application.app_context():
        colab_per = Colaborador.query.filter_by(documento="COLAB_PER_999").first()
        if not colab_per:
            colab_per = Colaborador(
                nombre_completo="Colaborador Perdomo Only",
                documento="COLAB_PER_999",
                cargo="Auxiliar Perdomo",
                sede_id=sede_per.id,
                total_horas_semana=42,
                activo=True
            )
            db.session.add(colab_per)
            db.session.commit()

    # Iniciar sesión en Sede Engativá
    _login_session(client, sede_id=sede_eng.id, sede_nombre="SEDE ENGATIVA 42H TEST")
    res = client.get('/colaboradores/api/horarios-todos')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True

    nombres = [c['nombre_completo'] for c in data['colaboradores']]
    # Debe estar Omar Morales (Engativá), pero NO el de Perdomo
    assert "Omar Morales Hernandez Test" in nombres
    assert "Colaborador Perdomo Only" not in nombres


# =========================================================================
# 3. ACTUALIZACIÓN DE HORARIOS CON CÁLCULO MILITAR EN BACKEND
# =========================================================================

def test_api_guardar_horarios_calcula_horas_militares(client, setup_colaboradores_42h):
    """Valida que /colaboradores/api/colaboradores/<cid>/horarios calcule automáticamente horas a partir de HH:MM."""
    colab = setup_colaboradores_42h['colaborador']
    _login_session(client, sede_id=setup_colaboradores_42h['sede_eng'].id)

    # Enviar nuevo horario militar: Lunes a Viernes 07:00 a 14:15 (7.25h * 4 + 7h = 36h) + Sabado 07:00 a 13:00 (6h) = 42h
    payload = {
        'total_horas_semana': 42,
        'fecha_inicio_horario': 'A partir del 15 de julio 2026',
        'horario_texto': 'Lunes 7:00 am a 2:00 pm, Martes a viernes 7:00 am a 2:15 pm, Sábado 7:00 am a 1:00 pm.',
        'horarios': [
            {'dia': 'Lunes', 'hora_entrada': '07:00', 'hora_salida': '14:00', 'horas_dia': 7.0},
            {'dia': 'Martes', 'hora_entrada': '07:00', 'hora_salida': '14:15', 'horas_dia': 7.25},
            {'dia': 'Miércoles', 'hora_entrada': '07:00', 'hora_salida': '14:15', 'horas_dia': 7.25},
            {'dia': 'Jueves', 'hora_entrada': '07:00', 'hora_salida': '14:15', 'horas_dia': 7.25},
            {'dia': 'Viernes', 'hora_entrada': '07:00', 'hora_salida': '14:15', 'horas_dia': 7.25},
            {'dia': 'Sábado', 'hora_entrada': '07:00', 'hora_salida': '13:00', 'horas_dia': 6.0},
        ]
    }

    res = client.put(f'/colaboradores/api/colaboradores/{colab.id}/horarios', json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['total_horas_calculado'] == 42.0

    # Verificar en base de datos
    with client.application.app_context():
        c_db = db.session.get(Colaborador, colab.id)
        assert round(c_db.horas_programadas_total, 2) == 42.0
        assert c_db.horario_texto == payload['horario_texto']


def test_api_guardar_horarios_rechaza_salida_anterior(client, setup_colaboradores_42h):
    """Valida que no se permita hora_salida <= hora_entrada en hora militar."""
    colab = setup_colaboradores_42h['colaborador']
    _login_session(client, sede_id=setup_colaboradores_42h['sede_eng'].id)

    payload = {
        'horarios': [
            {'dia': 'Lunes', 'hora_entrada': '14:00', 'hora_salida': '06:30'}  # Inválido: salida antes de entrada
        ]
    }

    res = client.put(f'/colaboradores/api/colaboradores/{colab.id}/horarios', json=payload)
    assert res.status_code == 400
    data = res.get_json()
    assert data['success'] is False
    assert 'debe ser posterior' in data['message']


# =========================================================================
# 4. RENDERIZADO EN DASHBOARD UNIFICADO /usuarios
# =========================================================================

def test_usuarios_dashboard_muestra_vigencia_y_horas(client, setup_colaboradores_42h):
    """El dashboard /usuarios debe desplegar la vigencia 'A partir del 15 de julio 2026', el total 42h y la matriz."""
    sede_eng = setup_colaboradores_42h['sede_eng']
    _login_session(client, sede_id=sede_eng.id, sede_nombre="SEDE ENGATIVA 42H TEST")

    res = client.get('/usuarios/?tab=colaboradores', follow_redirects=True)
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Verificaciones de interfaz
    assert 'A partir del 15 de julio 2026' in html
    assert '42h' in html
    assert 'modalMatrizHorarios' in html
    assert 'Matriz Semanal' in html
    assert '00:00 a 24:00' in html


# =========================================================================
# 5. DOCUMENTO (CÉDULA) SE CARGA Y GUARDA CORRECTAMENTE
# =========================================================================

def test_api_editar_actualiza_documento(client, setup_colaboradores_42h):
    """Valida que al editar un colaborador por PUT su documento se guarde y se valide duplicidad."""
    colab = setup_colaboradores_42h['colaborador']
    _login_session(client, sede_id=setup_colaboradores_42h['sede_eng'].id)

    nuevo_doc = "1098765432"
    payload = {
        'nombre_completo': colab.nombre_completo,
        'documento': nuevo_doc,
        'cargo': 'Coordinador Auxiliares',
        'sede_id': setup_colaboradores_42h['sede_eng'].id,
        'total_horas_semana': 42
    }

    res = client.put(f'/colaboradores/api/colaboradores/{colab.id}', json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['colaborador']['documento'] == nuevo_doc

    # Verificar persistencia en base de datos
    with client.application.app_context():
        c_db = db.session.get(Colaborador, colab.id)
        assert c_db.documento == nuevo_doc


def test_api_guardar_horarios_actualiza_documento(client, setup_colaboradores_42h):
    """Valida que la actualización de horarios también guarde el documento del colaborador."""
    colab = setup_colaboradores_42h['colaborador']
    _login_session(client, sede_id=setup_colaboradores_42h['sede_eng'].id)

    doc_horario = "52431987"
    payload = {
        'documento': doc_horario,
        'total_horas_semana': 42,
        'horarios': [
            {'dia': 'Lunes', 'hora_entrada': '06:30', 'hora_salida': '14:00', 'horas_dia': 7.5}
        ]
    }

    res = client.put(f'/colaboradores/api/colaboradores/{colab.id}/horarios', json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True

    with client.application.app_context():
        c_db = db.session.get(Colaborador, colab.id)
        assert c_db.documento == doc_horario


# =========================================================================
# 6. DOMINGO EXCLUIDO POR DÍA DE DESCANSO
# =========================================================================

def test_domingo_no_aparece_en_horarios(client, setup_colaboradores_42h):
    """Valida que domingo no aparezca en horarios de colaboradores ni en la matriz."""
    _login_session(client, sede_id=setup_colaboradores_42h['sede_eng'].id)

    res = client.get('/colaboradores/api/horarios-todos')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True

    for c in data['colaboradores']:
        dias_colab = [h['dia'] for h in c.get('horarios', [])]
        assert 'Domingo' not in dias_colab
        assert 'domingo' not in dias_colab
