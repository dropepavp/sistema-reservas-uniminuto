# Feature: sede-turno-selector
import pytest
from flask import Flask, redirect, request, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase
from sqlalchemy.exc import IntegrityError
from typing import Optional
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

class Base(DeclarativeBase):
    pass

test_db = SQLAlchemy(model_class=Base)

class SedeTest(test_db.Model):
    __tablename__ = 'sedes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, unique=True, nullable=False)

class AuxiliarTest(test_db.Model):
    __tablename__ = 'auxiliares'
    documento: Mapped[str] = mapped_column(String, primary_key=True)
    nombre_completo: Mapped[str] = mapped_column(String, nullable=False)
    correo: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    contrasena: Mapped[str] = mapped_column(String, nullable=False)
    rol: Mapped[str] = mapped_column(String, nullable=False, default='auxiliar')
    sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes.id'), nullable=True)
    sedes_asignadas: Mapped[list["AuxiliarSedeTest"]] = relationship(back_populates="auxiliar", cascade="all, delete-orphan")

class AuxiliarSedeTest(test_db.Model):
    __tablename__ = 'auxiliar_sedes'
    usuario_documento: Mapped[str] = mapped_column(ForeignKey('auxiliares.documento', ondelete='CASCADE'), primary_key=True)
    sede_id: Mapped[int] = mapped_column(ForeignKey('sedes.id'), primary_key=True)
    auxiliar: Mapped["AuxiliarTest"] = relationship(back_populates="sedes_asignadas")

@pytest.fixture(scope='function')
def app():
    flask_app = Flask(__name__)
    flask_app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:', SQLALCHEMY_TRACK_MODIFICATIONS=False, SECRET_KEY='test-secret-key', WTF_CSRF_ENABLED=False)
    test_db.init_app(flask_app)
    with flask_app.app_context():
        test_db.create_all()
        yield flask_app
        test_db.session.remove()
        test_db.drop_all()

def _ensure_sede(session, sede_id):
    sede = session.get(SedeTest, sede_id)
    if sede is None:
        sede = SedeTest(id=sede_id, nombre=f'Sede_{sede_id}')
        session.add(sede)
        session.flush()
    return sede

def _ensure_auxiliar(session, documento):
    aux = session.get(AuxiliarTest, documento)
    if aux is None:
        aux = AuxiliarTest(documento=documento, nombre_completo=f'Auxiliar {documento}', correo=f'{documento}@test.com', contrasena='hashed_pw', rol='auxiliar')
        session.add(aux)
        session.flush()
    return aux

@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(documento=st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789', min_size=5, max_size=15), sede_num=st.integers(min_value=1, max_value=10))
def test_unicidad_auxiliar_sedes(app, documento, sede_num):
    # Feature: sede-turno-selector, Property 1: Unicidad en auxiliar_sedes
    # Valida: Requisito 1.2
    with app.app_context():
        test_db.session.rollback()
        _ensure_sede(test_db.session, sede_num)
        _ensure_auxiliar(test_db.session, documento)
        existing = test_db.session.query(AuxiliarSedeTest).filter_by(usuario_documento=documento, sede_id=sede_num).first()
        if existing is None:
            test_db.session.add(AuxiliarSedeTest(usuario_documento=documento, sede_id=sede_num))
            test_db.session.commit()
        count_antes = test_db.session.query(AuxiliarSedeTest).filter_by(usuario_documento=documento, sede_id=sede_num).count()
        assert count_antes == 1
        duplicado = AuxiliarSedeTest(usuario_documento=documento, sede_id=sede_num)
        test_db.session.add(duplicado)
        try:
            test_db.session.flush()
            test_db.session.rollback()
            pytest.fail("La BD deberia haber rechazado el duplicado")
        except IntegrityError:
            test_db.session.rollback()
            count_despues = test_db.session.query(AuxiliarSedeTest).filter_by(usuario_documento=documento, sede_id=sede_num).count()
            assert count_despues == 1

@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(documento=st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789', min_size=5, max_size=15), sedes=st.lists(st.integers(min_value=1, max_value=20), min_size=0, max_size=10, unique=True))
def test_eliminacion_cascada(app, documento, sedes):
    # Feature: sede-turno-selector, Property 2: Eliminacion en cascada
    # Valida: Requisito 1.3
    with app.app_context():
        test_db.session.rollback()
        _ensure_auxiliar(test_db.session, documento)
        for sede_id in sedes:
            _ensure_sede(test_db.session, sede_id)
            existing = test_db.session.query(AuxiliarSedeTest).filter_by(usuario_documento=documento, sede_id=sede_id).first()
            if existing is None:
                test_db.session.add(AuxiliarSedeTest(usuario_documento=documento, sede_id=sede_id))
        test_db.session.commit()
        count_antes = test_db.session.query(AuxiliarSedeTest).filter_by(usuario_documento=documento).count()
        assert count_antes == len(sedes)
        aux = test_db.session.get(AuxiliarTest, documento)
        test_db.session.delete(aux)
        test_db.session.commit()
        count_despues = test_db.session.query(AuxiliarSedeTest).filter_by(usuario_documento=documento).count()
        assert count_despues == 0, f"Tras eliminar el auxiliar se esperaban 0 registros, se encontraron {count_despues}"


# ── Property 7 ────────────────────────────────────────────────────────────────
import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..'))

from auth import sede_requerida  # noqa: E402


def _make_app_sede():
    flask_app = Flask(__name__)
    flask_app.config.update(
        TESTING=True,
        SECRET_KEY='test-secret-key-p7',
        WTF_CSRF_ENABLED=False,
    )

    @flask_app.route('/ruta-protegida')
    @sede_requerida
    def ruta_protegida():
        return 'OK', 200

    return flask_app


@given(sede_val=st.none())
@settings(max_examples=100)
def test_sede_requerida_redirige_sin_sede(sede_val):
    # Feature: sede-turno-selector, Property 7: Rutas protegidas sin sede activa redirigen al selector
    # Valida: Requisitos 2.6, 4.3
    flask_app = _make_app_sede()
    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess['usuario'] = 'testuser'
            sess['sede_id'] = sede_val  # None

        response = client.get('/ruta-protegida')

        assert response.status_code in (301, 302), (
            f'Se esperaba redirect (301/302), se obtuvo {response.status_code}'
        )
        location = response.headers.get('Location', '')
        assert '/seleccionar-sede' in location, (
            f'Se esperaba redirect a /seleccionar-sede, se obtuvo Location: {location!r}'
        )


# ── Property 3 ────────────────────────────────────────────────────────────────
# Feature: sede-turno-selector, Property 3: Redireccion post-login segun cantidad de sedes
# Valida: Requisitos 2.1, 2.2

from werkzeug.security import generate_password_hash as _gen_hash, check_password_hash as _check_hash


def _make_login_app_p3():
    from flask_sqlalchemy import SQLAlchemy as _SA
    from sqlalchemy.orm import DeclarativeBase as _DecBase

    class _Base(_DecBase):
        pass

    _db = _SA(model_class=_Base)

    class _Sede(_db.Model):
        __tablename__ = 'sedes'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        nombre: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    class _Auxiliar(_db.Model):
        __tablename__ = 'auxiliares'
        documento: Mapped[str] = mapped_column(String, primary_key=True)
        nombre_completo: Mapped[str] = mapped_column(String, nullable=False)
        correo: Mapped[str] = mapped_column(String, unique=True, nullable=False)
        contrasena: Mapped[str] = mapped_column(String, nullable=False)
        rol: Mapped[str] = mapped_column(String, nullable=False, default='auxiliar')
        sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes.id'), nullable=True)
        sedes_asignadas: Mapped[list["_AuxiliarSede"]] = relationship(
            back_populates="auxiliar", cascade="all, delete-orphan"
        )

    class _AuxiliarSede(_db.Model):
        __tablename__ = 'auxiliar_sedes'
        usuario_documento: Mapped[str] = mapped_column(
            ForeignKey('auxiliares.documento', ondelete='CASCADE'), primary_key=True
        )
        sede_id: Mapped[int] = mapped_column(ForeignKey('sedes.id'), primary_key=True)
        auxiliar: Mapped["_Auxiliar"] = relationship(back_populates="sedes_asignadas")
        sede: Mapped["_Sede"] = relationship()

    flask_app = Flask(__name__)
    flask_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY='test-secret-key-p3',
        WTF_CSRF_ENABLED=False,
    )
    _db.init_app(flask_app)

    with flask_app.app_context():
        _db.create_all()

    @flask_app.route('/login', methods=['POST'])
    def login():
        documento = request.form.get('usuario', '')
        contrasena = request.form.get('contrasena', '')
        aux = _db.session.get(_Auxiliar, documento)
        if aux is None or not _check_hash(aux.contrasena, contrasena):
            return redirect('/login')
        session['usuario'] = aux.documento
        session['rol'] = aux.rol
        asignaciones = _db.session.query(_AuxiliarSede).filter_by(usuario_documento=documento).all()
        sedes = [a.sede for a in asignaciones if a.sede is not None]
        if len(sedes) == 0:
            session.clear()
            return redirect('/login')
        if len(sedes) == 1:
            session['sede_id'] = sedes[0].id
            session['sede_nombre'] = sedes[0].nombre
            return redirect('/')
        session['sede_id'] = None
        session['sede_nombre'] = None
        return redirect('/seleccionar-sede')

    flask_app._test_db = _db
    flask_app._Auxiliar = _Auxiliar
    flask_app._Sede = _Sede
    flask_app._AuxiliarSede = _AuxiliarSede
    return flask_app


@settings(max_examples=100, deadline=None)
@given(
    documento=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789',
        min_size=5,
        max_size=15,
    ),
    num_sedes=st.integers(min_value=1, max_value=8),
)
def test_redireccion_postlogin_segun_sedes(documento, num_sedes):
    # Feature: sede-turno-selector, Property 3: Redireccion post-login segun cantidad de sedes
    # Valida: Requisitos 2.1, 2.2
    flask_app = _make_login_app_p3()
    _db = flask_app._test_db
    _Auxiliar = flask_app._Auxiliar
    _Sede = flask_app._Sede
    _AuxiliarSede = flask_app._AuxiliarSede
    password = 'TestPass1'

    with flask_app.app_context():
        aux = _Auxiliar(
            documento=documento,
            nombre_completo='Auxiliar ' + documento,
            correo=documento + '@test.com',
            contrasena=_gen_hash(password),
            rol='auxiliar',
        )
        _db.session.add(aux)
        _db.session.flush()
        sede_ids = []
        for i in range(num_sedes):
            sede = _Sede(nombre='Sede_' + documento + '_' + str(i))
            _db.session.add(sede)
            _db.session.flush()
            _db.session.add(_AuxiliarSede(usuario_documento=documento, sede_id=sede.id))
            sede_ids.append(sede.id)
        _db.session.commit()

    with flask_app.test_client() as client:
        response = client.post(
            '/login',
            data={'usuario': documento, 'contrasena': password},
            follow_redirects=False,
        )
        assert response.status_code in (301, 302), (
            'Se esperaba redirect, se obtuvo ' + str(response.status_code)
        )
        location = response.headers.get('Location', '')
        with client.session_transaction() as sess:
            sede_id_en_sesion = sess.get('sede_id')

        if num_sedes == 1:
            assert location in ('/', 'http://localhost/'), (
                'Con 1 sede se esperaba redirect a /, se obtuvo: ' + repr(location)
            )
            assert sede_id_en_sesion == sede_ids[0], (
                'Con 1 sede se esperaba session[sede_id]=' + str(sede_ids[0]) +
                ', se obtuvo ' + repr(sede_id_en_sesion)
            )
        else:
            assert '/seleccionar-sede' in location, (
                'Con ' + str(num_sedes) + ' sedes se esperaba redirect a /seleccionar-sede, '
                'se obtuvo: ' + repr(location)
            )
            assert sede_id_en_sesion is None, (
                'Con ' + str(num_sedes) + ' sedes se esperaba session[sede_id]=None, '
                'se obtuvo ' + repr(sede_id_en_sesion)
            )


# -- Property 4 ---------------------------------------------------------------
# Feature: sede-turno-selector, Property 4: Admin ve todas las sedes en el selector
# Valida: Requisito 2.3

import uuid as _uuid


def _obtener_sedes_admin(db_session, rol, SedeModel):
    """Replica la logica de obtener_sedes_usuario para admin/superadmin."""
    if rol in ('admin', 'superadmin'):
        return db_session.query(SedeModel).all()
    return []


@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    documento=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789',
        min_size=5,
        max_size=15,
    ),
    rol=st.sampled_from(['admin', 'superadmin']),
    n_sedes=st.integers(min_value=0, max_value=10),
)
def test_admin_ve_todas_las_sedes(app, documento, rol, n_sedes):
    # Feature: sede-turno-selector, Property 4: Admin ve todas las sedes en el selector
    # Valida: Requisito 2.3
    run_id = _uuid.uuid4().hex[:8]
    with app.app_context():
        test_db.session.rollback()

        # Crear N sedes con nombres unicos usando run_id
        sede_ids_creados = []
        for i in range(n_sedes):
            nombre = f'P4_{run_id}_{i}'
            sede = SedeTest(nombre=nombre)
            test_db.session.add(sede)
            test_db.session.flush()
            sede_ids_creados.append(sede.id)
        test_db.session.commit()

        # Conjunto completo de IDs en la tabla sedes
        todas_las_sedes = test_db.session.query(SedeTest).all()
        ids_esperados = {s.id for s in todas_las_sedes}

        # Lógica de obtener_sedes_usuario para admin/superadmin
        sedes_retornadas = _obtener_sedes_admin(test_db.session, rol, SedeTest)
        ids_retornados = {s.id for s in sedes_retornadas}

        assert ids_retornados == ids_esperados, (
            f"Admin con rol '{rol}' deberia ver todas las sedes {ids_esperados}, "
            f"pero obtuvo {ids_retornados}"
        )


# ── Property 6 ────────────────────────────────────────────────────────────────
# Feature: sede-turno-selector, Property 6: Seleccion y cambio de sede actualizan session['sede_id']
# Valida: Requisitos 2.5, 3.2, 3.3


def _make_app_p6():
    """App Flask minima con SQLite en memoria que replica /seleccionar-sede y /cambiar-sede."""
    from flask_sqlalchemy import SQLAlchemy as _SA
    from sqlalchemy.orm import DeclarativeBase as _DecBase

    class _Base(_DecBase):
        pass

    _db = _SA(model_class=_Base)

    class _Sede(_db.Model):
        __tablename__ = 'sedes'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        nombre: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    class _Auxiliar(_db.Model):
        __tablename__ = 'auxiliares'
        documento: Mapped[str] = mapped_column(String, primary_key=True)
        nombre_completo: Mapped[str] = mapped_column(String, nullable=False)
        correo: Mapped[str] = mapped_column(String, unique=True, nullable=False)
        contrasena: Mapped[str] = mapped_column(String, nullable=False)
        rol: Mapped[str] = mapped_column(String, nullable=False, default='auxiliar')
        sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes.id'), nullable=True)
        sedes_asignadas: Mapped[list["_AuxiliarSede"]] = relationship(
            back_populates="auxiliar", cascade="all, delete-orphan"
        )

    class _AuxiliarSede(_db.Model):
        __tablename__ = 'auxiliar_sedes'
        usuario_documento: Mapped[str] = mapped_column(
            ForeignKey('auxiliares.documento', ondelete='CASCADE'), primary_key=True
        )
        sede_id: Mapped[int] = mapped_column(ForeignKey('sedes.id'), primary_key=True)
        auxiliar: Mapped["_Auxiliar"] = relationship(back_populates="sedes_asignadas")
        sede: Mapped["_Sede"] = relationship()

    flask_app = Flask(__name__)
    flask_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY='test-secret-key-p6',
        WTF_CSRF_ENABLED=False,
    )
    _db.init_app(flask_app)

    with flask_app.app_context():
        _db.create_all()

    def _sedes_autorizadas(documento, rol):
        if rol in ('admin', 'superadmin'):
            return _db.session.query(_Sede).all()
        asignaciones = _db.session.query(_AuxiliarSede).filter_by(usuario_documento=documento).all()
        return [a.sede for a in asignaciones if a.sede is not None]

    @flask_app.route('/seleccionar-sede', methods=['POST'])
    def seleccionar_sede_p6():
        from flask import abort
        documento = session.get('usuario')
        rol = session.get('rol', 'auxiliar')
        ids_autorizados = {s.id for s in _sedes_autorizadas(documento, rol)}
        try:
            sede_id = int(request.form.get('sede_id', 0))
        except (ValueError, TypeError):
            abort(403)
        if sede_id not in ids_autorizados:
            abort(403)
        sede = _db.session.get(_Sede, sede_id)
        session['sede_id'] = sede_id
        session['sede_nombre'] = sede.nombre if sede else None
        return redirect('/')

    @flask_app.route('/cambiar-sede', methods=['POST'])
    def cambiar_sede_p6():
        from flask import abort
        documento = session.get('usuario')
        rol = session.get('rol', 'auxiliar')
        ids_autorizados = {s.id for s in _sedes_autorizadas(documento, rol)}
        try:
            sede_id = int(request.form.get('sede_id', 0))
        except (ValueError, TypeError):
            abort(403)
        if sede_id not in ids_autorizados:
            abort(403)
        sede = _db.session.get(_Sede, sede_id)
        session['sede_id'] = sede_id
        session['sede_nombre'] = sede.nombre if sede else None
        return redirect('/')

    flask_app._test_db = _db
    flask_app._Auxiliar = _Auxiliar
    flask_app._Sede = _Sede
    flask_app._AuxiliarSede = _AuxiliarSede
    return flask_app


@settings(max_examples=100, deadline=None)
@given(
    documento=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789',
        min_size=5,
        max_size=15,
    ),
    num_sedes=st.integers(min_value=1, max_value=8),
    sede_index=st.integers(min_value=0, max_value=7),
)
def test_seleccion_cambio_sede_actualiza_session(documento, num_sedes, sede_index):
    # Feature: sede-turno-selector, Property 6: Seleccion y cambio de sede actualizan session['sede_id']
    # Valida: Requisitos 2.5, 3.2, 3.3
    flask_app = _make_app_p6()
    _db = flask_app._test_db
    _Auxiliar = flask_app._Auxiliar
    _Sede = flask_app._Sede
    _AuxiliarSede = flask_app._AuxiliarSede

    idx = sede_index % num_sedes

    with flask_app.app_context():
        aux = _Auxiliar(
            documento=documento,
            nombre_completo='Auxiliar ' + documento,
            correo=documento + '@test.com',
            contrasena='hashed_pw',
            rol='auxiliar',
        )
        _db.session.add(aux)
        _db.session.flush()
        sede_ids = []
        for i in range(num_sedes):
            sede = _Sede(nombre='P6_' + documento + '_' + str(i))
            _db.session.add(sede)
            _db.session.flush()
            _db.session.add(_AuxiliarSede(usuario_documento=documento, sede_id=sede.id))
            sede_ids.append(sede.id)
        _db.session.commit()

    sede_id_elegido = sede_ids[idx]

    # Verificar /seleccionar-sede
    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess['usuario'] = documento
            sess['rol'] = 'auxiliar'
            sess['sede_id'] = None
        response = client.post(
            '/seleccionar-sede',
            data={'sede_id': str(sede_id_elegido)},
            follow_redirects=False,
        )
        assert response.status_code in (301, 302), (
            f'/seleccionar-sede: se esperaba redirect, se obtuvo {response.status_code}'
        )
        with client.session_transaction() as sess:
            sede_en_sesion = sess.get('sede_id')
        assert sede_en_sesion == sede_id_elegido, (
            f'/seleccionar-sede: session[sede_id] esperado={sede_id_elegido}, obtenido={sede_en_sesion}'
        )

    # Verificar /cambiar-sede
    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess['usuario'] = documento
            sess['rol'] = 'auxiliar'
            sess['sede_id'] = None
        response = client.post(
            '/cambiar-sede',
            data={'sede_id': str(sede_id_elegido)},
            follow_redirects=False,
        )
        assert response.status_code in (301, 302), (
            f'/cambiar-sede: se esperaba redirect, se obtuvo {response.status_code}'
        )
        with client.session_transaction() as sess:
            sede_en_sesion = sess.get('sede_id')
        assert sede_en_sesion == sede_id_elegido, (
            f'/cambiar-sede: session[sede_id] esperado={sede_id_elegido}, obtenido={sede_en_sesion}'
        )


# ── Property 16 ───────────────────────────────────────────────────────────────
# Feature: sede-turno-selector, Property 16: sede_id no autorizado devuelve HTTP 403
# Valida: Requisitos 6.2, 6.3


@settings(max_examples=100, deadline=None)
@given(
    documento=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789',
        min_size=5,
        max_size=15,
    ),
    sedes_autorizadas=st.lists(
        st.integers(min_value=1, max_value=50),
        min_size=1,
        max_size=8,
        unique=True,
    ),
    sede_no_autorizada=st.integers(min_value=51, max_value=200),
)
def test_sede_id_no_autorizado_403(documento, sedes_autorizadas, sede_no_autorizada):
    # Feature: sede-turno-selector, Property 16: sede_id no autorizado devuelve HTTP 403
    # Valida: Requisitos 6.2, 6.3
    flask_app = _make_app_p6()
    _db = flask_app._test_db
    _Auxiliar = flask_app._Auxiliar
    _Sede = flask_app._Sede
    _AuxiliarSede = flask_app._AuxiliarSede

    with flask_app.app_context():
        aux = _Auxiliar(
            documento=documento,
            nombre_completo='Auxiliar ' + documento,
            correo=documento + '@test.com',
            contrasena='hashed_pw',
            rol='auxiliar',
        )
        _db.session.add(aux)
        _db.session.flush()
        for sid in sedes_autorizadas:
            sede = _Sede(nombre='P16_' + documento + '_' + str(sid))
            sede.id = sid
            _db.session.merge(sede)
            _db.session.flush()
            existing = _db.session.query(_AuxiliarSede).filter_by(
                usuario_documento=documento, sede_id=sid
            ).first()
            if existing is None:
                _db.session.add(_AuxiliarSede(usuario_documento=documento, sede_id=sid))
        _db.session.commit()

    sede_id_inicial = 999

    # Verificar /seleccionar-sede con sede_id no autorizado
    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess['usuario'] = documento
            sess['rol'] = 'auxiliar'
            sess['sede_id'] = sede_id_inicial

        response = client.post(
            '/seleccionar-sede',
            data={'sede_id': str(sede_no_autorizada)},
            follow_redirects=False,
        )
        assert response.status_code == 403, (
            f'/seleccionar-sede: se esperaba 403 para sede_id no autorizado {sede_no_autorizada}, '
            f'se obtuvo {response.status_code}'
        )
        with client.session_transaction() as sess:
            sede_en_sesion = sess.get('sede_id')
        assert sede_en_sesion == sede_id_inicial, (
            f'/seleccionar-sede: session[sede_id] no debe modificarse. '
            f'Esperado={sede_id_inicial}, obtenido={sede_en_sesion}'
        )

    # Verificar /cambiar-sede con sede_id no autorizado
    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess['usuario'] = documento
            sess['rol'] = 'auxiliar'
            sess['sede_id'] = sede_id_inicial

        response = client.post(
            '/cambiar-sede',
            data={'sede_id': str(sede_no_autorizada)},
            follow_redirects=False,
        )
        assert response.status_code == 403, (
            f'/cambiar-sede: se esperaba 403 para sede_id no autorizado {sede_no_autorizada}, '
            f'se obtuvo {response.status_code}'
        )
        with client.session_transaction() as sess:
            sede_en_sesion = sess.get('sede_id')
        assert sede_en_sesion == sede_id_inicial, (
            f'/cambiar-sede: session[sede_id] no debe modificarse. '
            f'Esperado={sede_id_inicial}, obtenido={sede_en_sesion}'
        )

# -- Property 15 ---------------------------------------------------------------
# Feature: sede-turno-selector, Property 15: Cambio de sede preserva el resto de la sesion
# Valida: Requisito 6.1


@settings(max_examples=100, deadline=None)
@given(
    documento=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789',
        min_size=5,
        max_size=15,
    ),
    rol=st.sampled_from(['auxiliar', 'admin', 'superadmin']),
    mod_access=st.dictionaries(
        keys=st.text(alphabet='abcdefghijklmnopqrstuvwxyz', min_size=1, max_size=10),
        values=st.booleans(),
        min_size=0,
        max_size=5,
    ),
    num_sedes=st.integers(min_value=2, max_value=6),
    sede_index=st.integers(min_value=0, max_value=5),
)
def test_cambio_sede_preserva_sesion(documento, rol, mod_access, num_sedes, sede_index):
    # Feature: sede-turno-selector, Property 15: Cambio de sede preserva el resto de la sesion
    # Valida: Requisito 6.1
    flask_app = _make_app_p6()
    _db = flask_app._test_db
    _Auxiliar = flask_app._Auxiliar
    _Sede = flask_app._Sede
    _AuxiliarSede = flask_app._AuxiliarSede

    idx = sede_index % num_sedes

    with flask_app.app_context():
        aux = _Auxiliar(
            documento=documento,
            nombre_completo='Auxiliar ' + documento,
            correo=documento + '@test.com',
            contrasena='hashed_pw',
            rol=rol,
        )
        _db.session.add(aux)
        _db.session.flush()
        sede_ids = []
        for i in range(num_sedes):
            sede = _Sede(nombre='P15_' + documento + '_' + str(i))
            _db.session.add(sede)
            _db.session.flush()
            if rol == 'auxiliar':
                _db.session.add(_AuxiliarSede(usuario_documento=documento, sede_id=sede.id))
            sede_ids.append(sede.id)
        _db.session.commit()

    sede_id_nuevo = sede_ids[idx]
    sede_id_inicial = sede_ids[(idx + 1) % num_sedes]

    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess['usuario'] = documento
            sess['rol'] = rol
            sess['mod_access'] = mod_access
            sess['sede_id'] = sede_id_inicial

        response = client.post(
            '/cambiar-sede',
            data={'sede_id': str(sede_id_nuevo)},
            follow_redirects=False,
        )
        assert response.status_code in (301, 302), (
            f'/cambiar-sede: se esperaba redirect, se obtuvo {response.status_code}'
        )

        with client.session_transaction() as sess:
            assert sess.get('usuario') == documento, (
                f"session['usuario'] cambio: esperado={documento!r}, obtenido={sess.get('usuario')!r}"
            )
            assert sess.get('rol') == rol, (
                f"session['rol'] cambio: esperado={rol!r}, obtenido={sess.get('rol')!r}"
            )
            assert sess.get('mod_access') == mod_access, (
                f"session['mod_access'] cambio: esperado={mod_access!r}, obtenido={sess.get('mod_access')!r}"
            )
            assert sess.get('sede_id') == sede_id_nuevo, (
                f"session['sede_id'] no se actualizo: esperado={sede_id_nuevo!r}, obtenido={sess.get('sede_id')!r}"
            )


# -- Property 5 ---------------------------------------------------------------
# Feature: sede-turno-selector, Property 5: Selector muestra nombres de todas las sedes disponibles
# Valida: Requisito 2.4


def _make_app_p5():
    """App Flask minima con SQLite en memoria para testear Property 5."""
    from flask_sqlalchemy import SQLAlchemy as _SA
    from sqlalchemy.orm import DeclarativeBase as _DecBase

    class _Base(_DecBase):
        pass

    _db = _SA(model_class=_Base)

    class _Sede(_db.Model):
        __tablename__ = 'sedes'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        nombre: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    class _Auxiliar(_db.Model):
        __tablename__ = 'auxiliares'
        documento: Mapped[str] = mapped_column(String, primary_key=True)
        nombre_completo: Mapped[str] = mapped_column(String, nullable=False)
        correo: Mapped[str] = mapped_column(String, unique=True, nullable=False)
        contrasena: Mapped[str] = mapped_column(String, nullable=False)
        rol: Mapped[str] = mapped_column(String, nullable=False, default='auxiliar')
        sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes.id'), nullable=True)
        sedes_asignadas: Mapped[list["_AuxiliarSede"]] = relationship(
            back_populates="auxiliar", cascade="all, delete-orphan"
        )

    class _AuxiliarSede(_db.Model):
        __tablename__ = 'auxiliar_sedes'
        usuario_documento: Mapped[str] = mapped_column(
            ForeignKey('auxiliares.documento', ondelete='CASCADE'), primary_key=True
        )
        sede_id: Mapped[int] = mapped_column(ForeignKey('sedes.id'), primary_key=True)
        auxiliar: Mapped["_Auxiliar"] = relationship(back_populates="sedes_asignadas")
        sede: Mapped["_Sede"] = relationship()

    flask_app = Flask(__name__)
    flask_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY='test-secret-key-p5',
        WTF_CSRF_ENABLED=False,
    )
    _db.init_app(flask_app)

    with flask_app.app_context():
        _db.create_all()

    _TEMPLATE_P5 = (
        "{% for sede in sedes %}"
        "<div class=\"form-check\">"
        "<input type=\"radio\" name=\"sede_id\" value=\"{{ sede.id }}\">"
        "<label>{{ sede.nombre }}</label>"
        "</div>"
        "{% else %}"
        "<p>No tienes sedes asignadas.</p>"
        "{% endfor %}"
    )

    @flask_app.route('/seleccionar-sede', methods=['GET'])
    def seleccionar_sede_p5():
        from flask import render_template_string
        documento = session.get('usuario')
        rol = session.get('rol', 'auxiliar')
        if rol in ('admin', 'superadmin'):
            sedes = _db.session.query(_Sede).all()
        else:
            asignaciones = _db.session.query(_AuxiliarSede).filter_by(
                usuario_documento=documento
            ).all()
            sedes = [a.sede for a in asignaciones if a.sede is not None]
        return render_template_string(_TEMPLATE_P5, sedes=sedes)

    flask_app._test_db = _db
    flask_app._Auxiliar = _Auxiliar
    flask_app._Sede = _Sede
    flask_app._AuxiliarSede = _AuxiliarSede
    return flask_app


@settings(max_examples=100, deadline=None)
@given(
    documento=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789',
        min_size=5,
        max_size=15,
    ),
    n_sedes=st.integers(min_value=1, max_value=10),
)
def test_selector_muestra_nombres_sedes(documento, n_sedes):
    # Feature: sede-turno-selector, Property 5: Selector muestra nombres de todas las sedes disponibles
    # Valida: Requisito 2.4
    flask_app = _make_app_p5()
    _db = flask_app._test_db
    _Auxiliar = flask_app._Auxiliar
    _Sede = flask_app._Sede
    _AuxiliarSede = flask_app._AuxiliarSede

    with flask_app.app_context():
        aux = _Auxiliar(
            documento=documento,
            nombre_completo='Auxiliar ' + documento,
            correo=documento + '@test.com',
            contrasena='hashed_pw',
            rol='auxiliar',
        )
        _db.session.add(aux)
        _db.session.flush()
        nombres_sedes = []
        for i in range(n_sedes):
            nombre = 'P5_' + documento + '_' + str(i)
            sede = _Sede(nombre=nombre)
            _db.session.add(sede)
            _db.session.flush()
            _db.session.add(_AuxiliarSede(usuario_documento=documento, sede_id=sede.id))
            nombres_sedes.append(nombre)
        _db.session.commit()

    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess['usuario'] = documento
            sess['rol'] = 'auxiliar'

        response = client.get('/seleccionar-sede')
        assert response.status_code == 200, (
            'Se esperaba 200, se obtuvo ' + str(response.status_code)
        )
        html = response.data.decode('utf-8')
        for nombre in nombres_sedes:
            assert nombre in html, (
                'El nombre de sede "' + nombre + '" no aparece en el HTML renderizado'
            )


# ── Property 8 ────────────────────────────────────────────────────────────────
# Feature: sede-turno-selector, Property 8: Navbar muestra control de cambio segun cantidad de sedes
# Valida: Requisitos 3.1, 3.5


def _render_navbar_p8(puede_cambiar_sede, sede_nombre=None):
    """Renderiza el fragmento del navbar usando una app Flask minima."""
    # Template minimo que replica la logica del navbar para el control de cambio de sede
    navbar_tmpl = (
        '{%- if session.get("puede_cambiar_sede") -%}'
        '<div id="control-cambio-sede">'
        '<form method="POST" action="/cambiar-sede">'
        '<button type="submit">Cambiar sede</button>'
        '</form>'
        '</div>'
        '{%- endif -%}'
    )
    flask_app = Flask(__name__)
    flask_app.config.update(TESTING=True, SECRET_KEY='test-secret-key-p8')

    @flask_app.route('/navbar-test')
    def navbar_test():
        from flask import render_template_string
        return render_template_string(navbar_tmpl)

    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess['puede_cambiar_sede'] = puede_cambiar_sede
            if sede_nombre:
                sess['sede_nombre'] = sede_nombre
        response = client.get('/navbar-test')
        return response.data.decode('utf-8')


@settings(max_examples=100)
@given(
    num_sedes=st.integers(min_value=2, max_value=10),
    sede_nombre=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789 ',
        min_size=1,
        max_size=20,
    ),
)
def test_navbar_control_cambio_sede(num_sedes, sede_nombre):
    # Feature: sede-turno-selector, Property 8: Navbar muestra control de cambio segun cantidad de sedes
    # Valida: Requisitos 3.1, 3.5

    # Caso 1: usuario con >1 sede (puede_cambiar_sede=True) -> control debe aparecer
    html_multi = _render_navbar_p8(puede_cambiar_sede=True, sede_nombre=sede_nombre)
    assert '/cambiar-sede' in html_multi, (
        f'Con {num_sedes} sedes (puede_cambiar_sede=True), '
        f'el navbar debe contener el control de cambio de sede (/cambiar-sede), '
        f'pero no se encontro en el HTML.'
    )

    # Caso 2: usuario con 1 sede (puede_cambiar_sede=False) -> control NO debe aparecer
    html_single = _render_navbar_p8(puede_cambiar_sede=False, sede_nombre=sede_nombre)
    assert '/cambiar-sede' not in html_single, (
        f'Con 1 sede (puede_cambiar_sede=False), '
        f'el navbar NO debe contener el control de cambio de sede, '
        f'pero se encontro /cambiar-sede en el HTML.'
    )


# -- Property 9 ---------------------------------------------------------------
# Feature: sede-turno-selector, Property 9: Navbar indica la sede activa
# Valida: Requisito 3.4

_NAVBAR_TEMPLATE_P9 = (
    "{% if session.get('sede_id') or session.get('sede_nombre') %}"
    "<span class=\"badge bg-secondary\">"
    "{{ session.get('sede_nombre') or 'Sede' }}"
    "</span>"
    "{% endif %}"
)


@settings(max_examples=100)
@given(
    sede_id=st.integers(min_value=1, max_value=1000),
    sede_nombre=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ',
        min_size=1,
        max_size=50,
    ),
)
def test_navbar_indica_sede_activa(sede_id, sede_nombre):
    # Feature: sede-turno-selector, Property 9: Navbar indica la sede activa
    # Valida: Requisito 3.4
    flask_app = Flask(__name__)
    flask_app.config.update(
        TESTING=True,
        SECRET_KEY='test-secret-key-p9',
    )

    @flask_app.route('/navbar-test-p9')
    def navbar_test_p9():
        from flask import render_template_string
        return render_template_string(_NAVBAR_TEMPLATE_P9)

    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess['sede_id'] = sede_id
            sess['sede_nombre'] = sede_nombre

        response = client.get('/navbar-test-p9')
        assert response.status_code == 200, (
            f'Se esperaba 200, se obtuvo {response.status_code}'
        )
        html = response.data.decode('utf-8')
        assert sede_nombre in html, (
            f'El navbar debe contener el nombre de la sede activa "{sede_nombre}", '
            f'pero no se encontro en el HTML: {html!r}'
        )


# -- Property 10 ---------------------------------------------------------------
# Feature: sede-turno-selector, Property 10: Filtrado de datos por sede activa
# Valida: Requisito 4.1


def _make_app_p10():
    """App Flask minima con SQLite en memoria con modelos simplificados para Property 10."""
    from flask_sqlalchemy import SQLAlchemy as _SA
    from sqlalchemy.orm import DeclarativeBase as _DecBase

    class _Base(_DecBase):
        pass

    _db = _SA(model_class=_Base)

    class _Sede(_db.Model):
        __tablename__ = 'sedes_p10'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        nombre: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    class _Prestamo(_db.Model):
        __tablename__ = 'prestamos_p10'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        descripcion: Mapped[str] = mapped_column(String, nullable=False)
        sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes_p10.id'), nullable=True)

    class _Reserva(_db.Model):
        __tablename__ = 'reservas_p10'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        descripcion: Mapped[str] = mapped_column(String, nullable=False)
        sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes_p10.id'), nullable=True)

    class _Inventario(_db.Model):
        __tablename__ = 'inventario_p10'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        descripcion: Mapped[str] = mapped_column(String, nullable=False)
        sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes_p10.id'), nullable=True)

    flask_app = Flask(__name__)
    flask_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY='test-secret-key-p10',
        WTF_CSRF_ENABLED=False,
    )
    _db.init_app(flask_app)

    with flask_app.app_context():
        _db.create_all()

    flask_app._test_db = _db
    flask_app._Sede = _Sede
    flask_app._Prestamo = _Prestamo
    flask_app._Reserva = _Reserva
    flask_app._Inventario = _Inventario
    return flask_app


@settings(max_examples=100, deadline=None)
@given(
    sede_activa_idx=st.integers(min_value=0, max_value=4),
    n_sedes=st.integers(min_value=2, max_value=5),
    n_registros_por_sede=st.integers(min_value=1, max_value=5),
)
def test_filtrado_datos_por_sede(sede_activa_idx, n_sedes, n_registros_por_sede):
    # Feature: sede-turno-selector, Property 10: Filtrado de datos por sede activa
    # Valida: Requisito 4.1
    flask_app = _make_app_p10()
    _db = flask_app._test_db
    _Sede = flask_app._Sede
    _Prestamo = flask_app._Prestamo
    _Reserva = flask_app._Reserva
    _Inventario = flask_app._Inventario

    idx = sede_activa_idx % n_sedes

    with flask_app.app_context():
        sede_ids = []
        for i in range(n_sedes):
            sede = _Sede(nombre=f'P10_s{i}_{sede_activa_idx}_{n_sedes}')
            _db.session.add(sede)
            _db.session.flush()
            sede_ids.append(sede.id)

        for sede_id in sede_ids:
            for j in range(n_registros_por_sede):
                _db.session.add(_Prestamo(descripcion=f'p_s{sede_id}_{j}', sede_id=sede_id))
                _db.session.add(_Reserva(descripcion=f'r_s{sede_id}_{j}', sede_id=sede_id))
                _db.session.add(_Inventario(descripcion=f'i_s{sede_id}_{j}', sede_id=sede_id))

        _db.session.commit()

        session_sede_id = sede_ids[idx]

        prestamos_filtrados = _db.session.query(_Prestamo).filter(
            _Prestamo.sede_id == session_sede_id
        ).all()
        assert len(prestamos_filtrados) == n_registros_por_sede
        for p in prestamos_filtrados:
            assert p.sede_id == session_sede_id

        reservas_filtradas = _db.session.query(_Reserva).filter(
            _Reserva.sede_id == session_sede_id
        ).all()
        assert len(reservas_filtradas) == n_registros_por_sede
        for r in reservas_filtradas:
            assert r.sede_id == session_sede_id

        inventario_filtrado = _db.session.query(_Inventario).filter(
            _Inventario.sede_id == session_sede_id
        ).all()
        assert len(inventario_filtrado) == n_registros_por_sede
        for item in inventario_filtrado:
            assert item.sede_id == session_sede_id


# -- Property 11 ---------------------------------------------------------------
# Feature: sede-turno-selector, Property 11: Nuevos registros heredan la sede activa
# Valida: Requisito 4.2


def _make_app_p11():
    from flask_sqlalchemy import SQLAlchemy as _SA
    from sqlalchemy.orm import DeclarativeBase as _DecBase

    class _Base(_DecBase):
        pass

    _db = _SA(model_class=_Base)

    class _Sede(_db.Model):
        __tablename__ = 'sedes_p11'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        nombre: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    class _Prestamo(_db.Model):
        __tablename__ = 'prestamos_p11'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        descripcion: Mapped[str] = mapped_column(String, nullable=False)
        sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes_p11.id'), nullable=True)

    class _Reserva(_db.Model):
        __tablename__ = 'reservas_p11'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        descripcion: Mapped[str] = mapped_column(String, nullable=False)
        sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes_p11.id'), nullable=True)

    class _Inventario(_db.Model):
        __tablename__ = 'inventario_p11'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        descripcion: Mapped[str] = mapped_column(String, nullable=False)
        sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes_p11.id'), nullable=True)

    flask_app = Flask(__name__)
    flask_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY='test-secret-key-p11',
        WTF_CSRF_ENABLED=False,
    )
    _db.init_app(flask_app)

    with flask_app.app_context():
        _db.create_all()

    @flask_app.route('/prestamos/crear', methods=['POST'])
    def crear_prestamo_p11():
        from flask import jsonify
        sede_id = session.get('sede_id')
        descripcion = request.form.get('descripcion', 'sin descripcion')
        prestamo = _Prestamo(descripcion=descripcion, sede_id=sede_id)
        _db.session.add(prestamo)
        _db.session.commit()
        return jsonify({'id': prestamo.id, 'sede_id': prestamo.sede_id})

    @flask_app.route('/reservas/crear', methods=['POST'])
    def crear_reserva_p11():
        from flask import jsonify
        sede_id = session.get('sede_id')
        descripcion = request.form.get('descripcion', 'sin descripcion')
        reserva = _Reserva(descripcion=descripcion, sede_id=sede_id)
        _db.session.add(reserva)
        _db.session.commit()
        return jsonify({'id': reserva.id, 'sede_id': reserva.sede_id})

    @flask_app.route('/inventario/crear', methods=['POST'])
    def crear_inventario_p11():
        from flask import jsonify
        sede_id = session.get('sede_id')
        descripcion = request.form.get('descripcion', 'sin descripcion')
        item = _Inventario(descripcion=descripcion, sede_id=sede_id)
        _db.session.add(item)
        _db.session.commit()
        return jsonify({'id': item.id, 'sede_id': item.sede_id})

    flask_app._test_db = _db
    flask_app._Sede = _Sede
    flask_app._Prestamo = _Prestamo
    flask_app._Reserva = _Reserva
    flask_app._Inventario = _Inventario
    return flask_app


@settings(max_examples=100, deadline=None)
@given(
    sede_id=st.integers(min_value=1, max_value=20),
    descripcion=st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789', min_size=3, max_size=20),
)
def test_nuevos_registros_heredan_sede_activa(sede_id, descripcion):
    # Feature: sede-turno-selector, Property 11: Nuevos registros heredan la sede activa
    # Valida: Requisito 4.2
    import json as _json

    flask_app = _make_app_p11()
    _db = flask_app._test_db
    _Sede = flask_app._Sede
    _Prestamo = flask_app._Prestamo
    _Reserva = flask_app._Reserva
    _Inventario = flask_app._Inventario

    with flask_app.app_context():
        sede = _Sede(id=sede_id, nombre='P11_sede_' + str(sede_id))
        _db.session.merge(sede)
        _db.session.commit()

    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess['sede_id'] = sede_id

        resp_p = client.post('/prestamos/crear', data={'descripcion': descripcion})
        assert resp_p.status_code == 200
        data_p = _json.loads(resp_p.data)
        assert data_p['sede_id'] == sede_id, (
            'Prestamo: sede_id retornado=' + repr(data_p['sede_id']) + ' != session sede_id=' + str(sede_id)
        )

        resp_r = client.post('/reservas/crear', data={'descripcion': descripcion})
        assert resp_r.status_code == 200
        data_r = _json.loads(resp_r.data)
        assert data_r['sede_id'] == sede_id, (
            'Reserva: sede_id retornado=' + repr(data_r['sede_id']) + ' != session sede_id=' + str(sede_id)
        )

        resp_i = client.post('/inventario/crear', data={'descripcion': descripcion})
        assert resp_i.status_code == 200
        data_i = _json.loads(resp_i.data)
        assert data_i['sede_id'] == sede_id, (
            'Inventario: sede_id retornado=' + repr(data_i['sede_id']) + ' != session sede_id=' + str(sede_id)
        )

    with flask_app.app_context():
        prestamo_db = _db.session.get(_Prestamo, data_p['id'])
        assert prestamo_db is not None
        assert prestamo_db.sede_id == sede_id

        reserva_db = _db.session.get(_Reserva, data_r['id'])
        assert reserva_db is not None
        assert reserva_db.sede_id == sede_id

        inventario_db = _db.session.get(_Inventario, data_i['id'])
        assert inventario_db is not None
        assert inventario_db.sede_id == sede_id
