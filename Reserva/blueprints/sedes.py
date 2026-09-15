"""
Blueprint para selección y cambio de sede durante la sesión.
"""
from flask import Blueprint, render_template, request, redirect, session, abort
from database import Sede, AuxiliarSede
from auth import login_required

sedes_bp = Blueprint('sedes', __name__)


def obtener_sedes_usuario(documento, rol):
    """
    Retorna la lista de sedes autorizadas para un usuario.
    - admin / superadmin: todas las sedes del sistema.
    - auxiliar: sedes asignadas en la tabla auxiliar_sedes.
    """
    if rol in ('admin', 'superadmin'):
        return Sede.query.all()

    asignaciones = AuxiliarSede.query.filter_by(usuario_documento=documento).all()
    return [a.sede for a in asignaciones]


@sedes_bp.route('/seleccionar-sede', methods=['GET'])
@login_required
def seleccionar_sede_get():
    """Muestra la pantalla de selección de sede."""
    documento = session.get('usuario')
    rol = session.get('rol')
    sedes = obtener_sedes_usuario(documento, rol)
    return render_template('seleccionar_sede.html', sedes=sedes)


@sedes_bp.route('/seleccionar-sede', methods=['POST'])
@login_required
def seleccionar_sede_post():
    """Establece session['sede_id'] y redirige al dashboard."""
    documento = session.get('usuario')
    rol = session.get('rol')
    sedes_autorizadas = obtener_sedes_usuario(documento, rol)
    ids_autorizados = {s.id for s in sedes_autorizadas}

    try:
        sede_id = int(request.form.get('sede_id', 0))
    except (ValueError, TypeError):
        abort(403)

    if sede_id not in ids_autorizados:
        abort(403)

    sede = Sede.query.get(sede_id)
    session['sede_id'] = sede_id
    session['sede_nombre'] = sede.nombre if sede else None
    return redirect('/')


@sedes_bp.route('/cambiar-sede', methods=['POST'])
@login_required
def cambiar_sede():
    """Actualiza session['sede_id'] sin tocar el resto de la sesión y redirige al dashboard."""
    documento = session.get('usuario')
    rol = session.get('rol')
    sedes_autorizadas = obtener_sedes_usuario(documento, rol)
    ids_autorizados = {s.id for s in sedes_autorizadas}

    try:
        sede_id = int(request.form.get('sede_id', 0))
    except (ValueError, TypeError):
        abort(403)

    if sede_id not in ids_autorizados:
        abort(403)

    sede = Sede.query.get(sede_id)
    session['sede_id'] = sede_id
    session['sede_nombre'] = sede.nombre if sede else None
    return redirect('/')
