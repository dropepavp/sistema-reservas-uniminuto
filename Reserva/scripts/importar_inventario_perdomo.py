"""
Script para importar y sincronizar el inventario de la Sede Perdomo
y poblar la tabla inventario_custodia con los 937 registros detallados.
"""
import os
import sys
import csv
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from database import db, Sede, Bodega, CategoriaInventario, Inventario, InventarioCustodia, init_db


def categorizar_item(desc: str, tipo: str, marca: str) -> str:
    desc_u = (desc or '').upper()
    tipo_u = (tipo or '').upper()
    marca_u = (marca or '').upper()

    if tipo_u == 'BODEGA_LOTE' or any(k in desc_u for k in [
        'BALON', 'CONO', 'PLATILLO', 'ARO', 'HULA', 'PELOTA', 'RAQUETA',
        'MALLA', 'SOGA', 'LAZO', 'COLCHONETA', 'TRAMPOLIN', 'POSTES DE VOLEIBOL', 'BOMBA', 'CANDADOS YALE'
    ]):
        return 'Material Deportivo y Lote'

    if any(k in desc_u for k in ['PORTATIL', 'PORTÁTIL', 'PROBOOK', 'LAPTOP']):
        return 'Equipos Portátiles'

    if any(k in desc_u for k in ['OPTIPLEX', 'TODO EN UNO', 'ALL-IN-ONE', 'M700Z', 'M73Z', 'PROONE']):
        return 'Todo en Uno'

    if any(k in desc_u for k in ['ONE SCREEN', '0NE SCREEN', 'PANTALLA']):
        return 'Pantallas Digitales Interactivas'

    if any(k in desc_u for k in ['VIDEO BEAM', 'PROYECTOR']):
        return 'Proyectores (Video Beam)'

    if any(k in desc_u for k in [
        'CONSOLA', 'GUITARRA', 'BAJO', 'MICROFONO', 'MICRÓFONO', 'AMPLIFICADOR',
        'TECLADO DIGITAL', 'TECLADO MUSICAL', 'CABINA', 'PARLANTE', 'BATERIA',
        'TAMBORA', 'ALEGRE', 'LLAMADOR', 'GAITAS', 'MINI COMPONENTE', 'ESTROBOSCOPIO',
        'INTERCOMUNICADOR', 'TELEVISOR'
    ]):
        return 'Audio/Video (HDMI, Parlantes)'

    if any(k in desc_u for k in [
        'TECLADO', 'MOUSE', 'MULTITOMA', 'MULTIOTOMA', 'DIADEMA', 'CABLE',
        'EXTENSOR', 'LAPIZ', 'ADAPTADOR', 'CARGADOR', 'PILAS', 'PILA'
    ]):
        return 'Periféricos (Teclados, Mouse)'

    if any(k in desc_u for k in [
        'ALCOHOLIMETRO', 'AUDIOMETRO', 'CALIBRADOR', 'DETECTOR', 'ESPIROMETRO',
        'LUXOMETRO', 'MEDIDOR', 'PROBADOR DE VISION', 'REGISTRADOR DE DATOS',
        'SONOMETRO', 'TENSIOMETRO', 'ADIPOMETRO', 'OXIMETRO', 'BASCULA',
        'DINAMOMETRO', 'GLUCOMETRO', 'GONIOMETRO'
    ]):
        return 'Equipos de Medición y Laboratorio'

    return 'Otros / General'


def main():
    app = create_app()
    with app.app_context():
        print("=== INICIANDO IMPORTACIÓN INVENTARIO SEDE PERDOMO ===")
        from sqlalchemy import text
        # Recrear tabla inventario_custodia limpia con nuevos anchos
        db.session.execute(text("DROP TABLE IF EXISTS inventario_custodia CASCADE;"))
        db.session.commit()
        init_db(app)

        # 1. Obtener o crear Sede Perdomo
        sede_perdomo = Sede.query.filter(Sede.nombre.ilike('%perdomo%')).first()
        if not sede_perdomo:
            sede_perdomo = Sede(nombre='PERDOMO')
            db.session.add(sede_perdomo)
            db.session.commit()
            print("Sede PERDOMO creada.")
        else:
            print(f"Sede PERDOMO encontrada (ID: {sede_perdomo.id}).")

        # 2. Asegurar Bodegas para Perdomo
        bodegas_def = [
            ('BODEGA GENERAL PERDOMO', sede_perdomo.id),
            ('SALONES PERDOMO', sede_perdomo.id),
            ('PANTALLAS DIGITALES', sede_perdomo.id),
            ('APOYO PERSONAL PISO8', sede_perdomo.id),
            ('BODEGA DEPORTES PERDOMO', sede_perdomo.id),
        ]
        bodegas_map = {}
        for b_name, s_id in bodegas_def:
            b_obj = Bodega.query.filter_by(nombre=b_name, sede_id=s_id).first()
            if not b_obj:
                b_obj = Bodega(nombre=b_name, sede_id=s_id)
                db.session.add(b_obj)
                db.session.commit()
                print(f"Bodega '{b_name}' creada.")
            bodegas_map[b_name] = b_obj

        # 3. Categorías
        nuevas_cats = [
            'Material Deportivo y Lote',
            'Equipos de Medición y Laboratorio',
            'Otros / General',
            'Equipos Portátiles',
            'Todo en Uno',
            'Pantallas Digitales Interactivas',
            'Proyectores (Video Beam)',
            'Audio/Video (HDMI, Parlantes)',
            'Periféricos (Teclados, Mouse)'
        ]
        for cat in nuevas_cats:
            if not CategoriaInventario.query.filter_by(nombre=cat).first():
                db.session.add(CategoriaInventario(nombre=cat))
        db.session.commit()

        # 4. Leer CSV
        csv_path = os.path.join('data', 'inventario_perdomo_raw.csv')
        if not os.path.exists(csv_path):
            print(f"Error: No existe el archivo {csv_path}")
            return

        with open(csv_path, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))

        print(f"Total registros a procesar: {len(rows)}")

        # Mantener registro de placas usadas en inventario para evitar colisiones
        placas_existentes = set(
            row[0] for row in db.session.query(Inventario.numero_inventario).all() if row[0]
        )
        lote_count = 1
        activo_count = 1
        placa_counters = {}

        insertados_inv = 0
        insertados_cust = 0

        for idx, r in enumerate(rows, start=1):
            tipo = (r.get('tipo_inventario') or 'ACTIVO_FIJO').strip().upper()
            placa_orig = (r.get('placa') or '').strip()
            serie = (r.get('serie') or '').strip()
            descripcion = (r.get('descripcion') or 'Sin descripción').strip()
            marca = (r.get('marca') or '').strip()
            estado_csv = (r.get('estado') or 'Configurado').strip()
            cantidad_str = (r.get('cantidad') or '1').strip()
            cant_ant = (r.get('cantidad_anterior') or '').strip()
            edificio = (r.get('edificio') or 'PERDOMO').strip()
            ubicacion = (r.get('ubicacion') or '').strip()
            centro_costo = (r.get('centro_costo') or '').strip()
            nombre_cc = (r.get('nombre_centro_costo') or '').strip()
            resp_custodia = (r.get('responsable_custodia') or '').strip()
            cedula_cust = (r.get('cedula_custodio') or '').strip()
            cargo_cust = (r.get('cargo_custodio') or '').strip()
            prog_area = (r.get('programa_area') or '').strip()
            func_inv = (r.get('funcionario_inventario') or '').strip()
            fecha_inv = (r.get('fecha_inventario') or '').strip()
            anio_lleg = (r.get('anio_llegada') or '').strip()
            es_inv = (r.get('es_investigacion') or 'No').strip()
            obs = (r.get('observaciones') or '').strip()

            # Cantidad entera
            try:
                cantidad = int(cantidad_str) if cantidad_str and cantidad_str.isdigit() else 1
            except ValueError:
                cantidad = 1

            # Generar numero_inventario único para Inventario
            es_placa_valida = placa_orig and placa_orig not in (
                'SIN PLACA', 'N0 PRESENTA', 'NO PRESENTA', 'NO SE VE'
            )
            if es_placa_valida:
                clean_placa = placa_orig
                if clean_placa in placas_existentes:
                    placa_counters[clean_placa] = placa_counters.get(clean_placa, 1) + 1
                    num_inventario = f"{clean_placa}-{placa_counters[clean_placa]}"
                else:
                    num_inventario = clean_placa
                placas_existentes.add(num_inventario)
            else:
                if tipo == 'BODEGA_LOTE':
                    num_inventario = f"PERD-LOT-{lote_count:04d}"
                    lote_count += 1
                else:
                    num_inventario = f"PERD-ACT-{activo_count:04d}"
                    activo_count += 1
                placas_existentes.add(num_inventario)

            # Categoría
            categoria = categorizar_item(descripcion, tipo, marca)

            # Bodega Perdomo destino
            ub_upper = ubicacion.upper()
            desc_upper = descripcion.upper()
            if tipo == 'BODEGA_LOTE' or 'DEPOSITO' in ub_upper or 'BALON' in desc_upper:
                bodega_target = bodegas_map.get('BODEGA DEPORTES PERDOMO') or bodegas_map['BODEGA GENERAL PERDOMO']
            elif 'ONE SCREEN' in desc_upper or '0NE SCREEN' in desc_upper:
                bodega_target = bodegas_map.get('PANTALLAS DIGITALES') or bodegas_map['SALONES PERDOMO']
            elif 'PISO 8' in ub_upper or 'OCTAVO PISO' in ub_upper or 'OFICINA CRAII' in ub_upper:
                bodega_target = bodegas_map.get('APOYO PERSONAL PISO8') or bodegas_map['BODEGA GENERAL PERDOMO']
            elif any(c.isdigit() for c in ubicacion) and len(ubicacion) <= 6:
                bodega_target = bodegas_map.get('SALONES PERDOMO') or bodegas_map['BODEGA GENERAL PERDOMO']
            else:
                bodega_target = bodegas_map['BODEGA GENERAL PERDOMO']

            # Estado enum para Inventario ('Disponible', 'En Préstamo', 'En Mantenimiento', 'En Reparación', 'De Baja')
            if estado_csv.upper() in ('CONFIGURADO', 'FUNCIONAL'):
                estado_inv = 'Disponible'
            elif estado_csv.upper() == 'SIN CONFIGURAR':
                estado_inv = 'En Reparación'
            else:
                estado_inv = 'Disponible'

            # Es por cantidad si es lote o cantidad > 1
            es_por_cant = (tipo == 'BODEGA_LOTE' or cantidad > 1)

            # Crear o actualizar registro en Inventario
            item_inv = Inventario.query.filter_by(numero_inventario=num_inventario).first()
            if not item_inv:
                item_inv = Inventario(
                    categoria=categoria,
                    item=descripcion,
                    marca_modelo=marca or None,
                    serial=serie or None,
                    activo_fijo=placa_orig or None,
                    numero_inventario=num_inventario,
                    ubicacion_permanente=f"{edificio} - {ubicacion}".strip(' -'),
                    estado=estado_inv,
                    observaciones=obs or None,
                    es_por_cantidad=es_por_cant,
                    cantidad_total=cantidad if es_por_cant else 1,
                    cantidad_disponible=cantidad if es_por_cant else 1,
                    bodega_id=bodega_target.id,
                    tipo_inventario=tipo,
                    centro_costo=centro_costo or None,
                    nombre_centro_costo=nombre_cc or None,
                    responsable_custodia=resp_custodia or None,
                    cedula_custodio=cedula_cust or None,
                    cargo_custodio=cargo_cust or None,
                    edificio=edificio or None,
                    ubicacion_detalle=ubicacion or None,
                    programa_area=prog_area or None
                )
                db.session.add(item_inv)
                db.session.flush()
                insertados_inv += 1

            # Crear registro en InventarioCustodia (con las 8 columnas requeridas)
            custodia_reg = InventarioCustodia(
                estado=estado_csv,  # Exacto: Configurado, Sin Configurar, FUNCIONAL
                nombre_centro_costo=nombre_cc or None,
                centro_costo=centro_costo or None,
                cargo_custodio=cargo_cust or None,
                responsable_custodia=resp_custodia or None,
                cedula_custodio=cedula_cust or None,
                edificio=edificio or None,
                ubicacion=ubicacion or None,
                tipo_inventario=tipo,
                placa=placa_orig or None,
                serie=serie or None,
                descripcion=descripcion,
                marca=marca or None,
                cantidad=cantidad,
                cantidad_anterior=cant_ant or None,
                programa_area=prog_area or None,
                funcionario_inventario=func_inv or None,
                fecha_inventario=fecha_inv or None,
                anio_llegada=anio_lleg or None,
                es_investigacion=es_inv or 'No',
                observaciones=obs or None,
                sede_id=sede_perdomo.id,
                inventario_id=item_inv.id
            )
            db.session.add(custodia_reg)
            insertados_cust += 1

            if idx % 100 == 0:
                db.session.commit()
                print(f"Progreso: {idx}/{len(rows)} registros procesados...")

        db.session.commit()
        print(f"=== IMPORTACIÓN COMPLETADA CON ÉXITO ===")
        print(f"- Registros insertados en Inventario: {insertados_inv}")
        print(f"- Registros insertados en InventarioCustodia: {insertados_cust}")
        print(f"- Total en BD Inventario Sede Perdomo: {Inventario.query.join(Inventario.bodega).filter(Bodega.sede_id == sede_perdomo.id).count()}")
        print(f"- Total en BD InventarioCustodia: {InventarioCustodia.query.count()}")


if __name__ == '__main__':
    main()
