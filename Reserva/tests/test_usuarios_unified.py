"""
Suite de Pruebas Automatizadas para el Directorio Unificado de Usuarios (/usuarios).
Valida:
1. Control de acceso y redirección de usuarios no autenticados.
2. Renderizado del Dashboard Unificado con pestañas:
   - Colaboradores (personal operativo, horarios, cobertura).
   - Profesores (cuerpo docente, programas).
   - Estudiantes (alumnos, códigos Banner, sedes).
3. Filtros de búsqueda y sedes en cada pestaña.
4. Redirecciones retrocompatibles desde las rutas previas:
   - /colaboradores/ -> /usuarios?tab=colaboradores
   - /profesores/    -> /usuarios?tab=profesores
   - /estudiantes/   -> /usuarios?tab=estudiantes
5. Funcionamiento continuo de las APIs REST subyacentes.
"""
import pytest
from database import db, Sede, Colaborador, Profesor, Estudiante, ProgramaAcademico


@pytest.fixture(scope='function')
def setup_usuarios(app):
    """Crea registros base para Colaborador, Profesor y Estudiante."""
    with app.app_context():
        # Sede
        sede = Sede.query.filter_by(nombre="Sede Principal Usuarios").first()
        if not sede:
            sede = Sede(nombre="Sede Principal Usuarios")
            db.session.add(sede)
            db.session.commit()

        # Programa
        prog = ProgramaAcademico.query.filter_by(nombre="Ingeniería de Software").first()
        if not prog:
            prog = ProgramaAcademico(nombre="Ingeniería de Software", codigo="ISOF", activo=True)
            db.session.add(prog)
            db.session.commit()

        # Colaborador
        colab = Colaborador.query.filter_by(documento="COLAB1010").first()
        if not colab:
            colab = Colaborador(
                nombre_completo="Carlos Colaborador Test",
                documento="COLAB1010",
                cargo="Auxiliar de Soporte TI",
                correo="carlos.colab@uniminuto.edu",
                telefono="3119998877",
                sede_id=sede.id,
                total_horas_semana=42,
                activo=True
            )
            db.session.add(colab)

        # Profesor
        prof = Profesor.query.filter_by(cedula=1020304050).first()
        if not prof:
            prof = Profesor(
                cedula=1020304050,
                nombre_completo="Dra. Marcela Docente Test",
                correo="marcela.docente@uniminuto.edu",
                telefono="3125554433",
                programa="Ingeniería de Software"
            )
            db.session.add(prof)

        # Estudiante
        est = Estudiante.query.filter_by(codigo_banner="U00012345").first()
        if not est:
            est = Estudiante(
                codigo_banner="U00012345",
                documento="1098765432",
                nombre_completo="Felipe Alumno Test",
                correo="felipe.alumno@uniminuto.edu",
                telefono="3131112233",
                sede_id=sede.id,
                descripcion_sede="Sede Principal Usuarios",
                programa_id=prog.id,
                atributo_programa="Ingeniería de Software",
                activo=True
            )
            db.session.add(est)

        db.session.commit()

        yield {
            'sede': sede,
            'programa': prog,
            'colaborador': colab,
            'profesor': prof,
            'estudiante': est
        }


def _login_admin(client):
    """Inicia sesión simulada como Administrador."""
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'
        sess['nombre_completo'] = 'Administrador de Pruebas'


# =========================================================================
# 1. CONTROL DE ACCESO
# =========================================================================

def test_usuarios_requiere_autenticacion(client):
    """Verifica que /usuarios/ redirija al login si el usuario no tiene sesión."""
    res = client.get('/usuarios/')
    assert res.status_code == 302
    assert '/login' in res.location


# =========================================================================
# 2. VISTAS Y PESTAÑAS DEL DASHBOARD UNIFICADO
# =========================================================================

def test_usuarios_dashboard_default_colaboradores(client, admin_user, setup_usuarios):
    """Verifica que el dashboard cargue por defecto la pestaña de Colaboradores."""
    _login_admin(client)

    res = client.get('/usuarios/')
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Elementos principales
    assert 'Directorio & Gestión de Usuarios' in html
    assert 'Colaboradores' in html
    assert 'Profesores' in html
    assert 'Estudiantes' in html
    assert 'Carlos Colaborador Test' in html
    assert 'Auxiliar de Soporte TI' in html


def test_usuarios_pestana_profesores(client, admin_user, setup_usuarios):
    """Verifica el renderizado de la pestaña de Profesores."""
    _login_admin(client)

    res = client.get('/usuarios/?tab=profesores')
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    assert 'Dra. Marcela Docente Test' in html
    assert '1020304050' in html
    assert 'Ingeniería de Software' in html
    assert 'modalEditarProfesor' in html


def test_usuarios_pestana_estudiantes(client, admin_user, setup_usuarios):
    """Verifica el renderizado de la pestaña de Estudiantes."""
    _login_admin(client)

    res = client.get('/usuarios/?tab=estudiantes')
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    assert 'Felipe Alumno Test' in html
    assert 'U00012345' in html
    assert 'modalEditarEstudiante' in html
    assert 'modalCrearEstudiante' in html


# =========================================================================
# 3. FILTROS Y BÚSQUEDA
# =========================================================================

def test_usuarios_busqueda_colaborador(client, admin_user, setup_usuarios):
    """Valida la búsqueda por texto en la pestaña de colaboradores."""
    _login_admin(client)

    res = client.get('/usuarios/?tab=colaboradores&busqueda=Carlos')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Carlos Colaborador Test' in html

    res_vacio = client.get('/usuarios/?tab=colaboradores&busqueda=NombreInexistente999')
    assert res_vacio.status_code == 200
    html_vacio = res_vacio.get_data(as_text=True)
    assert 'Carlos Colaborador Test' not in html_vacio
    assert 'No se encontraron colaboradores' in html_vacio


def test_usuarios_busqueda_profesor(client, admin_user, setup_usuarios):
    """Valida la búsqueda por texto en la pestaña de profesores."""
    _login_admin(client)

    res = client.get('/usuarios/?tab=profesores&busqueda=Marcela')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Dra. Marcela Docente Test' in html


def test_usuarios_busqueda_estudiante(client, admin_user, setup_usuarios):
    """Valida la búsqueda por texto o código banner en la pestaña de estudiantes."""
    _login_admin(client)

    res = client.get('/usuarios/?tab=estudiantes&busqueda=U00012345')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Felipe Alumno Test' in html


# =========================================================================
# 4. REDIRECCIONES RETROCOMPATIBLES
# =========================================================================

def test_redireccion_colaboradores_hacia_usuarios(client, admin_user):
    """Verifica que /colaboradores/ redirija a /usuarios?tab=colaboradores."""
    _login_admin(client)

    res = client.get('/colaboradores/', follow_redirects=False)
    assert res.status_code == 302
    assert '/usuarios' in res.location
    assert 'tab=colaboradores' in res.location


def test_redireccion_profesores_hacia_usuarios(client, admin_user):
    """Verifica que /profesores/ redirija a /usuarios?tab=profesores."""
    _login_admin(client)

    res = client.get('/profesores/', follow_redirects=False)
    assert res.status_code == 302
    assert '/usuarios' in res.location
    assert 'tab=profesores' in res.location


def test_redireccion_estudiantes_hacia_usuarios(client, admin_user):
    """Verifica que /estudiantes/ redirija a /usuarios?tab=estudiantes."""
    _login_admin(client)

    res = client.get('/estudiantes/', follow_redirects=False)
    assert res.status_code == 302
    assert '/usuarios' in res.location
    assert 'tab=estudiantes' in res.location


# =========================================================================
# 5. INTEGRIDAD DE APIS SUBYACENTES
# =========================================================================

def test_api_colaboradores_sigue_activa(client, admin_user, setup_usuarios):
    """Verifica que la API JSON de colaboradores responda correctamente."""
    _login_admin(client)

    res = client.get('/colaboradores/api/colaboradores')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    nombres = [c['nombre_completo'] for c in data['colaboradores']]
    assert 'Carlos Colaborador Test' in nombres


def test_api_profesores_buscar_sigue_activa(client, admin_user, setup_usuarios):
    """Verifica que la API de búsqueda de profesores responda en JSON."""
    _login_admin(client)

    res = client.get('/profesores/buscar?q=Marcela')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert len(data['results']) >= 1
    assert data['results'][0]['nombre_completo'] == 'Dra. Marcela Docente Test'


def test_api_estudiantes_buscar_sigue_activa(client, admin_user, setup_usuarios):
    """Verifica que la API de autocompletado de estudiantes responda en JSON."""
    _login_admin(client)

    res = client.get('/estudiantes/api/buscar?q=Felipe')
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]['codigo_banner'] == 'U00012345'
