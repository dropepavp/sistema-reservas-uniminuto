"""
Pruebas Automatizadas para los Accesos Rápidos del Inicio (index.html).
Valida:
1. Carga correcta de la página principal (/) con sesión de usuario.
2. Presencia de todos los accesos rápidos a los módulos del sistema:
   - Préstamos de Equipos
   - Reservas de Recursos
   - Salas de Cómputo
   - Gestión de Inventario
   - Mantenimiento & Hojas de Vida
   - Directorio de Usuarios
   - Colaboradores (tab colaboradores)
   - Profesores (tab profesores)
   - Estudiantes (tab estudiantes)
   - Programas Académicos
   - Estadísticas y Reportes
   - Bitácora & Auditoría
   - Configuración Global (Admin)
3. Enlaces y URLs generadas correctamente sin errores de Jinja2.
"""
import pytest
from database import db, Sede, Bodega


def _login_admin(client):
    with client.session_transaction() as sess:
        sess['usuario'] = '80140666'
        sess['rol'] = 'superadmin'
        sess['nombre_completo'] = 'Administrador de Pruebas'


def test_index_accesos_rapidos_todos_presentes(client, admin_user):
    """Verifica que todos los módulos tengan su tarjeta de acceso rápido en el inicio."""
    _login_admin(client)

    res = client.get('/')
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Encabezado de accesos rápidos
    assert 'Accesos Rápidos' in html

    # Módulos operativos básicos
    assert 'Préstamos de Equipos' in html
    assert 'Reservas de Recursos' in html
    assert 'Salas de Cómputo' in html
    assert 'Gestión de Inventario' in html

    # Módulo de mantenimiento técnico
    assert 'Mantenimiento & Hojas de Vida' in html
    assert '/mantenimiento/' in html

    # Módulos de la comunidad / usuarios
    assert 'Directorio de Usuarios' in html
    assert '/usuarios' in html
    assert 'Colaboradores' in html
    assert 'tab=colaboradores' in html
    assert 'Profesores' in html
    assert 'tab=profesores' in html
    assert 'Estudiantes' in html
    assert 'tab=estudiantes' in html

    # Módulo académico
    assert 'Programas Académicos' in html
    assert '/programas/' in html

    # Módulos analíticos y de auditoría
    assert 'Estadísticas y Reportes' in html
    assert '/estadisticas/' in html
    assert 'Bitácora & Auditoría' in html
    assert '/bitacora/' in html

    # Módulo de administración
    assert 'Configuración Global' in html
    assert '/admin/sedes_y_bodegas' in html


def test_index_accesos_rapidos_usuario_restringido(client, auxiliar_user):
    """Verifica que un auxiliar solo vea accesos rápidos a los que tiene permiso y no admin."""
    with client.session_transaction() as sess:
        sess['usuario'] = '98765432'
        sess['rol'] = 'auxiliar'
        sess['nombre_completo'] = 'Auxiliar Prueba'
        sess['mod_access_cache'] = {
            'prestamos': True,
            'reservas': False,
            'inventario': False,
            'profesores': False,
            'estadisticas': False,
            'bitacora': False,
            'salas_computo': False,
            'colaboradores': False,
            'mantenimiento': False,
            'usuarios': False
        }

    res = client.get('/')
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Puede ver el módulo permitido
    assert 'Préstamos de Equipos' in html

    # NO puede ver módulos no asignados ni configuración de admin
    assert 'Configuración Global' not in html
    assert 'Bitácora & Auditoría' not in html
    assert 'Mantenimiento & Hojas de Vida' not in html
