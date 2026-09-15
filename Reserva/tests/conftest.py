"""
Fixturas globales de Pytest para el proyecto Sistema Integrado UNIMINUTO.

Fixtures disponibles:
- app: Instancia de Flask en modo testing
- client: Cliente HTTP para pruebas
- app_context: Context manager de aplicación
- session: Sesión de base de datos
- sample_data: Datos de prueba precargados
- admin_user: Usuario administrador para testing
- auxiliar_user: Usuario auxiliar para testing
"""
import os
import sys
import pytest
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database import db, Auxiliar, Sede, Bodega, Inventario, CategoriaInventario, Profesor
from werkzeug.security import generate_password_hash


@pytest.fixture(scope='session')
def app():
    """Crea y configura una instancia de la aplicación Flask en modo testing."""
    os.environ['FLASK_CONFIG'] = 'testing'
    os.environ['FLASK_SECRET_KEY'] = 'testing-secret-key-12345'
    
    _app = create_app('testing')
    _app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'connect_args': {'check_same_thread': False},
            'poolclass': StaticPool
        },
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'testing-secret-key',
        'SUPERADMIN_DOCUMENTS': {'80140666'}
    })

    with _app.app_context():
        db.create_all()
        yield _app
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """Proporciona un cliente de pruebas HTTP para simular peticiones."""
    return app.test_client()


@pytest.fixture(scope='function')
def app_context(app):
    """Proporciona un contexto de aplicación activo."""
    with app.app_context():
        yield app


@pytest.fixture(scope='function')
def db_session(app):
    """Proporciona una sesión de BD limpia para cada test."""
    with app.app_context():
        db.create_all()
        yield db.session
        db.session.rollback()
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope='function')
def sample_data(app):
    """Puebla la base de datos en memoria con datos iniciales para pruebas."""
    with app.app_context():
        db.create_all()

        sede = Sede.query.filter_by(nombre="Sede Pruebas").first()
        if not sede:
            sede = Sede(nombre="Sede Pruebas")
            db.session.add(sede)
            db.session.commit()

        bodega = Bodega.query.filter_by(nombre="Bodega Pruebas").first()
        if not bodega:
            bodega = Bodega(nombre="Bodega Pruebas", sede_id=sede.id)
            db.session.add(bodega)
            db.session.commit()

        auxiliar = Auxiliar.query.filter_by(documento="12345678").first()
        if not auxiliar:
            auxiliar = Auxiliar(
                documento="12345678",
                nombre_completo="Usuario Prueba",
                correo="prueba@uniminuto.edu",
                contraseña=generate_password_hash("password123"),
                rol="admin"
            )
            db.session.add(auxiliar)

        categoria = CategoriaInventario.query.filter_by(nombre="Equipos Portátiles").first()
        if not categoria:
            categoria = CategoriaInventario(nombre="Equipos Portátiles")
            db.session.add(categoria)

        db.session.commit()

        item = Inventario.query.filter_by(numero_inventario="LAP01").first()
        if not item:
            item = Inventario(
                item="Portátil HP ProBook",
                marca_modelo="HP ProBook 440",
                serial="SN123456",
                numero_inventario="LAP01",
                categoria="Equipos Portátiles",
                estado="Disponible",
                bodega_id=bodega.id
            )
            db.session.add(item)
            db.session.commit()

        yield {
            'sede': sede,
            'bodega': bodega,
            'auxiliar': auxiliar,
            'categoria': categoria,
            'item': item
        }

        db.session.remove()


@pytest.fixture(scope='function')
def admin_user(app):
    """Crea un usuario administrador para pruebas."""
    with app.app_context():
        db.create_all()
        admin = Auxiliar.query.filter_by(documento="80140666").first()
        if not admin:
            admin = Auxiliar(
                documento="80140666",
                nombre_completo="Admin Test",
                correo="admin@uniminuto.edu",
                contraseña=generate_password_hash("AdminPassword123"),
                rol="superadmin"
            )
            db.session.add(admin)
            db.session.commit()
        return admin


@pytest.fixture(scope='function')
def auxiliar_user(app):
    """Crea un usuario auxiliar para pruebas."""
    with app.app_context():
        db.create_all()
        auxiliar = Auxiliar.query.filter_by(documento="98765432").first()
        if not auxiliar:
            auxiliar = Auxiliar(
                documento="98765432",
                nombre_completo="Auxiliar Test",
                correo="auxiliar@uniminuto.edu",
                contraseña=generate_password_hash("AuxiliarPass123"),
                rol="auxiliar"
            )
            db.session.add(auxiliar)
            db.session.commit()
        return auxiliar


@pytest.fixture(scope='function')
def profesor_data(app):
    """Crea un profesor para pruebas."""
    with app.app_context():
        db.create_all()
        profesor = Profesor.query.filter_by(cedula=1001001001).first()
        if not profesor:
            profesor = Profesor(
                cedula=1001001001,
                nombre_completo="Profesor Test",
                correo="profesor@uniminuto.edu",
                telefono="3101234567",
                programa="Ingeniería en Sistemas"
            )
            db.session.add(profesor)
            db.session.commit()
        return profesor
