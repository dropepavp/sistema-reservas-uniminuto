"""
Pruebas unitarias para los validadores del sistema en validators.py.

Cobertura de pruebas:
- validate_cedula: casos válidos, inválidos, límites
- validate_email: formato, longitud
- validate_password: longitud, complejidad
- validate_string_field: límites, caracteres especiales
"""
import pytest
from validators import DataValidator, BusinessValidator, ValidationError


# ── Tests para validate_cedula ─────────────────────────────────────────────

@pytest.mark.unit
def test_validate_cedula_valida_numerica():
    """Cédula numérica válida."""
    is_valid, value, err = DataValidator.validate_cedula("12345678")
    assert is_valid is True
    assert value == 12345678
    assert err == ""


@pytest.mark.unit
def test_validate_cedula_valida_alfanumerica():
    """Cédula alfanumérica válida (email)."""
    is_valid, value, err = DataValidator.validate_cedula("admin@uniminuto.edu")
    assert is_valid is True
    assert value == "admin@uniminuto.edu"
    assert err == ""


@pytest.mark.unit
def test_validate_cedula_invalida_vacia():
    """Cédula vacía debe fallar."""
    is_valid, value, err = DataValidator.validate_cedula("")
    assert is_valid is False
    assert value is None
    assert "requerido" in err


@pytest.mark.unit
def test_validate_cedula_none():
    """Cédula None debe fallar."""
    is_valid, value, err = DataValidator.validate_cedula(None)
    assert is_valid is False
    assert value is None


@pytest.mark.unit
def test_validate_cedula_muy_corta():
    """Cédula muy corta (< 3 caracteres)."""
    is_valid, value, err = DataValidator.validate_cedula("12")
    assert is_valid is False
    assert "3 y 254" in err


@pytest.mark.unit
def test_validate_cedula_muy_larga():
    """Cédula muy larga (> 254 caracteres)."""
    cedula_larga = "a" * 255
    is_valid, value, err = DataValidator.validate_cedula(cedula_larga)
    assert is_valid is False
    assert "3 y 254" in err


@pytest.mark.unit
def test_validate_cedula_numero_negativo():
    """Número negativo debe fallar."""
    is_valid, value, err = DataValidator.validate_cedula("-12345")
    assert is_valid is False


@pytest.mark.unit
def test_validate_cedula_caracteres_invalidos():
    """Caracteres no permitidos deben fallar."""
    is_valid, value, err = DataValidator.validate_cedula("usuario#123!")
    assert is_valid is False
    assert "letras, números y @ . _ -" in err


@pytest.mark.unit
def test_validate_cedula_limites_validos():
    """Mínimo (3 chars) y máximo (254 chars) válidos."""
    # Mínimo válido
    is_valid, _, _ = DataValidator.validate_cedula("abc")
    assert is_valid is True
    
    # Máximo válido
    cedula_254 = "a" * 254
    is_valid, _, _ = DataValidator.validate_cedula(cedula_254)
    assert is_valid is True


# ── Tests para validate_email ──────────────────────────────────────────────

@pytest.mark.unit
def test_validate_email_valido():
    """Email con formato válido."""
    is_valid, err = DataValidator.validate_email("usuario@uniminuto.edu")
    assert is_valid is True
    assert err == ""


@pytest.mark.unit
def test_validate_email_vacio():
    """Email vacío debe fallar."""
    is_valid, err = DataValidator.validate_email("")
    assert is_valid is False
    assert "requerido" in err


@pytest.mark.unit
def test_validate_email_sin_arroba():
    """Email sin @ debe fallar."""
    is_valid, err = DataValidator.validate_email("usuariouniminuto.edu")
    assert is_valid is False
    assert "inválido" in err.lower() or "formato" in err.lower()


@pytest.mark.unit
def test_validate_email_sin_dominio():
    """Email sin dominio debe fallar."""
    is_valid, err = DataValidator.validate_email("usuario@")
    assert is_valid is False


@pytest.mark.unit
def test_validate_email_sin_extension():
    """Email sin extensión debe fallar."""
    is_valid, err = DataValidator.validate_email("usuario@dominio")
    assert is_valid is False


@pytest.mark.unit
def test_validate_email_demasiado_largo():
    """Email mayor a 254 caracteres debe fallar."""
    email_largo = "a" * 250 + "@example.com"
    is_valid, err = DataValidator.validate_email(email_largo)
    assert is_valid is False
    assert "demasiado largo" in err


@pytest.mark.unit
def test_validate_email_multiples_puntos():
    """Email con múltiples puntos válido."""
    is_valid, err = DataValidator.validate_email("usuario.nombre@sub.dominio.edu")
    assert is_valid is True


@pytest.mark.unit
def test_validate_email_plus_addressing():
    """Email con + (plus addressing) válido."""
    is_valid, err = DataValidator.validate_email("usuario+tag@example.com")
    assert is_valid is True


@pytest.mark.unit
def test_validate_email_guion_dominio():
    """Email con guión en dominio válido."""
    is_valid, err = DataValidator.validate_email("usuario@my-domain.com")
    assert is_valid is True


# ── Tests para validate_password ───────────────────────────────────────────

@pytest.mark.unit
def test_validate_password_valida():
    """Contraseña válida con 8+ caracteres."""
    is_valid, err = DataValidator.validate_password("MiPassword123")
    assert is_valid is True
    assert err == ""


@pytest.mark.unit
def test_validate_password_vacia():
    """Contraseña vacía debe fallar."""
    is_valid, err = DataValidator.validate_password("")
    assert is_valid is False
    assert "requerida" in err


@pytest.mark.unit
def test_validate_password_muy_corta():
    """Contraseña con menos de 8 caracteres debe fallar."""
    is_valid, err = DataValidator.validate_password("Pass123")
    assert is_valid is False
    assert "8 caracteres" in err


@pytest.mark.unit
def test_validate_password_muy_larga():
    """Contraseña con más de 128 caracteres debe fallar."""
    password_larga = "a" * 129
    is_valid, err = DataValidator.validate_password(password_larga)
    assert is_valid is False
    assert "demasiado larga" in err


@pytest.mark.unit
def test_validate_password_exactamente_8_chars():
    """Contraseña con exactamente 8 caracteres válida."""
    is_valid, err = DataValidator.validate_password("Pass1234")
    assert is_valid is True


@pytest.mark.unit
def test_validate_password_128_caracteres():
    """Contraseña de exactamente 128 caracteres válida."""
    password = "a" * 127 + "1"
    is_valid, err = DataValidator.validate_password(password)
    assert is_valid is True


@pytest.mark.unit
def test_validate_password_caracteres_especiales():
    """Contraseña con caracteres especiales válida."""
    is_valid, err = DataValidator.validate_password("P@$$w0rd!123")
    assert is_valid is True


# ── Tests para validate_string_field ──────────────────────────────────────

@pytest.mark.unit
def test_validate_string_field_valido():
    """String válido dentro de límites."""
    is_valid, err = DataValidator.validate_string_field(
        "Juan Carlos", "Nombre", min_length=3, max_length=100
    )
    assert is_valid is True
    assert err == ""


@pytest.mark.unit
def test_validate_string_field_muy_corto():
    """String por debajo del mínimo."""
    is_valid, err = DataValidator.validate_string_field(
        "Jo", "Nombre", min_length=3, max_length=100
    )
    assert is_valid is False
    assert "mínimo 3" in err


@pytest.mark.unit
def test_validate_string_field_muy_largo():
    """String por encima del máximo."""
    is_valid, err = DataValidator.validate_string_field(
        "a" * 101, "Nombre", min_length=3, max_length=100
    )
    assert is_valid is False
    assert "máximo 100" in err


@pytest.mark.unit
def test_validate_string_field_vacio():
    """String vacío con requerimiento de longitud."""
    is_valid, err = DataValidator.validate_string_field(
        "", "Nombre", min_length=3, max_length=100
    )
    assert is_valid is False


@pytest.mark.unit
def test_validate_string_field_none():
    """String None debe fallar."""
    is_valid, err = DataValidator.validate_string_field(
        None, "Nombre", min_length=3, max_length=100
    )
    assert is_valid is False


# ── Tests de Integración ───────────────────────────────────────────────────

@pytest.mark.unit
def test_validar_usuario_completo_valido():
    """Validar todos los campos de un usuario válido."""
    cedula_ok, ced_val, _ = DataValidator.validate_cedula("12345678")
    email_ok, _ = DataValidator.validate_email("usuario@uniminuto.edu")
    pwd_ok, _ = DataValidator.validate_password("MiPassword123")
    nombre_ok, _ = DataValidator.validate_string_field(
        "Usuario Nombre", "Nombre", min_length=3, max_length=100
    )
    
    assert all([cedula_ok, email_ok, pwd_ok, nombre_ok])


@pytest.mark.unit
def test_validar_usuario_incompleto_falla():
    """Validación de usuario con un campo inválido falla."""
    cedula_ok, _, _ = DataValidator.validate_cedula("")  # Falla
    email_ok, _ = DataValidator.validate_email("usuario@uniminuto.edu")
    pwd_ok, _ = DataValidator.validate_password("MiPassword123")
    
    assert not cedula_ok
    assert email_ok and pwd_ok


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
