# -*- coding: utf-8 -*-
"""
Herramienta de reset de contrasenas del sistema.
Compatible con PostgreSQL y SQLite.
"""
import os
import sys

# Forzar stdout en UTF-8 para Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def listar_usuarios_pg():
    """Lista usuarios desde PostgreSQL via la app Flask."""
    try:
        from werkzeug.security import generate_password_hash, check_password_hash
        from app_improved import create_app
        from database import db, Auxiliar

        app = create_app()
        with app.app_context():
            users = Auxiliar.query.all()
            print(f"\n[PostgreSQL] Total de usuarios: {len(users)}")
            for u in users:
                print(f"\n  Documento    : {u.documento}")
                print(f"  Nombre       : {u.nombre_completo}")
                print(f"  Correo       : {u.correo}")
                print(f"  Rol          : {u.rol}")

                # Probar contrasenas comunes
                contrasenas = ['Prueba123', 'admin123', 'Admin123', '123456',
                               'password1', 'Uniminuto1', 'uniminuto1', 'Admin1234']
                encontrada = False
                for pwd in contrasenas:
                    try:
                        if check_password_hash(u.contraseña, pwd):
                            print(f"  Contrasena   : '{pwd}' (activa)")
                            encontrada = True
                            break
                    except Exception:
                        pass
                if not encontrada:
                    print(f"  Contrasena   : (hash desconocido, necesita reset)")
            return app, Auxiliar, generate_password_hash, check_password_hash, db
    except Exception as e:
        print(f"[PostgreSQL] Error al conectar: {e}")
        return None, None, None, None, None

def listar_usuarios_sqlite():
    """Lista usuarios desde SQLite."""
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sistema_prestamos.db')
    if not os.path.exists(db_path):
        print("[SQLite] No se encontro sistema_prestamos.db")
        return
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in c.fetchall()]
    print(f"[SQLite] Tablas: {tables}")
    if 'auxiliares' in tables:
        c.execute("SELECT documento, nombre_completo, correo, rol FROM auxiliares")
        rows = c.fetchall()
        print(f"[SQLite] Usuarios: {len(rows)}")
        for r in rows:
            print(f"  Doc:{r[0]} | Nombre:{r[1]} | Rol:{r[3]}")
    conn.close()

def reset_contrasena_pg(app, Auxiliar, generate_password_hash, check_password_hash, db_obj, doc, nueva_pwd):
    """Resetea contrasena en PostgreSQL."""
    with app.app_context():
        usuario = Auxiliar.query.get(str(doc).strip())
        if not usuario:
            print(f"  ERROR: Usuario '{doc}' no encontrado en PostgreSQL.")
            return False
        usuario.contraseña = generate_password_hash(nueva_pwd)
        db_obj.session.commit()
        ok = check_password_hash(usuario.contraseña, nueva_pwd)
        if ok:
            print(f"  OK: Contrasena actualizada correctamente.")
            print(f"  Verificacion: EXITOSA")
        else:
            print(f"  ERROR: La verificacion fallo, intente de nuevo.")
        return ok

if __name__ == '__main__':
    print("=" * 55)
    print("HERRAMIENTA DE RESET DE CONTRASENA")
    print("=" * 55)

    print("\n[1] Listando usuarios en SQLite...")
    listar_usuarios_sqlite()

    print("\n[2] Listando usuarios en PostgreSQL...")
    app, Auxiliar, gen_hash, chk_hash, db_obj = listar_usuarios_pg()

    if app is None:
        print("\nNo se pudo conectar a PostgreSQL. Verifique la conexion.")
        sys.exit(1)

    print("\n" + "=" * 55)
    print("OPCIONES:")
    print("  1 - Resetear contrasena de un usuario")
    print("  2 - Salir")
    opcion = input("Seleccione (1/2): ").strip()

    if opcion == '1':
        doc = input("Documento del usuario: ").strip()
        nueva_pwd = input("Nueva contrasena (min 8 chars, letra+numero): ").strip()

        if len(nueva_pwd) < 8:
            print("ERROR: La contrasena debe tener al menos 8 caracteres.")
        elif not any(c.isdigit() for c in nueva_pwd) or not any(c.isalpha() for c in nueva_pwd):
            print("ERROR: La contrasena debe tener al menos una letra y un numero.")
        else:
            reset_contrasena_pg(app, Auxiliar, gen_hash, chk_hash, db_obj, doc, nueva_pwd)
    else:
        print("Saliendo.")
