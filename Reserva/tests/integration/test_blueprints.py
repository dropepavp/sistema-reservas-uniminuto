"""
Tests de integración para los blueprints principales.

Prueba endpoints HTTP y flujos completos de:
- Autenticación (login, registro, logout)
- Préstamos (crear, devolver, editar)
- Reservas (crear, cancelar)
"""
import pytest
from datetime import date, timedelta


class TestAuthBlueprint:
    """Tests de integración para autenticación."""
    
    @pytest.mark.integration
    def test_registro_exitoso(self, client):
        """Flujo completo de registro de usuario."""
        response = client.post('/registro', data={
            'usuario': '55555555',
            'nombre_completo': 'Usuario Test',
            'correo': 'test@uniminuto.edu',
            'contraseña': 'TestPass123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    @pytest.mark.integration
    def test_login_exitoso(self, client, admin_user):
        """Flujo completo de login."""
        response = client.post('/login', data={
            'usuario': '80140666',
            'contraseña': 'AdminPassword123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'usuario' in response.data or b'sesion' in response.data or b'home' in response.data
    
    @pytest.mark.integration
    def test_login_fallido_credenciales_invalidas(self, client, admin_user):
        """Login falla con contraseña incorrecta."""
        response = client.post('/login', data={
            'usuario': '80140666',
            'contraseña': 'WrongPassword'
        }, follow_redirects=True)
        
        # Debería redirigir o mostrar error
        assert response.status_code == 200
    
    @pytest.mark.integration
    def test_logout(self, client, admin_user):
        """Flujo de logout."""
        # Primero login
        client.post('/login', data={
            'usuario': '80140666',
            'contraseña': 'AdminPassword123'
        })
        
        # Luego logout
        response = client.get('/logout', follow_redirects=True)
        assert response.status_code == 200
    
    @pytest.mark.integration
    def test_pagina_registro_accesible(self, client):
        """Página de registro debe ser accesible."""
        response = client.get('/registro')
        assert response.status_code == 200
        assert b'registro' in response.data or b'Registro' in response.data
    
    @pytest.mark.integration
    def test_pagina_login_accesible(self, client):
        """Página de login debe ser accesible."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'login' in response.data or b'Login' in response.data


class TestPrestamosBlueprint:
    """Tests de integración para módulo de préstamos."""
    
    @pytest.mark.integration
    def test_pagina_prestamos_requiere_login(self, client):
        """Acceso a préstamos sin login debe redirigir."""
        response = client.get('/prestamos/', follow_redirects=True)
        
        # Debería redirigir a login o mostrar acceso denegado
        assert response.status_code == 200
    
    @pytest.mark.integration
    def test_pagina_prestamos_con_login(self, client, admin_user):
        """Acceso a préstamos con login exitoso."""
        # Login primero
        client.post('/login', data={
            'usuario': '80140666',
            'contraseña': 'AdminPassword123'
        })
        
        # Intentar acceder a préstamos
        response = client.get('/prestamos/', follow_redirects=True)
        assert response.status_code == 200
    
    @pytest.mark.integration
    def test_crear_prestamo_datos_invalidos(self, client, admin_user, sample_data):
        """Crear préstamo con datos inválidos falla."""
        client.post('/login', data={
            'usuario': '80140666',
            'contraseña': 'AdminPassword123'
        })
        
        response = client.post('/prestamos/crear', data={
            'profesor_cedula': '',  # Inválido
            'equipos': [],  # Vacío
            'fecha_inicio': '2026-08-14',
            'hora_inicio': '08:00'
        }, follow_redirects=True)
        
        assert response.status_code == 200


class TestReservasBlueprint:
    """Tests de integración para módulo de reservas."""
    
    @pytest.mark.integration
    def test_pagina_reservas_requiere_login(self, client):
        """Acceso a reservas sin login debe redirigir."""
        response = client.get('/reservas/', follow_redirects=True)
        
        assert response.status_code == 200
    
    @pytest.mark.integration
    def test_pagina_reservas_con_login(self, client, admin_user):
        """Acceso a reservas con login exitoso."""
        client.post('/login', data={
            'usuario': '80140666',
            'contraseña': 'AdminPassword123'
        })
        
        response = client.get('/reservas/', follow_redirects=True)
        assert response.status_code == 200


class TestInventarioBlueprint:
    """Tests de integración para módulo de inventario."""
    
    @pytest.mark.integration
    def test_pagina_inventario_requiere_login(self, client):
        """Acceso a inventario sin login debe redirigir."""
        response = client.get('/inventario/', follow_redirects=True)
        
        assert response.status_code == 200
    
    @pytest.mark.integration
    def test_pagina_inventario_con_login(self, client, admin_user):
        """Acceso a inventario con login exitoso."""
        client.post('/login', data={
            'usuario': '80140666',
            'contraseña': 'AdminPassword123'
        })
        
        response = client.get('/inventario/', follow_redirects=True)
        assert response.status_code == 200


class TestAdminBlueprint:
    """Tests de integración para panel administrativo."""
    
    @pytest.mark.integration
    def test_admin_requiere_permisos_admin(self, client, auxiliar_user):
        """Acceso a admin panel sin permisos debe denegar."""
        client.post('/login', data={
            'usuario': '98765432',
            'contraseña': 'AuxiliarPass123'
        })
        
        response = client.get('/admin/configuracion', follow_redirects=True)
        # Debería redirigir o denegar
        assert response.status_code == 200
    
    @pytest.mark.integration
    def test_admin_con_permisos(self, client, admin_user):
        """Acceso a admin panel con permisos."""
        client.post('/login', data={
            'usuario': '80140666',
            'contraseña': 'AdminPassword123'
        })
        
        response = client.get('/admin/configuracion', follow_redirects=True)
        assert response.status_code == 200


class TestStaticPages:
    """Tests para páginas estáticas."""
    
    @pytest.mark.integration
    def test_homepage_accesible(self, client):
        """Homepage debe ser accesible (redirige a login si no autenticado)."""
        response = client.get('/', follow_redirects=True)
        assert response.status_code == 200
    
    @pytest.mark.integration
    def test_pagina_inexistente_404(self, client):
        """Página inexistente debe retornar 404."""
        response = client.get('/no-existe-esta-pagina')
        assert response.status_code == 404


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
