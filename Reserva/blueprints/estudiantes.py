# -*- coding: utf-8 -*-
"""
Blueprint para la gestión de la Base de Datos de Estudiantes UNIMINUTO.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, send_file
from sqlalchemy import or_, func, asc, desc
from datetime import datetime
import io
import pandas as pd

from extensions import db
from database import Estudiante, ProgramaAcademico, Sede, registrar_auditoria
from blueprints.auth import login_required

estudiantes_bp = Blueprint('estudiantes', __name__, url_prefix='/estudiantes')


@estudiantes_bp.route('/', methods=['GET'])
@login_required
def estudiantes_main():
    """Vista principal de gestión de estudiantes."""
    sede_filtro = request.args.get('sede', '').strip()
    programa_filtro = request.args.get('programa', '').strip()
    busqueda = request.args.get('q', '').strip()

    query = Estudiante.query

    if sede_filtro:
        query = query.filter(
            or_(
                Estudiante.descripcion_sede.ilike(f"%{sede_filtro}%"),
                Estudiante.sede_id == int(sede_filtro) if sede_filtro.isdigit() else False
            )
        )

    if programa_filtro:
        if programa_filtro.isdigit():
            query = query.filter(Estudiante.programa_id == int(programa_filtro))
        else:
            query = query.filter(
                or_(
                    Estudiante.atributo_programa.ilike(f"%{programa_filtro}%"),
                    Estudiante.programa_rel.has(ProgramaAcademico.nombre.ilike(f"%{programa_filtro}%"))
                )
            )

    if busqueda:
        query = query.filter(
            or_(
                Estudiante.nombre_completo.ilike(f"%{busqueda}%"),
                Estudiante.codigo_banner.ilike(f"%{busqueda}%"),
                Estudiante.documento.ilike(f"%{busqueda}%"),
                Estudiante.correo.ilike(f"%{busqueda}%")
            )
        )

    # Limitar la carga en la vista a los primeros 500 registros para velocidad óptima
    estudiantes = query.order_by(Estudiante.nombre_completo.asc()).limit(500).all()

    # Métricas / KPIs
    total_estudiantes = Estudiante.query.count()
    total_activos = Estudiante.query.filter_by(activo=True).count()
    total_engativa = Estudiante.query.filter(Estudiante.descripcion_sede.ilike('%ENGATIVA%')).count()
    total_cd_bolivar = Estudiante.query.filter(Estudiante.descripcion_sede.ilike('%BOLIVAR%')).count()

    programas = ProgramaAcademico.query.filter_by(activo=True).order_by(ProgramaAcademico.nombre.asc()).all()
    sedes = Sede.query.order_by(Sede.nombre.asc()).all()

    kpis = {
        'total': total_estudiantes,
        'activos': total_activos,
        'engativa': total_engativa,
        'cd_bolivar': total_cd_bolivar
    }

    filtros = {
        'sede': sede_filtro,
        'programa': programa_filtro,
        'q': busqueda
    }

    return render_template(
        'estudiantes.html',
        estudiantes=estudiantes,
        programas=programas,
        sedes=sedes,
        kpis=kpis,
        filtros=filtros
    )


@estudiantes_bp.route('/api/buscar', methods=['GET'])
@login_required
def api_buscar_estudiantes():
    """Buscador en tiempo real para autocompletado en préstamos, reservas y asistencias."""
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify([])

    estudiantes = Estudiante.query.filter(
        or_(
            Estudiante.nombre_completo.ilike(f"%{q}%"),
            Estudiante.codigo_banner.ilike(f"%{q}%"),
            Estudiante.documento.ilike(f"%{q}%")
        )
    ).limit(20).all()

    resultados = []
    for e in estudiantes:
        prog_nombre = e.programa_rel.nombre if e.programa_rel else (e.atributo_programa or 'Sin Programa')
        resultados.append({
            'id': e.id,
            'codigo_banner': e.codigo_banner,
            'documento': e.documento or e.codigo_banner,
            'nombre_completo': e.nombre_completo,
            'programa': prog_nombre,
            'atributo': e.atributo_programa or '',
            'sede': e.descripcion_sede or (e.sede.nombre if e.sede else ''),
            'correo': e.correo or '',
            'activo': e.activo
        })

    return jsonify(resultados)


@estudiantes_bp.route('/crear', methods=['POST'])
@login_required
def crear_estudiante():
    """Registra un nuevo estudiante."""
    codigo_banner = request.form.get('codigo_banner', '').strip()
    nombre_completo = request.form.get('nombre_completo', '').strip()
    documento = request.form.get('documento', '').strip() or codigo_banner
    tipo_documento = request.form.get('tipo_documento', 'CC').strip()
    correo = request.form.get('correo', '').strip()
    telefono = request.form.get('telefono', '').strip()
    programa_id = request.form.get('programa_id', type=int)
    sede_id = request.form.get('sede_id', type=int)
    descripcion_sede = request.form.get('descripcion_sede', '').strip()
    semestre = request.form.get('semestre', type=int)
    jornada = request.form.get('jornada', '').strip()
    observaciones = request.form.get('observaciones', '').strip()

    if not codigo_banner or not nombre_completo:
        flash('El código banner y el nombre completo son obligatorios.', 'danger')
        return redirect(url_for('estudiantes.estudiantes_main'))

    existente = Estudiante.query.filter_by(codigo_banner=codigo_banner).first()
    if existente:
        flash(f'Ya existe un estudiante con el código Banner {codigo_banner}.', 'warning')
        return redirect(url_for('estudiantes.estudiantes_main'))

    # Deducir atributo de programa si se seleccionó programa_id
    atributo_programa = None
    if programa_id:
        prog = ProgramaAcademico.query.get(programa_id)
        if prog:
            atributo_programa = prog.codigo

    # Deducir descripción de sede si se seleccionó sede_id
    if sede_id and not descripcion_sede:
        s = Sede.query.get(sede_id)
        if s:
            descripcion_sede = s.nombre

    nuevo = Estudiante(
        codigo_banner=codigo_banner,
        documento=documento,
        tipo_documento=tipo_documento,
        nombre_completo=nombre_completo.upper(),
        correo=correo,
        telefono=telefono,
        programa_id=programa_id,
        atributo_programa=atributo_programa,
        sede_id=sede_id,
        descripcion_sede=descripcion_sede,
        semestre=semestre,
        jornada=jornada,
        activo=True,
        observaciones=observaciones
    )

    db.session.add(nuevo)
    db.session.commit()

    registrar_auditoria(
        modulo='estudiantes',
        entidad_tipo='Estudiante',
        entidad_id=nuevo.id,
        accion='CREAR',
        usuario_documento=session.get('user_documento', ''),
        usuario_nombre=session.get('nombre_completo', ''),
        descripcion=f"Estudiante {nuevo.nombre_completo} ({nuevo.codigo_banner}) registrado.",
        datos_despues={'codigo_banner': nuevo.codigo_banner, 'nombre': nuevo.nombre_completo}
    )

    flash('Estudiante registrado exitosamente.', 'success')
    return redirect(url_for('estudiantes.estudiantes_main'))


@estudiantes_bp.route('/editar/<int:id>', methods=['POST'])
@login_required
def editar_estudiante(id):
    """Actualiza la información de un estudiante."""
    estudiante = Estudiante.query.get_or_404(id)

    codigo_banner = request.form.get('codigo_banner', '').strip()
    nombre_completo = request.form.get('nombre_completo', '').strip()
    documento = request.form.get('documento', '').strip()
    tipo_documento = request.form.get('tipo_documento', 'CC').strip()
    correo = request.form.get('correo', '').strip()
    telefono = request.form.get('telefono', '').strip()
    programa_id = request.form.get('programa_id', type=int)
    sede_id = request.form.get('sede_id', type=int)
    descripcion_sede = request.form.get('descripcion_sede', '').strip()
    semestre = request.form.get('semestre', type=int)
    jornada = request.form.get('jornada', '').strip()
    observaciones = request.form.get('observaciones', '').strip()

    if not codigo_banner or not nombre_completo:
        flash('El código y el nombre son campos obligatorios.', 'danger')
        return redirect(url_for('estudiantes.estudiantes_main'))

    # Verificar si el código ya lo tiene otro estudiante
    otro = Estudiante.query.filter(Estudiante.codigo_banner == codigo_banner, Estudiante.id != id).first()
    if otro:
        flash(f'El código {codigo_banner} ya pertenece a otro estudiante.', 'danger')
        return redirect(url_for('estudiantes.estudiantes_main'))

    estudiante.codigo_banner = codigo_banner
    estudiante.nombre_completo = nombre_completo.upper()
    estudiante.documento = documento or codigo_banner
    estudiante.tipo_documento = tipo_documento
    estudiante.correo = correo
    estudiante.telefono = telefono
    estudiante.programa_id = programa_id
    if programa_id:
        prog = ProgramaAcademico.query.get(programa_id)
        if prog:
            estudiante.atributo_programa = prog.codigo
    estudiante.sede_id = sede_id
    if sede_id and not descripcion_sede:
        s = Sede.query.get(sede_id)
        if s:
            descripcion_sede = s.nombre
    estudiante.descripcion_sede = descripcion_sede
    estudiante.semestre = semestre
    estudiante.jornada = jornada
    estudiante.observaciones = observaciones

    db.session.commit()

    registrar_auditoria(
        modulo='estudiantes',
        entidad_tipo='Estudiante',
        entidad_id=estudiante.id,
        accion='EDITAR',
        usuario_documento=session.get('user_documento', ''),
        usuario_nombre=session.get('nombre_completo', ''),
        descripcion=f"Estudiante {estudiante.nombre_completo} ({estudiante.codigo_banner}) actualizado."
    )

    flash('Estudiante actualizado exitosamente.', 'success')
    return redirect(url_for('estudiantes.estudiantes_main'))


@estudiantes_bp.route('/toggle-estado/<int:id>', methods=['POST'])
@login_required
def toggle_estado(id):
    """Activa o desactiva a un estudiante."""
    estudiante = Estudiante.query.get_or_404(id)
    estudiante.activo = not estudiante.activo
    db.session.commit()

    estado_txt = 'activado' if estudiante.activo else 'desactivado'
    flash(f"Estudiante {estudiante.nombre_completo} ha sido {estado_txt}.", 'info')
    return redirect(url_for('estudiantes.estudiantes_main'))


@estudiantes_bp.route('/exportar/<formato>', methods=['GET'])
@login_required
def exportar_estudiantes(formato):
    """Exporta los estudiantes filtrados a Excel o CSV."""
    estudiantes = Estudiante.query.order_by(Estudiante.nombre_completo.asc()).all()

    data = []
    for e in estudiantes:
        prog_nombre = e.programa_rel.nombre if e.programa_rel else (e.atributo_programa or 'Sin Programa')
        data.append({
            'Código Banner': e.codigo_banner,
            'Documento': e.documento or '',
            'Nombre Completo': e.nombre_completo,
            'Sede': e.descripcion_sede or (e.sede.nombre if e.sede else ''),
            'Atributo': e.atributo_programa or '',
            'Programa Académico': prog_nombre,
            'Correo': e.correo or '',
            'Teléfono': e.telefono or '',
            'Semestre': e.semestre or '',
            'Jornada': e.jornada or '',
            'Estado': 'Activo' if e.activo else 'Inactivo'
        })

    df = pd.DataFrame(data)

    output = io.BytesIO()
    if formato == 'excel':
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Estudiantes')
        output.seek(0)
        return send_file(
            output,
            download_name=f"Estudiantes_UNIMINUTO_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    else:
        df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        return send_file(
            output,
            download_name=f"Estudiantes_UNIMINUTO_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            as_attachment=True,
            mimetype='text/csv'
        )
