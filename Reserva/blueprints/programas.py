# -*- coding: utf-8 -*-
"""
Blueprint para la gestión de Programas Académicos UNIMINUTO.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, send_file
from sqlalchemy import or_, func, asc, desc
from datetime import datetime
import io
import pandas as pd

from extensions import db
from database import ProgramaAcademico, Profesor, Estudiante, Reserva, registrar_auditoria
from blueprints.auth import login_required

programas_bp = Blueprint('programas', __name__, url_prefix='/programas')


@programas_bp.route('/', methods=['GET'])
@login_required
def programas_main():
    """Vista principal del catálogo de programas académicos."""
    nivel_filtro = request.args.get('nivel', '').strip()
    busqueda = request.args.get('q', '').strip()

    query = ProgramaAcademico.query

    if nivel_filtro:
        query = query.filter(ProgramaAcademico.nivel == nivel_filtro)

    if busqueda:
        query = query.filter(
            or_(
                ProgramaAcademico.nombre.ilike(f"%{busqueda}%"),
                ProgramaAcademico.codigo.ilike(f"%{busqueda}%"),
                ProgramaAcademico.sub_nivel.ilike(f"%{busqueda}%")
            )
        )

    programas = query.order_by(ProgramaAcademico.nombre.asc()).all()

    # Conteos y KPIs
    total_programas = ProgramaAcademico.query.count()
    pregrados = ProgramaAcademico.query.filter_by(nivel='Pregrado').count()
    posgrados = ProgramaAcademico.query.filter_by(nivel='Posgrado').count()
    tecnicos = ProgramaAcademico.query.filter(
        or_(
            ProgramaAcademico.nivel == 'Técnico Profesional',
            ProgramaAcademico.sub_nivel.in_(['Tecnología', 'Técnico Profesional'])
        )
    ).count()

    # Diccionario de recuento de profesores y estudiantes por programa
    recuentos = {}
    for p in programas:
        n_profes = Profesor.query.filter(
            or_(Profesor.programa_id == p.id, Profesor.programa.ilike(f"%{p.nombre}%"))
        ).count()
        n_estudiantes = Estudiante.query.filter(
            or_(Estudiante.programa_id == p.id, Estudiante.atributo_programa == p.codigo)
        ).count()
        recuentos[p.id] = {
            'profesores': n_profes,
            'estudiantes': n_estudiantes
        }

    kpis = {
        'total': total_programas,
        'pregrados': pregrados,
        'posgrados': posgrados,
        'tecnicos': tecnicos
    }

    filtros = {
        'nivel': nivel_filtro,
        'q': busqueda
    }

    return render_template(
        'programas_academicos.html',
        programas=programas,
        recuentos=recuentos,
        kpis=kpis,
        filtros=filtros
    )


@programas_bp.route('/api/listar', methods=['GET'])
@login_required
def api_listar_programas():
    """API JSON para cargar selectores y autocompletado de programas académicos."""
    nivel = request.args.get('nivel', '')
    query = ProgramaAcademico.query.filter_by(activo=True)
    if nivel:
        query = query.filter_by(nivel=nivel)

    programas = query.order_by(ProgramaAcademico.nombre.asc()).all()
    return jsonify([
        {
            'id': p.id,
            'codigo': p.codigo,
            'nombre': p.nombre,
            'nivel': p.nivel or '',
            'sub_nivel': p.sub_nivel or '',
            'periodo': p.periodo or ''
        }
        for p in programas
    ])


@programas_bp.route('/crear', methods=['POST'])
@login_required
def crear_programa():
    """Crea un nuevo programa académico."""
    codigo = request.form.get('codigo', '').strip().upper()
    nombre = request.form.get('nombre', '').strip().upper()
    nivel = request.form.get('nivel', '').strip()
    sub_nivel = request.form.get('sub_nivel', '').strip()
    periodo = request.form.get('periodo', 'Semestral').strip()

    if not codigo or not nombre:
        flash('El código y el nombre del programa son obligatorios.', 'danger')
        return redirect(url_for('programas.programas_main'))

    existente = ProgramaAcademico.query.filter_by(codigo=codigo).first()
    if existente:
        flash(f'El código {codigo} ya está registrado para el programa {existente.nombre}.', 'warning')
        return redirect(url_for('programas.programas_main'))

    nuevo = ProgramaAcademico(
        codigo=codigo,
        nombre=nombre,
        nivel=nivel,
        sub_nivel=sub_nivel,
        periodo=periodo,
        activo=True
    )
    db.session.add(nuevo)
    db.session.commit()

    flash(f"Programa '{nombre}' ({codigo}) creado exitosamente.", 'success')
    return redirect(url_for('programas.programas_main'))


@programas_bp.route('/editar/<int:id>', methods=['POST'])
@login_required
def editar_programa(id):
    """Actualiza un programa académico."""
    prog = ProgramaAcademico.query.get_or_404(id)

    codigo = request.form.get('codigo', '').strip().upper()
    nombre = request.form.get('nombre', '').strip().upper()
    nivel = request.form.get('nivel', '').strip()
    sub_nivel = request.form.get('sub_nivel', '').strip()
    periodo = request.form.get('periodo', 'Semestral').strip()

    if not codigo or not nombre:
        flash('Código y nombre son obligatorios.', 'danger')
        return redirect(url_for('programas.programas_main'))

    otro = ProgramaAcademico.query.filter(ProgramaAcademico.codigo == codigo, ProgramaAcademico.id != id).first()
    if otro:
        flash(f'El código {codigo} ya lo utiliza otro programa.', 'danger')
        return redirect(url_for('programas.programas_main'))

    prog.codigo = codigo
    prog.nombre = nombre
    prog.nivel = nivel
    prog.sub_nivel = sub_nivel
    prog.periodo = periodo
    db.session.commit()

    flash(f"Programa '{nombre}' actualizado exitosamente.", 'success')
    return redirect(url_for('programas.programas_main'))


@programas_bp.route('/exportar', methods=['GET'])
@login_required
def exportar_programas():
    """Exporta el catálogo de programas a Excel."""
    programas = ProgramaAcademico.query.order_by(ProgramaAcademico.nombre.asc()).all()

    data = [
        {
            'Código Corto': p.codigo,
            'Programa General': p.nombre,
            'Nivel Programa': p.nivel or '',
            'Sub Nivel Programa': p.sub_nivel or '',
            'Periodo': p.periodo or '',
            'Estado': 'Activo' if p.activo else 'Inactivo'
        }
        for p in programas
    ]

    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Programas Académicos')
    output.seek(0)

    return send_file(
        output,
        download_name=f"Programas_Academicos_UNIMINUTO_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
