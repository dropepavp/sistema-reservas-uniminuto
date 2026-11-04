import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app
from database import (
    db, Recurso, Ubicacion, Sede, PuestoComputo, 
    Reserva, PrestamoEquipo, ClaseSalaComputo, 
    SoftwareAsignadoSala, NovedadTecnicaSala, PracticaLibre
)

def run():
    app = create_app()
    with app.app_context():
        # Identificar las salas de cómputo oficiales en Perdomo
        target_mapping = {
            'LS1': '704LS1',
            'LS2': '803LS2',
            'LS3': '804LS3',
            'LS4': '801LS4',
            'LS5': '703LS5'
        }
        
        # Obtener recursos de Perdomo
        sede_perdomo = Sede.query.filter(Sede.nombre.ilike('%perdomo%')).first()
        if not sede_perdomo:
            print("ERROR: Sede Perdomo no encontrada")
            return
            
        print(f"Sede Perdomo ID: {sede_perdomo.id}, Nombre: {sede_perdomo.nombre}")
        
        # Mapeo de recursos oficiales
        oficiales = {}
        for nombre in ['801LS4', '803LS2', '804LS3', '703LS5', '704LS1']:
            rec = Recurso.query.join(Ubicacion).filter(
                Ubicacion.sede_id == sede_perdomo.id,
                Recurso.nombre == nombre
            ).first()
            if rec:
                rec.activo = True
                rec.tipo = 'Aula'
                oficiales[nombre] = rec
                puestos_c = PuestoComputo.query.filter_by(recurso_id=rec.id).count()
                print(f"Oficial: ID {rec.id} -> {rec.nombre} (Puestos actuales: {puestos_c})")
            else:
                print(f"AVISO: No se encontró {nombre}")
                
        # Aliases a eliminar / migrar
        for alias, oficial_nombre in target_mapping.items():
            alias_rec = Recurso.query.join(Ubicacion).filter(
                Ubicacion.sede_id == sede_perdomo.id,
                Recurso.nombre == alias
            ).first()
            
            if not alias_rec:
                print(f"Alias {alias} no existe en Perdomo.")
                continue
                
            oficial_rec = oficiales.get(oficial_nombre)
            print(f"\nProcesando alias {alias} (ID {alias_rec.id}) -> Oficial {oficial_nombre} (ID {oficial_rec.id if oficial_rec else 'N/A'})")
            
            # Puestos
            puestos_alias = PuestoComputo.query.filter_by(recurso_id=alias_rec.id).all()
            if puestos_alias:
                puestos_oficial = PuestoComputo.query.filter_by(recurso_id=oficial_rec.id).all() if oficial_rec else []
                if not puestos_oficial and oficial_rec:
                    print(f"  Migrando {len(puestos_alias)} puestos de {alias} a {oficial_rec.nombre}...")
                    for p in puestos_alias:
                        p.recurso_id = oficial_rec.id
                        p.nombre_equipo = f"PC-{oficial_rec.nombre}-{str(p.numero_puesto).zfill(2)}"
                else:
                    print(f"  {oficial_rec.nombre} ya tiene {len(puestos_oficial)} puestos. Eliminando {len(puestos_alias)} puestos redundantes de {alias}...")
                    for p in puestos_alias:
                        db.session.delete(p)
                db.session.flush()

            # Reservas
            reservas = Reserva.query.filter_by(recurso_id=alias_rec.id).all()
            if reservas and oficial_rec:
                print(f"  Reasignando {len(reservas)} reservas a {oficial_rec.nombre}...")
                for r in reservas:
                    r.recurso_id = oficial_rec.id
                    
            # Prestamos
            prestamos = PrestamoEquipo.query.filter_by(recurso_id=alias_rec.id).all()
            if prestamos and oficial_rec:
                for pre in prestamos:
                    pre.recurso_id = oficial_rec.id

            # Clases
            clases = ClaseSalaComputo.query.filter_by(recurso_id=alias_rec.id).all()
            if clases and oficial_rec:
                for c in clases:
                    c.recurso_id = oficial_rec.id
                    c.salon = oficial_rec.nombre
                    
            # Novedades
            novedades = NovedadTecnicaSala.query.filter_by(recurso_id=alias_rec.id).all()
            if novedades and oficial_rec:
                for n in novedades:
                    n.recurso_id = oficial_rec.id
                    
            # Software
            softs = SoftwareAsignadoSala.query.filter_by(recurso_id=alias_rec.id).all()
            for s in softs:
                db.session.delete(s)
                
            db.session.flush()
            
            # Ahora eliminar el alias de recursos
            print(f"  Eliminando alias {alias} (ID {alias_rec.id})...")
            db.session.delete(alias_rec)

        db.session.commit()
        print("\nCommit realizado con éxito.")
        
        # Si 801LS4 no tiene puestos, generar 25 puestos
        rec_801 = oficiales.get('801LS4')
        if rec_801:
            puestos_801 = PuestoComputo.query.filter_by(recurso_id=rec_801.id).count()
            if puestos_801 == 0:
                print("Generando 25 puestos para 801LS4...")
                for i in range(1, 26):
                    db.session.add(PuestoComputo(
                        recurso_id=rec_801.id,
                        numero_puesto=i,
                        nombre_equipo=f"PC-801LS4-{str(i).zfill(2)}",
                        estado='Operativo'
                    ))
                db.session.commit()
                print("Puestos para 801LS4 generados.")

        # Verificación final
        recursos_perdomo = Recurso.query.join(Ubicacion).filter(
            Ubicacion.sede_id == sede_perdomo.id,
            Recurso.activo == True
        ).order_by(Recurso.nombre).all()
        
        print(f"\nTotal recursos activos en Perdomo: {len(recursos_perdomo)}")
        salas_computo_perdomo = [r.nombre for r in recursos_perdomo if 'LS' in r.nombre]
        print(f"Salas con 'LS' en Perdomo ({len(salas_computo_perdomo)}): {salas_computo_perdomo}")
        for r in recursos_perdomo:
            if 'LS' in r.nombre:
                cant_p = PuestoComputo.query.filter_by(recurso_id=r.id).count()
                print(f"  -> Sala: {r.nombre} (ID: {r.id}), Tipo: {r.tipo}, Puestos: {cant_p}")

if __name__ == '__main__':
    run()
