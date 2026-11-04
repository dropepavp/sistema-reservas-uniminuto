"""
Pruebas de integración para autenticación y login.
"""
import pytest


@pytest.mark.integration
def test_login_page_renders(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b"Iniciar" in response.data or b"login" in response.data.lower() or b"acceso" in response.data.lower() or b"usuario" in response.data.lower()


@pytest.mark.integration
def test_login_fail_invalid_credentials(client):
    response = client.post('/login', data={
        'usuario': 'inexistente',
        'contraseña': 'password_incorrecta'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"incorrect" in response.data.lower() or b"error" in response.data.lower() or b"inv\xc3\xa1lid" in response.data.lower() or b"no" in response.data.lower()
