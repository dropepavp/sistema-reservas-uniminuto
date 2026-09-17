"""
Extensiones centralizadas de Flask.

Este módulo instancia las extensiones compartidas (SQLAlchemy, CSRFProtect, Limiter, SocketIO)
sin importar la aplicación, evitando imports circulares entre database.py, app.py y los blueprints.

Uso:
    from extensions import db, csrf, limiter, socketio
"""
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO
from flask_migrate import Migrate
from flasgger import Swagger
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from urllib.parse import urlparse, unquote


def _make_engine(raw_url: str):
    """Crea un engine de SQLAlchemy usando connect_args para evitar
    problemas de encoding con caracteres especiales en la contraseña y soportar SSL."""
    if raw_url.startswith('postgres://'):
        raw_url = raw_url.replace('postgres://', 'postgresql://', 1)

    parsed = urlparse(raw_url)
    password = unquote(parsed.password or '')
    db_name = parsed.path.lstrip('/') or 'sistema_reserva'
    connect_args = {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 5432,
        'user': parsed.username or 'postgres',
        'password': password,
        'database': db_name,
        'client_encoding': 'utf8',
    }
    # Para bases de datos en la nube (Neon, Supabase, etc.), habilitar SSL
    if parsed.hostname and parsed.hostname not in ('localhost', '127.0.0.1'):
        connect_args['sslmode'] = 'require'

    return create_engine(
        'postgresql+psycopg2://',
        connect_args=connect_args,
        echo=False,
        pool_pre_ping=True,
    )


class Base(DeclarativeBase):
    """Base declarativa con soporte tipado para SQLAlchemy 2.0 y Pyright/Pylance."""
    pass


db = SQLAlchemy(model_class=Base)
Base.query = db.session.query_property()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per minute"], storage_uri="memory://")
socketio = SocketIO()
migrate = Migrate()
swagger = Swagger()
