"""
Servicio de autenticación: registro y verificación de credenciales de auxiliares.
"""
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
from database import db, Auxiliar
from validators import DataValidator


def registrar_auxiliar(documento, nombre_completo, correo, contraseña, rol='auxiliar', sede_id=None):
    """Registra un nuevo auxiliar con validaciones robustas."""
    try:
        doc_valid, doc_value, doc_error = DataValidator.validate_cedula(documento)
        if not doc_valid:
            current_app.logger.warning("Intento de registro con documento inválido: %s", doc_error)
            return False, doc_error

        email_valid, email_error = DataValidator.validate_email(correo)
        if not email_valid:
            return False, email_error

        pwd_valid, pwd_error = DataValidator.validate_password(contraseña)
        if not pwd_valid:
            return False, pwd_error

        name_valid, name_error = DataValidator.validate_string_field(
            nombre_completo, "Nombre completo", min_length=3, max_length=100
        )
        if not name_valid:
            return False, name_error

        documento = str(doc_value)

        if Auxiliar.query.get(documento):
            return False, "El usuario ya existe"

        if Auxiliar.query.filter_by(correo=correo.strip().lower()).first():
            return False, "El correo ya está registrado"

        hashed_password = generate_password_hash(contraseña)

        nuevo_auxiliar = Auxiliar(
            documento=documento,
            nombre_completo=nombre_completo.strip(),
            correo=correo.strip().lower(),
            contraseña=hashed_password,
            rol=rol,
            sede_id=sede_id
        )
        db.session.add(nuevo_auxiliar)
        db.session.commit()

        current_app.logger.info("Nuevo usuario registrado: %s - %s", documento, nombre_completo)
        return True, "Usuario registrado exitosamente"

    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Error al registrar auxiliar: %s", e, exc_info=True)
        return False, "Error interno del servidor"


def verificar_credenciales(documento, contraseña):
    """Verifica las credenciales de un auxiliar."""
    try:
        doc_valid, doc_value, doc_error = DataValidator.validate_cedula(documento)
        if not doc_valid:
            current_app.logger.warning("Intento de login con documento inválido: %s", documento)
            return False

        if not contraseña:
            return False

        documento = str(doc_value)
        usuario = Auxiliar.query.get(documento)

        if not usuario:
            current_app.logger.warning("Intento de login con usuario inexistente: %s", documento)
            return False

        is_valid = check_password_hash(usuario.contraseña, contraseña)

        if is_valid:
            current_app.logger.info("Login exitoso: %s", documento)
        else:
            current_app.logger.warning("Intento de login con contraseña incorrecta: %s", documento)

        return is_valid

    except Exception as e:
        current_app.logger.error("Error al verificar credenciales: %s", e, exc_info=True)
        return False
