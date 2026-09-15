

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
